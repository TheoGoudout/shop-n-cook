import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlmodel import Session

from app import crud
from app.api.deps import CurrentUser, PriceBookDep, SessionDep
from app.crud.shopping_list import _item_to_public, _sl_recipe_to_public
from app.models import (
    Message,
    ShoppingList,
    ShoppingListCreate,
    ShoppingListItem,
    ShoppingListItemCreate,
    ShoppingListItemPublic,
    ShoppingListItemUpdate,
    ShoppingListPublic,
    ShoppingListRecipe,
    ShoppingListRecipePublic,
    ShoppingListRecipeUpdate,
    ShoppingListsPublic,
    ShoppingListUpdate,
    StoreComparison,
    StoreComparisonEntry,
)
from app.services.ingredient_image import fetch_and_update_ingredient_image
from app.services.pricing import PriceBook

router = APIRouter(prefix="/shopping-lists", tags=["shopping-lists"])


def _check_list_access(
    shopping_list: ShoppingList | None,
    current_user: Any,
    _list_id: uuid.UUID,
    session: Session | None = None,
) -> ShoppingList:
    """Gate every read and write of one list.

    Access is decided by ``crud.user_can_access`` — your own lists, your
    household's, or anything if you are a superuser — so the household rule
    lives in exactly one place. ``session`` is optional only so the handful of
    superuser/self cases that cannot reach the database still work; every route
    here passes it.
    """
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    if current_user.is_superuser or shopping_list.owner_id == current_user.id:
        return shopping_list
    if session is not None and crud.user_can_access(
        session=session, user=current_user, owner_id=shopping_list.owner_id
    ):
        return shopping_list
    raise HTTPException(status_code=403, detail="Not enough permissions")


