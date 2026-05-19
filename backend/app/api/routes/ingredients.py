import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models.ingredient import (
    IngredientCreate,
    IngredientPublic,
    IngredientsPublic,
    IngredientUpdate,
)
from app.services.ingredient_image import fetch_and_update_ingredient_image

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("/", response_model=IngredientsPublic)
def read_ingredients(
    session: SessionDep,
    _current_user: CurrentUser,
    skip: int = 0,
    limit: int = 1000,
) -> Any:
    """List all ingredients in the catalog."""
    ingredients, count = crud.get_ingredients(session=session, skip=skip, limit=limit)
    return IngredientsPublic(
        data=[IngredientPublic.model_validate(i) for i in ingredients], count=count
    )


@router.post("/", response_model=IngredientPublic)
def create_ingredient(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    ingredient_in: IngredientCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    """Create an ingredient catalog entry. Superuser only."""
    existing = crud.get_ingredient_by_name(session=session, name=ingredient_in.name)
    if existing:
        raise HTTPException(status_code=409, detail="Ingredient already exists")
    ingredient = crud.create_ingredient(session=session, ingredient_in=ingredient_in)
    if not ingredient.image_url:
        background_tasks.add_task(fetch_and_update_ingredient_image, ingredient.id)
    return IngredientPublic.model_validate(ingredient)


@router.patch("/{id}", response_model=IngredientPublic)
def update_ingredient(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    id: uuid.UUID,
    update_in: IngredientUpdate,
) -> Any:
    """Update an ingredient's category or image. Superuser only."""
    ingredient = crud.get_ingredient(session=session, ingredient_id=id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    ingredient = crud.update_ingredient(
        session=session, ingredient=ingredient, update_in=update_in
    )
    return IngredientPublic.model_validate(ingredient)


@router.post("/{id}/fetch-image", response_model=IngredientPublic)
def fetch_ingredient_image(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    id: uuid.UUID,
    background_tasks: BackgroundTasks,
) -> Any:
    """Trigger an Open Food Facts image fetch for this ingredient. Superuser only."""
    ingredient = crud.get_ingredient(session=session, ingredient_id=id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    background_tasks.add_task(fetch_and_update_ingredient_image, ingredient.id)
    return IngredientPublic.model_validate(ingredient)
