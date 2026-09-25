import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.api.routes.shopping_lists import lines_for_list
from app.models.base import Message
from app.models.store import (
    IngredientPriceCreate,
    IngredientPricePublic,
    IngredientPricesPublic,
    Store,
    StoreCreate,
    StorePublic,
    StoresPublic,
    StoreUpdate,
)
from app.services.store_providers import (
    Capability,
    CapabilityNotSupportedError,
    CartHandoff,
    ProviderNotFoundError,
    ProviderUnavailableError,
    StoreListRequest,
    StoreProvider,
    build_cart_handoff,
    get_provider,
)
from app.services.store_providers.refresh import RefreshResult, refresh_store_prices

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


# --------------------------------------------------------------------------- #
# Provider-backed operations                                                   #
# --------------------------------------------------------------------------- #


def _provider_for(store: Store) -> StoreProvider:
    """The provider behind a store, or a 409 explaining that there isn't one."""
    if not store.provider_slug:
        raise HTTPException(
            status_code=409,
            detail=f"{store.name} has no provider; its prices are curated by hand",
        )
    try:
        return get_provider(store.provider_slug)
    except ProviderNotFoundError:
        raise HTTPException(
            status_code=409,
            detail=f"{store.name} names a provider this build does not register",
        ) from None


def _store_or_404(*, session: SessionDep, store_id: uuid.UUID) -> Store:
    store = crud.get_store(session=session, store_id=store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.post("/{store_id}/refresh-prices", response_model=RefreshResult)
def refresh_store_prices_route(
    *,
    session: SessionDep,
    _current_user: Annotated[Any, Depends(get_current_active_superuser)],
    store_id: uuid.UUID,
    limit: int = Query(default=200, ge=1, le=2000),
) -> Any:
    """Pull this store's prices off its website into the price book.

    Superuser only: ``IngredientPrice`` rows are shared by every user, so a
    refresh is an edit to common data rather than a personal preference.

    Always 200 for a store that has a provider. A retailer that is unreachable,
    or an ingredient it cannot match or price, is reported in ``skipped``
    rather than failing the run — and whatever price those ingredients already
    had is left alone.
    """
    store = _store_or_404(session=session, store_id=store_id)
    provider = _provider_for(store)
    if not provider.supports(Capability.PRICES):
        raise HTTPException(
            status_code=409,
            detail=f"{store.name} cannot publish prices to us",
        )
    ingredients, _ = crud.get_ingredients(session=session, limit=limit)
    return refresh_store_prices(
        session=session, store=store, provider=provider, ingredients=ingredients
    )


@router.post("/{store_id}/cart", response_model=CartHandoff)
def build_store_cart(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    store_id: uuid.UUID,
    request: StoreListRequest,
) -> Any:
    """Hand a shopping list over to this store's basket.

    Returns either a URL or a ``CartPlan`` for the browser extension to run,
    depending on the provider's transport. The client branches on
    ``transport``.
    """
    store = _store_or_404(session=session, store_id=store_id)
    provider = _provider_for(store)
    lines = lines_for_list(
        session=session,
        current_user=current_user,
        shopping_list_id=request.shopping_list_id,
    )
    try:
        return build_cart_handoff(
            provider=provider, lines=lines, branch_id=request.branch_id
        )
    except CapabilityNotSupportedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
