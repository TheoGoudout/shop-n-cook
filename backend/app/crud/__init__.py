from app.crud.ingredient import (
    create_ingredient,
    delete_ingredient,
    get_duplicate_groups,
    get_ingredient,
    get_ingredient_by_name,
    get_ingredients,
    get_or_create_ingredient,
    rename_ingredient_references,
    update_ingredient,
)
from app.crud.recipe import (
    create_recipe,
    delete_recipe,
    get_public_recipes,
    get_recipe,
    get_recipe_by_source_url,
    get_recipes,
    recipe_to_public,
    update_recipe,
)
from app.crud.shopping_list import (
    add_item_to_shopping_list,
    add_recipe_to_shopping_list,
    create_shopping_list,
    delete_shopping_list,
    delete_shopping_list_item,
    delete_shopping_list_recipe,
    get_shopping_list,
    get_shopping_list_item,
    get_shopping_list_recipe,
    get_shopping_lists,
    shopping_list_to_public,
    update_shopping_list,
    update_shopping_list_item,
    update_shopping_list_recipe,
)
from app.crud.user import authenticate, create_user, get_user_by_email, update_user
from app.crud.user_settings import (
    get_or_create_user_settings,
    get_user_settings,
    update_user_settings,
)

__all__ = [
    # ingredient catalog
    "get_ingredient",
    "get_ingredient_by_name",
    "get_ingredients",
    "get_or_create_ingredient",
    "create_ingredient",
    "update_ingredient",
    "delete_ingredient",
    "rename_ingredient_references",
    "get_duplicate_groups",
    # user
    "create_user",
    "update_user",
    "get_user_by_email",
    "authenticate",
    # user settings
    "get_user_settings",
    "get_or_create_user_settings",
    "update_user_settings",
    # recipe
    "get_recipe",
    "get_recipe_by_source_url",
    "get_recipes",
    "get_public_recipes",
    "create_recipe",
    "update_recipe",
    "delete_recipe",
    "recipe_to_public",
    # shopping list
    "get_shopping_list",
    "get_shopping_lists",
    "create_shopping_list",
    "update_shopping_list",
    "delete_shopping_list",
    "get_shopping_list_item",
    "add_item_to_shopping_list",
    "update_shopping_list_item",
    "delete_shopping_list_item",
    "add_recipe_to_shopping_list",
    "shopping_list_to_public",
    "get_shopping_list_recipe",
    "update_shopping_list_recipe",
    "delete_shopping_list_recipe",
]
