"""Price resolution across stores: curated price, indexed baseline, unpriced."""

from decimal import Decimal

import pytest

from app.models.ingredient import Ingredient, Unit
from app.models.store import IngredientPrice, Store
from app.services.pricing import PriceBook


@pytest.fixture
def flour() -> Ingredient:
    return Ingredient(
        name="flour",
        price_amount=Decimal("2.00"),
        price_quantity=1.0,
        price_unit=Unit.KILOGRAM,
    )


def make_store(slug: str, index: float, currency: str = "EUR") -> Store:
    return Store(name=slug.title(), slug=slug, price_index=index, currency=currency)


def test_without_a_store_the_baseline_is_used_unscaled(flour: Ingredient) -> None:
    book = PriceBook([flour])
    assert book.cost("flour", 1, Unit.KILOGRAM) == Decimal("2.0000")


def test_a_store_with_no_curated_price_scales_the_baseline(
    flour: Ingredient,
) -> None:
    """This is what keeps a sparse price matrix from reading as unpriced."""
    discounter = make_store("lidl", 0.85)
    book = PriceBook([flour], store=discounter)
    assert book.cost("flour", 1, Unit.KILOGRAM) == Decimal("1.7000")


def test_a_premium_store_scales_the_other_way(flour: Ingredient) -> None:
    premium = make_store("monoprix", 1.25)
    book = PriceBook([flour], store=premium)
    assert book.cost("flour", 1, Unit.KILOGRAM) == Decimal("2.5000")


def test_a_curated_store_price_wins_over_the_index(flour: Ingredient) -> None:
    """A real price is a fact; the index is only a fallback estimate."""
    store = make_store("carrefour", 1.05)
    curated = IngredientPrice(
        ingredient_id=flour.id,
        store_id=store.id,
        price_amount=Decimal("3.00"),
        price_quantity=1.0,
        price_unit=Unit.KILOGRAM,
    )
    book = PriceBook([flour], store=store, store_prices=[curated])
    # 3.00 exactly — not 3.00 * 1.05
    assert book.cost("flour", 1, Unit.KILOGRAM) == Decimal("3.0000")


def test_a_curated_store_price_still_converts_units(flour: Ingredient) -> None:
    store = make_store("aldi", 0.85)
    curated = IngredientPrice(
        ingredient_id=flour.id,
        store_id=store.id,
        price_amount=Decimal("3.00"),
        price_quantity=1.0,
        price_unit=Unit.KILOGRAM,
    )
    book = PriceBook([flour], store=store, store_prices=[curated])
    assert book.cost("flour", 500, Unit.GRAM) == Decimal("1.5000")


def test_a_curated_price_for_another_ingredient_does_not_leak(
    flour: Ingredient,
) -> None:
    sugar = Ingredient(
        name="sugar",
        price_amount=Decimal("1.00"),
        price_quantity=1.0,
        price_unit=Unit.KILOGRAM,
    )
    store = make_store("netto", 0.85)
    curated = IngredientPrice(
        ingredient_id=flour.id,
        store_id=store.id,
        price_amount=Decimal("9.00"),
        price_quantity=1.0,
        price_unit=Unit.KILOGRAM,
    )
    book = PriceBook([flour, sugar], store=store, store_prices=[curated])
    assert book.cost("flour", 1, Unit.KILOGRAM) == Decimal("9.0000")
    assert book.cost("sugar", 1, Unit.KILOGRAM) == Decimal("0.8500")


def test_the_ingredient_supplies_the_bridges_even_for_a_store_price() -> None:
    """Density is a property of the food, not of the shop selling it."""
    oil = Ingredient(
        name="oil",
        price_amount=Decimal("4.00"),
        price_quantity=1.0,
        price_unit=Unit.KILOGRAM,
        density_g_per_ml=0.92,
    )
    store = make_store("auchan", 1.0)
    curated = IngredientPrice(
        ingredient_id=oil.id,
        store_id=store.id,
        price_amount=Decimal("2.00"),
        price_quantity=1.0,
        price_unit=Unit.KILOGRAM,
    )
    book = PriceBook([oil], store=store, store_prices=[curated])
    # 1 L = 1000 ml * 0.92 = 920 g; at 2.00/kg that is 1.84
    assert book.cost("oil", 1, Unit.LITER) == Decimal("1.8400")


def test_an_unpriced_ingredient_stays_unpriced_at_every_store() -> None:
    """The index must never manufacture a price out of nothing."""
    mystery = Ingredient(name="saffron")
    book = PriceBook([mystery], store=make_store("lidl", 0.85))
    assert book.cost("saffron", 1, Unit.GRAM) is None


def test_the_store_currency_overrides_the_user_currency(flour: Ingredient) -> None:
    book = PriceBook([flour], currency="USD", store=make_store("tesco", 1.0, "GBP"))
    assert book.currency == "GBP"


def test_summarize_reflects_the_store(flour: Ingredient) -> None:
    book = PriceBook([flour], store=make_store("lidl", 0.85))
    summary = book.summarize([("flour", 2, Unit.KILOGRAM)])
    assert summary.total == Decimal("3.40")
