# Import order matters: user first (no deps), then ingredient,
# then recipe/shopping_list (import ingredient + user). This ensures SQLModel
# registers all table models before Alembic or the engine resolves relationships.
from sqlmodel import SQLModel  # noqa: F401 — re-exported for alembic env.py

from app.models.base import Message, get_datetime_utc
from app.models.ingredient import (
    Ingredient,
    IngredientBase,
    IngredientCategory,
    IngredientCreate,
    IngredientPublic,
    IngredientsPublic,
    IngredientUpdate,
    Unit,
)
from app.models.recipe import (
    Recipe,
    RecipeBase,
    RecipeCreate,
    RecipeIngredient,
    RecipeIngredientCreate,
    RecipeIngredientPublic,
    RecipePublic,
    RecipesPublic,
    RecipeUpdate,
)
from app.models.shopping_list import (
    ShoppingList,
    ShoppingListBase,
    ShoppingListCreate,
    ShoppingListItem,
    ShoppingListItemCreate,
    ShoppingListItemPublic,
    ShoppingListItemUpdate,
    ShoppingListPublic,
    ShoppingListRecipe,
    ShoppingListRecipePublic,
    ShoppingListRecipeUpdate,
    ShoppingListsPublic,
    ShoppingListUpdate,
)
from app.models.user import (
    NewPassword,
    Token,
    TokenPayload,
    UpdatePassword,
    User,
    UserBase,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

__all__ = [
    # base
    "SQLModel",
    "Message",
    "get_datetime_utc",
    # user / auth
    "Token",
    "TokenPayload",
    "NewPassword",
    "UserBase",
    "UserCreate",
    "UserRegister",
    "UserUpdate",
    "UserUpdateMe",
    "UpdatePassword",
    "User",
    "UserPublic",
    "UsersPublic",
    # ingredient
    "IngredientCategory",
    "Unit",
    "IngredientBase",
    "IngredientCreate",
    "IngredientUpdate",
    "Ingredient",
    "IngredientPublic",
    "IngredientsPublic",
    # recipe
    "RecipeIngredientCreate",
    "RecipeIngredientPublic",
    "RecipeBase",
    "RecipeCreate",
    "RecipeUpdate",
    "RecipeIngredient",
    "Recipe",
    "RecipePublic",
    "RecipesPublic",
    # shopping list
    "ShoppingListItemCreate",
    "ShoppingListItemUpdate",
    "ShoppingListItemPublic",
    "ShoppingListItem",
    "ShoppingListBase",
    "ShoppingListCreate",
    "ShoppingListUpdate",
    "ShoppingList",
    "ShoppingListPublic",
    "ShoppingListsPublic",
    "ShoppingListRecipe",
    "ShoppingListRecipePublic",
    "ShoppingListRecipeUpdate",
]
