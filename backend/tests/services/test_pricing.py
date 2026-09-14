"""Costing rules, and the cases that must honestly report "unpriced"."""

from decimal import Decimal

import pytest

from app.models.ingredient import Ingredient, Unit
from app.services.pricing import CostSummary, PriceBook, ingredient_cost, quantize_money


def make_ingredient(
    name: str = "flour",
    *,
    amount: str | None = "2.50",
    quantity: float | None = 1.0,
    unit: Unit | None = Unit.KILOGRAM,
    density: float | None = None,
    piece_weight: float | None = None,
    name_en: str | None = None,
) -> Ingredient:
    return Ingredient(
        name=name,
        name_en=name_en,
        price_amount=Decimal(amount) if amount is not None else None,
        price_quantity=quantity,
        price_unit=unit,
        density_g_per_ml=density,
        piece_weight_g=piece_weight,
    )


# --------------------------------------------------------------------------- #
# Direct conversion                                                            #
# --------------------------------------------------------------------------- #


def test_price_in_the_same_unit() -> None:
    flour = make_ingredient()
    assert ingredient_cost(flour, 1, Unit.KILOGRAM) == Decimal("2.5000")


def test_price_converts_within_the_dimension() -> None:
    """500 g of flour priced at 2.50/kg costs 1.25 without any extra data."""
    flour = make_ingredient()
    assert ingredient_cost(flour, 500, Unit.GRAM) == Decimal("1.2500")


def test_price_scales_with_quantity() -> None:
    flour = make_ingredient()
    assert ingredient_cost(flour, 2, Unit.KILOGRAM) == Decimal("5.0000")


def test_price_quoted_per_multiple_units() -> None:
    """ "6.00 per 3 kg" must not be read as "6.00 per kg"."""
    rice = make_ingredient("rice", amount="6.00", quantity=3, unit=Unit.KILOGRAM)
    assert ingredient_cost(rice, 1, Unit.KILOGRAM) == Decimal("2.0000")


# --------------------------------------------------------------------------- #
# Cross-dimension bridging                                                     #
# --------------------------------------------------------------------------- #


def test_volume_needs_a_density() -> None:
    """Without a density, a price per kilo cannot answer "what is a cup?"."""
    flour = make_ingredient()
    assert ingredient_cost(flour, 1, Unit.CUP) is None


def test_density_bridges_volume_to_mass() -> None:
    # 1 cup = 236.588 ml; at 0.53 g/ml that is ~125.4 g; at 2.50/kg, ~0.3135
    flour = make_ingredient(density=0.53)
    cost = ingredient_cost(flour, 1, Unit.CUP)
    assert cost is not None
    assert cost == pytest.approx(Decimal("0.3135"), abs=Decimal("0.001"))


def test_discrete_units_need_a_piece_weight() -> None:
    garlic = make_ingredient("garlic", amount="10.00", quantity=1, unit=Unit.KILOGRAM)
    assert ingredient_cost(garlic, 2, Unit.CLOVE) is None


def test_piece_weight_bridges_discrete_to_mass() -> None:
    """2 cloves at 5 g each, priced at 10.00/kg, is 0.10."""
    garlic = make_ingredient(
        "garlic", amount="10.00", quantity=1, unit=Unit.KILOGRAM, piece_weight=5.0
    )
    assert ingredient_cost(garlic, 2, Unit.CLOVE) == Decimal("0.1000")


def test_price_quoted_per_piece_needs_no_bridge() -> None:
    egg = make_ingredient("egg", amount="0.30", quantity=1, unit=Unit.PIECE)
    assert ingredient_cost(egg, 6, Unit.PIECE) == Decimal("1.8000")


def test_price_per_piece_does_not_answer_a_mass_question() -> None:
    egg = make_ingredient("egg", amount="0.30", quantity=1, unit=Unit.PIECE)
    assert ingredient_cost(egg, 100, Unit.GRAM) is None


# --------------------------------------------------------------------------- #
# Missing and invalid data                                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "kwargs",
    [
        {"amount": None},
        {"quantity": None},
        {"unit": None},
    ],
    ids=["no amount", "no quantity", "no unit"],
)
def test_incomplete_price_is_unpriced(kwargs: dict) -> None:
    assert ingredient_cost(make_ingredient(**kwargs), 1, Unit.KILOGRAM) is None


def test_zero_quantity_is_unpriced_not_free() -> None:
    assert ingredient_cost(make_ingredient(), 0, Unit.KILOGRAM) is None


# --------------------------------------------------------------------------- #
# PriceBook                                                                    #
# --------------------------------------------------------------------------- #


def test_price_book_matches_on_normalised_name() -> None:
    book = PriceBook([make_ingredient("Tomato", amount="3.00")])
    assert book.cost("tomatoes", 1, Unit.KILOGRAM) == Decimal("3.0000")
    assert book.cost("  TOMATO  ", 1, Unit.KILOGRAM) == Decimal("3.0000")


def test_price_book_matches_the_english_alias() -> None:
    book = PriceBook([make_ingredient("farine", name_en="flour")])
    assert book.lookup("flour") is not None
    assert book.lookup("farine") is not None


def test_price_book_alias_does_not_displace_a_real_row() -> None:
    """An alias must never shadow the ingredient actually named that."""
    canonical = make_ingredient("flour", amount="2.00")
    aliased = make_ingredient("farine", amount="9.99", name_en="flour")
    book = PriceBook([canonical, aliased])
    found = book.lookup("flour")
    assert found is canonical


def test_unknown_ingredient_is_unpriced() -> None:
    book = PriceBook([make_ingredient()])
    assert book.cost("saffron", 1, Unit.GRAM) is None


def test_summarize_totals_and_counts() -> None:
    book = PriceBook(
        [
            make_ingredient("flour", amount="2.00"),
            make_ingredient("sugar", amount="4.00"),
        ]
    )
    summary = book.summarize(
        [
            ("flour", 1, Unit.KILOGRAM),
            ("sugar", 500, Unit.GRAM),
            ("saffron", 1, Unit.GRAM),
        ]
    )
    assert summary.total == Decimal("4.00")
    assert summary.priced_count == 2
    assert summary.unpriced_count == 1
    assert not summary.is_complete


def test_summarize_with_nothing_priced_reports_none_not_zero() -> None:
    """A list of unknown items has no total — it does not cost nothing."""
    summary = PriceBook([]).summarize([("saffron", 1, Unit.GRAM)])
    assert summary.total is None
    assert summary.unpriced_count == 1


def test_summarize_of_an_empty_list() -> None:
    summary = PriceBook([]).summarize([])
    assert summary.total is None
    assert not summary.is_complete


def test_cost_summary_per_unit() -> None:
    summary = CostSummary(total=Decimal("12.00"), unpriced_count=0, priced_count=3)
    assert summary.per_unit(4) == Decimal("3.00")
    assert summary.is_complete


@pytest.mark.parametrize("divisor", [0, None, -1])
def test_per_unit_refuses_a_nonsense_divisor(divisor: int | None) -> None:
    summary = CostSummary(total=Decimal("12.00"), unpriced_count=0, priced_count=1)
    assert summary.per_unit(divisor) is None


def test_per_unit_of_an_unpriced_summary() -> None:
    assert CostSummary(total=None, unpriced_count=2, priced_count=0).per_unit(2) is None


def test_quantize_money_rounds_half_up() -> None:
    assert quantize_money(Decimal("1.005")) == Decimal("1.01")
    assert quantize_money(Decimal("1.004")) == Decimal("1.00")
