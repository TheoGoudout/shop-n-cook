"""Pull a store's prices off its website and into the price book.

This is the bridge that makes a chosen store's figures real: the price a user
sees while building a list should be the one they pay at the till, and the only
way to get that is from the retailer itself.

**Prices are written through, not fetched on the read path.** Costing a list
has to stay fast and synchronous, and an HTTP round trip per ingredient while
a page renders would be unusable. ``IngredientPrice`` already means "what this
ingredient costs at this store", which is exactly the right place to land
them — so a refresh upserts those rows and ``PriceBook`` carries on reading
them, unchanged and offline. Freshness becomes a background concern rather
than a latency one, and a store stays fully usable while its provider is down.

A refresh only ever *adds* knowledge. An ingredient the provider cannot match
or cannot price keeps whatever price it already had, and is reported rather
than blanked — losing a good curated price to a bad automated lookup would be
a poor trade.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from pydantic import BaseModel, Field
from sqlmodel import Session

from app import crud
from app.models.ingredient import Ingredient, Unit
from app.models.store import IngredientPriceCreate, Store
from app.services.store_providers.base import StoreProvider
from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.matching import resolve_item
from app.services.store_providers.models import (
    Capability,
    MatchStatus,
    StoreProduct,
)

#: Candidates fetched per ingredient. Enough for the ranker to have a real
#: choice without turning a refresh into a crawl.
SEARCH_LIMIT = 5


class SkipReason(str, Enum):
    """Why one ingredient came away without a refreshed price."""

    NO_MATCH = "no_match"
    """Nothing in the retailer's catalogue looked like this ingredient."""

    NO_PRICE = "no_price"
    """Matched a product, but the retailer did not publish its price."""

    NO_PACK_SIZE = "no_pack_size"
    """Priced, but with no net content — so there is no price *per* anything
    to store, and guessing one would poison every future calculation."""

    STORE_UNAVAILABLE = "store_unavailable"
    """The retailer could not be reached; the run stopped here."""


class RefreshSkip(BaseModel):
    ingredient_name: str
    reason: SkipReason


class RefreshResult(BaseModel):
    """What one refresh actually managed to do."""

    store_id: str
    store_name: str
    provider_slug: str
    refreshed_count: int = 0
    skipped: list[RefreshSkip] = Field(default_factory=list)
    stopped_early: bool = False
    """True when the retailer became unreachable partway through, so the
    remaining ingredients were never attempted rather than silently skipped."""

    @property
    def attempted_count(self) -> int:
        return self.refreshed_count + len(self.skipped)


def refresh_store_prices(
    *,
    session: Session,
    store: Store,
    provider: StoreProvider,
    ingredients: Sequence[Ingredient],
) -> RefreshResult:
    """Look each ingredient up at ``store`` and record what it costs there."""
    result = RefreshResult(
        store_id=str(store.id),
        store_name=store.name,
        provider_slug=provider.slug,
    )

    if not provider.supports(Capability.PRICES):
        # Not an error: plenty of stores are searchable but priceless, and the
        # caller is expected to have checked `can_refresh_prices` first.
        result.skipped = [
            RefreshSkip(ingredient_name=i.name, reason=SkipReason.NO_PRICE)
            for i in ingredients
        ]
        return result

    for ingredient in ingredients:
        try:
            candidates = provider.search(ingredient.name, limit=SEARCH_LIMIT)
        except ProviderUnavailableError:
            # One failure is enough to conclude the retailer is unreachable;
            # making every remaining ingredient wait out its own timeout helps
            # nobody, and half a refresh is still worth keeping.
            result.stopped_early = True
            break

        resolved = resolve_item(
            item_name=ingredient.name,
            quantity=1,
            unit=ingredient.price_unit or _fallback_unit(candidates),
            candidates=candidates,
            unpriced_reason=provider.unpriced_reason,
        )
        product = resolved.product
        if product is None or resolved.match_status is not MatchStatus.MATCHED:
            result.skipped.append(
                RefreshSkip(ingredient_name=ingredient.name, reason=SkipReason.NO_MATCH)
            )
            continue

        priced = product
        if priced.price is None:
            enriched = _attach_price(provider, priced)
            if enriched is None:
                result.skipped.append(
                    RefreshSkip(
                        ingredient_name=ingredient.name, reason=SkipReason.NO_PRICE
                    )
                )
                continue
            priced = enriched

        if (
            priced.price is None
            or priced.pack_quantity is None
            or priced.pack_unit is None
        ):
            result.skipped.append(
                RefreshSkip(
                    ingredient_name=ingredient.name, reason=SkipReason.NO_PACK_SIZE
                )
            )
            continue

        crud.upsert_ingredient_price(
            session=session,
            ingredient=ingredient,
            price_in=IngredientPriceCreate(
                store_id=store.id,
                price_amount=priced.price,
                price_quantity=priced.pack_quantity,
                price_unit=priced.pack_unit,
            ),
        )
        result.refreshed_count += 1

    if result.stopped_early:
        attempted = result.refreshed_count + len(result.skipped)
        for ingredient in ingredients[attempted:]:
            result.skipped.append(
                RefreshSkip(
                    ingredient_name=ingredient.name,
                    reason=SkipReason.STORE_UNAVAILABLE,
                )
            )
    return result


def _attach_price(
    provider: StoreProvider, product: StoreProduct
) -> StoreProduct | None:
    """Second chance for providers that price separately from searching."""
    try:
        enriched = provider.attach_prices([product])
    except ProviderUnavailableError:
        return None
    return enriched[0] if enriched and enriched[0].price is not None else None


def _fallback_unit(candidates: Sequence[StoreProduct]) -> Unit:
    """A unit to resolve against when the ingredient has no priced unit yet.

    Only affects pack-count arithmetic, which a refresh discards — it stores
    the pack's own price per its own unit. Borrowing the first candidate's unit
    keeps the resolver on a compatible dimension instead of forcing an
    ASSUMED_SINGLE that would change nothing anyway.
    """
    for candidate in candidates:
        if candidate.pack_unit is not None:
            return candidate.pack_unit
    return Unit.PIECE
