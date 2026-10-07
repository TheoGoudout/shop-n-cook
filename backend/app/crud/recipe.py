import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import ColumnElement
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, or_, select

from app.crud.query import paginate
from app.models import (
    Recipe,
    RecipeCreate,
    RecipeFilters,
    RecipeIngredient,
    RecipeIngredientCreate,
    RecipeIngredientPublic,
    RecipePublic,
    RecipeStep,
    RecipeStepCreate,
    RecipeStepIngredient,
    RecipeStepIngredientPublic,
    RecipeStepPublic,
    RecipeUpdate,
)
from app.models.recipe import ImportSource
from app.models.user import User
from app.services.pricing import CostSummary, PriceBook, quantize_money
from app.services.recipe_import.prompt import language_code
from app.services.recipe_import.version import IMPORT_VERSION


def recipe_ingredient_to_public(
    ri: RecipeIngredient,
    prices: PriceBook | None = None,
    *,
    scale: float = 1.0,
) -> RecipeIngredientPublic:
    """Public shape of a recipe ingredient, priced when a ``PriceBook`` is given.

    ``scale`` adjusts the quantity before pricing without changing the quantity
    reported, which is what lets a shopping list price a recipe at its planned
    servings rather than the recipe's own.
    """
    estimated_cost = (
        prices.cost(ri.ingredient_name, ri.quantity * scale, ri.unit)
        if prices is not None
        else None
    )
    return RecipeIngredientPublic(
        id=ri.id,
        ingredient_name=ri.ingredient_name,
        quantity=ri.quantity,
        unit=ri.unit,
        notes=ri.notes,
        estimated_cost=quantize_money(estimated_cost)
        if estimated_cost is not None
        else None,
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


def user_can_read_recipe(*, user: User, recipe: Recipe) -> bool:
    """Your own recipes, public ones, or any recipe if you are a superuser."""
    return user.is_superuser or recipe.owner_id == user.id or recipe.is_public


def user_can_edit_recipe(*, user: User, recipe: Recipe) -> bool:
    """Only the owner, or a superuser, may change a recipe — public or not."""
    return user.is_superuser or recipe.owner_id == user.id


def _owner_display_name(owner: User) -> str:
    return owner.full_name or owner.email.split("@")[0]


def servings_scale(recipe: Recipe, servings: int) -> float:
    """How far cooking ``servings`` stretches the recipe's own quantities."""
    return servings / (recipe.servings or 1)


def recipe_cost(
    recipe: Recipe, prices: PriceBook, *, scale: float = 1.0
) -> CostSummary:
    """Total what ``recipe`` costs to cook, at ``scale`` times its own servings."""
    return prices.summarize(
        [
            (ri.ingredient_name, ri.quantity * scale, ri.unit)
            for ri in recipe.recipe_ingredients
        ]
    )


def recipe_to_public(
    recipe: Recipe, owner: User | None = None, prices: PriceBook | None = None
) -> RecipePublic:
    resolved_owner = owner or recipe.owner
    owner_name = _owner_display_name(resolved_owner) if resolved_owner else None
    cost = recipe_cost(recipe, prices) if prices is not None else None
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
            recipe_ingredient_to_public(ri, prices) for ri in recipe.recipe_ingredients
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
        estimated_cost=cost.total if cost else None,
        estimated_cost_per_serving=cost.per_unit(recipe.servings) if cost else None,
        unpriced_ingredient_count=cost.unpriced_count if cost else 0,
        currency=prices.currency if prices is not None else "EUR",
    )


def _add_ingredients(
    session: Session,
    recipe: Recipe,
    ingredients_in: Sequence[RecipeIngredientCreate],
) -> list[RecipeIngredient]:
    """Add the recipe's ingredient rows, in order: steps refer to them by index."""
    rows = [
        RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_name=ing.ingredient_name,
            quantity=ing.quantity,
            unit=ing.unit,
            notes=ing.notes,
        )
        for ing in ingredients_in
    ]
    session.add_all(rows)
    return rows


