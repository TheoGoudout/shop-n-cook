import uuid
from decimal import Decimal

from sqlmodel import Session, col

from app.core.naming import normalize_ingredient_name
from app.core.units import convert, merge_key
from app.crud.query import owner_filter, paginate
from app.crud.recipe import recipe_cost, recipe_ingredient_to_public, servings_scale
from app.models import (
    PantryCheck,
    Recipe,
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
    ShoppingListUpdate,
    Unit,
)
from app.models.base import get_datetime_utc
from app.services.pricing import PriceBook, quantize_money

#: Quantities are rounded here so that repeatedly adding and removing a recipe
#: cannot accumulate binary-float dust into a visible "0.30000000000000004 kg".
_QUANTITY_PRECISION = 6

#: Below this a quantity is treated as gone rather than as a sliver of a gram.
_QUANTITY_EPSILON = 1e-9


def quantity_to_buy(item: ShoppingListItem) -> float:
    """What is still to be bought once what is at home is taken off."""
    return max(round(item.quantity - item.quantity_at_home, _QUANTITY_PRECISION), 0.0)


def items_to_buy(shopping_list: ShoppingList) -> list[tuple[ShoppingListItem, float]]:
    """Every item that still needs buying, with how much.

    An item fully covered by what is at home is left out entirely rather than
    carried as a zero line, so it neither costs nothing nor counts as unpriced.
    """
    return [
        (item, qty)
        for item in shopping_list.items
        if (qty := quantity_to_buy(item)) > _QUANTITY_EPSILON
    ]


def planned_recipe_to_public(
    slr: ShoppingListRecipe, prices: PriceBook | None = None
) -> ShoppingListRecipePublic:
    scale = servings_scale(slr.recipe, slr.servings_planned)
    cost = recipe_cost(slr.recipe, prices, scale=scale) if prices is not None else None
    return ShoppingListRecipePublic(
        id=slr.id,
        recipe_id=slr.recipe_id,
        recipe_title=slr.recipe.title,
        recipe_servings=slr.recipe.servings,
        servings_planned=slr.servings_planned,
        is_prepared=slr.is_prepared,
        ingredients=[
            recipe_ingredient_to_public(ri, prices, scale=scale)
            for ri in slr.recipe.recipe_ingredients
        ],
        estimated_cost=cost.total if cost else None,
    )


def shopping_list_item_to_public(
    item: ShoppingListItem, prices: PriceBook | None = None
) -> ShoppingListItemPublic:
    to_buy = quantity_to_buy(item)
    cost = None
    if prices is not None:
        cost = prices.cost(item.name, to_buy, item.unit) if to_buy > 0 else Decimal(0)
    return ShoppingListItemPublic(
        id=item.id,
        name=item.name,
        quantity=item.quantity,
        unit=item.unit,
        is_checked=item.is_checked,
        notes=item.notes,
        quantity_at_home=item.quantity_at_home,
        quantity_to_buy=to_buy,
        estimated_cost=quantize_money(cost) if cost is not None else None,
    )


def shopping_list_to_public(
    shopping_list: ShoppingList, prices: PriceBook | None = None
) -> ShoppingListPublic:
    cost = (
        prices.summarize(
            [(i.name, qty, i.unit) for i, qty in items_to_buy(shopping_list)]
        )
        if prices is not None
        else None
    )
    return ShoppingListPublic(
        id=shopping_list.id,
        name=shopping_list.name,
        start_date=shopping_list.start_date,
        end_date=shopping_list.end_date,
        owner_id=shopping_list.owner_id,
        created_at=shopping_list.created_at,
        pantry_checked_at=shopping_list.pantry_checked_at,
        items=[shopping_list_item_to_public(i, prices) for i in shopping_list.items],
        planned_recipes=[
            planned_recipe_to_public(r, prices) for r in shopping_list.planned_recipes
        ],
        estimated_total=cost.total if cost else None,
        unpriced_item_count=cost.unpriced_count if cost else 0,
        currency=prices.currency if prices is not None else "EUR",
    )


def get_shopping_list(
    *, session: Session, shopping_list_id: uuid.UUID
) -> ShoppingList | None:
    return session.get(ShoppingList, shopping_list_id)


def get_shopping_lists(
    *,
    session: Session,
    owner_ids: set[uuid.UUID] | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[ShoppingList], int]:
    """Newest lists first, owned by any of ``owner_ids`` (``None``: everyone's).

    Passing every household member's id is how a household sees its shared
    lists; see ``crud.visible_owner_ids``.
    """
    return paginate(
        session,
        ShoppingList,
        where=owner_filter(ShoppingList.owner_id, owner_ids),
        order_by=col(ShoppingList.created_at).desc(),
        skip=skip,
        limit=limit,
    )


