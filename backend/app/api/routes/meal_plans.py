import uuid
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import crud
from app.api.deps import (
    CurrentUser,
    PriceBookDep,
    SessionDep,
    SharedMealPlan,
    readable_recipe,
)
from app.models import Message, Recipe, ShoppingListPublic, User
from app.models.meal_plan import (
    MealPlan,
    MealPlanCreate,
    MealPlanEntry,
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
    cost_of,
    generate_menu,
    is_eligible,
    pick_replacement,
)

router = APIRouter(prefix="/meal-plans", tags=["meal-plans"])


def _entry_of(session: Session, plan: MealPlan, entry_id: uuid.UUID) -> MealPlanEntry:
    entry = crud.get_meal_plan_entry(session=session, entry_id=entry_id)
    if not entry or entry.meal_plan_id != plan.id:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


def _check_dates(start: date, end: date) -> None:
    if end < start:
        raise HTTPException(
            status_code=422, detail="end_date must not precede start_date"
        )


@router.get("/", response_model=MealPlansPublic)
def read_meal_plans(
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List the plans shared with your household. Superusers see all."""
    plans, count = crud.get_meal_plans(
        session=session,
        owner_ids=crud.visible_owner_ids(session=session, user=current_user),
        skip=skip,
        limit=limit,
    )
    return MealPlansPublic(
        data=[crud.meal_plan_to_public(p, prices) for p in plans], count=count
    )


@router.get("/{id}", response_model=MealPlanPublic)
def read_meal_plan(plan: SharedMealPlan, prices: PriceBookDep) -> Any:
    """Get one meal plan with all of its entries."""
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
    _check_dates(plan_in.start_date, plan_in.end_date)
    plan = crud.create_meal_plan(
        session=session, plan_in=plan_in, owner_id=current_user.id
    )
    return crud.meal_plan_to_public(plan, prices)


@router.put("/{id}", response_model=MealPlanPublic)
def update_meal_plan(
    *,
    session: SessionDep,
    plan: SharedMealPlan,
    prices: PriceBookDep,
    plan_in: MealPlanUpdate,
) -> Any:
    """Rename a meal plan or move its date range."""
    _check_dates(
        plan_in.start_date or plan.start_date, plan_in.end_date or plan.end_date
    )
    plan = crud.update_meal_plan(session=session, plan=plan, update_in=plan_in)
    return crud.meal_plan_to_public(plan, prices)


@router.delete("/{id}")
def delete_meal_plan(session: SessionDep, plan: SharedMealPlan) -> Message:
    """Delete a meal plan and its entries. Any generated list is kept."""
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
    plan: SharedMealPlan,
    prices: PriceBookDep,
    entry_in: MealPlanEntryCreate,
) -> Any:
    """Put a recipe in one of the plan's slots."""
    readable_recipe(session=session, user=current_user, recipe_id=entry_in.recipe_id)
    entry = crud.add_entry(session=session, plan=plan, entry_in=entry_in)
    return crud.meal_plan_entry_to_public(entry, prices)


@router.patch("/{id}/entries/{entry_id}", response_model=MealPlanEntryPublic)
def update_entry(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    plan: SharedMealPlan,
    prices: PriceBookDep,
    entry_id: uuid.UUID,
    update_in: MealPlanEntryUpdate,
) -> Any:
    """Move an entry to another slot, change its servings, or swap its recipe."""
    entry = _entry_of(session, plan, entry_id)
    if update_in.recipe_id is not None:
        readable_recipe(
            session=session, user=current_user, recipe_id=update_in.recipe_id
        )
    entry = crud.update_entry(session=session, entry=entry, update_in=update_in)
    return crud.meal_plan_entry_to_public(entry, prices)


@router.delete("/{id}/entries/{entry_id}")
def delete_entry(
    session: SessionDep, plan: SharedMealPlan, entry_id: uuid.UUID
) -> Message:
    """Remove one entry from the plan."""
    entry = _entry_of(session, plan, entry_id)
    crud.delete_entry(session=session, entry=entry)
    return Message(message="Entry deleted successfully")


# --------------------------------------------------------------------------- #
# Shopping list generation                                                     #
# --------------------------------------------------------------------------- #


@router.post("/{id}/shopping-list", response_model=ShoppingListPublic)
def generate_shopping_list(
    *,
    session: SessionDep,
    plan: SharedMealPlan,
    prices: PriceBookDep,
    name: str | None = None,
) -> Any:
    """Turn this plan into a shopping list.

    Every entry is added at its planned servings through the same merge rules
    used when adding a recipe by hand, so a recipe cooked twice in one week
    lands on a single row.
    """
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
    #: Per-weekday override of ``meal_types``, Monday first: seven lists, an
    #: empty one meaning no meal is planned that day.
    meals_by_weekday: list[list[MealType]] | None = Field(
        default=None, min_length=7, max_length=7
    )
    #: Batch cooking: how many meals one cooking covers (1 means none).
    batch_portions: int = Field(default=1, ge=1, le=3)
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


#: The parts of a generation request that describe *preferences*, saved on the
#: plan so that swapping one of its meals later still honours them.
_SAVED_SETTINGS = {
    "meal_types",
    "meals_by_weekday",
    "batch_portions",
    "servings",
    "budget",
    "require_vegan",
    "require_vegetarian",
    "require_gluten_free",
    "require_dairy_free",
    "max_prep_minutes",
    "match_season",
    "include_public",
}


class MenuSlot(BaseModel):
    entry_date: date
    meal_type: MealType
    #: Portions eaten at this meal; ``None`` means the menu's servings. A
    #: batch is cooked for the sum of its slots, so a leftover meal for one
    #: shrinks the batch rather than wasting food.
    servings: int | None = Field(default=None, ge=1, le=50)


class ProposedMealIn(BaseModel):
    """One cooking in a menu: the slot it is cooked in, then its leftovers."""

    recipe_id: uuid.UUID
    slots: list[MenuSlot] = Field(min_length=1)


class ProposedMeal(ProposedMealIn):
    recipe_title: str
    recipe_image_url: str | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    #: The menu's default servings per meal; each slot may override it.
    servings: int
    #: Portions the batch is cooked for: every slot's servings, added up.
    total_servings: int
    #: Cost of the whole batch, or ``None`` when unpriced.
    estimated_cost: Decimal | None = None


class MenuPreview(BaseModel):
    """A composed menu that has not been saved yet."""

    meals: list[ProposedMeal]
    servings: int
    budget: Decimal | None = None
    estimated_total: Decimal | None = None
    unpriced_meal_count: int = 0
    currency: str = "EUR"


class MenuPreviewRequest(GenerateMenuRequest):
    """Compose a menu, or rework one already proposed.

    Without ``meals`` a fresh menu is composed. With them, the meals are kept
    as given — which is how a recipe chosen by hand is priced — except those
    whose indices are in ``replace``, which get a new recipe picked under the
    same preferences.
    """

    meals: list[ProposedMealIn] | None = None
    replace: list[int] = Field(default_factory=list)


class SaveMenuRequest(GenerateMenuRequest):
    """Save a menu as a new plan: the reviewed ``meals``, or a fresh one."""

    meals: list[ProposedMealIn] | None = None


class MenuRecipeOptionsRequest(GenerateMenuRequest):
    """Which recipes may be chosen by hand for one slot of a menu."""

    meal_type: MealType = MealType.DINNER
    search: str | None = None


class MenuRecipeOption(BaseModel):
    id: uuid.UUID
    title: str
    image_url: str | None = None


def _candidate_recipes(
    *, session: SessionDep, current_user: User, include_public: bool
) -> list[Recipe]:
    """Everything this user may cook: their own recipes, plus public ones."""
    own, _ = crud.get_recipes(session=session, owner_id=current_user.id, limit=500)
    if not include_public:
        return own
    public, _ = crud.get_recipes(session=session, public_only=True, limit=500)
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
        meals_by_weekday=(
            tuple(tuple(day) for day in body.meals_by_weekday)
            if body.meals_by_weekday is not None
            else None
        ),
        batch_portions=body.batch_portions,
    )


