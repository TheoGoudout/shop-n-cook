"""Conversion between the members of the :class:`~app.models.ingredient.Unit` enum.

``Unit`` mixes three incompatible kinds of measurement, which is why a single
"price per unit" number cannot describe an ingredient:

* **mass** — ``g``, ``kg``, ``oz``, ``lb``; canonical base is the **gram**
* **volume** — ``ml``, ``cl``, ``dl``, ``L``, ``tsp``, ``tbsp``, ``cup``;
  canonical base is the **millilitre**
* **discrete** — ``piece``, ``bunch``, ``pinch``, ``clove``, ``slice``, ``can``,
  ``package``; each is its **own** class

Discrete units deliberately do not convert into one another: a clove is not a
slice, and neither is a "piece". They compare equal only to themselves.

Crossing between mass and volume (or between a discrete unit and either) is a
property of the *ingredient*, not of the units — a millilitre of oil and a
millilitre of honey do not weigh the same. Those bridges live on
``Ingredient.density_g_per_ml`` and ``Ingredient.piece_weight_g`` and are
applied by :mod:`app.services.pricing`, never here.
"""

from enum import Enum

from app.models.ingredient import Unit

__all__ = [
    "UnitDimension",
    "dimension",
    "is_discrete",
    "base_unit",
    "to_base",
    "from_base",
    "convert",
    "merge_key",
    "prettify",
]


class UnitDimension(str, Enum):
    """What kind of quantity a unit measures.

    This is a plain Python enum and is deliberately never persisted. SQLModel
    maps enum columns through SQLAlchemy's ``Enum`` type, which stores member
    *names*; keeping this one out of the database sidesteps that entirely.
    """

    MASS = "mass"
    VOLUME = "volume"
    DISCRETE = "discrete"


# Multipliers onto the canonical base of each dimension.
_MASS_TO_GRAM: dict[Unit, float] = {
    Unit.GRAM: 1.0,
    Unit.KILOGRAM: 1000.0,
    Unit.OUNCE: 28.349523125,
    Unit.POUND: 453.59237,
}

_VOLUME_TO_ML: dict[Unit, float] = {
    Unit.MILLILITER: 1.0,
    Unit.CENTILITER: 10.0,
    Unit.DECILITER: 100.0,
    Unit.LITER: 1000.0,
    # US customary spoons and cups, which is what recipe sites overwhelmingly use.
    Unit.TEASPOON: 4.92892159375,
    Unit.TABLESPOON: 14.78676478125,
    Unit.CUP: 236.5882365,
}

_DISCRETE_UNITS: frozenset[Unit] = frozenset(
    {
        Unit.PIECE,
        Unit.BUNCH,
        Unit.PINCH,
        Unit.CLOVE,
        Unit.SLICE,
        Unit.CAN,
        Unit.PACKAGE,
    }
)

# Ordered largest-last, for picking a human-friendly display unit.
_MASS_DISPLAY_STEPS: tuple[tuple[float, Unit], ...] = (
    (1000.0, Unit.KILOGRAM),
    (1.0, Unit.GRAM),
)
_VOLUME_DISPLAY_STEPS: tuple[tuple[float, Unit], ...] = (
    (1000.0, Unit.LITER),
    (1.0, Unit.MILLILITER),
)


def dimension(unit: Unit) -> UnitDimension:
    """Which dimension ``unit`` measures in."""
    if unit in _MASS_TO_GRAM:
        return UnitDimension.MASS
    if unit in _VOLUME_TO_ML:
        return UnitDimension.VOLUME
    return UnitDimension.DISCRETE


def is_discrete(unit: Unit) -> bool:
    """Whether ``unit`` counts things rather than measuring them."""
    return unit in _DISCRETE_UNITS


def base_unit(unit: Unit) -> Unit:
    """The canonical unit ``unit`` converts into.

    Discrete units are their own base — there is nothing to normalise them to.
    """
    match dimension(unit):
        case UnitDimension.MASS:
            return Unit.GRAM
        case UnitDimension.VOLUME:
            return Unit.MILLILITER
        case _:
            return unit


def to_base(quantity: float, unit: Unit) -> float:
    """Express ``quantity`` of ``unit`` in that unit's canonical base."""
    if unit in _MASS_TO_GRAM:
        return quantity * _MASS_TO_GRAM[unit]
    if unit in _VOLUME_TO_ML:
        return quantity * _VOLUME_TO_ML[unit]
    return quantity


def from_base(quantity: float, unit: Unit) -> float:
    """Inverse of :func:`to_base`: base quantity back into ``unit``."""
    if unit in _MASS_TO_GRAM:
        return quantity / _MASS_TO_GRAM[unit]
    if unit in _VOLUME_TO_ML:
        return quantity / _VOLUME_TO_ML[unit]
    return quantity


def convert(quantity: float, from_unit: Unit, to_unit: Unit) -> float | None:
    """Convert between two units, or ``None`` when they are incompatible.

    Mass and volume convert freely within their own dimension. A discrete unit
    converts only to itself — turning cloves into grams needs the ingredient's
    own weight, which this module does not know about.
    """
    if from_unit == to_unit:
        return quantity
    if dimension(from_unit) is not dimension(to_unit):
        return None
    if is_discrete(from_unit):
        # Same dimension but different members, e.g. CLOVE vs SLICE.
        return None
    return from_base(to_base(quantity, from_unit), to_unit)


def merge_key(unit: Unit) -> str:
    """A key identifying the set of units ``unit`` may be summed with.

    Every mass unit shares one key and every volume unit another, so ``300 g``
    and ``2 cup`` of the same ingredient land on the same shopping-list row.
    Each discrete unit keeps its own key.
    """
    dim = dimension(unit)
    if dim is UnitDimension.DISCRETE:
        return f"{dim.value}:{unit.value}"
    return str(dim.value)


def prettify(quantity: float, unit: Unit) -> tuple[float, Unit]:
    """Rescale ``quantity`` into the most readable unit of its dimension.

    ``(1500, GRAM)`` becomes ``(1.5, KILOGRAM)``; ``(0.5, LITER)`` becomes
    ``(500, MILLILITER)``. Discrete units are returned untouched.
    """
    dim = dimension(unit)
    if dim is UnitDimension.DISCRETE:
        return quantity, unit

    steps = _MASS_DISPLAY_STEPS if dim is UnitDimension.MASS else _VOLUME_DISPLAY_STEPS
    base_quantity = to_base(quantity, unit)
    magnitude = abs(base_quantity)

    for threshold, candidate in steps:
        if magnitude >= threshold:
            return from_base(base_quantity, candidate), candidate

    # Smaller than the finest step (or exactly zero): keep the finest one.
    smallest = steps[-1][1]
    return from_base(base_quantity, smallest), smallest
