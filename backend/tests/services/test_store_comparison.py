"""Ranking stores must not reward a store for the prices it is missing."""

import uuid
from decimal import Decimal
from typing import cast

from app.models.ingredient import Unit
from app.services.pricing import PriceBook
from app.services.store_comparison import BasketComparison, compare_stores


class _Book:
    """A price book reduced to a name → line cost table."""

    def __init__(self, costs: dict[str, str | None]) -> None:
        self._costs = costs

    def cost(self, name: str, _quantity: float, _unit: Unit) -> Decimal | None:
        value = self._costs.get(name)
        return Decimal(value) if value is not None else None


def _items(*names: str) -> list[tuple[str, float, Unit]]:
    return [(n, 1.0, Unit.KILOGRAM) for n in names]


def _compare(
    stores: dict[str, dict[str, str | None]], items: list[tuple[str, float, Unit]]
) -> tuple[dict[str, uuid.UUID], BasketComparison]:
    ids = {name: uuid.uuid4() for name in stores}
    books = [(ids[name], cast(PriceBook, _Book(c))) for name, c in stores.items()]
    return ids, compare_stores(books, items)


def test_a_missing_price_does_not_make_a_store_look_cheaper() -> None:
    # B is pricier on everything it prices, but it cannot price the oil.
    ids, result = _compare(
        {
            "a": {"flour": "2.00", "oil": "8.00"},
            "b": {"flour": "3.00", "oil": None},
        },
        _items("flour", "oil"),
    )
    by_id = {c.store_id: c for c in result.stores}
    a, b = by_id[ids["a"]], by_id[ids["b"]]

    # The raw sums say B is cheaper — that is the bug being guarded against.
    assert b.estimated_total is not None and a.estimated_total is not None
    assert b.estimated_total < a.estimated_total

    # Projected: B's level on flour is 3.00 / 2.50 = 1.2, A's is 0.8, so the
    # oil at B is estimated as 8.00 / 0.8 * 1.2 = 12.00.
    assert a.projected_total == Decimal("10.00")
    assert b.projected_total == Decimal("15.00")
    assert (a.projected_count, b.projected_count) == (0, 1)
    assert result.cheapest_store_id == ids["a"]
    assert result.stores[0].store_id == ids["a"]

    # The exact like-for-like figure covers flour alone.
    assert result.comparable_count == 1
    assert (a.comparable_total, b.comparable_total) == (
        Decimal("2.00"),
        Decimal("3.00"),
    )


def test_an_item_no_store_prices_is_reported_not_guessed() -> None:
    ids, result = _compare(
        {"a": {"flour": "2.00"}, "b": {"flour": "3.00"}},
        _items("flour", "saffron"),
    )
    assert result.unpriceable_count == 1
    for c in result.stores:
        assert c.projected_count == 0
        assert c.unpriced_count == 1
    assert result.cheapest_store_id == ids["a"]


def test_a_store_that_prices_nothing_is_not_ranked() -> None:
    ids, result = _compare(
        {"a": {"flour": "2.00"}, "b": {"flour": "3.00"}, "empty": {}},
        _items("flour"),
    )
    empty = next(c for c in result.stores if c.store_id == ids["empty"])
    assert empty.projected_total is None
    assert empty.estimated_total is None
    assert result.stores[-1].store_id == ids["empty"]
    assert result.comparable_count == 1


def test_without_common_items_no_estimate_is_made() -> None:
    # Nothing priced at both stores, so there is no price level to scale by.
    ids, result = _compare(
        {"a": {"flour": "2.00"}, "b": {"oil": "8.00"}},
        _items("flour", "oil"),
    )
    assert result.comparable_count == 0
    for c in result.stores:
        assert c.projected_total is None
        assert c.comparable_total is None
    assert result.cheapest_store_id is None


def test_a_single_store_is_never_called_the_cheapest() -> None:
    _, result = _compare({"a": {"flour": "2.00"}}, _items("flour"))
    assert result.cheapest_store_id is None
    assert result.stores[0].projected_total == Decimal("2.00")


def test_complete_stores_rank_on_their_real_totals() -> None:
    ids, result = _compare(
        {
            "a": {"flour": "3.00", "oil": "9.00"},
            "b": {"flour": "2.00", "oil": "7.00"},
        },
        _items("flour", "oil"),
    )
    assert result.cheapest_store_id == ids["b"]
    for c in result.stores:
        assert c.projected_total == c.estimated_total == c.comparable_total
        assert c.projected_count == 0
