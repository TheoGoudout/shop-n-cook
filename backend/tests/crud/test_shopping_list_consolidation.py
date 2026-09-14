"""How ingredients from several recipes land on one shopping-list row.

Before unit-aware merging, ``300 g flour`` and ``2 cup flour`` produced two
rows, as did ``tomato`` and ``tomatoes``. These tests pin the merge rules and,
just as importantly, the cases that must *not* merge.
"""

import uuid

from sqlmodel import Session

from app import crud
from app.models import (
    Recipe,
    RecipeCreate,
    RecipeIngredientCreate,
    ShoppingList,
    ShoppingListCreate,
    ShoppingListItemCreate,
    Unit,
)
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def _recipe(
    db: Session,
    owner_id: uuid.UUID,
    ingredients: list[tuple[str, float, Unit]],
    *,
    servings: int = 2,
) -> Recipe:
    recipe_in = RecipeCreate(
        title=random_lower_string(),
        servings=servings,
        ingredients=[
            RecipeIngredientCreate(ingredient_name=name, quantity=qty, unit=unit)
            for name, qty, unit in ingredients
        ],
    )
    return crud.create_recipe(session=db, recipe_in=recipe_in, owner_id=owner_id)


def _list(db: Session, owner_id: uuid.UUID) -> ShoppingList:
    return crud.create_shopping_list(
        session=db,
        list_in=ShoppingListCreate(name=random_lower_string()),
        owner_id=owner_id,
    )


def _items(sl: ShoppingList) -> dict[str, tuple[float, Unit]]:
    return {item.name.lower(): (item.quantity, item.unit) for item in sl.items}


def test_compatible_mass_units_merge_into_one_row(db: Session) -> None:
    """300 g + 1 kg of flour is one row of 1300 g, not two rows."""
    user = create_random_user(db)
    first = _recipe(db, user.id, [("flour", 300, Unit.GRAM)])
    second = _recipe(db, user.id, [("flour", 1, Unit.KILOGRAM)])
    sl = _list(db, user.id)

    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=first)
    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=second)

    assert len(sl.items) == 1
    quantity, unit = _items(sl)["flour"]
    assert unit is Unit.GRAM  # the unit of the row that already existed
    assert quantity == 1300


def test_volume_merges_into_an_existing_volume_row(db: Session) -> None:
    user = create_random_user(db)
    first = _recipe(db, user.id, [("milk", 500, Unit.MILLILITER)])
    second = _recipe(db, user.id, [("milk", 1, Unit.LITER)])
    sl = _list(db, user.id)

    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=first)
    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=second)

    assert len(sl.items) == 1
    quantity, unit = _items(sl)["milk"]
    assert unit is Unit.MILLILITER
    assert quantity == 1500


def test_plural_and_singular_names_merge(db: Session) -> None:
    user = create_random_user(db)
    first = _recipe(db, user.id, [("Tomato", 2, Unit.PIECE)])
    second = _recipe(db, user.id, [("tomatoes", 3, Unit.PIECE)])
    sl = _list(db, user.id)

    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=first)
    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=second)

    assert len(sl.items) == 1
    assert sl.items[0].quantity == 5


def test_mass_and_volume_do_not_merge(db: Session) -> None:
    """Without a density these are not the same quantity and must stay apart."""
    user = create_random_user(db)
    first = _recipe(db, user.id, [("oil", 100, Unit.GRAM)])
    second = _recipe(db, user.id, [("oil", 100, Unit.MILLILITER)])
    sl = _list(db, user.id)

    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=first)
    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=second)

    assert len(sl.items) == 2


def test_different_discrete_units_do_not_merge(db: Session) -> None:
    """2 cloves of garlic and 2 slices of garlic are not 4 of anything."""
    user = create_random_user(db)
    first = _recipe(db, user.id, [("garlic", 2, Unit.CLOVE)])
    second = _recipe(db, user.id, [("garlic", 2, Unit.SLICE)])
    sl = _list(db, user.id)

    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=first)
    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=second)

    assert len(sl.items) == 2


