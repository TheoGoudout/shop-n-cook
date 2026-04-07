from sqlmodel import Session

from app import crud
from app.models import Ingredient, IngredientCategory, IngredientCreate, Unit
from tests.utils.utils import random_lower_string


def create_random_ingredient(
    db: Session,
    *,
    category: IngredientCategory = IngredientCategory.OTHER,
    default_unit: Unit = Unit.PIECE,
) -> Ingredient:
    name = random_lower_string()
    ingredient_in = IngredientCreate(
        name=name, category=category, default_unit=default_unit
    )
    return crud.create_ingredient(session=db, ingredient_in=ingredient_in)
