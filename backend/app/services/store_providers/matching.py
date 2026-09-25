"""Ingredient -> product resolution. Store-independent, on purpose.

Turning "200 g tomates" into "this 500 g SKU, buy 1" is the genuinely hard part
of a store integration, and it is identical for every retailer. Providers only
fetch catalogues; all the judgement lives here, so twelve stores cannot drift
into twelve different answers for the same list.

Unit arithmetic is **not** done here. ``app.core.units`` is the single place
that converts, and this module calls it — which is what keeps a list costed
through a store provider agreeing with the same list costed through the store
comparison. Its refusals carry straight through:

- mass and volume never cross without the ingredient's density, so "200 g"
  against a pack sold in "ml" yields ASSUMED_SINGLE rather than a guess;
- discrete units convert only to themselves, so "3 cloves" can never become
  "buy 3 heads of garlic", and a bunch is never silently a piece.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Iterable, Sequence
from difflib import SequenceMatcher

from app.core.units import convert
from app.models.ingredient import Unit
from app.services.pricing import quantize_money
from app.services.store_providers.models import (
    ListLine,
    MatchStatus,
    PackStatus,
    PriceStatus,
    ResolvedItem,
    StoreProduct,
)

# --------------------------------------------------------------------------- #
# Units                                                                        #
# --------------------------------------------------------------------------- #


MAX_PACK_COUNT = 99


def compute_pack_count(
    *,
    required_quantity: float,
    required_unit: Unit,
    pack_quantity: float | None,
    pack_unit: Unit | None,
) -> tuple[int, PackStatus]:
    """How many packs to buy, and how much to trust that number."""
    if pack_quantity is None or pack_unit is None or pack_quantity <= 0:
        return 1, PackStatus.UNKNOWN_PACK_SIZE
    if required_quantity <= 0:
        return 1, PackStatus.ASSUMED_SINGLE

    required_in_pack_unit = convert(required_quantity, required_unit, pack_unit)
    if required_in_pack_unit is None:
        return 1, PackStatus.ASSUMED_SINGLE

    ratio = required_in_pack_unit / pack_quantity
    count = max(1, math.ceil(ratio - 1e-9))
    if count > MAX_PACK_COUNT:
        return MAX_PACK_COUNT, PackStatus.UNKNOWN_PACK_SIZE
    status = (
        PackStatus.EXACT
        if math.isclose(ratio, count, rel_tol=1e-6)
        else PackStatus.ROUNDED_UP
    )
    return count, status


# --------------------------------------------------------------------------- #
# Name matching                                                                #
# --------------------------------------------------------------------------- #

#: Articles and prepositions only. Descriptive words that shoppers actually
#: discriminate on ("bio", "frais", "demi") are deliberately NOT stopwords.
_STOPWORDS = frozenset(
    {
        "a",
        "au",
        "aux",
        "d",
        "de",
        "des",
        "du",
        "en",
        "et",
        "l",
        "la",
        "le",
        "les",
        "of",
        "the",
        "and",
        "with",
    }
)

_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NON_WORD.sub(" ", stripped).strip()


def _singularize(token: str) -> str:
    """Crude FR/EN plural folding: tomates -> tomate, oeufs -> oeuf.

    Deliberately conservative — only trims a trailing s/x on tokens long enough
    that the trim cannot destroy the word.
    """
    if len(token) > 3 and token[-1] in ("s", "x"):
        return token[:-1]
    return token


def tokenize(text: str) -> set[str]:
    return {
        _singularize(t) for t in normalize(text).split() if t and t not in _STOPWORDS
    }


def score_name(query: str, candidate: str) -> float:
    """Similarity in [0, 1] between an ingredient name and a product name.

    Weighted towards *recall of the query's words*: a product whose name
    contains every word of "tomates cerises" is a good match even though it
    adds "barquette 250g", which plain string similarity would punish.
    """
    q_tokens = tokenize(query)
    c_tokens = tokenize(candidate)
    if not q_tokens or not c_tokens:
        return 0.0

    intersection = q_tokens & c_tokens
    recall = len(intersection) / len(q_tokens)
    jaccard = len(intersection) / len(q_tokens | c_tokens)
    sequence = SequenceMatcher(None, normalize(query), normalize(candidate)).ratio()

    value = 0.55 * recall + 0.25 * jaccard + 0.20 * sequence

    # A product name literally containing the whole query is a strong signal
    # that token maths can under-rate on very long product names.
    if normalize(query) and normalize(query) in normalize(candidate):
        value = max(value, 0.80 + 0.20 * jaccard)

    return max(0.0, min(1.0, value))


#: At or above this, we present the match as decided.
MATCH_THRESHOLD = 0.55
#: Below this, nothing plausible was found and we prefer to say so.
MIN_SCORE = 0.30
#: Out-of-stock products stay eligible but lose ties to available ones.
_OUT_OF_STOCK_PENALTY = 0.05


def rank_candidates(
    query: str, candidates: Iterable[StoreProduct]
) -> list[tuple[StoreProduct, float]]:
    """Score and order candidates best-first."""
    scored: list[tuple[StoreProduct, float]] = []
    for product in candidates:
        value = score_name(query, product.name)
        if product.in_stock is False:
            value -= _OUT_OF_STOCK_PENALTY
        scored.append((product, max(0.0, value)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


# --------------------------------------------------------------------------- #
# Resolution                                                                   #
# --------------------------------------------------------------------------- #

MAX_ALTERNATIVES = 4


def resolve_item(
    *,
    item_name: str,
    quantity: float,
    unit: Unit,
    candidates: Sequence[StoreProduct],
    unpriced_reason: PriceStatus = PriceStatus.UNKNOWN,
) -> ResolvedItem:
    """Pick the best product for one list line and explain the outcome."""
    base = ResolvedItem(
        item_name=item_name,
        requested_quantity=quantity,
        requested_unit=unit,
        price_status=unpriced_reason,
    )
    if not candidates:
        base.match_status = MatchStatus.NO_CANDIDATES
        return base

    ranked = rank_candidates(item_name, candidates)
    best, best_score = ranked[0]
    if best_score < MIN_SCORE:
        base.match_status = MatchStatus.NO_CANDIDATES
        base.alternatives = [p for p, _ in ranked[:MAX_ALTERNATIVES]]
        return base

    pack_count, pack_status = compute_pack_count(
        required_quantity=quantity,
        required_unit=unit,
        pack_quantity=best.pack_quantity,
        pack_unit=best.pack_unit,
    )

    base.product = best
    base.match_score = round(best_score, 4)
    base.match_status = (
        MatchStatus.MATCHED
        if best_score >= MATCH_THRESHOLD
        else MatchStatus.LOW_CONFIDENCE
    )
    base.pack_count = pack_count
    base.pack_status = pack_status
    base.alternatives = [p for p, _ in ranked[1 : MAX_ALTERNATIVES + 1]]

    if best.price is not None:
        base.price_status = PriceStatus.PRICED
        base.line_total = quantize_money(best.price * pack_count)

    return base


# --------------------------------------------------------------------------- #
# Net-content parsing                                                          #
# --------------------------------------------------------------------------- #

#: Written unit tokens (FR + EN) to ``Unit``. Stores very often express pack size
#: only inside the product name ("Tomates pelées 400 g"), so every family needs
#: this; keeping it beside the unit table means one place to extend.
_UNIT_TOKENS: dict[str, Unit] = {
    "g": Unit.GRAM,
    "gr": Unit.GRAM,
    "gramme": Unit.GRAM,
    "grammes": Unit.GRAM,
    "kg": Unit.KILOGRAM,
    "kilo": Unit.KILOGRAM,
    "kilos": Unit.KILOGRAM,
    "ml": Unit.MILLILITER,
    "cl": Unit.CENTILITER,
    "dl": Unit.DECILITER,
    "l": Unit.LITER,
    "litre": Unit.LITER,
    "litres": Unit.LITER,
    "oz": Unit.OUNCE,
    "lb": Unit.POUND,
    "piece": Unit.PIECE,
    "pieces": Unit.PIECE,
    "unite": Unit.PIECE,
    "unites": Unit.PIECE,
}

_QUANTITY_RE = re.compile(
    r"(?<![a-z0-9])(\d+(?:[.,]\d+)?)\s*("
    + "|".join(sorted((re.escape(t) for t in _UNIT_TOKENS), key=len, reverse=True))
    + r")(?![a-z])"
)

_MULTIPACK_RE = re.compile(r"(?<![a-z0-9])(\d+)\s*[x*]\s*(\d+(?:[.,]\d+)?)\s*([a-z]+)")

#: Quantity parsing needs a *lighter* normalisation than name matching: the
#: decimal separator and the multipack "x" are significant. Stripping them the
#: way ``normalize`` does turns "1,5 kg" into "1 5kg", which then reads as 5 kg.
_QUANTITY_KEEP = re.compile(r"[^a-z0-9.,x*]+")


def _normalize_quantity_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _QUANTITY_KEEP.sub(" ", stripped).strip()


def parse_quantity(text: str) -> tuple[float, Unit] | None:
    """Read a net content out of free text, e.g. "Lait demi-écrémé 1 L".

    Handles multipacks ("6 x 125 g" -> 750 g) and decimal commas ("1,5 kg").
    Returns ``None`` when the text carries no recognisable quantity, which
    callers treat as ``UNKNOWN_PACK_SIZE`` rather than assuming anything.
    """
    normalized = _normalize_quantity_text(text)

    multipack = _MULTIPACK_RE.search(normalized)
    if multipack:
        unit = _UNIT_TOKENS.get(multipack.group(3))
        if unit is not None:
            count = float(multipack.group(1))
            each = float(multipack.group(2).replace(",", "."))
            return count * each, unit

    match = _QUANTITY_RE.search(normalized)
    if match:
        unit = _UNIT_TOKENS.get(match.group(2))
        if unit is not None:
            return float(match.group(1).replace(",", ".")), unit
    return None


# --------------------------------------------------------------------------- #
# List tidying                                                                 #
# --------------------------------------------------------------------------- #


def _merge_key(name: str) -> str:
    """Identity for merging: plural-folded, order-insensitive, stopword-free.

    ``normalize`` alone is not enough — it would keep "oignons" and "oignon"
    apart, which is exactly the duplicate a combined list should collapse.
    Falls back to the plain normalised string for names that are nothing but
    stopwords, so those never all collide on an empty key.
    """
    tokens = tokenize(name)
    return " ".join(sorted(tokens)) if tokens else normalize(name)


def merge_lines(lines: Sequence[ListLine]) -> list[tuple[ListLine, int]]:
    """Combine lines naming the same ingredient in compatible units.

    Two recipes each wanting onions should produce one line, not two. Returns
    each merged line with the number of originals folded into it, so the caller
    can show that a total came from more than one recipe.

    Lines whose units are not inter-convertible stay separate: "2 cloves of
    garlic" and "1 bulb of garlic" are both true and adding them is not.
    """
    merged: list[tuple[ListLine, int]] = []
    for line in lines:
        key = _merge_key(line.name)
        for index, (existing, count) in enumerate(merged):
            if _merge_key(existing.name) != key:
                continue
            converted = convert(line.quantity, line.unit, existing.unit)
            if converted is None:
                continue
            existing.quantity = round(existing.quantity + converted, 4)
            # Keep a category if either side knows one.
            if existing.category is None and line.category is not None:
                existing.category = line.category
            merged[index] = (existing, count + 1)
            break
        else:
            merged.append((line.model_copy(deep=True), 1))
    return merged
