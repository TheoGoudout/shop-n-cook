import uuid

from sqlmodel import Session

from app import crud
from app.models import (
    RecipeCreate,
    RecipeIngredientCreate,
    Unit,
)
from tests.utils.utils import random_lower_string


def create_random_recipe(
    db: Session,
    owner_id: uuid.UUID,
    *,
    with_ingredients: bool = False,
) -> object:
    title = random_lower_string()
    ingredients: list[RecipeIngredientCreate] = []

    if with_ingredients:
        for name in [random_lower_string(), random_lower_string()]:
            ingredients.append(
                RecipeIngredientCreate(
                    ingredient_name=name,
                    quantity=1.0,
                    unit=Unit.PIECE,
                )
            )

    recipe_in = RecipeCreate(title=title, ingredients=ingredients)
    return crud.create_recipe(session=db, recipe_in=recipe_in, owner_id=owner_id)
