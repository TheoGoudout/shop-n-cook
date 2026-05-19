import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, HttpUrl

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models import (
    Message,
    Recipe,
    RecipeCreate,
    RecipeIngredientCreate,
    RecipePublic,
    RecipesPublic,
    RecipeStepCreate,
    RecipeUpdate,
)
from app.models.user import User
from app.services.ingredient_image import fetch_and_update_ingredient_image
from app.services.recipe_import import (
    ParsedIngredient,
    ParsedRecipe,
    ParsedStep,
    import_recipe_from_url,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])


class ImportUrlRequest(BaseModel):
    url: HttpUrl
    language: str | None = None


class ReimportRequest(BaseModel):
    language: str | None = None


def _recipe_to_parsed(recipe: Recipe) -> ParsedRecipe:
    """Convert a saved Recipe back to ParsedRecipe format (used as DB cache hit)."""
    ri_map = {ri.id: ri for ri in recipe.recipe_ingredients}
    ingredients = [
        ParsedIngredient(
            name=ri.ingredient_name,
            quantity=ri.quantity,
            unit=ri.unit,
            notes=ri.notes,
        )
        for ri in recipe.recipe_ingredients
    ]
    steps = [
        ParsedStep(
            instruction=step.instruction,
            ingredient_names=[
                ri_map[si.recipe_ingredient_id].ingredient_name
                for si in step.step_ingredients
                if si.recipe_ingredient_id in ri_map
            ],
        )
        for step in sorted(recipe.steps, key=lambda s: s.step_number)
    ]
    return ParsedRecipe(
        title=recipe.title,
        description=recipe.description,
        servings=recipe.servings,
        prep_time_minutes=recipe.prep_time_minutes,
        cook_time_minutes=recipe.cook_time_minutes,
        source_url=recipe.source_url,
        image_url=recipe.image_url,
        ingredients=ingredients,
        steps=steps,
    )


def _parsed_to_update(parsed: ParsedRecipe) -> RecipeUpdate:
    name_to_idx = {ing.name.lower(): i for i, ing in enumerate(parsed.ingredients)}
    ingredients = [
        RecipeIngredientCreate(
            ingredient_name=ing.name,
            quantity=ing.quantity,
            unit=ing.unit,
            notes=ing.notes,
        )
        for ing in parsed.ingredients
    ]
    steps = [
        RecipeStepCreate(
            step_number=i + 1,
            instruction=step.instruction,
            ingredient_indices=[
                name_to_idx[n.lower()]
                for n in step.ingredient_names
                if n.lower() in name_to_idx
            ],
        )
        for i, step in enumerate(parsed.steps)
    ]
    return RecipeUpdate(
        title=parsed.title,
        description=parsed.description,
        servings=parsed.servings,
        prep_time_minutes=parsed.prep_time_minutes,
        cook_time_minutes=parsed.cook_time_minutes,
        source_url=parsed.source_url,
        image_url=parsed.image_url,
        ingredients=ingredients,
        steps=steps,
    )