def _user_request(
    body: GenerateMenuRequest, *, session: SessionDep, current_user: User
) -> GenerationRequest:
    """The request with servings and budget filled in from the user's settings.

    Household size and budget fall back to the user's settings when the request
    does not override them, so the common case is a single button with no form.
    """
    user_settings = crud.get_or_create_user_settings(
        session=session, user_id=current_user.id
    )
    servings = body.servings or user_settings.household_size
    budget = body.budget if body.budget is not None else user_settings.budget_amount
    request = _generation_request(body, servings=servings)
    return replace(request, budget=budget)


def _compose(
    request: GenerationRequest,
    candidates: list[Recipe],
    prices: PriceBookDep,
) -> list[tuple[Recipe, list[MenuSlot]]]:
    """A fresh menu, as recipes and the slots each one covers."""
    if request.slot_count == 0:
        raise HTTPException(status_code=422, detail="No meals selected for these days")
    if not candidates:
        raise HTTPException(
            status_code=422, detail="No recipes available to build a menu from"
        )
    meals = generate_menu(candidates, request, prices)
    if not meals:
        raise HTTPException(
            status_code=422,
            detail="No recipes match those constraints",
        )
    return [
        (
            meal.recipe,
            [
                MenuSlot(entry_date=day, meal_type=meal_type, servings=request.servings)
                for day, meal_type in [
                    (meal.entry_date, meal.meal_type),
                    *meal.leftovers,
                ]
            ],
        )
        for meal in meals
    ]


