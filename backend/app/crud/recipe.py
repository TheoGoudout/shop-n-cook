import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, or_, select

from app.models import (
    Recipe,
    RecipeCreate,
    RecipeIngredient,
    RecipeIngredientPublic,
    RecipePublic,
    RecipeStep,
    RecipeStepCreate,
    RecipeStepIngredient,
    RecipeStepIngredientPublic,
    RecipeStepPublic,
    RecipeUpdate,
)
from app.models.recipe import Difficulty, MealType, Season
from app.models.user import User


def recipe_ingredient_to_public(ri: RecipeIngredient) -> RecipeIngredientPublic:
    return RecipeIngredientPublic(
        id=ri.id,
        ingredient_name=ri.ingredient_name,
        quantity=ri.quantity,
        unit=ri.unit,
        notes=ri.notes,
    )


def _step_to_public(step: RecipeStep) -> RecipeStepPublic:
    return RecipeStepPublic(
        id=step.id,
        step_number=step.step_number,
        instruction=step.instruction,
        ingredients=[
            RecipeStepIngredientPublic(
                recipe_ingredient_id=si.recipe_ingredient_id,
                ingredient_name=si.recipe_ingredient.ingredient_name,
            )
            for si in step.step_ingredients
        ],
    )


def _owner_display_name(owner: User) -> str:
    return owner.full_name or owner.email.split("@")[0]


def recipe_to_public(recipe: Recipe, owner: User | None = None) -> RecipePublic:
    resolved_owner = owner or recipe.owner
    owner_name = _owner_display_name(resolved_owner) if resolved_owner else None
    return RecipePublic(
        id=recipe.id,
        title=recipe.title,
        description=recipe.description,
        servings=recipe.servings,
        prep_time_minutes=recipe.prep_time_minutes,
        cook_time_minutes=recipe.cook_time_minutes,
        source_url=recipe.source_url,
        image_url=recipe.image_url,
        is_public=recipe.is_public,
        owner_id=recipe.owner_id,
        owner_name=owner_name,
        created_at=recipe.created_at,
        ingredients=[
            recipe_ingredient_to_public(ri) for ri in recipe.recipe_ingredients
        ],
        steps=sorted(
            [_step_to_public(s) for s in recipe.steps],
            key=lambda s: s.step_number,
        ),
        seasons=recipe.seasons or [],
        is_vegan=recipe.is_vegan,
        is_vegetarian=recipe.is_vegetarian,
        is_gluten_free=recipe.is_gluten_free,
        is_dairy_free=recipe.is_dairy_free,
        kcal_per_serving=recipe.kcal_per_serving,
        difficulty=recipe.difficulty,
        meal_type=recipe.meal_type,
        cuisine_type=recipe.cuisine_type,
    )


def _create_steps(
    *,
    session: Session,
    recipe_id: uuid.UUID,
    steps_in: list[RecipeStepCreate],
    ri_list: list[RecipeIngredient],
) -> None:
    """Create RecipeStep rows and their RecipeStepIngredient links."""
    for step_in in steps_in:
        step = RecipeStep(
            recipe_id=recipe_id,
            step_number=step_in.step_number,
            instruction=step_in.instruction,
        )
        session.add(step)
        session.flush()
        for idx in step_in.ingredient_indices:
            if 0 <= idx < len(ri_list):
                session.add(
                    RecipeStepIngredient(
                        step_id=step.id,
                        recipe_ingredient_id=ri_list[idx].id,
                    )
                )


def get_recipe(*, session: Session, recipe_id: uuid.UUID) -> Recipe | None:
    return session.get(Recipe, recipe_id)


def get_recipe_by_source_url(
    *, session: Session, owner_id: uuid.UUID, source_url: str
) -> Recipe | None:
    return session.exec(
        select(Recipe).where(
            Recipe.owner_id == owner_id,
            Recipe.source_url == source_url,
        )
    ).first()


