import uuid

from sqlmodel import Session, col, func, select

from app.crud.ingredient import get_ingredient_by_name
from app.models import (
    Ingredient,
    IngredientCreate,
    Recipe,
    RecipeCreate,
    RecipeIngredient,
    RecipeIngredientCreate,
    RecipeIngredientPublic,
    RecipePublic,
    RecipeUpdate,
)


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


def recipe_to_public(recipe: Recipe) -> RecipePublic:
    return RecipePublic(
        id=recipe.id,
        title=recipe.title,
        description=recipe.description,
        instructions=recipe.instructions,
        servings=recipe.servings,
        prep_time_minutes=recipe.prep_time_minutes,
        cook_time_minutes=recipe.cook_time_minutes,
        source_url=recipe.source_url,
        image_url=recipe.image_url,
        owner_id=recipe.owner_id,
        created_at=recipe.created_at,
        ingredients=[_ri_to_public(ri) for ri in recipe.recipe_ingredients],
    )


def _resolve_ingredient_id(
    *, session: Session, ing_in: RecipeIngredientCreate
) -> uuid.UUID:
    """Return the ingredient ID, creating the ingredient by name if it doesn't exist."""
    if ing_in.ingredient_id is not None:
        return ing_in.ingredient_id
    assert ing_in.ingredient_name is not None  # guaranteed by model validator
    existing = get_ingredient_by_name(session=session, name=ing_in.ingredient_name)
    if existing:
        return existing.id
    new_ingredient = Ingredient.model_validate(
        IngredientCreate(name=ing_in.ingredient_name)
    )
    session.add(new_ingredient)
    session.flush()
    return new_ingredient.id


def get_recipe(*, session: Session, recipe_id: uuid.UUID) -> Recipe | None:
    return session.get(Recipe, recipe_id)


def get_recipes(
    *,
    session: Session,
    owner_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Recipe], int]:
    query = select(Recipe)
    count_query = select(func.count()).select_from(Recipe)

    if owner_id is not None:
        query = query.where(Recipe.owner_id == owner_id)
        count_query = count_query.where(Recipe.owner_id == owner_id)

    count = session.exec(count_query).one()
    recipes = session.exec(
        query.order_by(col(Recipe.created_at).desc()).offset(skip).limit(limit)
    ).all()
    return list(recipes), count


def create_recipe(
    *, session: Session, recipe_in: RecipeCreate, owner_id: uuid.UUID
) -> Recipe:
    recipe_data = recipe_in.model_dump(exclude={"ingredients"})
    db_recipe = Recipe(**recipe_data, owner_id=owner_id)
    session.add(db_recipe)
    session.flush()  # get db_recipe.id before inserting ingredients

    for ing_in in recipe_in.ingredients:
        ri = RecipeIngredient(
            recipe_id=db_recipe.id,
            ingredient_id=_resolve_ingredient_id(session=session, ing_in=ing_in),
            quantity=ing_in.quantity,
            unit=ing_in.unit,
            notes=ing_in.notes,
        )
        session.add(ri)

    session.commit()
    session.refresh(db_recipe)
    return db_recipe


def update_recipe(
    *,
    session: Session,
    db_recipe: Recipe,
    recipe_in: RecipeUpdate,
) -> Recipe:
    update_data = recipe_in.model_dump(exclude_unset=True, exclude={"ingredients"})
    db_recipe.sqlmodel_update(update_data)

    if recipe_in.ingredients is not None:
        for ri in list(db_recipe.recipe_ingredients):
            session.delete(ri)
        session.flush()
        for ing_in in recipe_in.ingredients:
            ri = RecipeIngredient(
                recipe_id=db_recipe.id,
                ingredient_id=_resolve_ingredient_id(session=session, ing_in=ing_in),
                quantity=ing_in.quantity,
                unit=ing_in.unit,
                notes=ing_in.notes,
            )
            session.add(ri)

    session.commit()
    session.refresh(db_recipe)
    return db_recipe


def delete_recipe(*, session: Session, recipe: Recipe) -> None:
    session.delete(recipe)
    session.commit()
