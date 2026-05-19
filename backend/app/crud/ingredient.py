import uuid

from sqlmodel import Session, func, select

from app.models.ingredient import Ingredient, IngredientCreate, IngredientUpdate


def get_ingredient_by_name(session: Session, name: str) -> Ingredient | None:
    return session.exec(
        select(Ingredient).where(func.lower(Ingredient.name) == name.lower())
    ).first()


def get_or_create_ingredient(
    session: Session, name: str
) -> tuple[Ingredient, bool]:
    existing = get_ingredient_by_name(session, name)
    if existing:
        return existing, False
    ingredient = Ingredient(name=name)
    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)
    return ingredient, True


def get_ingredients(
    session: Session, skip: int = 0, limit: int = 1000
) -> tuple[list[Ingredient], int]:
    count = session.exec(select(func.count()).select_from(Ingredient)).one()
    ingredients = session.exec(
        select(Ingredient).order_by(Ingredient.name).offset(skip).limit(limit)
    ).all()
    return list(ingredients), count


def get_ingredient(session: Session, ingredient_id: uuid.UUID) -> Ingredient | None:
    return session.get(Ingredient, ingredient_id)


def create_ingredient(session: Session, ingredient_in: IngredientCreate) -> Ingredient:
    ingredient = Ingredient.model_validate(ingredient_in)
    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)
    return ingredient


def update_ingredient(
    session: Session, ingredient: Ingredient, update_in: IngredientUpdate
) -> Ingredient:
    data = update_in.model_dump(exclude_unset=True)
    ingredient.sqlmodel_update(data)
    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)
    return ingredient