def _load_meals(
    meals_in: list[ProposedMealIn],
    body: GenerateMenuRequest,
    *,
    session: SessionDep,
    current_user: User,
    candidates: list[Recipe],
) -> list[tuple[Recipe, list[MenuSlot]]]:
    """Resolve a menu sent back by the client, checking every part of it.

    The client is trusted with nothing: each recipe must be one the user may
    read, and each slot must fall inside the plan and be used once per recipe.
    """
    by_id = {r.id: r for r in candidates}
    last_day = body.start_date + timedelta(days=body.days - 1)
    seen: set[tuple[date, MealType, uuid.UUID]] = set()
    loaded: list[tuple[Recipe, list[MenuSlot]]] = []
    for meal in meals_in:
        recipe = by_id.get(meal.recipe_id) or readable_recipe(
            session=session, user=current_user, recipe_id=meal.recipe_id
        )
        for slot in meal.slots:
            if not body.start_date <= slot.entry_date <= last_day:
                raise HTTPException(
                    status_code=422, detail="A meal falls outside the plan's dates"
                )
            key = (slot.entry_date, slot.meal_type, recipe.id)
            if key in seen:
                raise HTTPException(
                    status_code=422, detail="A recipe is planned twice in one slot"
                )
            seen.add(key)
        loaded.append((recipe, list(meal.slots)))
    return loaded


def _replace_meals(
    meals: list[tuple[Recipe, list[MenuSlot]]],
    indices: list[int],
    request: GenerationRequest,
    candidates: list[Recipe],
    prices: PriceBookDep,
) -> list[tuple[Recipe, list[MenuSlot]]]:
    """Give the meals at ``indices`` a new recipe, leftovers included.

    Each replacement sees the rest of the menu — including replacements made
    just before it — so swapping several meals at once does not hand back the
    same recipe for all of them.
    """
    if any(not 0 <= i < len(meals) for i in indices):
        raise HTTPException(status_code=422, detail="No such meal in the menu")
    result = list(meals)
    changed = False
    for index in dict.fromkeys(indices):
        recipe, slots = result[index]
        others = frozenset(r.id for j, (r, _) in enumerate(result) if j != index)
        replacement = pick_replacement(
            candidates,
            request,
            slots[0].entry_date,
            slots[0].meal_type,
            current_recipe_id=recipe.id,
            other_recipe_ids=others,
            prices=prices,
        )
        if replacement is not None:
            result[index] = (replacement, slots)
            changed = True
    if indices and not changed:
        raise HTTPException(
            status_code=422, detail="No alternative recipe matches those constraints"
        )
    return result


def _slot_servings(slot: MenuSlot, request: GenerationRequest) -> int:
    return slot.servings or request.servings


def _to_preview(
    meals: list[tuple[Recipe, list[MenuSlot]]],
    request: GenerationRequest,
    prices: PriceBookDep,
) -> MenuPreview:
    proposed = []
    for recipe, slots in meals:
        filled = [
            slot.model_copy(update={"servings": _slot_servings(slot, request)})
            for slot in slots
        ]
        total = sum(slot.servings or 0 for slot in filled)
        proposed.append(
            ProposedMeal(
                recipe_id=recipe.id,
                slots=filled,
                recipe_title=recipe.title,
                recipe_image_url=recipe.image_url,
                prep_time_minutes=recipe.prep_time_minutes,
                cook_time_minutes=recipe.cook_time_minutes,
                servings=request.servings,
                total_servings=total,
                estimated_cost=cost_of(recipe, prices, total),
            )
        )
    priced = [m.estimated_cost for m in proposed if m.estimated_cost is not None]
    return MenuPreview(
        meals=proposed,
        servings=request.servings,
        budget=request.budget,
        estimated_total=sum(priced, Decimal(0)) if priced else None,
        unpriced_meal_count=sum(1 for m in proposed if m.estimated_cost is None),
        currency=prices.currency,
    )


@router.post("/generate/preview", response_model=MenuPreview)
def preview_menu(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    body: MenuPreviewRequest,
) -> Any:
    """Compose a menu to review, without saving anything.

    Send the proposed ``meals`` back with ``replace`` to swap some of them, or
    with a recipe changed by hand to have it priced; save the result with
    ``POST /generate``.
    """
    request = _user_request(body, session=session, current_user=current_user)
    candidates = _candidate_recipes(
        session=session, current_user=current_user, include_public=body.include_public
    )
    if body.meals is None:
        meals = _compose(request, candidates, prices)
    else:
        meals = _load_meals(
            body.meals,
            body,
            session=session,
            current_user=current_user,
            candidates=candidates,
        )
        meals = _replace_meals(meals, body.replace, request, candidates, prices)
    return _to_preview(meals, request, prices)


