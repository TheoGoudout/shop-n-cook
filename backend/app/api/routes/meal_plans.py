import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, PriceBookDep, SessionDep
from app.models import Message, ShoppingListPublic, User
from app.models.meal_plan import (
    MealPlan,
    MealPlanCreate,
    MealPlanEntryCreate,
    MealPlanEntryPublic,
    MealPlanEntryUpdate,
    MealPlanPublic,
    MealPlansPublic,
    MealPlanUpdate,
)

router = APIRouter(prefix="/meal-plans", tags=["meal-plans"])


def _check_plan_access(plan: MealPlan | None, current_user: User) -> MealPlan:
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    if not current_user.is_superuser and plan.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return plan


def _check_recipe_usable(
    *, session: SessionDep, recipe_id: uuid.UUID, current_user: User
) -> None:
    """A plan may only reference a recipe the user is allowed to read."""
    recipe = crud.get_recipe(session=session, recipe_id=recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if (
        not current_user.is_superuser
        and recipe.owner_id != current_user.id
        and not recipe.is_public
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")


@router.get("/", response_model=MealPlansPublic)
def read_meal_plans(
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List meal plans. Superusers see all; regular users see only their own."""
    owner_id = None if current_user.is_superuser else current_user.id
    plans, count = crud.get_meal_plans(
        session=session, owner_id=owner_id, skip=skip, limit=limit
    )
    return MealPlansPublic(
        data=[crud.meal_plan_to_public(p, prices) for p in plans], count=count
    )


@router.get("/{id}", response_model=MealPlanPublic)
def read_meal_plan(
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
) -> Any:
    """Get one meal plan with all of its entries."""
    plan = crud.get_meal_plan(session=session, plan_id=id)
    plan = _check_plan_access(plan, current_user)
    return crud.meal_plan_to_public(plan, prices)


@router.post("/", response_model=MealPlanPublic)
def create_meal_plan(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    plan_in: MealPlanCreate,
) -> Any:
    """Create an empty meal plan over a date range."""
    if plan_in.end_date < plan_in.start_date:
        raise HTTPException(
            status_code=422, detail="end_date must not precede start_date"
        )
    plan = crud.create_meal_plan(
        session=session, plan_in=plan_in, owner_id=current_user.id
    )
    return crud.meal_plan_to_public(plan, prices)


@router.put("/{id}", response_model=MealPlanPublic)
def update_meal_plan(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
    plan_in: MealPlanUpdate,
) -> Any:
    """Rename a meal plan or move its date range."""
    plan = crud.get_meal_plan(session=session, plan_id=id)
    plan = _check_plan_access(plan, current_user)
    start = plan_in.start_date or plan.start_date
    end = plan_in.end_date or plan.end_date
    if end < start:
        raise HTTPException(
            status_code=422, detail="end_date must not precede start_date"
        )
    plan = crud.update_meal_plan(session=session, plan=plan, update_in=plan_in)
    return crud.meal_plan_to_public(plan, prices)


@router.delete("/{id}")
def delete_meal_plan(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """Delete a meal plan and its entries. Any generated list is kept."""
    plan = crud.get_meal_plan(session=session, plan_id=id)
    plan = _check_plan_access(plan, current_user)
    crud.delete_meal_plan(session=session, plan=plan)
    return Message(message="Meal plan deleted successfully")


# --------------------------------------------------------------------------- #
# Entries                                                                      #
# --------------------------------------------------------------------------- #


@router.post("/{id}/entries", response_model=MealPlanEntryPublic)
def add_entry(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
    entry_in: MealPlanEntryCreate,
) -> Any:
    """Put a recipe in one of the plan's slots."""
    plan = crud.get_meal_plan(session=session, plan_id=id)
    plan = _check_plan_access(plan, current_user)
    _check_recipe_usable(
        session=session, recipe_id=entry_in.recipe_id, current_user=current_user
    )
    entry = crud.add_entry(session=session, plan=plan, entry_in=entry_in)
    return crud.meal_plan_entry_to_public(entry, prices)


@router.patch("/{id}/entries/{entry_id}", response_model=MealPlanEntryPublic)
def update_entry(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
    entry_id: uuid.UUID,
    update_in: MealPlanEntryUpdate,
) -> Any:
    """Move an entry to another slot, change its servings, or swap its recipe."""
    plan = crud.get_meal_plan(session=session, plan_id=id)
    plan = _check_plan_access(plan, current_user)
    entry = crud.get_meal_plan_entry(session=session, entry_id=entry_id)
    if not entry or entry.meal_plan_id != id:
        raise HTTPException(status_code=404, detail="Entry not found")
    if update_in.recipe_id is not None:
        _check_recipe_usable(
            session=session, recipe_id=update_in.recipe_id, current_user=current_user
        )
    entry = crud.update_entry(session=session, entry=entry, update_in=update_in)
    return crud.meal_plan_entry_to_public(entry, prices)


@router.delete("/{id}/entries/{entry_id}")
def delete_entry(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    entry_id: uuid.UUID,
) -> Message:
    """Remove one entry from the plan."""
    plan = crud.get_meal_plan(session=session, plan_id=id)
    plan = _check_plan_access(plan, current_user)
    entry = crud.get_meal_plan_entry(session=session, entry_id=entry_id)
    if not entry or entry.meal_plan_id != id:
        raise HTTPException(status_code=404, detail="Entry not found")
    crud.delete_entry(session=session, entry=entry)
    return Message(message="Entry deleted successfully")


# --------------------------------------------------------------------------- #
# Shopping list generation                                                     #
# --------------------------------------------------------------------------- #


@router.post("/{id}/shopping-list", response_model=ShoppingListPublic)
def generate_shopping_list(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
    name: str | None = None,
) -> Any:
    """Turn this plan into a shopping list.

    Every entry is added at its planned servings through the same merge rules
    used when adding a recipe by hand, so a recipe cooked twice in one week
    lands on a single row.
    """
    plan = crud.get_meal_plan(session=session, plan_id=id)
    plan = _check_plan_access(plan, current_user)
    if not plan.entries:
        raise HTTPException(status_code=422, detail="Meal plan has no entries")
    shopping_list = crud.generate_shopping_list(session=session, plan=plan, name=name)
    return crud.shopping_list_to_public(shopping_list, prices)
