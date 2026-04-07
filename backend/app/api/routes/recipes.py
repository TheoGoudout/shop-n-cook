import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    Recipe,
    RecipeCreate,
    RecipePublic,
    RecipesPublic,
    RecipeUpdate,
)
from app.services.recipe_import import ParsedRecipe, import_recipe_from_url

router = APIRouter(prefix="/recipes", tags=["recipes"])


class ImportUrlRequest(BaseModel):
    url: HttpUrl


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
        parsed = import_recipe_from_url(str(body.url))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Failed to parse recipe: {exc}"
        ) from exc
    return parsed
