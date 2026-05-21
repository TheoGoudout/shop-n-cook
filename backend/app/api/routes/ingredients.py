import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models.ingredient import (
    DeduplicateMerge,
    DeduplicateResponse,
    IngredientCreate,
    IngredientPublic,
    IngredientsPublic,
    IngredientUpdate,
)
from app.services.ingredient_image import fetch_and_update_ingredient_image

logger = logging.getLogger(__name__)

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


@router.post("/deduplicate", response_model=DeduplicateResponse)
def deduplicate_ingredients(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    dry_run: bool = True,
) -> Any:
    """Merge near-duplicate ingredient catalog entries. Superuser only.

    Pass ?dry_run=false to apply changes. Default is preview-only.
    Cascades: recipe_ingredient.ingredient_name and shopping_list_item.name
    are updated to the canonical (shortest) name in each duplicate group.
    """
    groups = crud.get_duplicate_groups(session=session)
    merges: list[DeduplicateMerge] = []
    removed_count = 0
    for group in groups:
        group_sorted = sorted(group, key=lambda i: len(i.name))
        canonical = group_sorted[0]
        to_remove = group_sorted[1:]
        merges.append(
            DeduplicateMerge(
                kept=canonical.name,
                removed=[i.name for i in to_remove],
            )
        )
        if not dry_run:
            for dup in to_remove:
                crud.rename_ingredient_references(
                    session=session, old_name=dup.name, new_name=canonical.name
                )
                crud.delete_ingredient(session=session, ingredient=dup)
            removed_count += len(to_remove)
    return DeduplicateResponse(
        dry_run=dry_run, groups=merges, removed_count=removed_count
    )


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
    logger.info(
        "Queuing image fetch for ingredient %r (id=%s, current image=%s)",
        ingredient.name,
        ingredient.id,
        "set" if ingredient.image_url else "missing",
    )
    background_tasks.add_task(fetch_and_update_ingredient_image, ingredient.id)
    return IngredientPublic.model_validate(ingredient)
