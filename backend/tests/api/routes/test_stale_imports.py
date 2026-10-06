"""The admin's bulk reimport endpoints. Fetching and the model are mocked."""

import json
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import Recipe, RecipeCreate
from app.models.recipe import ImportSource
from app.services.recipe_import import IMPORT_VERSION
from app.services.store_providers.families.http_client import FetchedPage
from tests.utils.user import create_random_user

URL = f"{settings.API_V1_STR}/recipes/stale-imports"


def _stale_recipe(db: Session) -> Recipe:
    db.execute(update(Recipe).values(import_version=IMPORT_VERSION))
    db.commit()
    owner = create_random_user(db)
    recipe = crud.create_recipe(
        session=db,
        recipe_in=RecipeCreate(
            title="Vieille recette",
            source_url=f"https://{uuid.uuid4().hex[:10]}.example/1",
            import_consent=True,
            import_source=ImportSource.URL,
        ),
        owner_id=owner.id,
    )
    recipe.import_version = None
    db.add(recipe)
    db.commit()
    return recipe


def _llm() -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value.content = json.dumps(
        {"title": "Nouvelle", "servings": 6, "meal_type": "lunch"}
    )
    return llm


def test_status_counts_stale_recipes(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    _stale_recipe(db)

    response = client.get(URL, headers=superuser_token_headers)

    assert response.status_code == 200
    assert response.json() == {
        "import_version": IMPORT_VERSION,
        "stale_count": 1,
        "failed_count": 0,
        "running": False,
    }


def test_status_and_reimport_are_for_superusers_only(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    assert client.get(URL, headers=normal_user_token_headers).status_code == 403
    response = client.post(
        f"{URL}/reimport", headers=normal_user_token_headers, json={}
    )
    assert response.status_code == 403


def test_reimport_runs_a_batch_in_the_background(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    recipe = _stale_recipe(db)

    with (
        patch(
            "app.services.store_providers.families.http_client.fetch",
            return_value=FetchedPage(status_code=200, text="<html></html>"),
        ),
        patch("app.services.recipe_import.llm.get_llm", return_value=_llm()),
        patch.object(settings, "RECIPE_CRAWL_DELAY_SECONDS", 0),
    ):
        response = client.post(
            f"{URL}/reimport",
            headers=superuser_token_headers,
            json={"limit": 5, "language": "fr"},
        )

    assert response.status_code == 202
    assert response.json()["running"] is True
    db.expire_all()
    refreshed = db.get(Recipe, recipe.id)
    assert refreshed is not None
    assert refreshed.import_version == IMPORT_VERSION
    # No language recorded: read in, and recorded as, the one asked for.
    assert refreshed.import_language == "fr"
    # Someone's recipe: completed, never replaced.
    assert refreshed.title == "Vieille recette"
    assert refreshed.servings == 6
    assert client.get(URL, headers=superuser_token_headers).json()["stale_count"] == 0


def test_reimport_refuses_while_a_batch_runs(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    with patch("app.services.recipe_reimport.is_running", return_value=True):
        response = client.post(
            f"{URL}/reimport", headers=superuser_token_headers, json={}
        )
    assert response.status_code == 409


def test_reimport_needs_an_ai_provider(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    with patch(
        "app.services.recipe_import.llm.get_llm", side_effect=ValueError("no key")
    ):
        response = client.post(
            f"{URL}/reimport", headers=superuser_token_headers, json={}
        )
    assert response.status_code == 503


def test_reimport_batch_size_is_bounded(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{URL}/reimport", headers=superuser_token_headers, json={"limit": 1000}
    )
    assert response.status_code == 422


def test_single_reimport_reads_the_recipe_in_its_import_language(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    recipe = _stale_recipe(db)
    recipe.import_language = "fr"
    db.add(recipe)
    db.commit()
    llm = _llm()

    with (
        patch(
            "app.services.recipe_import.scraper.fetch_page",
            return_value=("recipe text", None),
        ),
        patch("app.services.recipe_import.llm.get_llm", return_value=llm),
    ):
        response = client.post(
            f"{settings.API_V1_STR}/recipes/{recipe.id}/reimport",
            headers=superuser_token_headers,
            json={"language": "en"},
        )

    assert response.status_code == 200
    assert "French" in llm.invoke.call_args.args[0][0].content
    db.expire_all()
    refreshed = db.get(Recipe, recipe.id)
    assert refreshed is not None
    assert refreshed.import_language == "fr"


def test_single_reimport_stamps_the_current_version(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    recipe = _stale_recipe(db)

    with (
        patch(
            "app.services.recipe_import.scraper.fetch_page",
            return_value=("recipe text", None),
        ),
        patch("app.services.recipe_import.llm.get_llm", return_value=_llm()),
    ):
        response = client.post(
            f"{settings.API_V1_STR}/recipes/{recipe.id}/reimport",
            headers=superuser_token_headers,
            json={},
        )

    assert response.status_code == 200
    db.expire_all()
    refreshed = db.get(Recipe, recipe.id)
    assert refreshed is not None
    assert refreshed.import_version == IMPORT_VERSION
    # No language recorded and none asked for: read, and recorded, as English.
    assert refreshed.import_language == "en"
