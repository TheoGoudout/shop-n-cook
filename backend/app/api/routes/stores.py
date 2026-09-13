import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models.base import Message
from app.models.store import (
    IngredientPriceCreate,
    IngredientPricePublic,
    IngredientPricesPublic,
    StoreCreate,
    StorePublic,
    StoresPublic,
    StoreUpdate,
)

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("/", response_model=StoresPublic)
def read_stores(
    session: SessionDep,
    _current_user: CurrentUser,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List the retailers prices can be compared across."""
    stores, count = crud.get_stores(
        session=session, active_only=active_only, skip=skip, limit=limit
    )
    return StoresPublic(data=[crud.store_to_public(s) for s in stores], count=count)


@router.post("/", response_model=StorePublic)
def create_store(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    store_in: StoreCreate,
) -> Any:
    """Add a retailer. Superuser only."""
    if crud.get_store_by_slug(session=session, slug=store_in.slug):
        raise HTTPException(status_code=409, detail="Store already exists")
    return crud.store_to_public(crud.create_store(session=session, store_in=store_in))


@router.patch("/{id}", response_model=StorePublic)
def update_store(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    id: uuid.UUID,
    update_in: StoreUpdate,
) -> Any:
    """Update a retailer. Superuser only."""
    store = crud.get_store(session=session, store_id=id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return crud.store_to_public(
        crud.update_store(session=session, store=store, update_in=update_in)
    )


@router.delete("/{id}")
def delete_store(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    id: uuid.UUID,
) -> Message:
    """Delete a retailer and every price recorded against it. Superuser only."""
    store = crud.get_store(session=session, store_id=id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    crud.delete_store(session=session, store=store)
    return Message(message="Store deleted successfully")


# --------------------------------------------------------------------------- #
# Per-ingredient prices, nested under the ingredient they belong to            #
# --------------------------------------------------------------------------- #

price_router = APIRouter(prefix="/ingredients", tags=["ingredient-prices"])


@price_router.get("/{id}/prices", response_model=IngredientPricesPublic)
def read_ingredient_prices(
    session: SessionDep,
    _current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """Every store price recorded for one ingredient."""
    ingredient = crud.get_ingredient(session=session, ingredient_id=id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    prices = crud.get_ingredient_prices(session=session, ingredient_id=id)
    return IngredientPricesPublic(
        data=[crud.ingredient_price_to_public(p) for p in prices], count=len(prices)
    )


@price_router.put("/{id}/prices", response_model=IngredientPricePublic)
def upsert_ingredient_price(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    id: uuid.UUID,
    price_in: IngredientPriceCreate,
) -> Any:
    """Set this ingredient's price at one store. Superuser only."""
    ingredient = crud.get_ingredient(session=session, ingredient_id=id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if not crud.get_store(session=session, store_id=price_in.store_id):
        raise HTTPException(status_code=404, detail="Store not found")
    price = crud.upsert_ingredient_price(
        session=session, ingredient=ingredient, price_in=price_in
    )
    return crud.ingredient_price_to_public(price)


@price_router.delete("/{id}/prices/{store_id}")
def delete_ingredient_price(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    id: uuid.UUID,
    store_id: uuid.UUID,
) -> Message:
    """Remove this ingredient's price at one store. Superuser only.

    The ingredient then falls back to the catalog baseline scaled by that
    store's price index.
    """
    price = crud.get_ingredient_price(
        session=session, ingredient_id=id, store_id=store_id
    )
    if not price:
        raise HTTPException(status_code=404, detail="Price not found")
    crud.delete_ingredient_price(session=session, price=price)
    return Message(message="Price deleted successfully")
