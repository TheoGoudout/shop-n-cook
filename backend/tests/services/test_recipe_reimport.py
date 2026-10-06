"""Bulk reimport of recipes an older import pipeline produced, on the real
database.

What matters most: a crawled recipe is replaced, but a person's recipe is only
ever completed, and a recipe that cannot be refreshed never blocks the queue.
"""

import json
import uuid
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text, update
from sqlmodel import Session

from app import crud
from app.core.db import engine
from app.models import (
    CrawledRecipe,
    CrawlStatus,
    Recipe,
    RecipeCreate,
    RecipeIngredientCreate,
    RecipeStepCreate,
    Unit,
)
from app.models.recipe import ImportSource, MealType
from app.services import recipe_reimport
from app.services.recipe_crawler.sites import SITES
from app.services.recipe_import import IMPORT_VERSION
from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families.http_client import FetchedPage
from tests.utils.user import create_random_user

FETCH = "app.services.store_providers.families.http_client.fetch"
GET_LLM = "app.services.recipe_import.llm.get_llm"


@dataclass
class FakeWeb:
    pages: dict[str, tuple[int, str]] = field(default_factory=dict)
    requested: list[str] = field(default_factory=list)
    down: set[str] = field(default_factory=set)

    def add(self, url: str, *, status: int = 200, robots: str = "") -> str:
        origin = "/".join(url.split("/")[:3])
        self.pages.setdefault(f"{origin}/robots.txt", (200, robots or "User-agent: *"))
        self.pages[url] = (status, "<html><body><h1>Recette</h1></body></html>")
        return url

    def fetch(self, url: str, **_: Any) -> FetchedPage:
        if any(url.startswith(origin) for origin in self.down):
            raise ProviderUnavailableError(f"{url} could not be reached")
        self.requested.append(url)
        status, body = self.pages.get(url, (404, "Not found"))
        return FetchedPage(status_code=status, text=body)


def _reply(**overrides: Any) -> MagicMock:
    data: dict[str, Any] = {
        "title": "Blanquette de veau",
        "description": "Un classique.",
        "servings": 4,
        "meal_type": "dinner",
        "cuisine_type": "French",
        "is_vegan": True,
        "ingredients": [
            {"name": "veau", "quantity": 800, "unit": "g", "category": "meat"},
            {"name": "carotte", "quantity": 2, "unit": "piece"},
        ],
        "steps": [
            {"instruction": "Couper le veau.", "ingredient_names": ["veau"]},
            {"instruction": "Ajouter les carottes.", "ingredient_names": ["carotte"]},
        ],
    }
    data.update(overrides)
    llm = MagicMock()
    llm.invoke.return_value.content = json.dumps(data)
    return llm


@pytest.fixture(autouse=True)
def only_these_recipes_are_stale(db: Session) -> None:
    """Other tests' recipes share the database; none of them is stale here."""
    db.execute(update(Recipe).values(import_version=IMPORT_VERSION))
    db.commit()


@pytest.fixture
def web() -> Generator[FakeWeb, None, None]:
    fake = FakeWeb()
    with patch(FETCH, side_effect=fake.fetch):
        yield fake


@pytest.fixture(autouse=True)
def llm() -> Generator[MagicMock, None, None]:
    reply = _reply()
    with patch(GET_LLM, return_value=reply):
        yield reply


def _host() -> str:
    return f"https://{uuid.uuid4().hex[:10]}.example"


def _recipe(
    db: Session,
    url: str,
    *,
    version: int | None = None,
    source: ImportSource | None = ImportSource.URL,
    **fields: Any,
) -> Recipe:
    owner = create_random_user(db)
    recipe = crud.create_recipe(
        session=db,
        recipe_in=RecipeCreate(
            title=fields.pop("title", "Ma blanquette"),
            source_url=url,
            import_consent=True,
            import_source=source,
            **fields,
        ),
        owner_id=owner.id,
    )
    recipe.import_version = version
    db.add(recipe)
    db.commit()
    return recipe


def _crawled(db: Session, recipe: Recipe) -> None:
    db.add(
        CrawledRecipe(
            site=SITES[0].slug,
            url=recipe.source_url or "",
            status=CrawlStatus.IMPORTED,
            recipe_id=recipe.id,
        )
    )
    db.commit()


def _run(db: Session, **kwargs: Any) -> recipe_reimport.ReimportReport:
    options: dict[str, Any] = {"limit": 10, "language": "en", "delay_seconds": 0}
    options.update(kwargs)
    return recipe_reimport.reimport_stale(db, **options)


def _fresh(db: Session, recipe: Recipe) -> Recipe:
    db.expire_all()
    found = db.get(Recipe, recipe.id)
    assert found is not None
    return found


