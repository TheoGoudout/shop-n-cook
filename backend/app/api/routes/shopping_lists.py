import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    AggregatedIngredient,
    Message,
    Recipe,
    ShoppingList,
    ShoppingListCheckedItem,
    ShoppingListCreate,
    ShoppingListPublic,
    ShoppingListRecipe,
    ShoppingListRecipeCreate,
    ShoppingListRecipePublic,
    ShoppingListRecipeUpdate,
    ShoppingListsSummary,
    ShoppingListSummary,
    ShoppingListUpdate,
)

router = APIRouter(prefix="/shopping-lists", tags=["shopping-lists"])


def _compute_ingredients(
    shopping_list: ShoppingList,
) -> list[AggregatedIngredient]:
    """Aggregate ingredients from all recipes in the list."""
    # key: (normalized_name, unit) -> {total_quantity, sources, is_checked}
    aggregated: dict[tuple[str, str], dict] = {}

    checked_keys: set[tuple[str, str]] = {
        (ci.ingredient_name.lower(), ci.unit.lower())
        for ci in shopping_list.checked_items
        if ci.is_checked
    }

    for slr in shopping_list.recipes:
        recipe = slr.recipe
        if not recipe:
            continue
        scale = (slr.num_people * slr.num_meals) / recipe.base_servings
        for ing in recipe.ingredients:
            key = (ing.name.lower().strip(), ing.unit.lower().strip())
            scaled_qty = round(ing.quantity * scale, 4)
            if key not in aggregated:
                aggregated[key] = {
                    "name": ing.name.strip(),
                    "unit": ing.unit.strip(),
                    "total_quantity": 0.0,
                    "sources": [],
                    "is_checked": key in checked_keys,
                }
            aggregated[key]["total_quantity"] = round(
                aggregated[key]["total_quantity"] + scaled_qty, 4
            )
            aggregated[key]["sources"].append(
                {
                    "slr_id": str(slr.id),
                    "recipe_id": str(recipe.id),
                    "recipe_title": recipe.title,
                    "quantity": scaled_qty,
                    "unit": ing.unit.strip(),
                }
            )

    return [
        AggregatedIngredient(
            name=v["name"],
            unit=v["unit"],
            total_quantity=v["total_quantity"],
            is_checked=v["is_checked"],
            sources=v["sources"],
        )
        for v in aggregated.values()
    ]


def _to_public(shopping_list: ShoppingList) -> ShoppingListPublic:
    recipes_public = [
        ShoppingListRecipePublic(
            id=slr.id,
            recipe_id=slr.recipe_id,
            num_people=slr.num_people,
            num_meals=slr.num_meals,
            recipe_title=slr.recipe.title if slr.recipe else "",
            recipe_base_servings=slr.recipe.base_servings if slr.recipe else 1,
        )
        for slr in shopping_list.recipes
    ]
    ingredients = _compute_ingredients(shopping_list)
    return ShoppingListPublic(
        id=shopping_list.id,
        name=shopping_list.name,
        owner_id=shopping_list.owner_id,
        created_at=shopping_list.created_at,
        recipes=recipes_public,
        ingredients=ingredients,
    )


