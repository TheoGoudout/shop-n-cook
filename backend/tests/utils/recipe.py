from sqlmodel import Session

from app.models import Recipe, RecipeIngredient
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_recipe(db: Session, owner_id=None) -> Recipe:
    if owner_id is None:
        user = create_random_user(db)
        owner_id = user.id
    recipe = Recipe(
        title=random_lower_string(),
        description=random_lower_string(),
        base_servings=4,
        owner_id=owner_id,
    )
    db.add(recipe)
    db.flush()
    ingredient = RecipeIngredient(
        recipe_id=recipe.id,
        name="flour",
        quantity=200.0,
        unit="g",
    )
    db.add(ingredient)
    db.commit()
    db.refresh(recipe)
    return recipe