@router.get("/", response_model=ShoppingListsPublic)
def read_shopping_lists(
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List shopping lists. Superusers see all; regular users see only their own."""
    # A household member sees the whole household's lists, not just their own.
    owner_ids = (
        None
        if current_user.is_superuser
        else crud.household_member_ids(session=session, user_id=current_user.id)
    )
    lists, count = crud.get_shopping_lists(
        session=session, owner_ids=owner_ids, skip=skip, limit=limit
    )
    return ShoppingListsPublic(
        data=[crud.shopping_list_to_public(sl, prices) for sl in lists], count=count
    )


@router.get("/{id}", response_model=ShoppingListPublic)
def read_shopping_list(
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
) -> Any:
    """Get a single shopping list with all its items and planned recipes."""
    sl = crud.get_shopping_list(session=session, shopping_list_id=id)
    _check_list_access(sl, current_user, id, session)
    return crud.shopping_list_to_public(sl, prices)  # type: ignore[arg-type]


@router.post("/", response_model=ShoppingListPublic)
def create_shopping_list(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    list_in: ShoppingListCreate,
) -> Any:
    """Create a new (empty) shopping list."""
    sl = crud.create_shopping_list(
        session=session, list_in=list_in, owner_id=current_user.id
    )
    return crud.shopping_list_to_public(sl, prices)


@router.put("/{id}", response_model=ShoppingListPublic)
def update_shopping_list(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
    list_in: ShoppingListUpdate,
) -> Any:
    """Update a shopping list name and/or date range."""
    sl = crud.get_shopping_list(session=session, shopping_list_id=id)
    sl = _check_list_access(sl, current_user, id, session)
    sl = crud.update_shopping_list(
        session=session,
        db_list=sl,
        list_in=list_in,
    )
    return crud.shopping_list_to_public(sl, prices)


@router.delete("/{id}")
def delete_shopping_list(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """Delete a shopping list and all its items."""
    sl = crud.get_shopping_list(session=session, shopping_list_id=id)
    _check_list_access(sl, current_user, id, session)
    crud.delete_shopping_list(session=session, shopping_list=sl)  # type: ignore[arg-type]
    return Message(message="Shopping list deleted successfully")


# ---- Items sub-resource ---- #


@router.post("/{id}/items", response_model=ShoppingListPublic)
def add_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
    item_in: ShoppingListItemCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    """Add an item to a shopping list."""
    sl = crud.get_shopping_list(session=session, shopping_list_id=id)
    sl = _check_list_access(sl, current_user, id, session)
    ingredient, created = crud.get_or_create_ingredient(
        session=session, name=item_in.name
    )
    if created:
        background_tasks.add_task(fetch_and_update_ingredient_image, ingredient.id)
    sl = crud.add_item_to_shopping_list(
        session=session,
        shopping_list=sl,
        item_in=item_in,
    )
    return crud.shopping_list_to_public(sl, prices)


@router.put("/{id}/items/{item_id}", response_model=ShoppingListItemPublic)
def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_id: uuid.UUID,
    item_in: ShoppingListItemUpdate,
) -> Any:
    """Update a shopping list item (quantity, unit, is_checked, notes)."""
    sl: ShoppingList | None = crud.get_shopping_list(
        session=session, shopping_list_id=id
    )
    _check_list_access(sl, current_user, id, session)
    item: ShoppingListItem | None = crud.get_shopping_list_item(
        session=session, item_id=item_id
    )
    if not item or item.shopping_list_id != id:
        raise HTTPException(status_code=404, detail="Item not found")
    updated = crud.update_shopping_list_item(
        session=session, item=item, item_in=item_in
    )
    return _item_to_public(updated)


@router.delete("/{id}/items/{item_id}")
def delete_item(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_id: uuid.UUID,
) -> Message:
    """Remove an item from a shopping list."""
    sl: ShoppingList | None = crud.get_shopping_list(
        session=session, shopping_list_id=id
    )
    _check_list_access(sl, current_user, id, session)
    item: ShoppingListItem | None = crud.get_shopping_list_item(
        session=session, item_id=item_id
    )
    if not item or item.shopping_list_id != id:
        raise HTTPException(status_code=404, detail="Item not found")
    crud.delete_shopping_list_item(session=session, item=item)
    return Message(message="Item removed successfully")


# ---- Recipe addition ---- #


@router.post("/{id}/add-recipe/{recipe_id}", response_model=ShoppingListPublic)
def add_recipe(
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
    recipe_id: uuid.UUID,
    servings: int | None = None,
) -> Any:
    """Add all ingredients from a recipe to the shopping list (scaled by servings).

    Items with the same ingredient + unit are aggregated (quantities summed).
    A ShoppingListRecipe record is created to track this recipe in the list.
    """
    sl = crud.get_shopping_list(session=session, shopping_list_id=id)
    sl = _check_list_access(sl, current_user, id, session)
    recipe = crud.get_recipe(session=session, recipe_id=recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if (
        not current_user.is_superuser
        and recipe.owner_id != current_user.id
        and not recipe.is_public
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    sl = crud.add_recipe_to_shopping_list(
        session=session,
        shopping_list=sl,
        recipe=recipe,
        servings=servings,
    )
    return crud.shopping_list_to_public(sl, prices)


@router.get("/{id}/store-comparison", response_model=StoreComparison)
def compare_stores(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """What this list would cost at each active retailer.

    This is the "shop where you like" view: every store is costed from the same
    basket, so the spread is comparable even where a store has few curated
    prices of its own and falls back to the catalog baseline.
    """
    sl = crud.get_shopping_list(session=session, shopping_list_id=id)
    sl = _check_list_access(sl, current_user, id, session)

    items = [(i.name, i.quantity, i.unit) for i in sl.items]
    stores, _ = crud.get_stores(session=session, active_only=True, limit=100)

    entries: list[StoreComparisonEntry] = []
    for store in stores:
        book = PriceBook.for_catalog(session=session, store=store)
        summary = book.summarize(items)
        entries.append(
            StoreComparisonEntry(
                store_id=store.id,
                store_name=store.name,
                store_slug=store.slug,
                currency=store.currency,
                estimated_total=summary.total,
                unpriced_item_count=summary.unpriced_count,
            )
        )

    entries.sort(key=lambda e: (e.estimated_total is None, e.estimated_total or 0))
    cheapest = next((e for e in entries if e.estimated_total is not None), None)
    return StoreComparison(
        data=entries,
        cheapest_store_id=cheapest.store_id if cheapest else None,
    )


# ---- Planned recipes sub-resource ---- #


@router.patch(
    "/{id}/planned-recipes/{planned_recipe_id}", response_model=ShoppingListRecipePublic
)
def update_planned_recipe(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
    planned_recipe_id: uuid.UUID,
    update_in: ShoppingListRecipeUpdate,
) -> Any:
    """Update a planned recipe (e.g. mark as prepared, change servings)."""
    sl: ShoppingList | None = crud.get_shopping_list(
        session=session, shopping_list_id=id
    )
    sl = _check_list_access(sl, current_user, id, session)
    sl_recipe: ShoppingListRecipe | None = crud.get_shopping_list_recipe(
        session=session, sl_recipe_id=planned_recipe_id
    )
    if not sl_recipe or sl_recipe.shopping_list_id != id:
        raise HTTPException(status_code=404, detail="Planned recipe not found")
    updated = crud.update_shopping_list_recipe(
        session=session, shopping_list=sl, sl_recipe=sl_recipe, update_in=update_in
    )
    return _sl_recipe_to_public(updated, prices)


@router.delete("/{id}/planned-recipes/{planned_recipe_id}")
def delete_planned_recipe(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    planned_recipe_id: uuid.UUID,
) -> Message:
    """Remove a planned recipe from the shopping list."""
    sl: ShoppingList | None = crud.get_shopping_list(
        session=session, shopping_list_id=id
    )
    sl = _check_list_access(sl, current_user, id, session)
    sl_recipe: ShoppingListRecipe | None = crud.get_shopping_list_recipe(
        session=session, sl_recipe_id=planned_recipe_id
    )
    if not sl_recipe or sl_recipe.shopping_list_id != id:
        raise HTTPException(status_code=404, detail="Planned recipe not found")
    crud.delete_shopping_list_recipe(
        session=session, shopping_list=sl, sl_recipe=sl_recipe
    )
    return Message(message="Planned recipe removed successfully")
