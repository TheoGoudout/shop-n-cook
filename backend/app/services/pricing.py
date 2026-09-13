"""Turn catalog reference prices into the cost of a recipe or a shopping list.

The entry point is :class:`PriceBook`: build one per request from the names you
are about to price, then ask it what each quantity costs. Anything it cannot
price — no reference price, or a unit it cannot bridge to the priced one — comes
back as ``None`` and is counted as *unpriced*. A missing price is never treated
as zero, because a silently-cheap shopping list is worse than an honestly
incomplete one.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, select

from app.core.naming import normalize_ingredient_name
from app.core.units import UnitDimension, convert, dimension, to_base
from app.models.ingredient import Ingredient, Unit

__all__ = ["CostSummary", "PriceBook", "ingredient_cost", "quantize_money"]

# Costs are accumulated at four decimal places so that per-unit prices of
# fractions of a cent do not vanish, and rounded to two only for display.
_INTERNAL_EXPONENT = Decimal("0.0001")
_MONEY_EXPONENT = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    """Round a computed cost to a presentable two decimal places."""
    return value.quantize(_MONEY_EXPONENT, rounding=ROUND_HALF_UP)


def _decimal(value: float) -> Decimal:
    # via str, so 0.1 stays 0.1 rather than becoming its binary expansion
    return Decimal(str(value))


def _to_grams(quantity: float, unit: Unit, ingredient: Ingredient) -> float | None:
    """Weight of ``quantity`` ``unit`` of this ingredient, if it can be known.

    Mass units convert outright. Volume needs the ingredient's density, and a
    discrete unit needs its per-piece weight; without those the question has no
    answer and the caller must report the item as unpriced.
    """
    match dimension(unit):
        case UnitDimension.MASS:
            return to_base(quantity, unit)
        case UnitDimension.VOLUME:
            if ingredient.density_g_per_ml is None:
                return None
            return to_base(quantity, unit) * ingredient.density_g_per_ml
        case _:
            if ingredient.piece_weight_g is None:
                return None
            return quantity * ingredient.piece_weight_g


def _price_per_gram(ingredient: Ingredient) -> Decimal | None:
    if ingredient.price_amount is None or ingredient.price_quantity is None:
        return None
    if ingredient.price_unit is None:
        return None
    grams = _to_grams(ingredient.price_quantity, ingredient.price_unit, ingredient)
    if grams is None or grams <= 0:
        return None
    return ingredient.price_amount / _decimal(grams)


def ingredient_cost(
    ingredient: Ingredient, quantity: float, unit: Unit
) -> Decimal | None:
    """What ``quantity`` ``unit`` of ``ingredient`` costs, or ``None``.

    Tries a straight conversion into the unit the price is quoted in first —
    that needs no extra data and is exact. Only when the quantity and the price
    are in different dimensions does it fall back to weighing both sides, which
    requires the ingredient's density or piece weight.
    """
    if ingredient.price_amount is None or ingredient.price_quantity is None:
        return None
    if ingredient.price_unit is None or quantity <= 0:
        return None

    direct = convert(quantity, unit, ingredient.price_unit)
    if direct is not None:
        cost = (
            ingredient.price_amount
            * _decimal(direct)
            / _decimal(ingredient.price_quantity)
        )
        return cost.quantize(_INTERNAL_EXPONENT, rounding=ROUND_HALF_UP)

    per_gram = _price_per_gram(ingredient)
    grams = _to_grams(quantity, unit, ingredient)
    if per_gram is None or grams is None:
        return None
    cost = per_gram * _decimal(grams)
    return cost.quantize(_INTERNAL_EXPONENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CostSummary:
    """Aggregate cost of a set of priced quantities.

    ``total`` is ``None`` when nothing at all could be priced, which the UI
    renders differently from a genuine zero.
    """

    total: Decimal | None
    unpriced_count: int
    priced_count: int

    @property
    def is_complete(self) -> bool:
        return self.unpriced_count == 0 and self.priced_count > 0

    def per_unit(self, divisor: int | None) -> Decimal | None:
        """``total`` split ``divisor`` ways — used for cost per serving."""
        if self.total is None or not divisor or divisor <= 0:
            return None
        return quantize_money(self.total / Decimal(divisor))


class PriceBook:
    """Reference prices for a known set of ingredient names.

    Built once per request and passed into the ``*_to_public`` helpers, so
    pricing a recipe costs one query rather than one per ingredient.
    """

    def __init__(self, ingredients: list[Ingredient], *, currency: str = "EUR") -> None:
        self.currency = currency
        self._by_name: dict[str, Ingredient] = {}
        for ingredient in ingredients:
            self._index(ingredient.name, ingredient)
            if ingredient.name_en:
                self._index(ingredient.name_en, ingredient)

    def _index(self, name: str, ingredient: Ingredient) -> None:
        key = normalize_ingredient_name(name)
        # A localised alias must never displace the row it is an alias of.
        if key and key not in self._by_name:
            self._by_name[key] = ingredient

    @classmethod
    def for_catalog(cls, *, session: Session, currency: str = "EUR") -> "PriceBook":
        """Load the whole catalog.

        Matching happens on the normalised name, which SQL cannot express, so
        narrowing the query by name would risk missing a row that only pairs
        up after normalisation. The catalog is small and this runs once per
        request, which is still far cheaper than a query per ingredient.
        """
        return cls(list(session.exec(select(Ingredient)).all()), currency=currency)

    def lookup(self, name: str) -> Ingredient | None:
        return self._by_name.get(normalize_ingredient_name(name))

    def cost(self, name: str, quantity: float, unit: Unit) -> Decimal | None:
        """Cost of ``quantity`` ``unit`` of the ingredient called ``name``."""
        ingredient = self.lookup(name)
        if ingredient is None:
            return None
        return ingredient_cost(ingredient, quantity, unit)

    def summarize(self, items: list[tuple[str, float, Unit]]) -> CostSummary:
        """Total ``items``, counting what could not be priced."""
        total = Decimal(0)
        priced = 0
        unpriced = 0
        for name, quantity, unit in items:
            line = self.cost(name, quantity, unit)
            if line is None:
                unpriced += 1
            else:
                total += line
                priced += 1
        return CostSummary(
            total=quantize_money(total) if priced else None,
            unpriced_count=unpriced,
            priced_count=priced,
        )
