import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, col, select

from app.crud.query import owner_filter, paginate
from app.crud.recipe import recipe_cost, servings_scale
from app.crud.shopping_list import add_recipe_to_shopping_list, create_shopping_list
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
from app.models.shopping_list import ShoppingList, ShoppingListCreate
from app.services.pricing import PriceBook


def meal_plan_entry_to_public(
    entry: MealPlanEntry, prices: PriceBook | None = None
) -> MealPlanEntryPublic:
    scale = servings_scale(entry.recipe, entry.servings)
    cost = (
        recipe_cost(entry.recipe, prices, scale=scale) if prices is not None else None
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
        batch_of_id=entry.batch_of_id,
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
        total = sum(priced, Decimal(0)) if priced else None

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
    owner_ids: set[uuid.UUID] | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[MealPlan], int]:
    """Latest plans first, owned by any of ``owner_ids`` (``None``: everyone's).

    Passing every household member's id is how a household sees its shared
    plans; see ``crud.visible_owner_ids``.
    """
    return paginate(
        session,
        MealPlan,
        where=owner_filter(MealPlan.owner_id, owner_ids),
        order_by=col(MealPlan.start_date).desc(),
        skip=skip,
        limit=limit,
    )


def recent_recipe_ids(
    *,
    session: Session,
    owner_ids: set[uuid.UUID],
    before: date,
    days: int = 21,
) -> frozenset[uuid.UUID]:
    """Recipes planned in the ``days`` before ``before`` by any of ``owner_ids``.

    What a household has just eaten, so a new menu can avoid serving it again.
    """
    statement = (
        select(MealPlanEntry.recipe_id)
        .join(MealPlan, col(MealPlan.id) == col(MealPlanEntry.meal_plan_id))
        .where(
            col(MealPlanEntry.entry_date) >= before - timedelta(days=days),
            col(MealPlanEntry.entry_date) < before,
            col(MealPlan.owner_id).in_(owner_ids),
        )
        .distinct()
    )
    return frozenset(session.exec(statement).all())


def create_meal_plan(
    *, session: Session, plan_in: MealPlanCreate, owner_id: uuid.UUID
) -> MealPlan:
    plan = MealPlan(**plan_in.model_dump(), owner_id=owner_id)
    session.add(plan)
    session.flush()
    session.refresh(plan)
    return plan


def update_meal_plan(
    *, session: Session, plan: MealPlan, update_in: MealPlanUpdate
) -> MealPlan:
    plan.sqlmodel_update(update_in.model_dump(exclude_unset=True))
    session.add(plan)
    session.flush()
    session.refresh(plan)
    return plan


def delete_meal_plan(*, session: Session, plan: MealPlan) -> None:
    session.delete(plan)
    session.flush()


# --------------------------------------------------------------------------- #
# Entries                                                                      #
# --------------------------------------------------------------------------- #


def get_meal_plan_entry(
    *, session: Session, entry_id: uuid.UUID
) -> MealPlanEntry | None:
    return session.get(MealPlanEntry, entry_id)


def add_entry(
    *,
    session: Session,
    plan: MealPlan,
    entry_in: MealPlanEntryCreate,
    batch_of: MealPlanEntry | None = None,
) -> MealPlanEntry:
    """Add one meal; ``batch_of`` makes it leftovers of that cooked entry."""
    entry = MealPlanEntry(
        **entry_in.model_dump(),
        meal_plan_id=plan.id,
        batch_of_id=batch_of.id if batch_of is not None else None,
    )
    session.add(entry)
    session.flush()
    session.refresh(entry)
    return entry


def get_batch_leftovers(
    *, session: Session, entry: MealPlanEntry
) -> list[MealPlanEntry]:
    """The meals eaten from the batch cooked at ``entry``."""
    return list(
        session.exec(
            select(MealPlanEntry).where(MealPlanEntry.batch_of_id == entry.id)
        ).all()
    )


def update_entry(
    *, session: Session, entry: MealPlanEntry, update_in: MealPlanEntryUpdate
) -> MealPlanEntry:
    """Change one meal, keeping batch cooking consistent.

    Changing the recipe of a cooked batch changes its leftovers with it — they
    are the same dish. Changing the recipe of a leftover means it is no longer
    leftovers, so it leaves the batch.
    """
    changes = update_in.model_dump(exclude_unset=True)
    new_recipe = changes.get("recipe_id")
    if new_recipe is not None and new_recipe != entry.recipe_id:
        if entry.batch_of_id is not None:
            entry.batch_of_id = None
        else:
            for leftover in get_batch_leftovers(session=session, entry=entry):
                leftover.recipe_id = new_recipe
                session.add(leftover)
    entry.sqlmodel_update(changes)
    session.add(entry)
    session.flush()
    session.refresh(entry)
    return entry


def delete_entry(*, session: Session, entry: MealPlanEntry) -> None:
    session.delete(entry)
    session.flush()


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
        shopping_list = add_recipe_to_shopping_list(
            session=session,
            shopping_list=shopping_list,
            recipe=entry.recipe,
            servings=entry.servings,
        )

    plan.shopping_list_id = shopping_list.id
    session.add(plan)
    session.flush()
    session.refresh(shopping_list)
    return shopping_list
