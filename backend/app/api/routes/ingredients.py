import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    IngredientCategory,
    IngredientPublic,
    IngredientsPublic,
)

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("/", response_model=IngredientsPublic)
def read_ingredients(
    session: SessionDep,
    _: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    category: IngredientCategory | None = None,
) -> Any:
    ingredients, count = crud.get_ingredients(
        session=session, skip=skip, limit=limit, search=search, category=category
    )
    return IngredientsPublic(data=ingredients, count=count)


@router.get("/{id}", response_model=IngredientPublic)
def read_ingredient(session: SessionDep, _: CurrentUser, id: uuid.UUID) -> Any:
    ingredient = crud.get_ingredient(session=session, ingredient_id=id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return ingredient
