from fastapi import APIRouter

from app.api.routes import households, items, login, private, recipes, shopping_lists, users, utils
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(recipes.router)
api_router.include_router(households.router)
api_router.include_router(shopping_lists.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
