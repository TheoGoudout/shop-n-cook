import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.models.base import get_datetime_utc


class Unit(str, Enum):
    GRAM = "g"
    KILOGRAM = "kg"
    MILLILITER = "ml"
    CENTILITER = "cl"
    DECILITER = "dl"
    LITER = "L"
    PIECE = "piece"
    TABLESPOON = "tbsp"
    TEASPOON = "tsp"
    CUP = "cup"
    OUNCE = "oz"
    POUND = "lb"
    BUNCH = "bunch"
    PINCH = "pinch"
    CLOVE = "clove"
    SLICE = "slice"
    CAN = "can"
    PACKAGE = "package"


class IngredientCategory(str, Enum):
    PRODUCE = "produce"
    DAIRY = "dairy"
    MEAT = "meat"
    SEAFOOD = "seafood"
    GRAINS = "grains"
    PANTRY = "pantry"
    SPICES = "spices"
    BEVERAGES = "beverages"
    FROZEN = "frozen"
    BAKERY = "bakery"
    OTHER = "other"


class PriceSource(str, Enum):
    """Where an ingredient's reference price came from.

    ``ESTIMATED`` rows were filled in by the LLM assist and may be overwritten
    by a later estimate run; ``MANUAL`` rows were curated by a human and never
    are.
    """

    MANUAL = "manual"
    ESTIMATED = "estimated"


class IngredientPricingBase(SQLModel):
    """Reference price and the conversion bridges that make it usable.

    The price is stored the way a human quotes it — "2.50 for 1 kg" — as
    ``price_amount`` per ``price_quantity`` ``price_unit``, and normalised at
    read time. ``density_g_per_ml`` and ``piece_weight_g`` are what let a price
    quoted per kilo answer "what do 2 tablespoons cost?"; without them a recipe
    ingredient measured in another dimension is reported as unpriced rather
    than guessed at.
    """

    price_amount: Decimal | None = Field(
        default=None, max_digits=10, decimal_places=4, ge=0
    )
    price_quantity: float | None = Field(default=None, gt=0)
    price_unit: Unit | None = Field(default=None)
    density_g_per_ml: float | None = Field(default=None, gt=0)
    piece_weight_g: float | None = Field(default=None, gt=0)


class Ingredient(IngredientPricingBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255, unique=True, index=True)
    name_en: str | None = Field(default=None, max_length=255)
    category: IngredientCategory = Field(default=IngredientCategory.OTHER)
    image_url: str | None = Field(default=None, max_length=2048)
    price_source: PriceSource | None = Field(default=None)
    price_updated_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )


class IngredientPublic(IngredientPricingBase):
    id: uuid.UUID
    name: str
    name_en: str | None
    category: IngredientCategory
    image_url: str | None
    price_source: PriceSource | None = None
    price_updated_at: datetime | None = None


class IngredientCreate(IngredientPricingBase):
    name: str = Field(min_length=1, max_length=255)
    category: IngredientCategory = IngredientCategory.OTHER
    image_url: str | None = None


class IngredientUpdate(IngredientPricingBase):
    category: IngredientCategory | None = None
    image_url: str | None = None


def touch_price(ingredient: Ingredient, *, source: PriceSource) -> None:
    """Stamp provenance on an ingredient whose price was just written."""
    ingredient.price_source = source
    ingredient.price_updated_at = get_datetime_utc()


class IngredientsPublic(SQLModel):
    data: list[IngredientPublic]
    count: int


class DeduplicateMerge(SQLModel):
    kept: str
    removed: list[str]


class DeduplicateResponse(SQLModel):
    dry_run: bool
    groups: list[DeduplicateMerge]
    removed_count: int
