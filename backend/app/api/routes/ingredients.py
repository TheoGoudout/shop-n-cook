import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Ingredient,
    IngredientCategory,
    IngredientCreate,
    IngredientPublic,
    IngredientsPublic,
    IngredientUpdate,
    Message,
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
    """
    List ingredients. Supports optional full-text search and category filter.
    """
    ingredients, count = crud.get_ingredients(
        session=session, skip=skip, limit=limit, search=search, category=category
    )
    return IngredientsPublic(data=ingredients, count=count)


@router.get("/{id}", response_model=IngredientPublic)
def read_ingredient(session: SessionDep, _: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get a single ingredient by ID.
    """
    ingredient = crud.get_ingredient(session=session, ingredient_id=id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return ingredient


@router.post("/", response_model=IngredientPublic)
def create_ingredient(
    *, session: SessionDep, _: CurrentUser, ingredient_in: IngredientCreate
) -> Any:
    """
    Create a new ingredient. Any authenticated user may add ingredients.
    Returns 400 if an ingredient with the same name already exists.
    """
    existing = crud.get_ingredient_by_name(session=session, name=ingredient_in.name)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An ingredient with this name already exists",
        )
    return crud.create_ingredient(session=session, ingredient_in=ingredient_in)


@router.put("/{id}", response_model=IngredientPublic)
def update_ingredient(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    ingredient_in: IngredientUpdate,
) -> Any:
    """
    Update an ingredient. Superusers only.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    ingredient: Ingredient | None = crud.get_ingredient(
        session=session, ingredient_id=id
    )
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if ingredient_in.name:
        existing = crud.get_ingredient_by_name(session=session, name=ingredient_in.name)
        if existing and existing.id != id:
            raise HTTPException(
                status_code=400,
                detail="An ingredient with this name already exists",
            )
    return crud.update_ingredient(
        session=session, db_ingredient=ingredient, ingredient_in=ingredient_in
    )


@router.delete("/{id}")
def delete_ingredient(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an ingredient. Superusers only.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    ingredient = crud.get_ingredient(session=session, ingredient_id=id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if crud.ingredient_has_references(session=session, ingredient_id=id):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete ingredient that is used in recipes or shopping lists",
        )
    crud.delete_ingredient(session=session, ingredient=ingredient)
    return Message(message="Ingredient deleted successfully")
