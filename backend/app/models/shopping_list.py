import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import get_datetime_utc
from app.models.ingredient import Ingredient, IngredientCategory, Unit
from app.models.recipe import Recipe, RecipeIngredientPublic

if TYPE_CHECKING:
    from app.models.user import User


# --------------------------------------------------------------------------- #
# ShoppingListRecipe schemas                                                    #
# --------------------------------------------------------------------------- #


class ShoppingListRecipeBase(SQLModel):
    servings_planned: int = Field(ge=1)
    is_prepared: bool = False


class ShoppingListRecipeUpdate(SQLModel):
    is_prepared: bool | None = None
    servings_planned: int | None = Field(default=None, ge=1)


class ShoppingListRecipePublic(SQLModel):
    id: uuid.UUID
    recipe_id: uuid.UUID
    recipe_title: str
    recipe_servings: int | None
    servings_planned: int
    is_prepared: bool
    ingredients: list[RecipeIngredientPublic] = []


# --------------------------------------------------------------------------- #
# ShoppingListRecipe table model                                                #
# --------------------------------------------------------------------------- #


class ShoppingListRecipe(ShoppingListRecipeBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shopping_list_id: uuid.UUID = Field(
        foreign_key="shoppinglist.id", nullable=False, ondelete="CASCADE"
    )
    recipe_id: uuid.UUID = Field(
        foreign_key="recipe.id", nullable=False, ondelete="CASCADE"
    )
    shopping_list: "ShoppingList" = Relationship(back_populates="planned_recipes")
    recipe: Recipe = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


# --------------------------------------------------------------------------- #
# ShoppingListItem schemas                                                     #
# --------------------------------------------------------------------------- #


class ShoppingListItemBase(SQLModel):
    quantity: float = Field(gt=0)
    unit: Unit
    is_checked: bool = False
    notes: str | None = Field(default=None, max_length=255)


class ShoppingListItemCreate(ShoppingListItemBase):
    ingredient_id: uuid.UUID


class ShoppingListItemUpdate(SQLModel):
    quantity: float | None = Field(default=None, gt=0)
    unit: Unit | None = None
    is_checked: bool | None = None
    notes: str | None = Field(default=None, max_length=255)


class ShoppingListItemPublic(SQLModel):
    id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str
    ingredient_category: IngredientCategory
    quantity: float
    unit: Unit
    is_checked: bool
    notes: str | None = None


# --------------------------------------------------------------------------- #
# ShoppingListItem table model                                                 #
# --------------------------------------------------------------------------- #


class ShoppingListItem(ShoppingListItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shopping_list_id: uuid.UUID = Field(
        foreign_key="shoppinglist.id", nullable=False, ondelete="CASCADE"
    )
    ingredient_id: uuid.UUID = Field(
        foreign_key="ingredient.id", nullable=False, ondelete="RESTRICT"
    )
    shopping_list: "ShoppingList" = Relationship(back_populates="items")
    ingredient: Ingredient = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


# --------------------------------------------------------------------------- #
# ShoppingList schemas                                                         #
# --------------------------------------------------------------------------- #


class ShoppingListBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None


class ShoppingListCreate(ShoppingListBase):
    pass


class ShoppingListUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None


# --------------------------------------------------------------------------- #
# ShoppingList table model                                                     #
# --------------------------------------------------------------------------- #


class ShoppingList(ShoppingListBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner: "User" = Relationship(back_populates="shopping_lists")
    items: list[ShoppingListItem] = Relationship(
        back_populates="shopping_list",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    planned_recipes: list[ShoppingListRecipe] = Relationship(
        back_populates="shopping_list",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"},
    )


# --------------------------------------------------------------------------- #
# ShoppingList response schemas                                                #
# --------------------------------------------------------------------------- #


class ShoppingListPublic(ShoppingListBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    items: list[ShoppingListItemPublic] = []
    planned_recipes: list[ShoppingListRecipePublic] = []


class ShoppingListsPublic(SQLModel):
    data: list[ShoppingListPublic]
    count: int