def test_only_url_imports_from_an_older_pipeline_are_stale(
    db: Session, web: FakeWeb
) -> None:
    host = _host()
    legacy = _recipe(db, web.add(f"{host}/1"))
    older = _recipe(db, web.add(f"{host}/2"), version=IMPORT_VERSION - 1)
    _recipe(db, web.add(f"{host}/3"), version=IMPORT_VERSION)
    _recipe(db, web.add(f"{host}/4"), source=ImportSource.PHOTO)
    _recipe(db, web.add(f"{host}/5"), source=None)

    assert recipe_reimport.count_stale(db) == (2, 0)

    report = _run(db)

    assert report == recipe_reimport.ReimportReport(updated=2)
    assert web.requested == [f"{host}/robots.txt", f"{host}/1", f"{host}/2"]
    assert _fresh(db, legacy).import_version == IMPORT_VERSION
    assert _fresh(db, older).import_version == IMPORT_VERSION
    assert recipe_reimport.count_stale(db) == (0, 0)


def test_a_new_url_import_is_stamped_with_the_current_version(db: Session) -> None:
    recipe = _recipe(db, f"{_host()}/1", version=IMPORT_VERSION)
    assert recipe.import_version == IMPORT_VERSION
    owner = create_random_user(db)
    typed = crud.create_recipe(
        session=db, recipe_in=RecipeCreate(title="À la main"), owner_id=owner.id
    )
    assert typed.import_version is None


