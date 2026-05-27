import uuid

from sqlmodel import Session, col, func, select

from app.crud.recipe import recipe_ingredient_to_public
from app.models import (
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
)


def _sl_recipe_to_public(slr: ShoppingListRecipe) -> ShoppingListRecipePublic:
    return ShoppingListRecipePublic(
        id=slr.id,
        recipe_id=slr.recipe_id,
        recipe_title=slr.recipe.title,
        recipe_servings=slr.recipe.servings,
        servings_planned=slr.servings_planned,
        is_prepared=slr.is_prepared,
        ingredients=[
            recipe_ingredient_to_public(ri) for ri in slr.recipe.recipe_ingredients
        ],
    )


def _item_to_public(item: ShoppingListItem) -> ShoppingListItemPublic:
    return ShoppingListItemPublic(
        id=item.id,
        name=item.name,
        quantity=item.quantity,
        unit=item.unit,
        is_checked=item.is_checked,
        notes=item.notes,
    )


def shopping_list_to_public(shopping_list: ShoppingList) -> ShoppingListPublic:
    return ShoppingListPublic(
        id=shopping_list.id,
        name=shopping_list.name,
        start_date=shopping_list.start_date,
        end_date=shopping_list.end_date,
        owner_id=shopping_list.owner_id,
        created_at=shopping_list.created_at,
        items=[_item_to_public(i) for i in shopping_list.items],
        planned_recipes=[
            _sl_recipe_to_public(r) for r in shopping_list.planned_recipes
        ],
    )


def get_shopping_list(
    *, session: Session, shopping_list_id: uuid.UUID
) -> ShoppingList | None:
    return session.get(ShoppingList, shopping_list_id)


def get_shopping_lists(
    *,
    session: Session,
    owner_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[ShoppingList], int]:
    query = select(ShoppingList)
    count_query = select(func.count()).select_from(ShoppingList)

    if owner_id is not None:
        query = query.where(ShoppingList.owner_id == owner_id)
        count_query = count_query.where(ShoppingList.owner_id == owner_id)

    count = session.exec(count_query).one()
    lists = session.exec(
        query.order_by(col(ShoppingList.created_at).desc()).offset(skip).limit(limit)
    ).all()
    return list(lists), count


def create_shopping_list(
    *, session: Session, list_in: ShoppingListCreate, owner_id: uuid.UUID
) -> ShoppingList:
    db_list = ShoppingList(**list_in.model_dump(), owner_id=owner_id)
    session.add(db_list)
    session.commit()
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
    session.commit()
    session.refresh(db_list)
    return db_list


def delete_shopping_list(*, session: Session, shopping_list: ShoppingList) -> None:
    session.delete(shopping_list)
    session.commit()


def add_item_to_shopping_list(
    *,
    session: Session,
    shopping_list: ShoppingList,
    item_in: ShoppingListItemCreate,
) -> ShoppingList:
    item = ShoppingListItem(
        shopping_list_id=shopping_list.id,
        name=item_in.name,
        quantity=item_in.quantity,
        unit=item_in.unit,
        is_checked=item_in.is_checked,
        notes=item_in.notes,
    )
    session.add(item)
    session.commit()
    session.refresh(shopping_list)
    return shopping_list


def update_shopping_list_item(
    *,
    session: Session,
    item: ShoppingListItem,
    item_in: ShoppingListItemUpdate,
) -> ShoppingListItem:
    update_data = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_data)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def get_shopping_list_item(
    *, session: Session, item_id: uuid.UUID
) -> ShoppingListItem | None:
    return session.get(ShoppingListItem, item_id)


def delete_shopping_list_item(*, session: Session, item: ShoppingListItem) -> None:
    session.delete(item)
    session.commit()


def get_shopping_list_recipe(
    *, session: Session, sl_recipe_id: uuid.UUID
) -> ShoppingListRecipe | None:
    return session.get(ShoppingListRecipe, sl_recipe_id)


def _adjust_items_for_recipe(
    *,
    session: Session,
    shopping_list: ShoppingList,
    sl_recipe: ShoppingListRecipe,
    old_servings: int,
    new_servings: int,
) -> None:
    """Adjust shopping list items when a recipe's planned servings change.

    Subtracts the old contribution and adds the new one for each ingredient.
    Items that drop to zero or below are deleted.
    """
    recipe = sl_recipe.recipe
    original_servings = recipe.servings or 1
    old_scale = old_servings / original_servings
    new_scale = new_servings / original_servings

    existing: dict[tuple[str, str], ShoppingListItem] = {
        (item.name.lower(), item.unit): item for item in shopping_list.items
    }

    for ri in recipe.recipe_ingredients:
        key = (ri.ingredient_name.lower(), ri.unit)
        delta = ri.quantity * (new_scale - old_scale)
        if abs(delta) < 1e-9:
            continue
        if key in existing:
            item = existing[key]
            item.quantity += delta
            if item.quantity <= 1e-9:
                session.delete(item)
                del existing[key]
            else:
                session.add(item)
        elif delta > 0:
            new_item = ShoppingListItem(
                shopping_list_id=shopping_list.id,
                name=ri.ingredient_name,
                quantity=delta,
                unit=ri.unit,
            )
            session.add(new_item)
            existing[key] = new_item


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
            old_servings=sl_recipe.servings_planned,
            new_servings=update_in.servings_planned,
        )
    update_data = update_in.model_dump(exclude_unset=True)
    sl_recipe.sqlmodel_update(update_data)
    session.add(sl_recipe)
    session.commit()
    session.refresh(sl_recipe)
    return sl_recipe


def delete_shopping_list_recipe(
    *, session: Session, shopping_list: ShoppingList, sl_recipe: ShoppingListRecipe
) -> None:
    _adjust_items_for_recipe(
        session=session,
        shopping_list=shopping_list,
        sl_recipe=sl_recipe,
        old_servings=sl_recipe.servings_planned,
        new_servings=0,
    )
    session.delete(sl_recipe)
    session.commit()


def add_recipe_to_shopping_list(
    *,
    session: Session,
    shopping_list: ShoppingList,
    recipe: Recipe,
    servings: int | None = None,
) -> ShoppingList:
    """Add all recipe ingredients to the shopping list (scaled by servings).

    A ShoppingListRecipe tracking record is always created.
    Items with the same name + unit are aggregated (quantities summed).
    """
    target_servings = servings or recipe.servings or 1
    original_servings = recipe.servings or 1
    scale = target_servings / original_servings

    sl_recipe = ShoppingListRecipe(
        shopping_list_id=shopping_list.id,
        recipe_id=recipe.id,
        servings_planned=target_servings,
    )
    session.add(sl_recipe)
    session.flush()

    existing: dict[tuple[str, str], ShoppingListItem] = {
        (item.name.lower(), item.unit): item for item in shopping_list.items
    }

    for ri in recipe.recipe_ingredients:
        scaled_qty = ri.quantity * scale
        key = (ri.ingredient_name.lower(), ri.unit)
        if key in existing:
            existing[key].quantity += scaled_qty
            session.add(existing[key])
        else:
            new_item = ShoppingListItem(
                shopping_list_id=shopping_list.id,
                name=ri.ingredient_name,
                quantity=scaled_qty,
                unit=ri.unit,
            )
            session.add(new_item)
            existing[key] = new_item

    session.commit()
    session.refresh(shopping_list)
    return shopping_list
