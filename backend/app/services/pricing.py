"""Turn catalog reference prices into the cost of a recipe or a shopping list.

The entry point is :class:`PriceBook`: build one per request from the names you
are about to price, then ask it what each quantity costs. Anything it cannot
price — no reference price, or a unit it cannot bridge to the priced one — comes
back as ``None`` and is counted as *unpriced*. A missing price is never treated
as zero, because a silently-cheap shopping list is worse than an honestly
incomplete one.
"""

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, select

from app.core.naming import normalize_ingredient_name
from app.core.units import UnitDimension, convert, dimension, to_base
from app.models.ingredient import Ingredient, Unit
from app.models.store import IngredientPrice, Store

__all__ = [
    "CostSummary",
    "PriceBook",
    "QuotedPrice",
    "ingredient_cost",
    "quantize_money",
]

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


@dataclass(frozen=True)
class QuotedPrice:
    """A price the way it is quoted: an amount per a quantity of a unit.

    Both the catalog's reference price and a store's own price take this shape,
    so the costing arithmetic does not need to know which one it was handed.
    """

    amount: Decimal
    quantity: float
    unit: Unit

    @classmethod
    def from_ingredient(cls, ingredient: Ingredient) -> "QuotedPrice | None":
        if ingredient.price_amount is None or ingredient.price_quantity is None:
            return None
        if ingredient.price_unit is None:
            return None
        return cls(
            amount=ingredient.price_amount,
            quantity=ingredient.price_quantity,
            unit=ingredient.price_unit,
        )


def _price_per_gram(price: QuotedPrice, ingredient: Ingredient) -> Decimal | None:
    """Normalise a quoted price to per-gram, using the ingredient's bridges."""
    grams = _to_grams(price.quantity, price.unit, ingredient)
    if grams is None or grams <= 0:
        return None
    return price.amount / _decimal(grams)


def ingredient_cost(
    ingredient: Ingredient,
    quantity: float,
    unit: Unit,
    *,
    quoted: "QuotedPrice | None" = None,
    index: float = 1.0,
) -> Decimal | None:
    """What ``quantity`` ``unit`` of ``ingredient`` costs, or ``None``.

    ``quoted`` overrides the catalog's own reference price — that is how a
    store's price for this ingredient is applied — while the ingredient still
    supplies the density and piece weight, which are properties of the food
    and not of the shop. ``index`` scales the result and is only meaningful
    for the catalog baseline, never for a real store price.

    Tries a straight conversion into the unit the price is quoted in first —
    that needs no extra data and is exact. Only when the quantity and the price
    are in different dimensions does it fall back to weighing both sides, which
    requires the ingredient's density or piece weight.
    """
    price = quoted or QuotedPrice.from_ingredient(ingredient)
    if price is None or quantity <= 0:
        return None

    direct = convert(quantity, unit, price.unit)
    if direct is not None:
        cost = price.amount * _decimal(direct) / _decimal(price.quantity)
        return _scale(cost, index)

    per_gram = _price_per_gram(price, ingredient)
    grams = _to_grams(quantity, unit, ingredient)
    if per_gram is None or grams is None:
        return None
    return _scale(per_gram * _decimal(grams), index)


def _scale(cost: Decimal, index: float) -> Decimal:
    scaled = cost if index == 1.0 else cost * _decimal(index)
    return scaled.quantize(_INTERNAL_EXPONENT, rounding=ROUND_HALF_UP)


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

    When a ``store`` is given, prices resolve in this order:

    1. the store's own price for the ingredient, when one has been curated;
    2. the catalog's reference price scaled by the store's ``price_index``;
    3. unpriced.

    Step 2 is what keeps a sparse price matrix useful: a store with only a
    handful of curated prices still produces a whole-basket estimate, clearly
    derived from the baseline, instead of a mostly-empty list.
    """

    def __init__(
        self,
        ingredients: list[Ingredient],
        *,
        currency: str = "EUR",
        store: Store | None = None,
        store_prices: list[IngredientPrice] | None = None,
    ) -> None:
        self.store = store
        self.currency = store.currency if store is not None else currency
        self._index_factor = store.price_index if store is not None else 1.0
        self._by_name: dict[str, Ingredient] = {}
        for ingredient in ingredients:
            self._index(ingredient.name, ingredient)
            if ingredient.name_en:
                self._index(ingredient.name_en, ingredient)
        self._store_prices: dict[uuid.UUID, IngredientPrice] = {
            row.ingredient_id: row for row in (store_prices or [])
        }

    def _index(self, name: str, ingredient: Ingredient) -> None:
        key = normalize_ingredient_name(name)
        # A localised alias must never displace the row it is an alias of.
        if key and key not in self._by_name:
            self._by_name[key] = ingredient

    @classmethod
    def for_catalog(
        cls,
        *,
        session: Session,
        currency: str = "EUR",
        store: Store | None = None,
    ) -> "PriceBook":
        """Load the whole catalog, and a store's prices when one is selected.

        Matching happens on the normalised name, which SQL cannot express, so
        narrowing the query by name would risk missing a row that only pairs
        up after normalisation. The catalog is small and this runs once per
        request, which is still far cheaper than a query per ingredient.
        """
        ingredients = list(session.exec(select(Ingredient)).all())
        store_prices: list[IngredientPrice] = []
        if store is not None:
            store_prices = list(
                session.exec(
                    select(IngredientPrice).where(IngredientPrice.store_id == store.id)
                ).all()
            )
        return cls(
            ingredients,
            currency=currency,
            store=store,
            store_prices=store_prices,
        )

    def lookup(self, name: str) -> Ingredient | None:
        return self._by_name.get(normalize_ingredient_name(name))

    def cost(self, name: str, quantity: float, unit: Unit) -> Decimal | None:
        """Cost of ``quantity`` ``unit`` of the ingredient called ``name``."""
        ingredient = self.lookup(name)
        if ingredient is None:
            return None

        store_price = self._store_prices.get(ingredient.id)
        if store_price is not None:
            # A real price for this store needs no index adjustment.
            return ingredient_cost(
                ingredient,
                quantity,
                unit,
                quoted=QuotedPrice(
                    amount=store_price.price_amount,
                    quantity=store_price.price_quantity,
                    unit=store_price.price_unit,
                ),
            )
        return ingredient_cost(ingredient, quantity, unit, index=self._index_factor)

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
