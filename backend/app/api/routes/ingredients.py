import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models.base import Message
from app.models.ingredient import (
    DeduplicateMerge,
    DeduplicateResponse,
    IngredientCreate,
    IngredientPublic,
    IngredientsPublic,
    IngredientUpdate,
)
from app.services.ingredient_image import fetch_and_update_ingredient_image
from app.services.ingredient_price import (
    estimate_ingredient_price,
    estimate_prices_batch,
)

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
    """Update an ingredient's category, image or reference price. Superuser only."""
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


class EstimatePricesRequest(BaseModel):
    """Which ingredients to price, and in what currency.

    An empty ``ingredient_ids`` means "everything without a curated price",
    which is the common case after a bulk import.
    """

    ingredient_ids: list[uuid.UUID] = []
    currency: str = "EUR"


@router.post("/{id}/estimate-price", response_model=IngredientPublic)
def estimate_ingredient_price_route(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    id: uuid.UUID,
    background_tasks: BackgroundTasks,
    currency: str = "EUR",
) -> Any:
    """Queue an LLM price estimate for this ingredient. Superuser only.

    A price a human curated is never overwritten — see
    ``services.ingredient_price.may_overwrite``.
    """
    ingredient = crud.get_ingredient(session=session, ingredient_id=id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    background_tasks.add_task(
        estimate_ingredient_price, ingredient.id, currency=currency
    )
    return IngredientPublic.model_validate(ingredient)


@router.post("/estimate-prices", response_model=Message)
def estimate_ingredient_prices_route(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    body: EstimatePricesRequest,
    background_tasks: BackgroundTasks,
) -> Any:
    """Queue LLM price estimates for many ingredients. Superuser only."""
    if body.ingredient_ids:
        ids = body.ingredient_ids
    else:
        ingredients, _ = crud.get_ingredients(session=session, skip=0, limit=1000)
        ids = [i.id for i in ingredients if i.price_amount is None]

    if not ids:
        return Message(message="No ingredients need a price estimate")

    background_tasks.add_task(estimate_prices_batch, list(ids), currency=body.currency)
    return Message(message=f"Estimating prices for {len(ids)} ingredient(s)")


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
