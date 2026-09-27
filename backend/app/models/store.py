import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import get_datetime_utc
from app.models.ingredient import Unit

# --------------------------------------------------------------------------- #
# Store schemas                                                                #
# --------------------------------------------------------------------------- #


class StoreBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    country: str = Field(default="FR", min_length=2, max_length=2)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    #: Multiplier applied to an ingredient's base price when this store has no
    #: price of its own. A sparse price matrix would otherwise leave most of
    #: the catalog unpriced the moment a store is selected, which is worse than
    #: an approximate answer clearly derived from the baseline.
    price_index: float = Field(default=1.0, gt=0)
    logo_url: str | None = Field(default=None, max_length=2048)
    is_active: bool = Field(default=True)
    #: Links this store to a registered provider in
    #: ``app.services.store_providers`` — the machinery that knows how to read
    #: this retailer's site. ``None`` means a store whose prices are only ever
    #: curated by hand, which is every store today and stays perfectly valid:
    #: a market stall has no website to read.
    provider_slug: str | None = Field(default=None, max_length=64, index=True)


class StoreCreate(StoreBase):
    pass


class StoreUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    price_index: float | None = Field(default=None, gt=0)
    logo_url: str | None = Field(default=None, max_length=2048)
    is_active: bool | None = None


class StorePublic(StoreBase):
    id: uuid.UUID
    #: What the store's provider can actually do, resolved at read time from
    #: the registry rather than stored — so a capability cannot drift out of
    #: sync with the code that implements it. Empty for a hand-curated store.
    capabilities: list[str] = Field(default_factory=list)
    #: True when prices for this store can be refreshed from the retailer.
    can_refresh_prices: bool = False
    #: True when a basket can be handed over, and only through the extension.
    requires_extension: bool = False


class StoresPublic(SQLModel):
    data: list["StorePublic"]
    count: int


# --------------------------------------------------------------------------- #
# Store table model                                                            #
# --------------------------------------------------------------------------- #


class Store(StoreBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    slug: str = Field(min_length=1, max_length=255, unique=True, index=True)
    prices: list["IngredientPrice"] = Relationship(
        back_populates="store", cascade_delete=True
    )


# --------------------------------------------------------------------------- #
# IngredientPrice schemas                                                      #
# --------------------------------------------------------------------------- #


class IngredientPriceBase(SQLModel):
    """What one ingredient costs at one store.

    Shaped like ``Ingredient``'s own reference price — an amount per a quantity
    of a unit — so the two resolve through identical arithmetic.
    """

    price_amount: Decimal = Field(max_digits=10, decimal_places=4, ge=0)
    price_quantity: float = Field(gt=0)
    price_unit: Unit


class IngredientPriceCreate(IngredientPriceBase):
    store_id: uuid.UUID


class IngredientPriceUpdate(SQLModel):
    price_amount: Decimal | None = Field(
        default=None, max_digits=10, decimal_places=4, ge=0
    )
    price_quantity: float | None = Field(default=None, gt=0)
    price_unit: Unit | None = None


class IngredientPricePublic(IngredientPriceBase):
    id: uuid.UUID
    ingredient_id: uuid.UUID
    store_id: uuid.UUID
    store_name: str | None = None
    updated_at: datetime | None = None


class IngredientPricesPublic(SQLModel):
    data: list[IngredientPricePublic]
    count: int


# --------------------------------------------------------------------------- #
# IngredientPrice table model                                                  #
# --------------------------------------------------------------------------- #


class IngredientPrice(IngredientPriceBase, table=True):
    __table_args__ = (
        UniqueConstraint("ingredient_id", "store_id", name="uq_ingredient_store_price"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ingredient_id: uuid.UUID = Field(
        foreign_key="ingredient.id", nullable=False, ondelete="CASCADE", index=True
    )
    store_id: uuid.UUID = Field(
        foreign_key="store.id", nullable=False, ondelete="CASCADE", index=True
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    store: Store = Relationship(
        back_populates="prices", sa_relationship_kwargs={"lazy": "selectin"}
    )


# --------------------------------------------------------------------------- #
# Comparison across stores                                                     #
# --------------------------------------------------------------------------- #


class StoreComparisonEntry(SQLModel):
    """What one shopping list would cost at one store."""

    store_id: uuid.UUID
    store_name: str
    store_slug: str
    currency: str
    estimated_total: Decimal | None = None
    unpriced_item_count: int = 0


class StoreComparison(SQLModel):
    data: list[StoreComparisonEntry]
    cheapest_store_id: uuid.UUID | None = None
