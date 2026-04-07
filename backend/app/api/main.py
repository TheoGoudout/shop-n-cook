from fastapi import APIRouter

from app.api.routes import ingredients, login, private, recipes, users, utils
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(ingredients.router)
api_router.include_router(recipes.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
