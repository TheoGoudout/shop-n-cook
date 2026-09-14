"""Unit conversion, and — just as importantly — what must refuse to convert."""

import pytest

from app.core.units import (
    UnitDimension,
    base_unit,
    convert,
    dimension,
    from_base,
    is_discrete,
    merge_key,
    prettify,
    to_base,
)
from app.models.ingredient import Unit

MASS_UNITS = [Unit.GRAM, Unit.KILOGRAM, Unit.OUNCE, Unit.POUND]
VOLUME_UNITS = [
    Unit.MILLILITER,
    Unit.CENTILITER,
    Unit.DECILITER,
    Unit.LITER,
    Unit.TEASPOON,
    Unit.TABLESPOON,
    Unit.CUP,
]
DISCRETE_UNITS = [
    Unit.PIECE,
    Unit.BUNCH,
    Unit.PINCH,
    Unit.CLOVE,
    Unit.SLICE,
    Unit.CAN,
    Unit.PACKAGE,
]


def test_every_unit_has_exactly_one_dimension() -> None:
    """A new Unit member must be classified, or pricing silently mis-handles it."""
    assert set(MASS_UNITS + VOLUME_UNITS + DISCRETE_UNITS) == set(Unit)


@pytest.mark.parametrize("unit", MASS_UNITS)
def test_mass_units(unit: Unit) -> None:
    assert dimension(unit) is UnitDimension.MASS
    assert base_unit(unit) is Unit.GRAM
    assert not is_discrete(unit)


@pytest.mark.parametrize("unit", VOLUME_UNITS)
def test_volume_units(unit: Unit) -> None:
    assert dimension(unit) is UnitDimension.VOLUME
    assert base_unit(unit) is Unit.MILLILITER
    assert not is_discrete(unit)


@pytest.mark.parametrize("unit", DISCRETE_UNITS)
def test_discrete_units_are_their_own_base(unit: Unit) -> None:
    assert dimension(unit) is UnitDimension.DISCRETE
    assert base_unit(unit) is unit
    assert is_discrete(unit)
    assert to_base(3, unit) == 3


@pytest.mark.parametrize(
    ("quantity", "unit", "expected_grams"),
    [
        (1, Unit.GRAM, 1.0),
        (1, Unit.KILOGRAM, 1000.0),
        (1, Unit.OUNCE, 28.349523125),
        (1, Unit.POUND, 453.59237),
        (2.5, Unit.KILOGRAM, 2500.0),
    ],
)
def test_mass_to_base(quantity: float, unit: Unit, expected_grams: float) -> None:
    assert to_base(quantity, unit) == pytest.approx(expected_grams)


@pytest.mark.parametrize(
    ("quantity", "unit", "expected_ml"),
    [
        (1, Unit.MILLILITER, 1.0),
        (1, Unit.CENTILITER, 10.0),
        (1, Unit.DECILITER, 100.0),
        (1, Unit.LITER, 1000.0),
        (1, Unit.TEASPOON, 4.92892159375),
        (1, Unit.TABLESPOON, 14.78676478125),
        (1, Unit.CUP, 236.5882365),
    ],
)
def test_volume_to_base(quantity: float, unit: Unit, expected_ml: float) -> None:
    assert to_base(quantity, unit) == pytest.approx(expected_ml)


@pytest.mark.parametrize("unit", MASS_UNITS + VOLUME_UNITS)
def test_to_base_and_back_round_trips(unit: Unit) -> None:
    assert from_base(to_base(7.5, unit), unit) == pytest.approx(7.5)


def test_convert_within_mass() -> None:
    assert convert(2, Unit.KILOGRAM, Unit.GRAM) == pytest.approx(2000)
    assert convert(500, Unit.GRAM, Unit.KILOGRAM) == pytest.approx(0.5)


def test_convert_within_volume() -> None:
    assert convert(1, Unit.LITER, Unit.MILLILITER) == pytest.approx(1000)
    assert convert(3, Unit.TEASPOON, Unit.TABLESPOON) == pytest.approx(1.0)


def test_convert_across_dimensions_is_refused() -> None:
    """Grams to millilitres needs a density, which units alone cannot supply."""
    assert convert(100, Unit.GRAM, Unit.MILLILITER) is None
    assert convert(1, Unit.CUP, Unit.KILOGRAM) is None


def test_discrete_units_do_not_convert_into_each_other() -> None:
    """A clove is not a slice, and neither is a generic "piece"."""
    assert convert(2, Unit.CLOVE, Unit.SLICE) is None
    assert convert(2, Unit.CLOVE, Unit.PIECE) is None
    assert convert(2, Unit.PIECE, Unit.GRAM) is None


def test_discrete_unit_converts_to_itself() -> None:
    assert convert(4, Unit.CLOVE, Unit.CLOVE) == 4


def test_merge_key_groups_compatible_units() -> None:
    assert merge_key(Unit.GRAM) == merge_key(Unit.KILOGRAM) == merge_key(Unit.POUND)
    assert merge_key(Unit.CUP) == merge_key(Unit.LITER) == merge_key(Unit.TEASPOON)
    assert merge_key(Unit.GRAM) != merge_key(Unit.LITER)


def test_merge_key_keeps_discrete_units_apart() -> None:
    assert merge_key(Unit.CLOVE) != merge_key(Unit.SLICE)
    assert merge_key(Unit.CLOVE) != merge_key(Unit.GRAM)
    assert merge_key(Unit.PIECE) == merge_key(Unit.PIECE)


@pytest.mark.parametrize(
    ("quantity", "unit", "expected"),
    [
        (1500, Unit.GRAM, (1.5, Unit.KILOGRAM)),
        (999, Unit.GRAM, (999.0, Unit.GRAM)),
        (0.5, Unit.KILOGRAM, (500.0, Unit.GRAM)),
        (0.5, Unit.LITER, (500.0, Unit.MILLILITER)),
        (2500, Unit.MILLILITER, (2.5, Unit.LITER)),
        (1, Unit.CUP, (236.5882365, Unit.MILLILITER)),
    ],
)
def test_prettify(quantity: float, unit: Unit, expected: tuple[float, Unit]) -> None:
    value, chosen = prettify(quantity, unit)
    assert chosen is expected[1]
    assert value == pytest.approx(expected[0])


def test_prettify_leaves_discrete_units_alone() -> None:
    assert prettify(3, Unit.CLOVE) == (3, Unit.CLOVE)


def test_prettify_handles_zero() -> None:
    assert prettify(0, Unit.KILOGRAM) == (0.0, Unit.GRAM)