def test_a_crawled_recipe_is_replaced_and_read_in_its_sites_language(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    recipe = _recipe(
        db,
        web.add(f"{_host()}/1"),
        description="Ancienne description",
        ingredients=[
            RecipeIngredientCreate(
                ingredient_name="veau", quantity=1, unit=Unit.KILOGRAM
            )
        ],
    )
    _crawled(db, recipe)

    assert _run(db, language="en").updated == 1

    recipe = _fresh(db, recipe)
    assert recipe.title == "Blanquette de veau"
    assert recipe.description == "Un classique."
    assert [ri.ingredient_name for ri in recipe.recipe_ingredients] == [
        "veau",
        "carotte",
    ]
    assert len(recipe.steps) == 2
    assert recipe.is_vegan
    assert recipe.import_version == IMPORT_VERSION
    system_prompt = llm.invoke.call_args.args[0][0].content
    assert "French" in system_prompt
    assert recipe.import_language == "fr", "the language used is recorded"


def test_a_crawled_recipe_is_not_replaced_by_an_incomplete_reply(
    db: Session, web: FakeWeb
) -> None:
    recipe = _recipe(db, web.add(f"{_host()}/1"), description="Ancienne")
    _crawled(db, recipe)

    with patch(GET_LLM, return_value=_reply(steps=[])):
        report = _run(db)

    assert report == recipe_reimport.ReimportReport(failed=1)
    recipe = _fresh(db, recipe)
    assert recipe.description == "Ancienne"
    assert recipe.import_version is None
    assert recipe.reimport_attempted_at is not None


def test_a_persons_recipe_is_only_completed(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    recipe = _recipe(
        db,
        web.add(f"{_host()}/1"),
        title="Blanquette de mamie",
        description="Ma version.",
        ingredients=[
            RecipeIngredientCreate(
                ingredient_name="carotte", quantity=3, unit=Unit.PIECE
            ),
            RecipeIngredientCreate(
                ingredient_name="veau", quantity=1, unit=Unit.KILOGRAM
            ),
        ],
    )

    assert _run(db, language="fr").updated == 1

    recipe = _fresh(db, recipe)
    # What the person wrote stays.
    assert recipe.title == "Blanquette de mamie"
    assert recipe.description == "Ma version."
    assert [(ri.ingredient_name, ri.quantity) for ri in recipe.recipe_ingredients] == [
        ("carotte", 3),
        ("veau", 1),
    ]
    assert not recipe.is_vegan, "a diet flag is never overruled"
    # What was missing is filled in; the new steps point at their ingredients.
    assert recipe.servings == 4
    assert recipe.meal_type == MealType.DINNER
    assert recipe.cuisine_type == "French"
    steps = sorted(recipe.steps, key=lambda s: s.step_number)
    assert [
        [si.recipe_ingredient.ingredient_name for si in s.step_ingredients]
        for s in steps
    ] == [
        ["veau"],
        ["carotte"],
    ]
    assert recipe.import_version == IMPORT_VERSION
    system_prompt = llm.invoke.call_args.args[0][0].content
    assert "French" in system_prompt, "read in the language the admin asked for"
    assert recipe.import_language == "fr"


def test_a_recipe_is_read_again_in_the_language_it_was_imported_in(
    db: Session, web: FakeWeb, llm: MagicMock
) -> None:
    recipe = _recipe(db, web.add(f"{_host()}/1"), import_language="fr-FR")
    assert recipe.import_language == "fr"

    assert _run(db, language="en").updated == 1

    system_prompt = llm.invoke.call_args.args[0][0].content
    assert "French" in system_prompt, "never translated into the admin's language"
    assert _fresh(db, recipe).import_language == "fr"


def test_a_typed_in_recipe_records_no_import_language(db: Session) -> None:
    owner = create_random_user(db)
    typed = crud.create_recipe(
        session=db, recipe_in=RecipeCreate(title="À la main"), owner_id=owner.id
    )
    assert typed.import_language is None


def test_a_recipe_that_fails_goes_to_the_back_of_the_queue(
    db: Session, web: FakeWeb
) -> None:
    host = _host()
    refused = _recipe(
        db, web.add(f"{host}/private/1", robots="User-agent: *\nDisallow: /private/")
    )
    gone = _recipe(db, web.add(f"{host}/2", status=404))
    good = _recipe(db, web.add(f"{host}/3"))

    assert _run(db, limit=2) == recipe_reimport.ReimportReport(failed=2)
    assert f"{host}/private/1" not in web.requested
    assert _fresh(db, refused).reimport_attempted_at is not None
    assert _fresh(db, gone).reimport_attempted_at is not None
    assert recipe_reimport.count_stale(db) == (3, 2)

    # The next batch starts with the recipe nobody tried yet.
    assert _run(db, limit=1) == recipe_reimport.ReimportReport(updated=1)
    assert _fresh(db, good).import_version == IMPORT_VERSION
    assert recipe_reimport.count_stale(db) == (2, 2)


def test_a_host_that_is_down_is_left_for_a_later_batch(
    db: Session, web: FakeWeb
) -> None:
    down, up = _host(), _host()
    web.down.add(down)
    first = _recipe(db, web.add(f"{down}/1"))
    _recipe(db, web.add(f"{down}/2"))
    _recipe(db, web.add(f"{up}/1"))

    report = _run(db)

    assert report == recipe_reimport.ReimportReport(updated=1, skipped=2)
    # Nothing is recorded against the down host's recipes.
    assert _fresh(db, first).reimport_attempted_at is None
    assert recipe_reimport.count_stale(db) == (2, 0)


def test_a_throttling_host_is_not_asked_again_in_the_same_batch(
    db: Session, web: FakeWeb
) -> None:
    host = _host()
    _recipe(db, web.add(f"{host}/1", status=429))
    _recipe(db, web.add(f"{host}/2"))

    assert _run(db) == recipe_reimport.ReimportReport(skipped=2)
    assert f"{host}/2" not in web.requested


def test_requests_to_one_host_are_spaced(db: Session, web: FakeWeb) -> None:
    host = _host()
    _recipe(db, web.add(f"{host}/1"))
    _recipe(db, web.add(f"{host}/2"))
    waits: list[float] = []

    def pause(seconds: float) -> bool:
        waits.append(seconds)
        return False

    _run(db, delay_seconds=30, pause=pause)

    assert len(waits) == 1
    assert 29 < waits[0] <= 30


def test_nothing_stale_fetches_nothing(db: Session, web: FakeWeb) -> None:
    assert _run(db) == recipe_reimport.ReimportReport()
    assert web.requested == []


def test_one_batch_at_a_time(db: Session, web: FakeWeb) -> None:
    _recipe(db, web.add(f"{_host()}/1"))
    assert not recipe_reimport.is_running(engine)

    with engine.connect() as other_worker:
        other_worker.execute(
            text("SELECT pg_advisory_lock(:key)"),
            {"key": recipe_reimport.ADVISORY_LOCK_KEY},
        )
        assert recipe_reimport.is_running(engine)
        assert recipe_reimport.run_batch(engine, limit=10, language=None) is None
        other_worker.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": recipe_reimport.ADVISORY_LOCK_KEY},
        )

    with patch.object(recipe_reimport.settings, "RECIPE_CRAWL_DELAY_SECONDS", 0):
        report = recipe_reimport.run_batch(engine, limit=10, language=None)
    assert report == recipe_reimport.ReimportReport(updated=1)
    assert not recipe_reimport.is_running(engine)


def test_ingredients_alone_are_filled_around_the_existing_steps(
    db: Session, web: FakeWeb
) -> None:
    recipe = _recipe(
        db,
        web.add(f"{_host()}/1"),
        servings=2,
        steps=[RecipeStepCreate(step_number=1, instruction="Ma méthode.")],
    )

    _run(db)

    recipe = _fresh(db, recipe)
    assert recipe.servings == 2
    assert [s.instruction for s in recipe.steps] == ["Ma méthode."]
    # It had no ingredients: they are filled in, and its own steps kept.
    assert [ri.ingredient_name for ri in recipe.recipe_ingredients] == [
        "veau",
        "carotte",
    ]