def _add_steps(
    session: Session,
    recipe: Recipe,
    steps_in: Sequence[RecipeStepCreate],
    ingredients: Sequence[RecipeIngredient],
) -> None:
    """Add the recipe's steps, each linked to the ingredients it uses.

    An ingredient index out of range is ignored rather than refused: it comes
    from an AI import as often as from a person.
    """
    for step_in in steps_in:
        step = RecipeStep(
            recipe_id=recipe.id,
            step_number=step_in.step_number,
            instruction=step_in.instruction,
        )
        session.add(step)
        session.add_all(
            RecipeStepIngredient(
                step_id=step.id, recipe_ingredient_id=ingredients[i].id
            )
            for i in step_in.ingredient_indices
            if 0 <= i < len(ingredients)
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


def _filter_conditions(filters: RecipeFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.search:
        pattern = f"%{filters.search}%"
        conditions.append(
            or_(
                col(Recipe.title).ilike(pattern),
                col(Recipe.description).ilike(pattern),
            )
        )
    if filters.seasons:
        seasons = pg_array([s.value for s in filters.seasons], type_=sa.String)
        conditions.append(col(Recipe.seasons).bool_op("&&")(seasons))
    for flag in ("is_vegan", "is_vegetarian", "is_gluten_free", "is_dairy_free"):
        if getattr(filters, flag) is True:
            conditions.append(col(getattr(Recipe, flag)).is_(True))
    if filters.difficulty is not None:
        conditions.append(col(Recipe.difficulty) == filters.difficulty)
    if filters.meal_type is not None:
        conditions.append(col(Recipe.meal_type) == filters.meal_type)
    if filters.cuisine_type:
        conditions.append(col(Recipe.cuisine_type).ilike(f"%{filters.cuisine_type}%"))
    return conditions


def get_recipes(
    *,
    session: Session,
    filters: RecipeFilters | None = None,
    owner_id: uuid.UUID | None = None,
    public_only: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Recipe], int]:
    """Newest recipes first, narrowed by ``filters``, an owner, or public ones."""
    where = _filter_conditions(filters or RecipeFilters())
    if public_only:
        where.append(col(Recipe.is_public).is_(True))
    if owner_id is not None:
        where.append(col(Recipe.owner_id) == owner_id)
    return paginate(
        session,
        Recipe,
        where=where,
        order_by=col(Recipe.created_at).desc(),
        skip=skip,
        limit=limit,
        # Every listed recipe shows its owner's name.
        options=[selectinload(Recipe.owner)],  # type: ignore[arg-type]
    )


def create_recipe(
    *, session: Session, recipe_in: RecipeCreate, owner_id: uuid.UUID
) -> Recipe:
    recipe = Recipe(
        **recipe_in.model_dump(exclude={"ingredients", "steps"}), owner_id=owner_id
    )
    if recipe.import_consent:
        recipe.import_consent_at = datetime.now(timezone.utc)
    if recipe.import_language is not None:
        recipe.import_language = language_code(recipe.import_language)
    if recipe.import_source == ImportSource.URL:
        # The page was parsed moments ago, by this server's pipeline.
        recipe.import_version = IMPORT_VERSION
    session.add(recipe)
    ingredients = _add_ingredients(session, recipe, recipe_in.ingredients)
    _add_steps(session, recipe, recipe_in.steps, ingredients)
    session.flush()
    session.refresh(recipe)
    return recipe


def update_recipe(
    *,
    session: Session,
    db_recipe: Recipe,
    recipe_in: RecipeUpdate,
) -> Recipe:
    """Update a recipe; ``ingredients`` and ``steps``, when given, replace all."""
    db_recipe.sqlmodel_update(
        recipe_in.model_dump(exclude_unset=True, exclude={"ingredients", "steps"})
    )

    ingredients = list(db_recipe.recipe_ingredients)
    if recipe_in.ingredients is not None:
        for row in ingredients:
            session.delete(row)
        session.flush()
        ingredients = _add_ingredients(session, db_recipe, recipe_in.ingredients)

    if recipe_in.steps is not None:
        for step in list(db_recipe.steps):
            session.delete(step)
        session.flush()
        _add_steps(session, db_recipe, recipe_in.steps, ingredients)

    session.flush()
    session.refresh(db_recipe)
    return db_recipe


def delete_recipe(*, session: Session, recipe: Recipe) -> None:
    session.delete(recipe)
    session.flush()