@router.post("/generate/options", response_model=list[MenuRecipeOption])
def menu_recipe_options(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: MenuRecipeOptionsRequest,
) -> Any:
    """Recipes that may be picked by hand for one slot of a menu.

    Only recipes matching the menu's preferences are offered, so a hand-picked
    meal cannot break the diet the menu was generated for.
    """
    request = _generation_request(body, servings=body.servings or 1)
    candidates = _candidate_recipes(
        session=session, current_user=current_user, include_public=body.include_public
    )
    needle = (body.search or "").strip().lower()
    options = [
        r
        for r in candidates
        if is_eligible(r, request, body.meal_type)
        and (not needle or needle in r.title.lower())
    ]
    options.sort(key=lambda r: r.title.lower())
    return [
        MenuRecipeOption(id=r.id, title=r.title, image_url=r.image_url)
        for r in options[:50]
    ]


@router.post("/generate", response_model=MealPlanPublic)
def generate_menu_route(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    body: SaveMenuRequest,
) -> Any:
    """Save a menu as a new plan: the reviewed ``meals``, or a freshly composed one.

    With batch cooking, each meal's first slot is where it is cooked and the
    rest are saved as its leftovers. The preferences are saved on the plan so
    that later swaps keep honouring them.
    """
    request = _user_request(body, session=session, current_user=current_user)
    candidates = _candidate_recipes(
        session=session, current_user=current_user, include_public=body.include_public
    )
    if body.meals is None:
        meals = _compose(request, candidates, prices)
    else:
        if not body.meals:
            raise HTTPException(status_code=422, detail="The menu has no meals")
        meals = _load_meals(
            body.meals,
            body,
            session=session,
            current_user=current_user,
            candidates=candidates,
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
    plan.generation_settings = body.model_dump(mode="json", include=_SAVED_SETTINGS)

    for recipe, slots in meals:
        cooked = None
        for slot in slots:
            entry = crud.add_entry(
                session=session,
                plan=plan,
                entry_in=MealPlanEntryCreate(
                    recipe_id=recipe.id,
                    entry_date=slot.entry_date,
                    meal_type=slot.meal_type,
                    servings=_slot_servings(slot, request),
                ),
                batch_of=cooked,
            )
            cooked = cooked or entry
    session.refresh(plan)
    return crud.meal_plan_to_public(plan, prices)


@router.post("/{id}/entries/{entry_id}/swap", response_model=MealPlanEntryPublic)
def swap_entry(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    plan: SharedMealPlan,
    prices: PriceBookDep,
    entry_id: uuid.UUID,
    body: GenerateMenuRequest | None = None,
) -> Any:
    """Replace one meal without disturbing the rest of the plan.

    The replacement still respects the week's variety rules, so swapping out of
    a pasta night does not hand back another one. Without a body, the
    preferences the plan was generated with apply. A batch-cooked meal is
    swapped together with its leftovers, whichever of them was asked for.
    """
    entry = _entry_of(session, plan, entry_id)

    cooked = entry
    if entry.batch_of_id is not None:
        cooked = (
            crud.get_meal_plan_entry(session=session, entry_id=entry.batch_of_id)
            or entry
        )
    batch = {cooked.id} | {
        e.id for e in crud.get_batch_leftovers(session=session, entry=cooked)
    }

    if body is None:
        body = GenerateMenuRequest.model_validate(
            {**(plan.generation_settings or {}), "start_date": cooked.entry_date}
        )
    candidates = _candidate_recipes(
        session=session, current_user=current_user, include_public=body.include_public
    )
    request = _generation_request(body, servings=cooked.servings)
    others = frozenset(e.recipe_id for e in plan.entries if e.id not in batch)

    replacement = pick_replacement(
        candidates,
        request,
        cooked.entry_date,
        cooked.meal_type,
        current_recipe_id=cooked.recipe_id,
        other_recipe_ids=others,
        prices=prices,
    )
    if replacement is None:
        raise HTTPException(
            status_code=422, detail="No alternative recipe matches those constraints"
        )

    crud.update_entry(
        session=session,
        entry=cooked,
        update_in=MealPlanEntryUpdate(recipe_id=replacement.id),
    )
    session.refresh(entry)
    return crud.meal_plan_entry_to_public(entry, prices)
