import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import model_validator
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import get_datetime_utc
from app.models.ingredient import IngredientCategory, Unit

if TYPE_CHECKING:
    from app.models.user import User


# --------------------------------------------------------------------------- #
# Recipe metadata enums                                                        #
# --------------------------------------------------------------------------- #


class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    DESSERT = "dessert"
    DRINK = "drink"
    OTHER = "other"


# --------------------------------------------------------------------------- #
# RecipeIngredient schemas                                                     #
# --------------------------------------------------------------------------- #


class RecipeIngredientBase(SQLModel):
    ingredient_name: str = Field(min_length=1, max_length=255)
    quantity: float = Field(gt=0)
    unit: Unit
    notes: str | None = Field(default=None, max_length=255)


class RecipeIngredientCreate(RecipeIngredientBase):
    category: IngredientCategory | None = None
    name_en: str | None = None


class RecipeIngredientPublic(SQLModel):
    id: uuid.UUID
    ingredient_name: str
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
    recipe: "Recipe" = Relationship(back_populates="recipe_ingredients")


# --------------------------------------------------------------------------- #
# RecipeStep schemas                                                           #
# --------------------------------------------------------------------------- #


class RecipeStepCreate(SQLModel):
    step_number: int
    instruction: str = Field(min_length=1)
    ingredient_indices: list[int] = []


class RecipeStepIngredientPublic(SQLModel):
    recipe_ingredient_id: uuid.UUID
    ingredient_name: str


class RecipeStepPublic(SQLModel):
    id: uuid.UUID
    step_number: int
    instruction: str
    ingredients: list[RecipeStepIngredientPublic] = []


# --------------------------------------------------------------------------- #
# RecipeStep table models                                                      #
# --------------------------------------------------------------------------- #


class RecipeStepIngredient(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    step_id: uuid.UUID = Field(
        foreign_key="recipestep.id", nullable=False, ondelete="CASCADE"
    )
    recipe_ingredient_id: uuid.UUID = Field(
        foreign_key="recipeingredient.id", nullable=False, ondelete="CASCADE"
    )
    step: "RecipeStep" = Relationship(back_populates="step_ingredients")
    recipe_ingredient: RecipeIngredient = Relationship(
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class RecipeStep(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recipe_id: uuid.UUID = Field(
        foreign_key="recipe.id", nullable=False, ondelete="CASCADE"
    )
    step_number: int
    instruction: str
    recipe: "Recipe" = Relationship(back_populates="steps")
    step_ingredients: list[RecipeStepIngredient] = Relationship(
        back_populates="step",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )


# --------------------------------------------------------------------------- #
# Recipe schemas                                                               #
# --------------------------------------------------------------------------- #


class RecipeBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    servings: int | None = Field(default=None, ge=1)
    prep_time_minutes: int | None = Field(default=None, ge=0)
    cook_time_minutes: int | None = Field(default=None, ge=0)
    source_url: str | None = None
    image_url: str | None = None
    is_public: bool = Field(default=False)
    # Metadata
    seasons: list[Season] = Field(
        default_factory=list,
        sa_column=Column(PG_ARRAY(sa.String), nullable=True, server_default="{}"),
    )
    is_vegan: bool = Field(default=False)
    is_vegetarian: bool = Field(default=False)
    is_gluten_free: bool = Field(default=False)
    is_dairy_free: bool = Field(default=False)
    kcal_per_serving: int | None = Field(default=None, ge=0)
    difficulty: Difficulty | None = Field(default=None)
    meal_type: MealType | None = Field(default=None)
    cuisine_type: str | None = Field(default=None, max_length=100)


class RecipeCreate(RecipeBase):
    ingredients: list[RecipeIngredientCreate] = []
    steps: list[RecipeStepCreate] = []
    import_consent: bool = Field(default=False)

    @model_validator(mode="after")
    def check_import_consent(self) -> "RecipeCreate":
        if self.source_url and not self.import_consent:
            raise ValueError("import_consent is required when source_url is provided")
        return self


class RecipeUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    servings: int | None = Field(default=None, ge=1)
    prep_time_minutes: int | None = Field(default=None, ge=0)
    cook_time_minutes: int | None = Field(default=None, ge=0)
    source_url: str | None = None
    image_url: str | None = None
    is_public: bool | None = None
    ingredients: list[RecipeIngredientCreate] | None = None
    steps: list[RecipeStepCreate] | None = None
    # Metadata
    seasons: list[Season] | None = None
    is_vegan: bool | None = None
    is_vegetarian: bool | None = None
    is_gluten_free: bool | None = None
    is_dairy_free: bool | None = None
    kcal_per_serving: int | None = None
    difficulty: Difficulty | None = None
    meal_type: MealType | None = None
    cuisine_type: str | None = None


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
    import_consent: bool = Field(default=False)
    import_consent_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner: "User" = Relationship(back_populates="recipes")
    recipe_ingredients: list[RecipeIngredient] = Relationship(
        back_populates="recipe",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    steps: list[RecipeStep] = Relationship(
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
    owner_name: str | None = None
    created_at: datetime | None = None
    ingredients: list[RecipeIngredientPublic] = []
    steps: list[RecipeStepPublic] = []


class RecipesPublic(SQLModel):
    data: list[RecipePublic]
    count: int
