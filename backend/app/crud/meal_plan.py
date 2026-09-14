import uuid

from sqlmodel import Session, col, func, select

from app.models.meal_plan import (
    MealPlan,
    MealPlanCreate,
    MealPlanEntry,
    MealPlanEntryCreate,
    MealPlanEntryPublic,
    MealPlanEntryUpdate,
    MealPlanPublic,
    MealPlanUpdate,
)
from app.models.recipe import Recipe
from app.models.shopping_list import ShoppingList, ShoppingListCreate
from app.services.pricing import PriceBook


def _entry_scale(entry: MealPlanEntry) -> float:
    """How far this entry's servings stretch the recipe's own quantities."""
    return entry.servings / (entry.recipe.servings or 1)


def meal_plan_entry_to_public(
    entry: MealPlanEntry, prices: PriceBook | None = None
) -> MealPlanEntryPublic:
    scale = _entry_scale(entry)
    cost = (
        prices.summarize(
            [
                (ri.ingredient_name, ri.quantity * scale, ri.unit)
                for ri in entry.recipe.recipe_ingredients
            ]
        )
        if prices is not None
        else None
    )
    return MealPlanEntryPublic(
        id=entry.id,
        meal_plan_id=entry.meal_plan_id,
        recipe_id=entry.recipe_id,
        recipe_title=entry.recipe.title,
        recipe_image_url=entry.recipe.image_url,
        recipe_servings=entry.recipe.servings,
        prep_time_minutes=entry.recipe.prep_time_minutes,
        cook_time_minutes=entry.recipe.cook_time_minutes,
        entry_date=entry.entry_date,
        meal_type=entry.meal_type,
        servings=entry.servings,
        estimated_cost=cost.total if cost else None,
        estimated_cost_per_serving=cost.per_unit(entry.servings) if cost else None,
    )


def meal_plan_to_public(
    plan: MealPlan, prices: PriceBook | None = None
) -> MealPlanPublic:
    entries = sorted(
        plan.entries, key=lambda e: (e.entry_date, e.meal_type.value, e.recipe_id.hex)
    )
    public_entries = [meal_plan_entry_to_public(e, prices) for e in entries]

    total = None
    unpriced = 0
    if prices is not None:
        priced = [e.estimated_cost for e in public_entries if e.estimated_cost]
        unpriced = sum(1 for e in public_entries if e.estimated_cost is None)
        total = sum(priced) if priced else None

    return MealPlanPublic(
        id=plan.id,
        name=plan.name,
        start_date=plan.start_date,
        end_date=plan.end_date,
        owner_id=plan.owner_id,
        created_at=plan.created_at,
        shopping_list_id=plan.shopping_list_id,
        entries=public_entries,
        estimated_total=total,
        unpriced_entry_count=unpriced,
        currency=prices.currency if prices is not None else "EUR",
    )


# --------------------------------------------------------------------------- #
# Meal plans                                                                   #
# --------------------------------------------------------------------------- #


def get_meal_plan(*, session: Session, plan_id: uuid.UUID) -> MealPlan | None:
    return session.get(MealPlan, plan_id)


def get_meal_plans(
    *,
    session: Session,
    owner_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[MealPlan], int]:
    query = select(MealPlan)
    count_query = select(func.count()).select_from(MealPlan)
    if owner_id is not None:
        query = query.where(MealPlan.owner_id == owner_id)
        count_query = count_query.where(MealPlan.owner_id == owner_id)

    count = session.exec(count_query).one()
    plans = session.exec(
        query.order_by(col(MealPlan.start_date).desc()).offset(skip).limit(limit)
    ).all()
    return list(plans), count


def create_meal_plan(
    *, session: Session, plan_in: MealPlanCreate, owner_id: uuid.UUID
) -> MealPlan:
    plan = MealPlan(**plan_in.model_dump(), owner_id=owner_id)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def update_meal_plan(
    *, session: Session, plan: MealPlan, update_in: MealPlanUpdate
) -> MealPlan:
    plan.sqlmodel_update(update_in.model_dump(exclude_unset=True))
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def delete_meal_plan(*, session: Session, plan: MealPlan) -> None:
    session.delete(plan)
    session.commit()


# --------------------------------------------------------------------------- #
# Entries                                                                      #
# --------------------------------------------------------------------------- #


def get_meal_plan_entry(
    *, session: Session, entry_id: uuid.UUID
) -> MealPlanEntry | None:
    return session.get(MealPlanEntry, entry_id)


def add_entry(
    *, session: Session, plan: MealPlan, entry_in: MealPlanEntryCreate
) -> MealPlanEntry:
    entry = MealPlanEntry(**entry_in.model_dump(), meal_plan_id=plan.id)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def update_entry(
    *, session: Session, entry: MealPlanEntry, update_in: MealPlanEntryUpdate
) -> MealPlanEntry:
    entry.sqlmodel_update(update_in.model_dump(exclude_unset=True))
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def delete_entry(*, session: Session, entry: MealPlanEntry) -> None:
    session.delete(entry)
    session.commit()


# --------------------------------------------------------------------------- #
# Turning a plan into a shopping list                                          #
# --------------------------------------------------------------------------- #


def generate_shopping_list(
    *, session: Session, plan: MealPlan, name: str | None = None
) -> ShoppingList:
    """Build a shopping list covering everything this plan calls for.

    Each entry is added at its own planned servings, reusing
    ``add_recipe_to_shopping_list`` so the unit-aware merge rules are identical
    to adding those recipes by hand. The same recipe appearing twice in a week
    therefore accumulates on one row rather than producing two.

    The list is linked back onto the plan so the UI can offer to open it
    instead of generating another.
    """
    # Imported here: shopping_list's CRUD imports recipe's, and importing it at
    # module scope would close the loop through this module's own helpers.
    from app.crud.shopping_list import add_recipe_to_shopping_list, create_shopping_list

    shopping_list = create_shopping_list(
        session=session,
        list_in=ShoppingListCreate(
            name=name or plan.name,
            start_date=plan.start_date,
            end_date=plan.end_date,
        ),
        owner_id=plan.owner_id,
    )

    for entry in plan.entries:
        recipe: Recipe = entry.recipe
        shopping_list = add_recipe_to_shopping_list(
            session=session,
            shopping_list=shopping_list,
            recipe=recipe,
            servings=entry.servings,
        )

    plan.shopping_list_id = shopping_list.id
    session.add(plan)
    session.commit()
    session.refresh(shopping_list)
    return shopping_list
