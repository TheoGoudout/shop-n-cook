import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import model_validator
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import get_datetime_utc
from app.models.ingredient import Ingredient, IngredientCategory, Unit

if TYPE_CHECKING:
    from app.models.user import User


# --------------------------------------------------------------------------- #
# RecipeIngredient schemas                                                     #
# --------------------------------------------------------------------------- #


class RecipeIngredientBase(SQLModel):
    quantity: float = Field(gt=0)
    unit: Unit
    notes: str | None = Field(default=None, max_length=255)


class RecipeIngredientCreate(RecipeIngredientBase):
    ingredient_id: uuid.UUID | None = None
    ingredient_name: str | None = Field(default=None, min_length=1, max_length=255)
    ingredient_category: IngredientCategory = Field(default=IngredientCategory.OTHER)
    ingredient_default_unit: Unit = Field(default=Unit.PIECE)

    @model_validator(mode="after")
    def check_ingredient_source(self) -> "RecipeIngredientCreate":
        if self.ingredient_id is None and not self.ingredient_name:
            raise ValueError("Either ingredient_id or ingredient_name must be provided")
        return self


class RecipeIngredientPublic(SQLModel):
    id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str
    ingredient_category: IngredientCategory
    quantity: float
    unit: Unit
    notes: str | None = None


# --------------------------------------------------------------------------- #
# RecipeIngredient table model                                                 #
# --------------------------------------------------------------------------- #


class RecipeIngredient(RecipeIngredientBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recipe_id: uuid.UUID = Field(
        foreign_key="recipe.id", nullable=False, ondelete="CASCADE"
    )
    ingredient_id: uuid.UUID = Field(
        foreign_key="ingredient.id", nullable=False, ondelete="RESTRICT"
    )
    recipe: "Recipe" = Relationship(back_populates="recipe_ingredients")
    ingredient: Ingredient = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


# --------------------------------------------------------------------------- #
# Recipe schemas                                                               #
# --------------------------------------------------------------------------- #


class RecipeBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    instructions: str | None = None
    servings: int | None = Field(default=None, ge=1)
    prep_time_minutes: int | None = Field(default=None, ge=0)
    cook_time_minutes: int | None = Field(default=None, ge=0)
    source_url: str | None = None
    image_url: str | None = None


class RecipeCreate(RecipeBase):
    ingredients: list[RecipeIngredientCreate] = []


class RecipeUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    instructions: str | None = None
    servings: int | None = Field(default=None, ge=1)
    prep_time_minutes: int | None = Field(default=None, ge=0)
    cook_time_minutes: int | None = Field(default=None, ge=0)
    source_url: str | None = None
    image_url: str | None = None
    ingredients: list[RecipeIngredientCreate] | None = None


# --------------------------------------------------------------------------- #
# Recipe table model                                                           #
# --------------------------------------------------------------------------- #


class Recipe(RecipeBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner: "User" = Relationship(back_populates="recipes")
    recipe_ingredients: list[RecipeIngredient] = Relationship(
        back_populates="recipe",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )


# --------------------------------------------------------------------------- #
# Recipe response schemas                                                      #
# --------------------------------------------------------------------------- #


class RecipePublic(RecipeBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    ingredients: list[RecipeIngredientPublic] = []


class RecipesPublic(SQLModel):
    data: list[RecipePublic]
    count: int
