"""LLM assist for filling gaps in the ingredient catalog's reference prices.

Curating a price for every ingredient by hand does not scale, but an estimate
is not a fact either. So this service is deliberately narrow:

* it only ever writes rows whose price is missing or was itself estimated —
  a ``MANUAL`` price is never overwritten by a guess;
* every row it writes is stamped ``PriceSource.ESTIMATED``, so the provenance
  stays visible in the admin UI and a human can correct it;
* a response it cannot parse, or one with an implausible value, is dropped
  rather than written.

It runs as a FastAPI background task, mirroring ``ingredient_image``.
"""

from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field

from app.models.ingredient import Ingredient, PriceSource, Unit, touch_price
from app.services.recipe_import import llm as llm_module

logger = logging.getLogger(__name__)

#: A grocery staple outside this range is almost certainly a hallucinated
#: order of magnitude rather than a real price, so it is discarded.
_MIN_PRICE = Decimal("0.01")
_MAX_PRICE = Decimal("1000")

#: Prices are asked for per one of these, which keeps the model from inventing
#: pack sizes and keeps every estimate comparable.
_PRICE_UNITS = (Unit.KILOGRAM, Unit.LITER, Unit.PIECE)

_UNIT_VALUES = ", ".join(u.value for u in _PRICE_UNITS)


class EstimatedPrice(BaseModel):
    """One price estimate as returned by the model."""

    name: str
    price_amount: Decimal = Field(gt=0)
    price_unit: Unit
    density_g_per_ml: float | None = None
    piece_weight_g: float | None = None


def build_price_prompt(currency: str) -> str:
    """System prompt asking for a typical supermarket price per ingredient.

    The ingredient names themselves are sent as the human message, not baked
    into the prompt, so the instructions stay cacheable across batches.
    """
    return f"""You estimate typical supermarket prices for grocery ingredients.

For each ingredient you are given, return the average retail price in \
{currency} for ONE of an appropriate unit.

Rules:
- price_unit must be one of: {_UNIT_VALUES}
- Use "kg" for anything sold by weight, "L" for liquids sold by volume, and \
"piece" only for things genuinely sold individually (an egg, a lemon).
- Price a mid-range supermarket own-brand product. Exclude premium, organic \
and first-price ranges.
- density_g_per_ml: include for liquids and for powders commonly measured by \
volume (flour, sugar, oil, milk). Omit when it does not apply.
- piece_weight_g: include when the ingredient is also counted (a clove of \
garlic, one onion, one egg). Omit when it does not apply.
- Return every ingredient you were given, using its name exactly as provided.

Return ONLY a JSON array, no prose and no markdown fences:
[{{"name": "...", "price_amount": 2.5, "price_unit": "kg", \
"density_g_per_ml": null, "piece_weight_g": null}}]"""


def _response_text(raw: Any) -> str:
    """Flatten a chat response into text, tolerating Anthropic content blocks."""
    if isinstance(raw, str):
        content = raw.strip()
    elif isinstance(raw, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in raw
        ).strip()
    else:
        content = ""

    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    return content


def parse_price_response(raw: Any) -> list[EstimatedPrice]:
    """Parse the model's reply, dropping anything malformed or implausible.

    One bad entry must not cost the whole batch, so each is validated on its
    own and simply skipped when it fails.
    """
    content = _response_text(raw)
    if not content:
        return []
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Price estimate response was not valid JSON")
        return []

    if not isinstance(payload, list):
        logger.warning("Price estimate response was not a JSON array")
        return []

    estimates: list[EstimatedPrice] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        try:
            estimate = EstimatedPrice(**entry)
        except (ValueError, TypeError, InvalidOperation):
            logger.warning("Dropping unparseable price estimate: %r", entry)
            continue
        if not _MIN_PRICE <= estimate.price_amount <= _MAX_PRICE:
            logger.warning(
                "Dropping implausible price %s for %r",
                estimate.price_amount,
                estimate.name,
            )
            continue
        estimates.append(estimate)
    return estimates


def may_overwrite(ingredient: Ingredient) -> bool:
    """Whether an estimate is allowed to write over this ingredient's price.

    A price a human entered is authoritative and is left alone.
    """
    if ingredient.price_source is PriceSource.MANUAL:
        return False
    return True


def apply_estimates(
    ingredients: list[Ingredient], estimates: list[EstimatedPrice]
) -> list[Ingredient]:
    """Write estimates onto the ingredients they name. Returns those changed."""
    by_name = {i.name.strip().lower(): i for i in ingredients}
    changed: list[Ingredient] = []

    for estimate in estimates:
        ingredient = by_name.get(estimate.name.strip().lower())
        if ingredient is None:
            logger.warning("Estimate for unknown ingredient %r", estimate.name)
            continue
        if not may_overwrite(ingredient):
            logger.info("Keeping curated price for %r", ingredient.name)
            continue

        ingredient.price_amount = estimate.price_amount
        ingredient.price_quantity = 1.0
        ingredient.price_unit = estimate.price_unit
        if estimate.density_g_per_ml:
            ingredient.density_g_per_ml = estimate.density_g_per_ml
        if estimate.piece_weight_g:
            ingredient.piece_weight_g = estimate.piece_weight_g
        touch_price(ingredient, source=PriceSource.ESTIMATED)
        changed.append(ingredient)

    return changed


def estimate_prices_batch(
    ingredient_ids: list[uuid.UUID], *, currency: str = "EUR"
) -> None:
    """Estimate and store prices for ingredients that do not have a curated one."""
    from sqlmodel import Session

    from app.core.db import engine

    if not ingredient_ids:
        logger.info("estimate_prices_batch called with empty list, skipping")
        return

    with Session(engine) as session:
        ingredients = [
            ing
            for iid in ingredient_ids
            if (ing := session.get(Ingredient, iid)) is not None
        ]
        candidates = [i for i in ingredients if may_overwrite(i)]
        if not candidates:
            logger.info("No ingredients eligible for price estimation")
            return

        logger.info("Estimating prices for %d ingredient(s)", len(candidates))
        names = [i.name for i in candidates]

        try:
            llm_module.configure_langsmith()
            llm = llm_module.get_llm()
            from langchain_core.messages import HumanMessage, SystemMessage

            response = llm.invoke(
                [
                    SystemMessage(content=build_price_prompt(currency)),
                    HumanMessage(content="\n".join(names)),
                ]
            )
        except Exception:
            # A pricing estimate is a convenience; never let it take down the
            # request that queued it.
            logger.exception("Price estimation call failed")
            return

        estimates = parse_price_response(response.content)
        changed = apply_estimates(candidates, estimates)

        if not changed:
            logger.info("No price updates to commit")
            return

        for ingredient in changed:
            session.add(ingredient)
        session.commit()
        logger.info("Committed estimated prices for %d ingredient(s)", len(changed))


def estimate_ingredient_price(
    ingredient_id: uuid.UUID, *, currency: str = "EUR"
) -> None:
    """Estimate the price of a single ingredient."""
    estimate_prices_batch([ingredient_id], currency=currency)
