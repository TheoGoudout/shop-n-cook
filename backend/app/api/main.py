from fastapi import APIRouter

from app.api.routes import (
    households,
    ingredients,
    login,
    meal_plans,
    private,
    recipes,
    shopping_lists,
    stores,
    user_settings,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(recipes.router)
api_router.include_router(shopping_lists.router)
api_router.include_router(user_settings.router)
api_router.include_router(ingredients.router)
api_router.include_router(stores.router)
api_router.include_router(stores.price_router)
api_router.include_router(meal_plans.router)
api_router.include_router(households.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
