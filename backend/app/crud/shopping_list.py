import uuid

from sqlmodel import Session, col, func, select

from app.models import (
    Recipe,
    RecipeIngredientPublic,
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
from app.models.recipe import RecipeIngredient


def _ri_to_public(ri: RecipeIngredient) -> RecipeIngredientPublic:
    return RecipeIngredientPublic(
        id=ri.id,
        ingredient_id=ri.ingredient_id,
        ingredient_name=ri.ingredient.name,
        ingredient_category=ri.ingredient.category,
        quantity=ri.quantity,
        unit=ri.unit,
        notes=ri.notes,
    )


def _sl_recipe_to_public(slr: ShoppingListRecipe) -> ShoppingListRecipePublic:
    return ShoppingListRecipePublic(
        id=slr.id,
        recipe_id=slr.recipe_id,
        recipe_title=slr.recipe.title,
        recipe_servings=slr.recipe.servings,
        servings_planned=slr.servings_planned,
        is_prepared=slr.is_prepared,
        ingredients=[_ri_to_public(ri) for ri in slr.recipe.recipe_ingredients],
    )


def _item_to_public(item: ShoppingListItem) -> ShoppingListItemPublic:
    return ShoppingListItemPublic(
        id=item.id,
        ingredient_id=item.ingredient_id,
        ingredient_name=item.ingredient.name,
        ingredient_category=item.ingredient.category,
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
        ingredient_id=item_in.ingredient_id,
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


def update_shopping_list_recipe(
    *,
    session: Session,
    sl_recipe: ShoppingListRecipe,
    update_in: ShoppingListRecipeUpdate,
) -> ShoppingListRecipe:
    update_data = update_in.model_dump(exclude_unset=True)
    sl_recipe.sqlmodel_update(update_data)
    session.add(sl_recipe)
    session.commit()
    session.refresh(sl_recipe)
    return sl_recipe


def delete_shopping_list_recipe(
    *, session: Session, sl_recipe: ShoppingListRecipe
) -> None:
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
    Items with the same ingredient + unit are aggregated (quantities summed).
    """
    target_servings = servings or recipe.servings or 1
    original_servings = recipe.servings or 1
    scale = target_servings / original_servings

    # Track this recipe in the list
    sl_recipe = ShoppingListRecipe(
        shopping_list_id=shopping_list.id,
        recipe_id=recipe.id,
        servings_planned=target_servings,
    )
    session.add(sl_recipe)
    session.flush()  # get sl_recipe.id

    existing: dict[tuple[uuid.UUID, str], ShoppingListItem] = {
        (item.ingredient_id, item.unit): item for item in shopping_list.items
    }

    for ri in recipe.recipe_ingredients:
        scaled_qty = ri.quantity * scale
        key = (ri.ingredient_id, ri.unit)
        if key in existing:
            existing[key].quantity += scaled_qty
            session.add(existing[key])
        else:
            new_item = ShoppingListItem(
                shopping_list_id=shopping_list.id,
                ingredient_id=ri.ingredient_id,
                quantity=scaled_qty,
                unit=ri.unit,
            )
            session.add(new_item)
            existing[key] = new_item

    session.commit()
    session.refresh(shopping_list)
    return shopping_list
