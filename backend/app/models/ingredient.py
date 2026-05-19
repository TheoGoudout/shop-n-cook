import uuid
from enum import Enum

from sqlmodel import Field, SQLModel


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


class Ingredient(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255, unique=True, index=True)
    category: IngredientCategory = Field(default=IngredientCategory.OTHER)
    image_url: str | None = Field(default=None, max_length=2048)


class IngredientPublic(SQLModel):
    id: uuid.UUID
    name: str
    category: IngredientCategory
    image_url: str | None


class IngredientCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    category: IngredientCategory = IngredientCategory.OTHER
    image_url: str | None = None


class IngredientUpdate(SQLModel):
    category: IngredientCategory | None = None
    image_url: str | None = None


class IngredientsPublic(SQLModel):
    data: list[IngredientPublic]
    count: int
