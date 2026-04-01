import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    recipes: list["Recipe"] = Relationship(back_populates="owner", cascade_delete=True)
    shopping_lists: list["ShoppingList"] = Relationship(back_populates="owner", cascade_delete=True)
    household_memberships: list["HouseholdMember"] = Relationship(back_populates="user", cascade_delete=True)
    owned_households: list["Household"] = Relationship(back_populates="owner", cascade_delete=True)


class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# ---------------------------------------------------------------------------
# Item (legacy)
# ---------------------------------------------------------------------------

class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class ItemCreate(ItemBase):
    pass


class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# ---------------------------------------------------------------------------
# Household
# ---------------------------------------------------------------------------

class HouseholdBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)


class HouseholdCreate(HouseholdBase):
    pass


class HouseholdUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class Household(HouseholdBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    owner: User | None = Relationship(back_populates="owned_households")
    members: list["HouseholdMember"] = Relationship(back_populates="household", cascade_delete=True)


class HouseholdMember(SQLModel, table=True):
    __tablename__ = "householdmember"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    household_id: uuid.UUID = Field(foreign_key="household.id", nullable=False, ondelete="CASCADE")
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    household: Household | None = Relationship(back_populates="members")
    user: User | None = Relationship(back_populates="household_memberships")


class HouseholdMemberPublic(SQLModel):
    user_id: uuid.UUID
    user_email: str
    user_full_name: str | None = None


class HouseholdPublic(HouseholdBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    members: list[HouseholdMemberPublic] = []
    member_count: int = 0


class HouseholdsPublic(SQLModel):
    data: list[HouseholdPublic]
    count: int


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------

class RecipeIngredientBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    quantity: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=50)


class RecipeIngredientCreate(RecipeIngredientBase):
    pass


class RecipeIngredientUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, min_length=1, max_length=50)


class RecipeIngredient(RecipeIngredientBase, table=True):
    __tablename__ = "recipeingredient"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recipe_id: uuid.UUID = Field(foreign_key="recipe.id", nullable=False, ondelete="CASCADE")
    recipe: Optional["Recipe"] = Relationship(back_populates="ingredients")


class RecipeIngredientPublic(RecipeIngredientBase):
    id: uuid.UUID
    recipe_id: uuid.UUID


class RecipeBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None)
    base_servings: int = Field(default=4, ge=1)


class RecipeCreate(RecipeBase):
    ingredients: list[RecipeIngredientCreate] = []


class RecipeUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None)
    base_servings: int | None = Field(default=None, ge=1)
    ingredients: list[RecipeIngredientCreate] | None = None


class Recipe(RecipeBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    owner: User | None = Relationship(back_populates="recipes")
    ingredients: list[RecipeIngredient] = Relationship(back_populates="recipe", cascade_delete=True)
    shopping_list_entries: list["ShoppingListRecipe"] = Relationship(back_populates="recipe")


class RecipePublic(RecipeBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    ingredients: list[RecipeIngredientPublic] = []


class RecipesPublic(SQLModel):
    data: list[RecipePublic]
    count: int


# ---------------------------------------------------------------------------
# Shopping List
# ---------------------------------------------------------------------------

class ShoppingListRecipeBase(SQLModel):
    num_people: int = Field(ge=1)
    num_meals: int = Field(ge=1, default=1)


class ShoppingListRecipeCreate(ShoppingListRecipeBase):
    recipe_id: uuid.UUID


class ShoppingListRecipeUpdate(SQLModel):
    num_people: int | None = Field(default=None, ge=1)
    num_meals: int | None = Field(default=None, ge=1)


class ShoppingListRecipe(ShoppingListRecipeBase, table=True):
    __tablename__ = "shoppinglistrecipe"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shopping_list_id: uuid.UUID = Field(foreign_key="shoppinglist.id", nullable=False, ondelete="CASCADE")
    recipe_id: uuid.UUID = Field(foreign_key="recipe.id", nullable=False, ondelete="CASCADE")
    shopping_list: Optional["ShoppingList"] = Relationship(back_populates="recipes")
    recipe: Recipe | None = Relationship(back_populates="shopping_list_entries")


class ShoppingListCheckedItem(SQLModel, table=True):
    __tablename__ = "shoppinglistcheckeditem"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    shopping_list_id: uuid.UUID = Field(foreign_key="shoppinglist.id", nullable=False, ondelete="CASCADE")
    ingredient_name: str = Field(max_length=255)
    unit: str = Field(max_length=50)
    is_checked: bool = Field(default=True)
    shopping_list: Optional["ShoppingList"] = Relationship(back_populates="checked_items")


class ShoppingListBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)


class ShoppingListCreate(ShoppingListBase):
    pass


class ShoppingListUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class ShoppingList(ShoppingListBase, table=True):
    __tablename__ = "shoppinglist"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    owner: User | None = Relationship(back_populates="shopping_lists")
    recipes: list[ShoppingListRecipe] = Relationship(back_populates="shopping_list", cascade_delete=True)
    checked_items: list[ShoppingListCheckedItem] = Relationship(back_populates="shopping_list", cascade_delete=True)


# --- Public schemas for responses ---

class ShoppingListRecipePublic(ShoppingListRecipeBase):
    id: uuid.UUID
    recipe_id: uuid.UUID
    recipe_title: str
    recipe_base_servings: int


class AggregatedIngredient(SQLModel):
    """An ingredient aggregated across all recipes in a shopping list."""
    name: str
    unit: str
    total_quantity: float
    is_checked: bool
    sources: list[dict]  # [{recipe_id, recipe_title, quantity, slr_id}]


class ShoppingListPublic(ShoppingListBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    recipes: list[ShoppingListRecipePublic] = []
    ingredients: list[AggregatedIngredient] = []


class ShoppingListsPublic(SQLModel):
    data: list[ShoppingListBase]
    count: int


class ShoppingListSummary(ShoppingListBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    recipe_count: int = 0


class ShoppingListsSummary(SQLModel):
    data: list[ShoppingListSummary]
    count: int


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------

class Message(SQLModel):
    message: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