@router.get("/public", response_model=RecipesPublic)
def read_public_recipes(
    session: SessionDep,
    _current_user: CurrentUser,
    owner_id: uuid.UUID | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all public recipes. Optionally filter by owner_id or search query."""
    recipes, count = crud.get_public_recipes(
        session=session, owner_id=owner_id, search=search, skip=skip, limit=limit
    )
    return RecipesPublic(data=[crud.recipe_to_public(r) for r in recipes], count=count)


@router.get("/", response_model=RecipesPublic)
def read_recipes(
    session: SessionDep,
    current_user: CurrentUser,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List recipes. Superusers see all; regular users see only their own."""
    owner_id = None if current_user.is_superuser else current_user.id
    recipes, count = crud.get_recipes(
        session=session, owner_id=owner_id, search=search, skip=skip, limit=limit
    )
    return RecipesPublic(data=[crud.recipe_to_public(r) for r in recipes], count=count)


@router.get("/{id}", response_model=RecipePublic)
def read_recipe(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """Get a single recipe by ID. Public recipes are visible to all authenticated users."""
    recipe = crud.get_recipe(session=session, recipe_id=id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if (
        not current_user.is_superuser
        and recipe.owner_id != current_user.id
        and not recipe.is_public
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return crud.recipe_to_public(recipe)


def _sync_ingredient_catalog(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    ingredient_names: list[str],
) -> None:
    for name in ingredient_names:
        ingredient, created = crud.get_or_create_ingredient(session=session, name=name)
        if created:
            background_tasks.add_task(fetch_and_update_ingredient_image, ingredient.id)


@router.post("/", response_model=RecipePublic)
def create_recipe(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    recipe_in: RecipeCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    """Create a new recipe. Ingredients are added in the same request."""
    recipe = crud.create_recipe(
        session=session, recipe_in=recipe_in, owner_id=current_user.id
    )
    _sync_ingredient_catalog(
        session,
        background_tasks,
        [i.ingredient_name for i in recipe_in.ingredients or []],
    )
    return crud.recipe_to_public(recipe)


@router.put("/{id}", response_model=RecipePublic)
def update_recipe(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    recipe_in: RecipeUpdate,
    background_tasks: BackgroundTasks,
) -> Any:
    """Update a recipe. If `ingredients` is provided the list is fully replaced."""
    recipe: Recipe | None = crud.get_recipe(session=session, recipe_id=id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if not current_user.is_superuser and recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if recipe.is_public and recipe_in.is_public is False:
        raise HTTPException(
            status_code=422, detail="Cannot make a public recipe private"
        )
    recipe = crud.update_recipe(session=session, db_recipe=recipe, recipe_in=recipe_in)
    _sync_ingredient_catalog(
        session,
        background_tasks,
        [i.ingredient_name for i in recipe_in.ingredients or []],
    )
    return crud.recipe_to_public(recipe)


@router.post("/{id}/reimport", response_model=RecipePublic)
def reimport_recipe(
    *,
    session: SessionDep,
    _current_user: Annotated[User, Depends(get_current_active_superuser)],
    id: uuid.UUID,
    body: ReimportRequest,
) -> Any:
    """Re-fetch and re-parse a recipe from its source URL. Superuser only.

    Fully replaces the recipe's content (title, description, ingredients, steps,
    image) while preserving its id, owner, and creation date.
    """
    recipe = crud.get_recipe(session=session, recipe_id=id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if not recipe.source_url:
        raise HTTPException(
            status_code=422, detail="Recipe has no source URL to reimport from"
        )
    try:
        parsed = import_recipe_from_url(recipe.source_url, language=body.language)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Failed to parse recipe: {exc}"
        ) from exc
    recipe = crud.update_recipe(
        session=session, db_recipe=recipe, recipe_in=_parsed_to_update(parsed)
    )
    return crud.recipe_to_public(recipe)


@router.delete("/{id}")
def delete_recipe(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """Delete a recipe (owner or superuser only)."""
    recipe = crud.get_recipe(session=session, recipe_id=id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if not current_user.is_superuser and recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    crud.delete_recipe(session=session, recipe=recipe)
    return Message(message="Recipe deleted successfully")


@router.post("/import-url", response_model=ParsedRecipe)
def import_recipe_url(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: ImportUrlRequest,
) -> Any:
    """Parse a recipe from a URL using AI. Returns pre-filled data for review — does NOT save.

    If the current user already has a saved recipe with the same source URL, that
    recipe's data is returned immediately without calling the LLM.

    Requires ANTHROPIC_API_KEY to be configured. Returns 503 if not set.
    """
    url = str(body.url)
    existing = crud.get_recipe_by_source_url(
        session=session, owner_id=current_user.id, source_url=url
    )
    if existing:
        return _recipe_to_parsed(existing)

    try:
        parsed = import_recipe_from_url(url, language=body.language)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Failed to parse recipe: {exc}"
        ) from exc
    return parsed
