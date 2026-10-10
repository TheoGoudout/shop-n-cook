import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from pydantic import BaseModel, Field, HttpUrl
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from app import crud
from app.api.deps import (
    CurrentUser,
    EditableRecipe,
    PriceBookDep,
    ReadableRecipe,
    SessionDep,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.db import engine
from app.core.limiter import limiter, user_or_ip_key
from app.models import (
    Message,
    Recipe,
    RecipeCreate,
    RecipeFilters,
    RecipeIngredientCreate,
    RecipePublic,
    RecipesPublic,
    RecipeUpdate,
    StaleImportsPublic,
)
from app.models.recipe import ImportSource
from app.services import recipe_reimport
from app.services.ingredient_image import fetch_and_update_ingredients_batch
from app.services.recipe_crawler.crawler import llm_configured
from app.services.recipe_import import (
    IMPORT_VERSION,
    InvalidPhotoError,
    NoRecipeFoundError,
    ParsedRecipe,
    import_recipe_from_photos,
    import_recipe_from_url,
    validate_photos,
)
from app.services.recipe_import.mapping import parsed_to_update, recipe_to_parsed

router = APIRouter(prefix="/recipes", tags=["recipes"])


class ImportUrlRequest(BaseModel):
    url: HttpUrl
    language: str | None = None


class ReimportRequest(BaseModel):
    #: Used only when the recipe does not record the language it was read in.
    language: str | None = None


class ReimportStaleRequest(BaseModel):
    #: Each recipe is one page fetch and one model call.
    limit: int = Field(default=20, ge=1, le=200)
    #: The language to read pages in when the recipe does not record one.
    language: str | None = None


class RecipeListQuery(RecipeFilters):
    skip: int = 0
    limit: int = 100


class PublicRecipeListQuery(RecipeListQuery):
    owner_id: uuid.UUID | None = None


@contextmanager
def _import_errors() -> Iterator[None]:
    """Turn a failed import into the HTTP error the client knows how to show."""
    try:
        yield
    except NoRecipeFoundError as exc:
        raise HTTPException(status_code=422, detail="no_recipe_found") from exc
    except ValueError as exc:
        # The pipeline raises ValueError when no AI provider is configured.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Failed to parse recipe: {exc}"
        ) from exc


def _recipes_page(
    recipes: list[Recipe], count: int, prices: PriceBookDep
) -> RecipesPublic:
    return RecipesPublic(
        data=[crud.recipe_to_public(r, prices=prices) for r in recipes], count=count
    )


@router.get("/public", response_model=RecipesPublic)
def read_public_recipes(
    session: SessionDep,
    _current_user: CurrentUser,
    prices: PriceBookDep,
    query: Annotated[PublicRecipeListQuery, Query()],
) -> Any:
    """List all public recipes. Optionally filter by owner_id or search query."""
    recipes, count = crud.get_recipes(
        session=session,
        filters=query,
        owner_id=query.owner_id,
        public_only=True,
        skip=query.skip,
        limit=query.limit,
    )
    return _recipes_page(recipes, count, prices)


@router.get("/", response_model=RecipesPublic)
def read_recipes(
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    query: Annotated[RecipeListQuery, Query()],
) -> Any:
    """List recipes. Superusers see all; regular users see only their own."""
    recipes, count = crud.get_recipes(
        session=session,
        filters=query,
        owner_id=None if current_user.is_superuser else current_user.id,
        skip=query.skip,
        limit=query.limit,
    )
    return _recipes_page(recipes, count, prices)


def _stale_imports_status(session: Session) -> StaleImportsPublic:
    stale, tried = recipe_reimport.count_stale(session)
    return StaleImportsPublic(
        import_version=IMPORT_VERSION,
        stale_count=stale,
        failed_count=tried,
        running=recipe_reimport.is_running(engine),
    )


