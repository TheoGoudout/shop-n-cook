import uuid
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import crud
from app.api.deps import CurrentUser, PriceBookDep, SessionDep
from app.models import Message, Recipe, ShoppingListPublic, User
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
from app.models.recipe import MealType
from app.services.menu_generator import (
    GenerationRequest,
    generate_menu,
    pick_replacement,
)

router = APIRouter(prefix="/meal-plans", tags=["meal-plans"])


def _check_plan_access(
    plan: MealPlan | None, current_user: User, session: Session | None = None
) -> MealPlan:
    """Gate every read and write of one plan.

    Delegates to ``crud.user_can_access`` so the household rule has a single
    definition shared with shopping lists.
    """
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    if current_user.is_superuser or plan.owner_id == current_user.id:
        return plan
    if session is not None and crud.user_can_access(
        session=session, user=current_user, owner_id=plan.owner_id
    ):
        return plan
    raise HTTPException(status_code=403, detail="Not enough permissions")


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
    # A household member sees the whole household's plans, not just their own.
    owner_ids = (
        None
        if current_user.is_superuser
        else crud.household_member_ids(session=session, user_id=current_user.id)
    )
    plans, count = crud.get_meal_plans(
        session=session, owner_ids=owner_ids, skip=skip, limit=limit
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
    plan = _check_plan_access(plan, current_user, session)
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
    plan = _check_plan_access(plan, current_user, session)
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
    plan = _check_plan_access(plan, current_user, session)
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
    plan = _check_plan_access(plan, current_user, session)
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
    plan = _check_plan_access(plan, current_user, session)
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
    plan = _check_plan_access(plan, current_user, session)
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
    plan = _check_plan_access(plan, current_user, session)
    if not plan.entries:
        raise HTTPException(status_code=422, detail="Meal plan has no entries")
    shopping_list = crud.generate_shopping_list(session=session, plan=plan, name=name)
    return crud.shopping_list_to_public(shopping_list, prices)


# --------------------------------------------------------------------------- #
# Generation                                                                   #
# --------------------------------------------------------------------------- #


class GenerateMenuRequest(BaseModel):
    """What to compose, and the constraints it must respect."""

    name: str | None = None
    start_date: date
    days: int = Field(default=7, ge=1, le=31)
    meal_types: list[MealType] = Field(default_factory=lambda: [MealType.DINNER])
    servings: int | None = Field(default=None, ge=1)
    budget: Decimal | None = Field(default=None, ge=0)
    require_vegan: bool = False
    require_vegetarian: bool = False
    require_gluten_free: bool = False
    require_dairy_free: bool = False
    max_prep_minutes: int | None = Field(default=None, ge=0)
    match_season: bool = True
    include_public: bool = True
    seed: int = 0


def _candidate_recipes(
    *, session: SessionDep, current_user: User, include_public: bool
) -> list[Recipe]:
    """Everything this user may cook: their own recipes, plus public ones."""
    own, _ = crud.get_recipes(session=session, owner_id=current_user.id, limit=500)
    if not include_public:
        return own
    public, _ = crud.get_public_recipes(session=session, limit=500)
    by_id = {r.id: r for r in own}
    for recipe in public:
        by_id.setdefault(recipe.id, recipe)
    return list(by_id.values())


def _generation_request(
    body: GenerateMenuRequest, *, servings: int
) -> GenerationRequest:
    return GenerationRequest(
        start_date=body.start_date,
        days=body.days,
        meal_types=tuple(body.meal_types),
        servings=servings,
        budget=body.budget,
        require_vegan=body.require_vegan,
        require_vegetarian=body.require_vegetarian,
        require_gluten_free=body.require_gluten_free,
        require_dairy_free=body.require_dairy_free,
        max_prep_minutes=body.max_prep_minutes,
        match_season=body.match_season,
        seed=body.seed,
    )


@router.post("/generate", response_model=MealPlanPublic)
def generate_menu_route(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    body: GenerateMenuRequest,
) -> Any:
    """Compose a menu and save it as a new plan.

    Household size and budget fall back to the user's settings when the request
    does not override them, so the common case is a single button with no form.
    """
    user_settings = crud.get_or_create_user_settings(
        session=session, user_id=current_user.id
    )
    servings = body.servings or user_settings.household_size
    budget = body.budget if body.budget is not None else user_settings.budget_amount

    candidates = _candidate_recipes(
        session=session, current_user=current_user, include_public=body.include_public
    )
    if not candidates:
        raise HTTPException(
            status_code=422, detail="No recipes available to build a menu from"
        )

    request = _generation_request(body, servings=servings)
    request = replace(request, budget=budget)
    meals = generate_menu(candidates, request, prices)
    if not meals:
        raise HTTPException(
            status_code=422,
            detail="No recipes match those constraints",
        )

    plan = crud.create_meal_plan(
        session=session,
        plan_in=MealPlanCreate(
            name=body.name or f"Menu {body.start_date.isoformat()}",
            start_date=body.start_date,
            end_date=body.start_date + timedelta(days=body.days - 1),
        ),
        owner_id=current_user.id,
    )
    for meal in meals:
        crud.add_entry(
            session=session,
            plan=plan,
            entry_in=MealPlanEntryCreate(
                recipe_id=meal.recipe.id,
                entry_date=meal.entry_date,
                meal_type=meal.meal_type,
                servings=meal.servings,
            ),
        )
    session.refresh(plan)
    return crud.meal_plan_to_public(plan, prices)


@router.post("/{id}/entries/{entry_id}/swap", response_model=MealPlanEntryPublic)
def swap_entry(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
    entry_id: uuid.UUID,
    body: GenerateMenuRequest | None = None,
) -> Any:
    """Replace one meal without disturbing the rest of the plan.

    The replacement still respects the week's variety rules, so swapping out of
    a pasta night does not hand back another one.
    """
    plan = crud.get_meal_plan(session=session, plan_id=id)
    plan = _check_plan_access(plan, current_user, session)
    entry = crud.get_meal_plan_entry(session=session, entry_id=entry_id)
    if not entry or entry.meal_plan_id != id:
        raise HTTPException(status_code=404, detail="Entry not found")

    body = body or GenerateMenuRequest(start_date=entry.entry_date)
    candidates = _candidate_recipes(
        session=session, current_user=current_user, include_public=body.include_public
    )
    request = _generation_request(body, servings=entry.servings)
    others = frozenset(e.recipe_id for e in plan.entries if e.id != entry.id)

    replacement = pick_replacement(
        candidates,
        request,
        entry.entry_date,
        entry.meal_type,
        current_recipe_id=entry.recipe_id,
        other_recipe_ids=others,
        prices=prices,
    )
    if replacement is None:
        raise HTTPException(
            status_code=422, detail="No alternative recipe matches those constraints"
        )

    entry = crud.update_entry(
        session=session,
        entry=entry,
        update_in=MealPlanEntryUpdate(recipe_id=replacement.id),
    )
    return crud.meal_plan_entry_to_public(entry, prices)
