"""Tests for the AI recipe import endpoint. All LLM and HTTP calls are mocked."""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import settings


def _make_llm_response(data: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = json.dumps(data)
    return msg


_SAMPLE_RECIPE = {
    "title": "Test Pasta",
    "description": "A simple pasta dish",
    "instructions": "Boil pasta. Add sauce.",
    "servings": 2,
    "prep_time_minutes": 10,
    "cook_time_minutes": 20,
    "ingredients": [
        {
            "name": "pasta",
            "category": "grains",
            "quantity": 200.0,
            "unit": "g",
            "notes": None,
        }
    ],
}


def test_import_recipe_url_success(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _make_llm_response(_SAMPLE_RECIPE)

    with (
        patch(
            "app.services.recipe_import._fetch_page",
            return_value=("some recipe text", None),
        ),
        patch("app.services.recipe_import._get_llm", return_value=llm_mock),
    ):
        response = client.post(
            f"{settings.API_V1_STR}/recipes/import-url",
            headers=superuser_token_headers,
            json={"url": "https://example.com/recipe"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Pasta"
    assert data["servings"] == 2
    assert len(data["ingredients"]) == 1
    assert data["ingredients"][0]["name"] == "pasta"


def test_import_recipe_url_no_api_key_returns_503(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    with (
        patch(
            "app.services.recipe_import._fetch_page", return_value=("some text", None)
        ),
        patch(
            "app.services.recipe_import._get_llm",
            side_effect=ValueError("ANTHROPIC_API_KEY is not configured"),
        ),
    ):
        response = client.post(
            f"{settings.API_V1_STR}/recipes/import-url",
            headers=superuser_token_headers,
            json={"url": "https://example.com/recipe"},
        )

    assert response.status_code == 503


def test_import_recipe_url_parse_error_returns_422(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    with (
        patch(
            "app.services.recipe_import._fetch_page",
            return_value=("not a recipe", None),
        ),
        patch(
            "app.services.recipe_import._get_llm",
            side_effect=RuntimeError("LLM unavailable"),
        ),
    ):
        response = client.post(
            f"{settings.API_V1_STR}/recipes/import-url",
            headers=superuser_token_headers,
            json={"url": "https://example.com/bad"},
        )

    assert response.status_code == 422


def test_import_recipe_url_requires_auth(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/recipes/import-url",
        json={"url": "https://example.com/recipe"},
    )
    assert response.status_code == 401


def test_import_recipe_url_strips_markdown_fences(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    fenced = f"```json\n{json.dumps(_SAMPLE_RECIPE)}\n```"
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = MagicMock(content=fenced)

    with (
        patch("app.services.recipe_import._fetch_page", return_value=("text", None)),
        patch("app.services.recipe_import._get_llm", return_value=llm_mock),
    ):
        response = client.post(
            f"{settings.API_V1_STR}/recipes/import-url",
            headers=superuser_token_headers,
            json={"url": "https://example.com/recipe"},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Test Pasta"


def test_get_llm_unknown_provider() -> None:
    from unittest.mock import patch as p

    from app.services.recipe_import import _get_llm

    with p.object(settings, "AI_PROVIDER", "unknown"):
        try:
            _get_llm()
            raise AssertionError("should raise")
        except ValueError as exc:
            assert "Unknown AI_PROVIDER" in str(exc)


def test_import_recipe_filters_null_quantity_ingredients(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    recipe_with_garnish = {
        **_SAMPLE_RECIPE,
        "ingredients": [
            {
                "name": "pasta",
                "category": "grains",
                "quantity": 200.0,
                "unit": "g",
                "notes": None,
            },
            {
                "name": "maple syrup",
                "category": "pantry",
                "quantity": None,
                "unit": None,
                "notes": "to serve",
            },
            {
                "name": "butter",
                "category": "dairy",
                "quantity": None,
                "unit": None,
                "notes": "to serve",
            },
        ],
    }
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _make_llm_response(recipe_with_garnish)

    with (
        patch(
            "app.services.recipe_import._fetch_page",
            return_value=("some recipe text", None),
        ),
        patch("app.services.recipe_import._get_llm", return_value=llm_mock),
    ):
        response = client.post(
            f"{settings.API_V1_STR}/recipes/import-url",
            headers=superuser_token_headers,
            json={"url": "https://example.com/recipe"},
        )

    assert response.status_code == 200
    ingredients = response.json()["ingredients"]
    assert len(ingredients) == 1
    assert ingredients[0]["name"] == "pasta"


def test_import_returns_source_url_and_image_url(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _make_llm_response(_SAMPLE_RECIPE)

    with (
        patch(
            "app.services.recipe_import._fetch_page",
            return_value=("text", "https://example.com/image.jpg"),
        ),
        patch("app.services.recipe_import._get_llm", return_value=llm_mock),
    ):
        response = client.post(
            f"{settings.API_V1_STR}/recipes/import-url",
            headers=superuser_token_headers,
            json={"url": "https://example.com/recipe"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["source_url"] == "https://example.com/recipe"
    assert data["image_url"] == "https://example.com/image.jpg"


def test_configure_langsmith_sets_env() -> None:
    import os

    from app.services.recipe_import import _configure_langsmith

    with (
        patch.object(settings, "LANGCHAIN_TRACING_V2", True),
        patch.object(settings, "LANGCHAIN_API_KEY", "test-key"),
        patch.object(settings, "LANGCHAIN_PROJECT", "test-proj"),
        patch.object(
            settings, "LANGCHAIN_ENDPOINT", "https://eu.api.smith.langchain.com"
        ),
    ):
        _configure_langsmith()
        assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
        assert os.environ.get("LANGCHAIN_API_KEY") == "test-key"
        assert (
            os.environ.get("LANGCHAIN_ENDPOINT") == "https://eu.api.smith.langchain.com"
        )


# ---- _build_system_prompt tests ----


def test_build_system_prompt_french() -> None:
    from app.services.recipe_import import _build_system_prompt

    prompt = _build_system_prompt("fr")
    assert "French" in prompt
    assert "Translate" in prompt


def test_build_system_prompt_french_regional() -> None:
    from app.services.recipe_import import _build_system_prompt

    prompt = _build_system_prompt("fr-FR")
    assert "French" in prompt


def test_build_system_prompt_english_default() -> None:
    from app.services.recipe_import import _build_system_prompt

    prompt = _build_system_prompt(None)
    assert "American English" in prompt


def test_import_recipe_url_with_language(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _make_llm_response(_SAMPLE_RECIPE)

    with (
        patch("app.services.recipe_import._fetch_page", return_value=("texte", None)),
        patch("app.services.recipe_import._get_llm", return_value=llm_mock),
    ):
        response = client.post(
            f"{settings.API_V1_STR}/recipes/import-url",
            headers=superuser_token_headers,
            json={"url": "https://example.com/recette", "language": "fr"},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Test Pasta"


# ---- _get_llm provider tests ----


def test_get_llm_anthropic_provider() -> None:
    from unittest.mock import MagicMock, patch

    from app.services.recipe_import import _get_llm

    mock_llm = MagicMock()
    with (
        patch.object(settings, "AI_PROVIDER", "anthropic"),
        patch.object(settings, "ANTHROPIC_API_KEY", "test-key"),
        patch("langchain_anthropic.ChatAnthropic", return_value=mock_llm),
    ):
        llm = _get_llm()
    assert llm is mock_llm


def test_get_llm_anthropic_no_key() -> None:
    from app.services.recipe_import import _get_llm

    with (
        patch.object(settings, "AI_PROVIDER", "anthropic"),
        patch.object(settings, "ANTHROPIC_API_KEY", ""),
    ):
        try:
            _get_llm()
            raise AssertionError("should raise")
        except ValueError as exc:
            assert "ANTHROPIC_API_KEY" in str(exc)


def test_get_llm_openai_provider() -> None:
    from unittest.mock import MagicMock, patch

    from app.services.recipe_import import _get_llm

    mock_llm = MagicMock()
    with (
        patch.object(settings, "AI_PROVIDER", "openai"),
        patch.object(settings, "OPENAI_API_KEY", "test-key"),
        patch("langchain_openai.ChatOpenAI", return_value=mock_llm),
    ):
        llm = _get_llm()
    assert llm is mock_llm


def test_get_llm_openai_no_key() -> None:
    from app.services.recipe_import import _get_llm

    with (
        patch.object(settings, "AI_PROVIDER", "openai"),
        patch.object(settings, "OPENAI_API_KEY", ""),
    ):
        try:
            _get_llm()
            raise AssertionError("should raise")
        except ValueError as exc:
            assert "OPENAI_API_KEY" in str(exc)


def test_get_llm_google_provider() -> None:
    from unittest.mock import MagicMock, patch

    from app.services.recipe_import import _get_llm

    mock_llm = MagicMock()
    with (
        patch.object(settings, "AI_PROVIDER", "google"),
        patch.object(settings, "GOOGLE_API_KEY", "test-key"),
        patch("langchain_google_genai.ChatGoogleGenerativeAI", return_value=mock_llm),
    ):
        llm = _get_llm()
    assert llm is mock_llm


def test_get_llm_google_no_key() -> None:
    from app.services.recipe_import import _get_llm

    with (
        patch.object(settings, "AI_PROVIDER", "google"),
        patch.object(settings, "GOOGLE_API_KEY", ""),
    ):
        try:
            _get_llm()
            raise AssertionError("should raise")
        except ValueError as exc:
            assert "GOOGLE_API_KEY" in str(exc)


# ---- _fetch_page tests ----


def _make_httpx_response(html: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


def test_fetch_page_json_ld() -> None:
    import json as _json
    from unittest.mock import patch

    from app.services.recipe_import import _fetch_page

    recipe_data = {
        "@type": "Recipe",
        "name": "JSON-LD Cake",
        "description": "A cake",
        "recipeIngredient": ["200g flour"],
        "recipeInstructions": "Mix and bake.",
    }
    html = f"""<html>
<head>
  <meta property="og:image" content="https://example.com/cake.jpg"/>
  <script type="application/ld+json">{_json.dumps(recipe_data)}</script>
</head>
<body><p>Recipe page</p></body>
</html>"""
    with patch("httpx.get", return_value=_make_httpx_response(html)):
        text, image_url = _fetch_page("https://example.com/cake")

    assert "JSON-LD Cake" in text
    assert image_url == "https://example.com/cake.jpg"


def test_fetch_page_json_ld_list_wrapper() -> None:
    """JSON-LD wrapped in an array should still be detected."""
    import json as _json
    from unittest.mock import patch

    from app.services.recipe_import import _fetch_page

    recipe_data = [
        {"@type": "WebPage"},
        {"@type": "Recipe", "name": "List Wrapped Soup", "recipeIngredient": ["water"]},
    ]
    html = f"""<html><head>
    <script type="application/ld+json">{_json.dumps(recipe_data)}</script>
    </head><body></body></html>"""
    with patch("httpx.get", return_value=_make_httpx_response(html)):
        text, image_url = _fetch_page("https://example.com/soup")

    assert "List Wrapped Soup" in text
    assert image_url is None


def test_fetch_page_html_sections() -> None:
    """HTML with Ingredients/Instructions sections is extracted via targeted parser."""
    from unittest.mock import patch

    from app.services.recipe_import import _fetch_page

    html = """<html><head><title>HTML Recipe</title></head><body>
<h2>Ingredients</h2>
<ul><li>100g flour</li><li>2 eggs</li></ul>
<h2>Instructions</h2>
<p>Mix flour and eggs. Bake at 180°C for 30 minutes.</p>
</body></html>"""
    with patch("httpx.get", return_value=_make_httpx_response(html)):
        text, image_url = _fetch_page("https://example.com/html-recipe")

    assert "flour" in text.lower()
    assert image_url is None


def test_fetch_page_fallback_plain_text() -> None:
    """Pages with no structured data fall back to full-text extraction."""
    from unittest.mock import patch

    from app.services.recipe_import import _fetch_page

    html = """<html><head><title>Plain Recipe</title></head><body>
<p>Just some plain text about a recipe with no sections.</p>
</body></html>"""
    with patch("httpx.get", return_value=_make_httpx_response(html)):
        text, image_url = _fetch_page("https://example.com/plain")

    assert "Plain Recipe" in text or "plain text" in text.lower()