def test_different_ingredients_do_not_merge(db: Session) -> None:
    user = create_random_user(db)
    recipe = _recipe(db, user.id, [("flour", 100, Unit.GRAM), ("sugar", 50, Unit.GRAM)])
    sl = _list(db, user.id)

    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=recipe)

    assert len(sl.items) == 2


def test_manual_item_merges_into_an_existing_row(db: Session) -> None:
    user = create_random_user(db)
    recipe = _recipe(db, user.id, [("flour", 1, Unit.KILOGRAM)])
    sl = _list(db, user.id)
    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=recipe)

    sl = crud.add_item_to_shopping_list(
        session=db,
        shopping_list=sl,
        item_in=ShoppingListItemCreate(name="flour", quantity=500, unit=Unit.GRAM),
    )

    assert len(sl.items) == 1
    quantity, unit = _items(sl)["flour"]
    assert unit is Unit.KILOGRAM
    assert quantity == 1.5


def test_removing_a_recipe_subtracts_converted_quantities(db: Session) -> None:
    """The row must come back to exactly what the other recipe contributed."""
    user = create_random_user(db)
    first = _recipe(db, user.id, [("flour", 300, Unit.GRAM)])
    second = _recipe(db, user.id, [("flour", 1, Unit.KILOGRAM)])
    sl = _list(db, user.id)

    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=first)
    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=second)
    planned = [p for p in sl.planned_recipes if p.recipe_id == second.id][0]
    crud.delete_shopping_list_recipe(session=db, shopping_list=sl, sl_recipe=planned)
    db.refresh(sl)

    assert len(sl.items) == 1
    assert sl.items[0].quantity == 300


def test_removing_every_recipe_empties_the_list(db: Session) -> None:
    user = create_random_user(db)
    recipe = _recipe(db, user.id, [("flour", 300, Unit.GRAM)])
    sl = _list(db, user.id)
    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=recipe)

    crud.delete_shopping_list_recipe(
        session=db, shopping_list=sl, sl_recipe=sl.planned_recipes[0]
    )
    db.refresh(sl)

    assert sl.items == []


def test_changing_servings_rescales_the_merged_row(db: Session) -> None:
    user = create_random_user(db)
    recipe = _recipe(db, user.id, [("flour", 200, Unit.GRAM)], servings=2)
    sl = _list(db, user.id)
    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=recipe)
    assert sl.items[0].quantity == 200

    from app.models import ShoppingListRecipeUpdate

    crud.update_shopping_list_recipe(
        session=db,
        shopping_list=sl,
        sl_recipe=sl.planned_recipes[0],
        update_in=ShoppingListRecipeUpdate(servings_planned=4),
    )
    db.refresh(sl)

    assert sl.items[0].quantity == 400


def test_repeated_add_and_remove_does_not_accumulate_float_dust(db: Session) -> None:
    """Rounding keeps a cycle of edits from leaving 0.30000000000000004 behind."""
    user = create_random_user(db)
    base = _recipe(db, user.id, [("flour", 0.1, Unit.KILOGRAM)])
    extra = _recipe(db, user.id, [("flour", 0.2, Unit.KILOGRAM)])
    sl = _list(db, user.id)
    sl = crud.add_recipe_to_shopping_list(session=db, shopping_list=sl, recipe=base)

    for _ in range(5):
        sl = crud.add_recipe_to_shopping_list(
            session=db, shopping_list=sl, recipe=extra
        )
        planned = [p for p in sl.planned_recipes if p.recipe_id == extra.id][0]
        crud.delete_shopping_list_recipe(
            session=db, shopping_list=sl, sl_recipe=planned
        )
        db.refresh(sl)

    assert len(sl.items) == 1
    assert sl.items[0].quantity == 0.1