def get_recipes(
    *,
    session: Session,
    owner_id: uuid.UUID | None = None,
    search: str | None = None,
    public_only: bool = False,
    eager_load_owner: bool = False,
    skip: int = 0,
    limit: int = 100,
    seasons: list[Season] | None = None,
    is_vegan: bool | None = None,
    is_vegetarian: bool | None = None,
    is_gluten_free: bool | None = None,
    is_dairy_free: bool | None = None,
    difficulty: Difficulty | None = None,
    meal_type: MealType | None = None,
    cuisine_type: str | None = None,
) -> tuple[list[Recipe], int]:
    query = select(Recipe)
    count_query = select(func.count()).select_from(Recipe)

    if public_only:
        query = query.where(Recipe.is_public == True)  # noqa: E712
        count_query = count_query.where(Recipe.is_public == True)  # noqa: E712

    if eager_load_owner:
        query = query.options(selectinload(Recipe.owner))  # type: ignore[arg-type]

    if owner_id is not None:
        query = query.where(Recipe.owner_id == owner_id)
        count_query = count_query.where(Recipe.owner_id == owner_id)

    if search:
        pattern = f"%{search}%"
        search_filter = or_(
            col(Recipe.title).ilike(pattern),
            col(Recipe.description).ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if seasons:
        seasons_arr = pg_array([s.value for s in seasons], type_=sa.String)
        seasons_filter = col(Recipe.seasons).bool_op("&&")(seasons_arr)
        query = query.where(seasons_filter)
        count_query = count_query.where(seasons_filter)

    if is_vegan is True:
        query = query.where(Recipe.is_vegan == True)  # noqa: E712
        count_query = count_query.where(Recipe.is_vegan == True)  # noqa: E712

    if is_vegetarian is True:
        query = query.where(Recipe.is_vegetarian == True)  # noqa: E712
        count_query = count_query.where(Recipe.is_vegetarian == True)  # noqa: E712

    if is_gluten_free is True:
        query = query.where(Recipe.is_gluten_free == True)  # noqa: E712
        count_query = count_query.where(Recipe.is_gluten_free == True)  # noqa: E712

    if is_dairy_free is True:
        query = query.where(Recipe.is_dairy_free == True)  # noqa: E712
        count_query = count_query.where(Recipe.is_dairy_free == True)  # noqa: E712

    if difficulty is not None:
        query = query.where(Recipe.difficulty == difficulty.value)
        count_query = count_query.where(Recipe.difficulty == difficulty.value)

    if meal_type is not None:
        query = query.where(Recipe.meal_type == meal_type.value)
        count_query = count_query.where(Recipe.meal_type == meal_type.value)

    if cuisine_type:
        pattern = f"%{cuisine_type}%"
        query = query.where(col(Recipe.cuisine_type).ilike(pattern))
        count_query = count_query.where(col(Recipe.cuisine_type).ilike(pattern))

    count = session.exec(count_query).one()
    recipes = session.exec(
        query.order_by(col(Recipe.created_at).desc()).offset(skip).limit(limit)
    ).all()
    return list(recipes), count


def get_public_recipes(
    *,
    session: Session,
    owner_id: uuid.UUID | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
    seasons: list[Season] | None = None,
    is_vegan: bool | None = None,
    is_vegetarian: bool | None = None,
    is_gluten_free: bool | None = None,
    is_dairy_free: bool | None = None,
    difficulty: Difficulty | None = None,
    meal_type: MealType | None = None,
    cuisine_type: str | None = None,
) -> tuple[list[Recipe], int]:
    return get_recipes(
        session=session,
        owner_id=owner_id,
        search=search,
        public_only=True,
        eager_load_owner=True,
        skip=skip,
        limit=limit,
        seasons=seasons,
        is_vegan=is_vegan,
        is_vegetarian=is_vegetarian,
        is_gluten_free=is_gluten_free,
        is_dairy_free=is_dairy_free,
        difficulty=difficulty,
        meal_type=meal_type,
        cuisine_type=cuisine_type,
    )


def create_recipe(
    *, session: Session, recipe_in: RecipeCreate, owner_id: uuid.UUID
) -> Recipe:
    recipe_data = recipe_in.model_dump(exclude={"ingredients", "steps"})
    db_recipe = Recipe(**recipe_data, owner_id=owner_id)
    if db_recipe.import_consent:
        db_recipe.import_consent_at = datetime.now(timezone.utc)
    session.add(db_recipe)
    session.flush()

    ri_list: list[RecipeIngredient] = []
    for ing_in in recipe_in.ingredients:
        ri = RecipeIngredient(
            recipe_id=db_recipe.id,
            ingredient_name=ing_in.ingredient_name,
            quantity=ing_in.quantity,
            unit=ing_in.unit,
            notes=ing_in.notes,
        )
        session.add(ri)
        session.flush()
        ri_list.append(ri)

    _create_steps(
        session=session,
        recipe_id=db_recipe.id,
        steps_in=recipe_in.steps,
        ri_list=ri_list,
    )

    session.commit()
    session.refresh(db_recipe)
    return db_recipe


def update_recipe(
    *,
    session: Session,
    db_recipe: Recipe,
    recipe_in: RecipeUpdate,
) -> Recipe:
    update_data = recipe_in.model_dump(
        exclude_unset=True, exclude={"ingredients", "steps"}
    )
    db_recipe.sqlmodel_update(update_data)

    ri_list: list[RecipeIngredient] = list(db_recipe.recipe_ingredients)

    if recipe_in.ingredients is not None:
        for ri in list(db_recipe.recipe_ingredients):
            session.delete(ri)
        session.flush()
        ri_list = []
        for ing_in in recipe_in.ingredients:
            ri = RecipeIngredient(
                recipe_id=db_recipe.id,
                ingredient_name=ing_in.ingredient_name,
                quantity=ing_in.quantity,
                unit=ing_in.unit,
                notes=ing_in.notes,
            )
            session.add(ri)
            session.flush()
            ri_list.append(ri)

    if recipe_in.steps is not None:
        for step in list(db_recipe.steps):
            session.delete(step)
        session.flush()
        _create_steps(
            session=session,
            recipe_id=db_recipe.id,
            steps_in=recipe_in.steps,
            ri_list=ri_list,
        )

    session.commit()
    session.refresh(db_recipe)
    return db_recipe


def delete_recipe(*, session: Session, recipe: Recipe) -> None:
    session.delete(recipe)
    session.commit()