@router.get("/", response_model=ShoppingListsSummary)
def read_shopping_lists(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    count_statement = (
        select(func.count())
        .select_from(ShoppingList)
        .where(ShoppingList.owner_id == current_user.id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(ShoppingList)
        .where(ShoppingList.owner_id == current_user.id)
        .order_by(col(ShoppingList.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    lists = session.exec(statement).all()
    data = [
        ShoppingListSummary(
            id=sl.id,
            name=sl.name,
            owner_id=sl.owner_id,
            created_at=sl.created_at,
            recipe_count=len(sl.recipes),
        )
        for sl in lists
    ]
    return ShoppingListsSummary(data=data, count=count)


@router.get("/{id}", response_model=ShoppingListPublic)
def read_shopping_list(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    sl = session.get(ShoppingList, id)
    if not sl:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    if sl.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return _to_public(sl)


@router.post("/", response_model=ShoppingListPublic)
def create_shopping_list(
    *, session: SessionDep, current_user: CurrentUser, list_in: ShoppingListCreate
) -> Any:
    sl = ShoppingList(name=list_in.name, owner_id=current_user.id)
    session.add(sl)
    session.commit()
    session.refresh(sl)
    return _to_public(sl)


@router.put("/{id}", response_model=ShoppingListPublic)
def update_shopping_list(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    list_in: ShoppingListUpdate,
) -> Any:
    sl = session.get(ShoppingList, id)
    if not sl:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    if sl.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if list_in.name is not None:
        sl.name = list_in.name
    session.add(sl)
    session.commit()
    session.refresh(sl)
    return _to_public(sl)


@router.delete("/{id}")
def delete_shopping_list(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    sl = session.get(ShoppingList, id)
    if not sl:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    if sl.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(sl)
    session.commit()
    return Message(message="Shopping list deleted successfully")


# ---------------------------------------------------------------------------
# Recipe entries
# ---------------------------------------------------------------------------

@router.post("/{id}/recipes", response_model=ShoppingListPublic)
def add_recipe_to_list(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    entry_in: ShoppingListRecipeCreate,
) -> Any:
    sl = session.get(ShoppingList, id)
    if not sl:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    if sl.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    recipe = session.get(Recipe, entry_in.recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions on recipe")

    entry = ShoppingListRecipe(
        shopping_list_id=id,
        recipe_id=entry_in.recipe_id,
        num_people=entry_in.num_people,
        num_meals=entry_in.num_meals,
    )
    session.add(entry)
    session.commit()
    session.refresh(sl)
    return _to_public(sl)


@router.put("/{id}/recipes/{entry_id}", response_model=ShoppingListPublic)
def update_recipe_in_list(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    entry_id: uuid.UUID,
    entry_in: ShoppingListRecipeUpdate,
) -> Any:
    sl = session.get(ShoppingList, id)
    if not sl:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    if sl.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    entry = session.get(ShoppingListRecipe, entry_id)
    if not entry or entry.shopping_list_id != id:
        raise HTTPException(status_code=404, detail="Recipe entry not found")

    if entry_in.num_people is not None:
        entry.num_people = entry_in.num_people
    if entry_in.num_meals is not None:
        entry.num_meals = entry_in.num_meals

    session.add(entry)
    session.commit()
    session.refresh(sl)
    return _to_public(sl)


@router.delete("/{id}/recipes/{entry_id}", response_model=ShoppingListPublic)
def remove_recipe_from_list(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    entry_id: uuid.UUID,
) -> Any:
    sl = session.get(ShoppingList, id)
    if not sl:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    if sl.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    entry = session.get(ShoppingListRecipe, entry_id)
    if not entry or entry.shopping_list_id != id:
        raise HTTPException(status_code=404, detail="Recipe entry not found")

    session.delete(entry)
    session.commit()
    session.refresh(sl)
    return _to_public(sl)


# ---------------------------------------------------------------------------
# Check / uncheck ingredients
# ---------------------------------------------------------------------------

@router.post("/{id}/ingredients/check", response_model=ShoppingListPublic)
def toggle_ingredient(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    ingredient_name: str,
    unit: str,
    is_checked: bool,
) -> Any:
    sl = session.get(ShoppingList, id)
    if not sl:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    if sl.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    name_key = ingredient_name.lower().strip()
    unit_key = unit.lower().strip()

    checked_item = session.exec(
        select(ShoppingListCheckedItem)
        .where(ShoppingListCheckedItem.shopping_list_id == id)
        .where(ShoppingListCheckedItem.ingredient_name == name_key)
        .where(ShoppingListCheckedItem.unit == unit_key)
    ).first()

    if checked_item:
        checked_item.is_checked = is_checked
        session.add(checked_item)
    else:
        checked_item = ShoppingListCheckedItem(
            shopping_list_id=id,
            ingredient_name=name_key,
            unit=unit_key,
            is_checked=is_checked,
        )
        session.add(checked_item)

    session.commit()
    session.refresh(sl)
    return _to_public(sl)
