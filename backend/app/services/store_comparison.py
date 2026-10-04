"""Compare what one basket costs across stores, without hiding the gaps.

Summing each store's priced lines is not a comparison: a store that cannot
price the olive oil looks cheaper than one that can, simply because it is
missing a line. This module puts every store on the same footing in two ways.

* **Comparable total** — the sum over only the items *every* compared store
  prices. Exact, but it may leave items out.
* **Projected total** — the store's own prices, plus an estimate for each item
  it lacks but another store prices. The estimate is the other stores' price
  for that item, brought to this store's price level as measured on the
  comparable items. Every store's projection then covers the same items, so
  the totals rank fairly; how many lines were estimated is reported alongside,
  so the UI can say so.

Both the price level and the estimate are *medians*, never means or ratios of
sums. Store prices come from product matching, and one bad match — a pack
priced as a single piece, a premium variant — is routine. With a mean, that one
line would be copied into every other store's estimate; with a ratio of sums,
the single most expensive item would set a store's level for the whole basket.
A median lets no single price dominate either.

An item no store can price is left out of every total alike and counted as
``unpriceable``: it does not distort the ranking, but the totals are short of
it and the caller must say so.

A store that prices nothing at all is not compared — projecting a whole basket
for it would be invention, not estimation.

All compared stores are assumed to share a currency, which holds for the
seeded retailers (all EUR).
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from app.models.ingredient import Unit
from app.services.pricing import PriceBook, quantize_money

__all__ = ["BasketComparison", "StoreCosting", "compare_stores"]


@dataclass(frozen=True)
class StoreCosting:
    store_id: uuid.UUID
    #: Sum of the lines this store prices itself; ``None`` if it prices none.
    estimated_total: Decimal | None
    priced_count: int
    unpriced_count: int
    #: Sum over the items every compared store prices.
    comparable_total: Decimal | None
    #: Own prices plus estimates for the items other stores price.
    projected_total: Decimal | None
    #: How many lines of ``projected_total`` are estimates.
    projected_count: int


@dataclass(frozen=True)
class BasketComparison:
    #: In ranking order: by projected total, unrankable stores last.
    stores: list[StoreCosting]
    cheapest_store_id: uuid.UUID | None
    item_count: int
    #: Items every compared store prices.
    comparable_count: int
    #: Items no store prices; missing from every total.
    unpriceable_count: int


def compare_stores(
    books: list[tuple[uuid.UUID, PriceBook]],
    items: list[tuple[str, float, Unit]],
) -> BasketComparison:
    """Cost ``items`` at each store and rank the stores on a like-for-like basis."""
    lines: dict[uuid.UUID, list[Decimal | None]] = {
        store_id: [book.cost(name, qty, unit) for name, qty, unit in items]
        for store_id, book in books
    }
    n = len(items)
    compared = [sid for sid, _ in books if any(c is not None for c in lines[sid])]

    def priced_by(i: int) -> list[uuid.UUID]:
        return [sid for sid in compared if lines[sid][i] is not None]

    common = [i for i in range(n) if compared and len(priced_by(i)) == len(compared)]
    priced_somewhere = [i for i in range(n) if priced_by(i)]

    levels = _price_levels(lines, compared, common)

    costings: dict[uuid.UUID, StoreCosting] = {}
    for store_id, _ in books:
        own = lines[store_id]
        priced = [c for c in own if c is not None]
        is_compared = store_id in compared
        projected, projected_count = (
            _project(lines, store_id, priced_somewhere, levels)
            if is_compared
            else (None, 0)
        )
        costings[store_id] = StoreCosting(
            store_id=store_id,
            estimated_total=quantize_money(sum(priced, Decimal(0))) if priced else None,
            priced_count=len(priced),
            unpriced_count=n - len(priced),
            comparable_total=(
                quantize_money(sum((own[i] or Decimal(0) for i in common), Decimal(0)))
                if is_compared and common
                else None
            ),
            projected_total=projected,
            projected_count=projected_count,
        )

    ranked = sorted(
        costings.values(),
        key=lambda c: (
            c.projected_total is None,
            c.projected_total or Decimal(0),
            c.estimated_total is None,
            c.estimated_total or Decimal(0),
        ),
    )
    rankable = [c for c in ranked if c.projected_total is not None]
    # "Cheapest" only means something against at least one other store.
    cheapest = rankable[0].store_id if len(rankable) >= 2 else None

    return BasketComparison(
        stores=ranked,
        cheapest_store_id=cheapest,
        item_count=n,
        comparable_count=len(common),
        unpriceable_count=n - len(priced_somewhere),
    )


def _price_levels(
    lines: dict[uuid.UUID, list[Decimal | None]],
    compared: list[uuid.UUID],
    common: list[int],
) -> dict[uuid.UUID, Decimal] | None:
    """Each store's price level relative to a typical store, on the common items.

    Per item, a store's price is compared with that item's median price across
    stores; the store's level is the median of those ratios, taken on a log
    scale so that "twice as dear" and "half as dear" weigh the same. Every
    item counts once, whatever it costs, and a single mismatched price cannot
    move the level.

    ``None`` when there is nothing to measure it on, in which case no estimate
    can be grounded and missing lines stay missing.
    """
    if not common or not compared:
        return None
    log_ratios: dict[uuid.UUID, list[Decimal]] = {sid: [] for sid in compared}
    for i in common:
        prices = {sid: lines[sid][i] or Decimal(0) for sid in compared}
        if any(p <= 0 for p in prices.values()):
            # A free line says nothing about how dear the store is.
            continue
        typical = median(prices.values())
        for sid, price in prices.items():
            log_ratios[sid].append((price / typical).ln())
    if not all(log_ratios.values()):
        return None
    return {sid: median(logs).exp() for sid, logs in log_ratios.items()}


def _project(
    lines: dict[uuid.UUID, list[Decimal | None]],
    store_id: uuid.UUID,
    priced_somewhere: list[int],
    levels: dict[uuid.UUID, Decimal] | None,
) -> tuple[Decimal | None, int]:
    """This store's total over every item some store prices, and how many lines were estimated."""
    total = Decimal(0)
    estimated = 0
    for i in priced_somewhere:
        own = lines[store_id][i]
        if own is not None:
            total += own
            continue
        if levels is None:
            # Missing lines with no grounded estimate: not comparable.
            return None, 0
        # The other stores' prices, each brought back to a typical price level.
        others = [
            line / levels[sid] for sid in levels if (line := lines[sid][i]) is not None
        ]
        total += median(others) * levels[store_id]
        estimated += 1
    return quantize_money(total), estimated