@router.get(
    "/stale-imports",
    response_model=StaleImportsPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def read_stale_imports(session: SessionDep) -> Any:
    """How many recipes an older import pipeline produced. Superuser only."""
    return _stale_imports_status(session)


@router.post(
    "/stale-imports/reimport",
    response_model=StaleImportsPublic,
    status_code=202,
    dependencies=[Depends(get_current_active_superuser)],
)
def reimport_stale_imports(
    session: SessionDep, body: ReimportStaleRequest, background_tasks: BackgroundTasks
) -> Any:
    """Start reimporting up to ``limit`` stale recipes, in the background.

    Crawled recipes are replaced; everyone else's are only completed. See
    ``services/recipe_reimport.py``. Superuser only.
    """
    if recipe_reimport.is_running(engine):
        raise HTTPException(status_code=409, detail="A reimport is already running")
    if not llm_configured():
        raise HTTPException(status_code=503, detail="No AI provider is configured")
    background_tasks.add_task(
        recipe_reimport.run_batch, engine, limit=body.limit, language=body.language
    )
    return _stale_imports_status(session).model_copy(update={"running": True})


@router.get("/{id}", response_model=RecipePublic)
def read_recipe(recipe: ReadableRecipe, prices: PriceBookDep) -> Any:
    """Get a single recipe by ID. Public recipes are visible to all authenticated users."""
    return crud.recipe_to_public(recipe, prices=prices)


def _sync_ingredient_catalog(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    ingredients: list[RecipeIngredientCreate],
) -> None:
    ids_to_update = crud.sync_ingredient_catalog(
        session=session, ingredients=ingredients
    )
    if ids_to_update:
        background_tasks.add_task(fetch_and_update_ingredients_batch, ids_to_update)


def _save_update(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    recipe: Recipe,
    recipe_in: RecipeUpdate,
    prices: PriceBookDep,
) -> RecipePublic:
    recipe = crud.update_recipe(session=session, db_recipe=recipe, recipe_in=recipe_in)
    _sync_ingredient_catalog(session, background_tasks, recipe_in.ingredients or [])
    return crud.recipe_to_public(recipe, prices=prices)


@router.post("/", response_model=RecipePublic)
def create_recipe(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    recipe_in: RecipeCreate,
    background_tasks: BackgroundTasks,
) -> Any:
    """Create a new recipe. Ingredients are added in the same request."""
    recipe = crud.create_recipe(
        session=session, recipe_in=recipe_in, owner_id=current_user.id
    )
    _sync_ingredient_catalog(session, background_tasks, recipe_in.ingredients)
    return crud.recipe_to_public(recipe, prices=prices)


@router.put("/{id}", response_model=RecipePublic)
def update_recipe(
    *,
    session: SessionDep,
    recipe: EditableRecipe,
    prices: PriceBookDep,
    recipe_in: RecipeUpdate,
    background_tasks: BackgroundTasks,
) -> Any:
    """Update a recipe. If `ingredients` is provided the list is fully replaced."""
    if recipe.is_public and recipe_in.is_public is False:
        raise HTTPException(
            status_code=422, detail="Cannot make a public recipe private"
        )
    return _save_update(session, background_tasks, recipe, recipe_in, prices)


@router.post(
    "/{id}/reimport",
    response_model=RecipePublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def reimport_recipe(
    *,
    session: SessionDep,
    prices: PriceBookDep,
    id: uuid.UUID,
    body: ReimportRequest,
    background_tasks: BackgroundTasks,
) -> Any:
    """Re-fetch and re-parse a recipe from its source URL. Superuser only.

    Fully replaces the recipe's content (title, description, ingredients, steps,
    image) while preserving its id, owner, and creation date. The page is read
    in the language the recipe was imported in; ``language`` only stands in
    for a recipe that does not record one.
    """
    recipe = crud.get_recipe(session=session, recipe_id=id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if not recipe.source_url:
        raise HTTPException(
            status_code=422, detail="Recipe has no source URL to reimport from"
        )
    with _import_errors():
        parsed = import_recipe_from_url(
            recipe.source_url, language=recipe.import_language or body.language
        )
    if recipe.import_source == ImportSource.URL:
        recipe.import_version = IMPORT_VERSION
    recipe.import_language = parsed.language
    return _save_update(
        session, background_tasks, recipe, parsed_to_update(parsed), prices
    )


@router.delete("/{id}")
def delete_recipe(session: SessionDep, recipe: EditableRecipe) -> Message:
    """Delete a recipe (owner or superuser only)."""
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
        catalog = crud.get_ingredients_by_name(
            session=session,
            names=[ri.ingredient_name for ri in existing.recipe_ingredients],
        )
        return recipe_to_parsed(existing, catalog)
    with _import_errors():
        return import_recipe_from_url(url, language=body.language)


async def _read_upload(photo: UploadFile) -> bytes:
    """Read one upload, refusing to buffer more than the configured limit.

    Reading one byte past the limit is enough to reject the file without pulling
    a whole oversized upload into memory.
    """
    data = await photo.read(settings.RECIPE_PHOTO_MAX_BYTES + 1)
    await photo.close()
    return data


@router.post("/import-photos", response_model=ParsedRecipe)
@limiter.limit(settings.RECIPE_PHOTO_RATE_LIMIT, key_func=user_or_ip_key)
async def import_recipe_photos(
    *,
    request: Request,  # noqa: ARG001 — consumed by slowapi rate-limit decorator
    current_user: CurrentUser,  # noqa: ARG001 — auth gate, and the rate-limit key
    # FastAPI now describes uploads with OpenAPI 3.1 `contentMediaType`, which
    # the pinned @hey-api/openapi-ts types as `string`; `format: binary` keeps the
    # generated client typed as `Blob | File`.
    photos: Annotated[
        list[UploadFile],
        File(json_schema_extra={"items": {"type": "string", "format": "binary"}}),
    ],
    language: Annotated[str | None, Form()] = None,
) -> Any:
    """Parse a recipe from photos using AI. Returns pre-filled data for review — does NOT save.

    Every photo is treated as part of a single recipe (e.g. the facing pages of a
    cookbook spread). Images are validated, sent to the vision model and then
    discarded — nothing is stored.

    Requires a provider API key to be configured. Returns 503 if not set.
    """
    try:
        validated = validate_photos([await _read_upload(photo) for photo in photos])
    except InvalidPhotoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with _import_errors():
        # The provider call blocks for up to two minutes; keep it off the event loop.
        return await run_in_threadpool(
            import_recipe_from_photos, validated, language=language
        )
