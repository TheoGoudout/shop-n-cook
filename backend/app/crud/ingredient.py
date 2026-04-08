import uuid

from sqlmodel import Session, col, func, select

from app.models import (
    Ingredient,
    IngredientCategory,
    IngredientCreate,
    IngredientUpdate,
    RecipeIngredient,
    ShoppingListItem,
)


def get_ingredient(*, session: Session, ingredient_id: uuid.UUID) -> Ingredient | None:
    return session.get(Ingredient, ingredient_id)


def get_ingredient_by_name(*, session: Session, name: str) -> Ingredient | None:
    statement = select(Ingredient).where(func.lower(Ingredient.name) == name.lower())
    return session.exec(statement).first()


def get_ingredients(
    *,
    session: Session,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    category: IngredientCategory | None = None,
) -> tuple[list[Ingredient], int]:
    query = select(Ingredient)
    count_query = select(func.count()).select_from(Ingredient)

    if search:
        query = query.where(col(Ingredient.name).ilike(f"%{search}%"))
        count_query = count_query.where(col(Ingredient.name).ilike(f"%{search}%"))
    if category:
        query = query.where(Ingredient.category == category)
        count_query = count_query.where(Ingredient.category == category)

    count = session.exec(count_query).one()
    ingredients = session.exec(
        query.order_by(col(Ingredient.name)).offset(skip).limit(limit)
    ).all()
    return list(ingredients), count


def create_ingredient(
    *, session: Session, ingredient_in: IngredientCreate
) -> Ingredient:
    db_ingredient = Ingredient.model_validate(ingredient_in)
    session.add(db_ingredient)
    session.commit()
    session.refresh(db_ingredient)
    return db_ingredient


def update_ingredient(
    *,
    session: Session,
    db_ingredient: Ingredient,
    ingredient_in: IngredientUpdate,
) -> Ingredient:
    update_data = ingredient_in.model_dump(exclude_unset=True)
    db_ingredient.sqlmodel_update(update_data)
    session.add(db_ingredient)
    session.commit()
    session.refresh(db_ingredient)
    return db_ingredient


def ingredient_has_references(*, session: Session, ingredient_id: uuid.UUID) -> bool:
    """Return True if the ingredient is referenced by any recipe or shopping list."""
    in_recipe = session.exec(
        select(RecipeIngredient).where(RecipeIngredient.ingredient_id == ingredient_id)
    ).first()
    if in_recipe:
        return True
    in_list = session.exec(
        select(ShoppingListItem).where(ShoppingListItem.ingredient_id == ingredient_id)
    ).first()
    return in_list is not None


def delete_ingredient(*, session: Session, ingredient: Ingredient) -> None:
    session.delete(ingredient)
    session.commit()
