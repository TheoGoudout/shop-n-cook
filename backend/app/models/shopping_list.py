import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import get_datetime_utc, stored_enum
from app.models.ingredient import Unit
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
    #: Cost of this recipe at ``servings_planned``, not at its own ``servings``.
    estimated_cost: Decimal | None = None


# --------------------------------------------------------------------------- #
# ShoppingListRecipe table model                                                #
# --------------------------------------------------------------------------- #


class ShoppingListRecipe(ShoppingListRecipeBase, table=True):
    __table_args__ = (
        CheckConstraint("servings_planned >= 1", name="ck_shoppinglistrecipe_servings"),
    )

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
    name: str = Field(min_length=1, max_length=255)
    quantity: float = Field(gt=0)
    unit: Unit = Field(sa_type=stored_enum(Unit, 50))
    is_checked: bool = False
    notes: str | None = Field(default=None, max_length=255)
    #: How much of ``quantity`` is already at home, in the item's own ``unit``.
    #: Kept apart from ``quantity`` rather than subtracted from it, so adding,
    #: rescaling or removing a recipe still moves the need by the right amount.
    quantity_at_home: float = Field(default=0, ge=0)


class ShoppingListItemCreate(ShoppingListItemBase):
    pass


class ShoppingListItemUpdate(SQLModel):
    quantity: float | None = Field(default=None, gt=0)
    unit: Unit | None = None
    is_checked: bool | None = None
    notes: str | None = Field(default=None, max_length=255)
    quantity_at_home: float | None = Field(default=None, ge=0)


class ShoppingListItemPublic(SQLModel):
    id: uuid.UUID
    name: str
    #: What the planned recipes and manual additions call for.
    quantity: float
    unit: Unit
    is_checked: bool
    notes: str | None = None
    quantity_at_home: float = 0
    #: ``quantity`` less what is at home, never below zero.
    quantity_to_buy: float
    #: Cost of ``quantity_to_buy`` only: what is at home costs nothing more.
    estimated_cost: Decimal | None = None


class PantryCheckEntry(SQLModel):
    item_id: uuid.UUID
    quantity_at_home: float = Field(ge=0)


class PantryCheck(SQLModel):
    """The "what do I already have?" step, saved for several items at once.

    Items not mentioned keep their current at-home quantity.
    """

    items: list[PantryCheckEntry] = []


# --------------------------------------------------------------------------- #
# ShoppingListItem table model                                                 #
# --------------------------------------------------------------------------- #


class ShoppingListItem(ShoppingListItemBase, table=True):
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_shoppinglistitem_quantity"),
        CheckConstraint(
            "quantity_at_home >= 0", name="ck_shoppinglistitem_quantity_at_home"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shopping_list_id: uuid.UUID = Field(
        foreign_key="shoppinglist.id", nullable=False, ondelete="CASCADE"
    )
    shopping_list: "ShoppingList" = Relationship(back_populates="items")


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
    #: When someone last went through the list checking what is at home;
    #: ``None`` until they have, which is what prompts the UI to suggest it.
    pantry_checked_at: datetime | None = Field(
        default=None,
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
    pantry_checked_at: datetime | None = None
    items: list[ShoppingListItemPublic] = []
    planned_recipes: list[ShoppingListRecipePublic] = []
    #: Sum over the priced items only; ``unpriced_item_count`` says how much of
    #: the list that total is silent about.
    estimated_total: Decimal | None = None
    unpriced_item_count: int = 0
    currency: str = "EUR"


class ShoppingListsPublic(SQLModel):
    data: list[ShoppingListPublic]
    count: int
