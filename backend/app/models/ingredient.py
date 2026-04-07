import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.models.base import get_datetime_utc


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


class Unit(str, Enum):
    GRAM = "g"
    KILOGRAM = "kg"
    MILLILITER = "ml"
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


# --------------------------------------------------------------------------- #
# Ingredient schemas                                                           #
# --------------------------------------------------------------------------- #


class IngredientBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    category: IngredientCategory = Field(default=IngredientCategory.OTHER)
    default_unit: Unit = Field(default=Unit.PIECE)


class IngredientCreate(IngredientBase):
    pass


class IngredientUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: IngredientCategory | None = None
    default_unit: Unit | None = None


# --------------------------------------------------------------------------- #
# Ingredient table model                                                       #
# --------------------------------------------------------------------------- #


class Ingredient(IngredientBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# --------------------------------------------------------------------------- #
# Ingredient response schemas                                                  #
# --------------------------------------------------------------------------- #


class IngredientPublic(IngredientBase):
    id: uuid.UUID
    created_at: datetime | None = None


class IngredientsPublic(SQLModel):
    data: list[IngredientPublic]
    count: int
