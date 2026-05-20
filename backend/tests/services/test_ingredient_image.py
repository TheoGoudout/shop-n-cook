"""Unit tests for the ingredient image service."""

import uuid
from unittest.mock import MagicMock, patch

import pytest


def _session_ctx(mock_session: MagicMock) -> MagicMock:
    """Return a mock that acts as Session(engine) context manager."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_session)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _make_ingredient(
    *,
    name: str = "garlic",
    image_url: str | None = None,
    other_category: bool = True,
) -> MagicMock:
    from app.models.ingredient import IngredientCategory

    ing = MagicMock()
    ing.id = uuid.uuid4()
    ing.name = name
    ing.category = (
        IngredientCategory.OTHER if other_category else IngredientCategory.PRODUCE
    )
    ing.image_url = image_url
    return ing


# ---- fetch_image_from_spoonacular ----


def test_fetch_image_no_api_key(caplog: pytest.LogCaptureFixture) -> None:
    from app.core.config import settings
    from app.services.ingredient_image import fetch_image_from_spoonacular

    with patch.object(settings, "SPOONACULAR_API_KEY", None):
        result = fetch_image_from_spoonacular("tomato")

    assert result is None
    assert "SPOONACULAR_API_KEY not set" in caplog.text


def test_fetch_image_returns_url() -> None:
    from app.core.config import settings
    from app.services.ingredient_image import fetch_image_from_spoonacular

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [{"id": 11529, "name": "tomato", "image": "tomato.png"}]
    }

    with (
        patch.object(settings, "SPOONACULAR_API_KEY", "fake-key"),
        patch("httpx.get", return_value=mock_resp),
    ):
        result = fetch_image_from_spoonacular("tomato")

    assert result == "https://spoonacular.com/cdn/ingredients_250x250/tomato.png"


def test_fetch_image_no_results(caplog: pytest.LogCaptureFixture) -> None:
    from app.core.config import settings
    from app.services.ingredient_image import fetch_image_from_spoonacular

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}

    with (
        patch.object(settings, "SPOONACULAR_API_KEY", "fake-key"),
        patch("httpx.get", return_value=mock_resp),
    ):
        result = fetch_image_from_spoonacular("tomato")

    assert result is None
    assert "No Spoonacular results found" in caplog.text


def test_fetch_image_http_error(caplog: pytest.LogCaptureFixture) -> None:
    from app.core.config import settings
    from app.services.ingredient_image import fetch_image_from_spoonacular

    with (
        patch.object(settings, "SPOONACULAR_API_KEY", "fake-key"),
        patch("httpx.get", side_effect=Exception("connection error")),
    ):
        result = fetch_image_from_spoonacular("tomato")

    assert result is None
    assert "Failed to fetch image from Spoonacular" in caplog.text


# ---- fetch_and_update_ingredients_batch ----


def test_batch_empty_list(caplog: pytest.LogCaptureFixture) -> None:
    from app.services.ingredient_image import fetch_and_update_ingredients_batch

    fetch_and_update_ingredients_batch([])
    assert "empty list" in caplog.text


def test_batch_missing_ingredient_id(caplog: pytest.LogCaptureFixture) -> None:
    from app.services.ingredient_image import fetch_and_update_ingredients_batch

    missing_id = uuid.uuid4()
    mock_session = MagicMock()
    mock_session.get.return_value = None

    with patch("sqlmodel.Session", return_value=_session_ctx(mock_session)):
        fetch_and_update_ingredients_batch([missing_id])

    assert "not found in DB" in caplog.text


def test_batch_no_updates_needed(caplog: pytest.LogCaptureFixture) -> None:
    """Ingredient already has image and non-OTHER category → nothing committed."""
    from app.services.ingredient_image import fetch_and_update_ingredients_batch

    ing = _make_ingredient(image_url="https://example.com/g.jpg", other_category=False)

    mock_session = MagicMock()
    mock_session.get.return_value = ing

    with patch("sqlmodel.Session", return_value=_session_ctx(mock_session)):
        fetch_and_update_ingredients_batch([ing.id])

    mock_session.commit.assert_not_called()
    assert "No updates needed" in caplog.text


def test_batch_force_image_fetches_even_with_existing_image() -> None:
    """force_image=True should call fetch_image_from_spoonacular even if image already set."""
    from app.services.ingredient_image import fetch_and_update_ingredients_batch

    ing = _make_ingredient(image_url="https://existing.com/old.jpg")
    new_url = "https://spoonacular.com/cdn/ingredients_250x250/garlic.png"

    mock_session = MagicMock()
    mock_session.get.return_value = ing

    with (
        patch("sqlmodel.Session", return_value=_session_ctx(mock_session)),
        patch(
            "app.services.ingredient_image.fetch_image_from_spoonacular",
            return_value=new_url,
        ) as mock_fetch,
        patch(
            "app.services.ingredient_image._suggest_categories_batch",
            return_value={},
        ),
    ):
        fetch_and_update_ingredients_batch([ing.id], force_image=True)

    mock_fetch.assert_called_once_with(ing.name)
    assert ing.image_url == new_url
    mock_session.commit.assert_called_once()


def test_batch_no_image_url_obtained(caplog: pytest.LogCaptureFixture) -> None:
    """When Spoonacular returns None the warning is logged."""
    from app.services.ingredient_image import fetch_and_update_ingredients_batch

    ing = _make_ingredient()
    mock_session = MagicMock()
    mock_session.get.return_value = ing

    with (
        patch("sqlmodel.Session", return_value=_session_ctx(mock_session)),
        patch(
            "app.services.ingredient_image.fetch_image_from_spoonacular",
            return_value=None,
        ),
        patch(
            "app.services.ingredient_image._suggest_categories_batch", return_value={}
        ),
    ):
        fetch_and_update_ingredients_batch([ing.id])

    assert "No image URL obtained" in caplog.text


def test_batch_category_suggested(caplog: pytest.LogCaptureFixture) -> None:
    """When a category is found it is applied and logged."""
    from app.services.ingredient_image import fetch_and_update_ingredients_batch

    ing = _make_ingredient()
    mock_session = MagicMock()
    mock_session.get.return_value = ing

    with (
        patch("sqlmodel.Session", return_value=_session_ctx(mock_session)),
        patch(
            "app.services.ingredient_image.fetch_image_from_spoonacular",
            return_value=None,
        ),
        patch(
            "app.services.ingredient_image._suggest_categories_batch",
            return_value={ing.name: "produce"},
        ),
    ):
        fetch_and_update_ingredients_batch([ing.id])

    assert ing.category == "produce"
    assert "Setting category" in caplog.text


# ---- fetch_and_update_ingredient_image ----


def test_single_calls_batch_with_force_image() -> None:
    """fetch_and_update_ingredient_image delegates to batch with force_image=True."""
    from app.services.ingredient_image import fetch_and_update_ingredient_image

    iid = uuid.uuid4()
    with patch(
        "app.services.ingredient_image.fetch_and_update_ingredients_batch"
    ) as mock_batch:
        fetch_and_update_ingredient_image(iid)

    mock_batch.assert_called_once_with([iid], force_image=True)
