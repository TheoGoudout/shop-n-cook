import uuid
from datetime import datetime, timezone

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
from app.models.user import User


def _ri_to_public(ri: RecipeIngredient) -> RecipeIngredientPublic:
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
        ingredients=[_ri_to_public(ri) for ri in recipe.recipe_ingredients],
        steps=sorted(
            [_step_to_public(s) for s in recipe.steps],
            key=lambda s: s.step_number,
        ),
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
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Recipe], int]:
    query = select(Recipe)
    count_query = select(func.count()).select_from(Recipe)

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
) -> tuple[list[Recipe], int]:
    query = (
        select(Recipe)
        .where(Recipe.is_public == True)  # noqa: E712
        .options(selectinload(Recipe.owner))  # type: ignore[arg-type]
    )
    count_query = (
        select(func.count()).select_from(Recipe).where(Recipe.is_public == True)  # noqa: E712
    )

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

    count = session.exec(count_query).one()
    recipes = session.exec(
        query.order_by(col(Recipe.created_at).desc()).offset(skip).limit(limit)
    ).all()
    return list(recipes), count


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