def create_shopping_list(
    *, session: Session, list_in: ShoppingListCreate, owner_id: uuid.UUID
) -> ShoppingList:
    db_list = ShoppingList(**list_in.model_dump(), owner_id=owner_id)
    session.add(db_list)
    session.flush()
    session.refresh(db_list)
    return db_list


def update_shopping_list(
    *,
    session: Session,
    db_list: ShoppingList,
    list_in: ShoppingListUpdate,
) -> ShoppingList:
    update_data = list_in.model_dump(exclude_unset=True)
    db_list.sqlmodel_update(update_data)
    session.add(db_list)
    session.flush()
    session.refresh(db_list)
    return db_list


def delete_shopping_list(*, session: Session, shopping_list: ShoppingList) -> None:
    session.delete(shopping_list)
    session.flush()


def add_item_to_shopping_list(
    *,
    session: Session,
    shopping_list: ShoppingList,
    item_in: ShoppingListItemCreate,
) -> ShoppingList:
    """Add an item by hand, merging it into a matching row if one exists.

    Typing "200 g flour" onto a list that already calls for flour should give
    one row, exactly as adding a recipe would.
    """
    existing = _index_items(shopping_list).get(_item_key(item_in.name, item_in.unit))
    if existing is not None:
        converted = convert(item_in.quantity, item_in.unit, existing.unit)
        if converted is not None:
            existing.quantity = round(
                existing.quantity + converted, _QUANTITY_PRECISION
            )
            if item_in.notes and not existing.notes:
                existing.notes = item_in.notes
            session.add(existing)
            session.flush()
            session.refresh(shopping_list)
            return shopping_list

    item = ShoppingListItem(
        shopping_list_id=shopping_list.id,
        name=item_in.name,
        quantity=item_in.quantity,
        unit=item_in.unit,
        is_checked=item_in.is_checked,
        notes=item_in.notes,
    )
    session.add(item)
    session.flush()
    session.refresh(shopping_list)
    return shopping_list


def update_shopping_list_item(
    *,
    session: Session,
    item: ShoppingListItem,
    item_in: ShoppingListItemUpdate,
) -> ShoppingListItem:
    update_data = item_in.model_dump(exclude_unset=True)
    new_unit = update_data.get("unit")
    if (
        new_unit is not None
        and new_unit != item.unit
        and "quantity_at_home" not in update_data
    ):
        # What is at home is recorded in the item's unit, so it follows a unit
        # change. Where no conversion exists it is forgotten, not guessed.
        converted = convert(item.quantity_at_home, item.unit, new_unit)
        update_data["quantity_at_home"] = (
            round(converted, _QUANTITY_PRECISION) if converted is not None else 0.0
        )
    item.sqlmodel_update(update_data)
    session.add(item)
    session.flush()
    session.refresh(item)
    return item


def apply_pantry_check(
    *, session: Session, shopping_list: ShoppingList, check: PantryCheck
) -> ShoppingList:
    """Record what is already at home, and that the list has been checked.

    Every ``check.items`` id must belong to ``shopping_list``; the route checks
    that before calling, so a stale id leaves the list untouched.
    """
    by_id = {item.id: item for item in shopping_list.items}
    for entry in check.items:
        item = by_id[entry.item_id]
        item.quantity_at_home = round(entry.quantity_at_home, _QUANTITY_PRECISION)
        session.add(item)
    shopping_list.pantry_checked_at = get_datetime_utc()
    session.add(shopping_list)
    session.flush()
    session.refresh(shopping_list)
    return shopping_list


def get_shopping_list_item(
    *, session: Session, item_id: uuid.UUID
) -> ShoppingListItem | None:
    return session.get(ShoppingListItem, item_id)


def delete_shopping_list_item(*, session: Session, item: ShoppingListItem) -> None:
    session.delete(item)
    session.flush()


def get_shopping_list_recipe(
    *, session: Session, sl_recipe_id: uuid.UUID
) -> ShoppingListRecipe | None:
    return session.get(ShoppingListRecipe, sl_recipe_id)


def _item_key(name: str, unit: Unit) -> tuple[str, str]:
    """Identity of a shopping-list row.

    Two entries merge when they name the same thing and their units can be
    summed: every mass unit shares a key and every volume unit another, so
    ``300 g flour`` and ``2 cup flour`` land on one row, while ``2 cloves`` and
    ``2 slices`` stay apart.
    """
    return normalize_ingredient_name(name), merge_key(unit)


