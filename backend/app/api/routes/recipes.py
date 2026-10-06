import uuid
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
from sqlmodel import Session, col, select
from starlette.concurrency import run_in_threadpool

from app import crud
from app.api.deps import (
    CurrentUser,
    PriceBookDep,
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
    RecipeIngredientCreate,
    RecipePublic,
    RecipesPublic,
    RecipeUpdate,
    StaleImportsPublic,
)
from app.models.ingredient import Ingredient, IngredientCategory
from app.models.recipe import Difficulty, ImportSource, MealType, Season
from app.models.user import User
from app.services import recipe_reimport
from app.services.ingredient_image import fetch_and_update_ingredients_batch
from app.services.recipe_crawler.crawler import llm_configured
from app.services.recipe_import import (
    IMPORT_VERSION,
    InvalidPhotoError,
    NoRecipeFoundError,
    ParsedIngredient,
    ParsedRecipe,
    ParsedStep,
    import_recipe_from_photos,
    import_recipe_from_url,
    validate_photos,
)
from app.services.recipe_import.mapping import parsed_to_update

router = APIRouter(prefix="/recipes", tags=["recipes"])


class ImportUrlRequest(BaseModel):
    url: HttpUrl
    language: str | None = None


class ReimportRequest(BaseModel):
    language: str | None = None


class ReimportStaleRequest(BaseModel):
    #: Each recipe is one page fetch and one model call.
    limit: int = Field(default=20, ge=1, le=200)
    #: The language to read pages in when the recipe does not say: any recipe
    #: that was not crawled.
    language: str | None = None


def _recipe_to_parsed(recipe: Recipe, session: Session) -> ParsedRecipe:
    """Convert a saved Recipe back to ParsedRecipe format (used as DB cache hit)."""
    names = [ri.ingredient_name for ri in recipe.recipe_ingredients]
    catalog: dict[str, Ingredient] = {}
    if names:
        rows = session.exec(
            select(Ingredient).where(col(Ingredient.name).in_(names))
        ).all()
        catalog = {row.name: row for row in rows}

    ri_map = {ri.id: ri for ri in recipe.recipe_ingredients}
    ingredients = [
        ParsedIngredient(
            name=ri.ingredient_name,
            name_en=catalog[ri.ingredient_name].name_en
            if ri.ingredient_name in catalog
            else None,
            category=catalog[ri.ingredient_name].category
            if ri.ingredient_name in catalog
            else IngredientCategory.OTHER,
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


@router.get("/public", response_model=RecipesPublic)
def read_public_recipes(
    session: SessionDep,
    _current_user: CurrentUser,
    prices: PriceBookDep,
    owner_id: uuid.UUID | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
    seasons: list[Season] | None = Query(default=None),
    is_vegan: bool | None = None,
    is_vegetarian: bool | None = None,
    is_gluten_free: bool | None = None,
    is_dairy_free: bool | None = None,
    difficulty: Difficulty | None = None,
    meal_type: MealType | None = None,
    cuisine_type: str | None = None,
) -> Any:
    """List all public recipes. Optionally filter by owner_id or search query."""
    recipes, count = crud.get_public_recipes(
        session=session,
        owner_id=owner_id,
        search=search,
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
    return RecipesPublic(
        data=[crud.recipe_to_public(r, prices=prices) for r in recipes], count=count
    )


@router.get("/", response_model=RecipesPublic)
def read_recipes(
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
    seasons: list[Season] | None = Query(default=None),
    is_vegan: bool | None = None,
    is_vegetarian: bool | None = None,
    is_gluten_free: bool | None = None,
    is_dairy_free: bool | None = None,
    difficulty: Difficulty | None = None,
    meal_type: MealType | None = None,
    cuisine_type: str | None = None,
) -> Any:
    """List recipes. Superusers see all; regular users see only their own."""
    owner_id = None if current_user.is_superuser else current_user.id
    recipes, count = crud.get_recipes(
        session=session,
        owner_id=owner_id,
        search=search,
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
    return RecipesPublic(
        data=[crud.recipe_to_public(r, prices=prices) for r in recipes], count=count
    )


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
def read_recipe(
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
    id: uuid.UUID,
) -> Any:
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
    _sync_ingredient_catalog(session, background_tasks, recipe_in.ingredients or [])
    return crud.recipe_to_public(recipe, prices=prices)


@router.put("/{id}", response_model=RecipePublic)
def update_recipe(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    prices: PriceBookDep,
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
    _sync_ingredient_catalog(session, background_tasks, recipe_in.ingredients or [])
    return crud.recipe_to_public(recipe, prices=prices)


@router.post("/{id}/reimport", response_model=RecipePublic)
def reimport_recipe(
    *,
    session: SessionDep,
    _current_user: Annotated[User, Depends(get_current_active_superuser)],
    prices: PriceBookDep,
    id: uuid.UUID,
    body: ReimportRequest,
    background_tasks: BackgroundTasks,
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
    recipe_in = parsed_to_update(parsed)
    if recipe.import_source == ImportSource.URL:
        recipe.import_version = IMPORT_VERSION
    recipe = crud.update_recipe(session=session, db_recipe=recipe, recipe_in=recipe_in)
    _sync_ingredient_catalog(session, background_tasks, recipe_in.ingredients or [])
    return crud.recipe_to_public(recipe, prices=prices)


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
        return _recipe_to_parsed(existing, session)

    try:
        parsed = import_recipe_from_url(url, language=body.language)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Failed to parse recipe: {exc}"
        ) from exc
    return parsed


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
    photos: Annotated[list[UploadFile], File()],
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

    try:
        # The provider call blocks for up to two minutes; keep it off the event loop.
        parsed = await run_in_threadpool(
            import_recipe_from_photos, validated, language=language
        )
    except NoRecipeFoundError as exc:
        raise HTTPException(status_code=422, detail="no_recipe_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Failed to parse recipe: {exc}"
        ) from exc
    return parsed
