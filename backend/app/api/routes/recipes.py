import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
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
from app.services.recipe_import import ParsedRecipe, import_recipe_from_url

router = APIRouter(prefix="/recipes", tags=["recipes"])


class ImportUrlRequest(BaseModel):
    url: HttpUrl
    language: str | None = None


class ReimportRequest(BaseModel):
    language: str | None = None


def _parsed_to_update(parsed: ParsedRecipe) -> RecipeUpdate:
    name_to_idx = {ing.name.lower(): i for i, ing in enumerate(parsed.ingredients)}
    ingredients = [
        RecipeIngredientCreate(
            ingredient_name=ing.name,
            ingredient_category=ing.category,
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


@router.get("/", response_model=RecipesPublic)
def read_recipes(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List recipes. Superusers see all; regular users see only their own."""
    owner_id = None if current_user.is_superuser else current_user.id
    recipes, count = crud.get_recipes(
        session=session, owner_id=owner_id, skip=skip, limit=limit
    )
    return RecipesPublic(data=[crud.recipe_to_public(r) for r in recipes], count=count)


@router.get("/{id}", response_model=RecipePublic)
def read_recipe(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """Get a single recipe by ID."""
    recipe = crud.get_recipe(session=session, recipe_id=id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if not current_user.is_superuser and recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return crud.recipe_to_public(recipe)


@router.post("/", response_model=RecipePublic)
def create_recipe(
    *, session: SessionDep, current_user: CurrentUser, recipe_in: RecipeCreate
) -> Any:
    """Create a new recipe. Ingredients are added in the same request."""
    recipe = crud.create_recipe(
        session=session, recipe_in=recipe_in, owner_id=current_user.id
    )
    return crud.recipe_to_public(recipe)


@router.put("/{id}", response_model=RecipePublic)
def update_recipe(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    recipe_in: RecipeUpdate,
) -> Any:
    """Update a recipe. If `ingredients` is provided the list is fully replaced."""
    recipe: Recipe | None = crud.get_recipe(session=session, recipe_id=id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if not current_user.is_superuser and recipe.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    recipe = crud.update_recipe(session=session, db_recipe=recipe, recipe_in=recipe_in)
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
    _current_user: CurrentUser,
    body: ImportUrlRequest,
) -> Any:
    """Parse a recipe from a URL using AI. Returns pre-filled data for review — does NOT save.

    Requires ANTHROPIC_API_KEY to be configured. Returns 503 if not set.
    """
    try:
        parsed = import_recipe_from_url(str(body.url), language=body.language)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Failed to parse recipe: {exc}"
        ) from exc
    return parsed