def _index_items(
    shopping_list: ShoppingList,
) -> dict[tuple[str, str], ShoppingListItem]:
    index: dict[tuple[str, str], ShoppingListItem] = {}
    for item in shopping_list.items:
        index.setdefault(_item_key(item.name, item.unit), item)
    return index


def _apply_recipe_delta(
    *,
    session: Session,
    shopping_list: ShoppingList,
    recipe: Recipe,
    old_scale: float,
    new_scale: float,
) -> None:
    """Move the list's items by one recipe's change in planned quantity.

    A single path serves adding a recipe (``old_scale`` 0), rescaling it and
    removing it (``new_scale`` 0), so the merge rules cannot drift apart
    between those cases. Quantities are converted into the unit of whichever
    row already exists, so that row's unit is stable no matter what units later
    recipes use.
    """
    existing = _index_items(shopping_list)

    for ri in recipe.recipe_ingredients:
        key = _item_key(ri.ingredient_name, ri.unit)
        delta = ri.quantity * (new_scale - old_scale)
        if abs(delta) < _QUANTITY_EPSILON:
            continue

        item = existing.get(key)
        if item is not None:
            # Same merge key guarantees this conversion is defined.
            converted = convert(delta, ri.unit, item.unit)
            if converted is None:  # pragma: no cover - defensive
                continue
            item.quantity = round(item.quantity + converted, _QUANTITY_PRECISION)
            if item.quantity <= _QUANTITY_EPSILON:
                session.delete(item)
                del existing[key]
            else:
                session.add(item)
        elif delta > 0:
            new_item = ShoppingListItem(
                shopping_list_id=shopping_list.id,
                name=ri.ingredient_name,
                quantity=round(delta, _QUANTITY_PRECISION),
                unit=ri.unit,
            )
            session.add(new_item)
            existing[key] = new_item


def _adjust_items_for_recipe(
    *,
    session: Session,
    shopping_list: ShoppingList,
    sl_recipe: ShoppingListRecipe,
    new_servings: int,
) -> None:
    """Move the list's items as a planned recipe goes to ``new_servings``."""
    recipe = sl_recipe.recipe
    _apply_recipe_delta(
        session=session,
        shopping_list=shopping_list,
        recipe=recipe,
        old_scale=servings_scale(recipe, sl_recipe.servings_planned),
        new_scale=servings_scale(recipe, new_servings),
    )


def update_shopping_list_recipe(
    *,
    session: Session,
    shopping_list: ShoppingList,
    sl_recipe: ShoppingListRecipe,
    update_in: ShoppingListRecipeUpdate,
) -> ShoppingListRecipe:
    if (
        update_in.servings_planned is not None
        and update_in.servings_planned != sl_recipe.servings_planned
    ):
        _adjust_items_for_recipe(
            session=session,
            shopping_list=shopping_list,
            sl_recipe=sl_recipe,
            new_servings=update_in.servings_planned,
        )
    update_data = update_in.model_dump(exclude_unset=True)
    sl_recipe.sqlmodel_update(update_data)
    session.add(sl_recipe)
    session.flush()
    session.refresh(sl_recipe)
    return sl_recipe


def delete_shopping_list_recipe(
    *, session: Session, shopping_list: ShoppingList, sl_recipe: ShoppingListRecipe
) -> None:
    _adjust_items_for_recipe(
        session=session,
        shopping_list=shopping_list,
        sl_recipe=sl_recipe,
        new_servings=0,
    )
    session.delete(sl_recipe)
    session.flush()


def add_recipe_to_shopping_list(
    *,
    session: Session,
    shopping_list: ShoppingList,
    recipe: Recipe,
    servings: int | None = None,
) -> ShoppingList:
    """Add all recipe ingredients to the shopping list (scaled by servings).

    A ShoppingListRecipe tracking record is always created. Ingredients that
    name the same thing in compatible units are aggregated onto one row — see
    :func:`_item_key`.
    """
    target_servings = servings or recipe.servings or 1

    sl_recipe = ShoppingListRecipe(
        shopping_list_id=shopping_list.id,
        recipe_id=recipe.id,
        servings_planned=target_servings,
    )
    session.add(sl_recipe)
    session.flush()

    _apply_recipe_delta(
        session=session,
        shopping_list=shopping_list,
        recipe=recipe,
        old_scale=0.0,
        new_scale=servings_scale(recipe, target_servings),
    )

    session.flush()
    session.refresh(shopping_list)
    return shopping_list
