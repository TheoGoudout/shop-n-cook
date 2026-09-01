"""Tests for the AI recipe import from photos. All LLM calls are mocked.

Photos are transient — nothing is written to disk or to the database — so these
tests only ever exercise validation, the model request and the error mapping.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import settings
from app.core.limiter import limiter, user_or_ip_key
from app.models.recipe import ImportSource, RecipeCreate
from app.services.recipe_import.errors import InvalidPhotoError
from app.services.recipe_import.photos import (
    PhotoInput,
    sniff_media_type,
    validate_photos,
)
from app.services.recipe_import.prompt import build_system_prompt

# Smallest byte strings that pass the magic-byte sniffer. The model is mocked, so
# they never have to decode as real images.
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 32
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP_BYTES = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 32

IMPORT_PHOTOS_URL = f"{settings.API_V1_STR}/recipes/import-photos"

_SAMPLE_RECIPE = {
    "title": "Grandma's Tarte Tatin",
    "description": "Caramelised apple tart",
    "steps": [
        {"instruction": "Caramelise the sugar.", "ingredient_names": ["sugar"]},
        {"instruction": "Arrange the apples.", "ingredient_names": ["apples"]},
    ],
    "servings": 6,
    "prep_time_minutes": 25,
    "cook_time_minutes": 40,
    "ingredients": [
        {"name": "sugar", "quantity": 150.0, "unit": "g", "notes": None},
        {"name": "apples", "quantity": 6.0, "unit": "piece", "notes": None},
    ],
}


def _make_llm_response(data: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = json.dumps(data)
    return msg


def _files(*payloads: bytes) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        ("photos", (f"photo{i}.jpg", payload, "image/jpeg"))
        for i, payload in enumerate(payloads)
    ]


# --------------------------------------------------------------------------- #
# Route: happy path                                                            #
# --------------------------------------------------------------------------- #


def test_import_recipe_photos_success(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _make_llm_response(_SAMPLE_RECIPE)

    with patch(
        "app.services.recipe_import.llm.get_llm", return_value=llm_mock
    ) as get_llm_mock:
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(JPEG_BYTES, PNG_BYTES),
            data={"language": "en"},
        )

    assert response.status_code == 200
    content = response.json()
    assert content["title"] == "Grandma's Tarte Tatin"
    assert len(content["ingredients"]) == 2
    assert len(content["steps"]) == 2
    # Photo imports have no page to link back to.
    assert content["source_url"] is None
    assert content["image_url"] is None
    get_llm_mock.assert_called_once_with(vision=True)


def test_import_recipe_photos_sends_images_to_the_model(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Both photos reach the model as base64 blocks, in one single message."""
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _make_llm_response(_SAMPLE_RECIPE)

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(JPEG_BYTES, WEBP_BYTES),
        )

    assert response.status_code == 200
    (messages,), _ = llm_mock.invoke.call_args
    system_message, human_message = messages
    assert "photographs of a recipe" in system_message.content
    image_blocks = [b for b in human_message.content if b["type"] == "image"]
    assert [b["mime_type"] for b in image_blocks] == ["image/jpeg", "image/webp"]
    assert all(b["source_type"] == "base64" for b in image_blocks)
    assert human_message.content[-1]["type"] == "text"


def test_import_recipe_photos_accepts_a_single_photo(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _make_llm_response(_SAMPLE_RECIPE)

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(JPEG_BYTES),
        )

    assert response.status_code == 200


# --------------------------------------------------------------------------- #
# Route: rejections                                                            #
# --------------------------------------------------------------------------- #


def test_import_recipe_photos_requires_authentication(client: TestClient) -> None:
    response = client.post(IMPORT_PHOTOS_URL, files=_files(JPEG_BYTES))
    assert response.status_code == 401


def test_import_recipe_photos_rejects_too_many_photos(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    llm_mock = MagicMock()
    too_many = [JPEG_BYTES] * (settings.RECIPE_PHOTO_MAX_COUNT + 1)

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(*too_many),
        )

    assert response.status_code == 400
    assert str(settings.RECIPE_PHOTO_MAX_COUNT) in response.json()["detail"]
    llm_mock.invoke.assert_not_called()


def test_import_recipe_photos_rejects_oversized_photo(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    llm_mock = MagicMock()
    oversized = JPEG_BYTES + b"\x00" * settings.RECIPE_PHOTO_MAX_BYTES

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(oversized),
        )

    assert response.status_code == 400
    assert "limit" in response.json()["detail"]
    llm_mock.invoke.assert_not_called()


def test_import_recipe_photos_rejects_non_image(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """A text file renamed to .jpg is caught by the magic-byte sniffer."""
    llm_mock = MagicMock()

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(b"this is definitely not an image"),
        )

    assert response.status_code == 400
    assert "JPEG, PNG or WebP" in response.json()["detail"]
    llm_mock.invoke.assert_not_called()


def test_import_recipe_photos_rejects_empty_photo(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    llm_mock = MagicMock()

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(b""),
        )

    assert response.status_code == 400
    llm_mock.invoke.assert_not_called()


def test_import_recipe_photos_requires_a_photo(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """FastAPI rejects the request before the handler runs when photos is missing."""
    response = client.post(
        IMPORT_PHOTOS_URL,
        headers=superuser_token_headers,
        data={"language": "en"},
    )
    assert response.status_code == 422


def test_import_recipe_photos_no_recipe_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """An empty title is the model's 'nothing legible here' signal."""
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _make_llm_response({"title": ""})

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(JPEG_BYTES),
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "no_recipe_found"


def test_import_recipe_photos_missing_title_is_no_recipe_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _make_llm_response({"ingredients": []})

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(JPEG_BYTES),
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "no_recipe_found"


def test_import_recipe_photos_provider_not_configured(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    with patch(
        "app.services.recipe_import.llm.get_llm",
        side_effect=ValueError("ANTHROPIC_API_KEY is not configured"),
    ):
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(JPEG_BYTES),
        )

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_import_recipe_photos_unexpected_error(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    with patch(
        "app.services.recipe_import.llm.get_llm",
        side_effect=RuntimeError("provider exploded"),
    ):
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(JPEG_BYTES),
        )

    assert response.status_code == 422
    assert "Failed to parse recipe" in response.json()["detail"]


def test_import_recipe_photos_strips_markdown_fences(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    llm_mock = MagicMock()
    fenced = MagicMock()
    fenced.content = f"```json\n{json.dumps(_SAMPLE_RECIPE)}\n```"
    llm_mock.invoke.return_value = fenced

    with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
        response = client.post(
            IMPORT_PHOTOS_URL,
            headers=superuser_token_headers,
            files=_files(JPEG_BYTES),
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Grandma's Tarte Tatin"


# --------------------------------------------------------------------------- #
# Rate limiting                                                                #
# --------------------------------------------------------------------------- #


def test_import_recipe_photos_is_rate_limited(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """The per-user limit kicks in once the configured allowance is spent.

    Rate limiting is off for the rest of the suite (RATE_LIMIT_ENABLED=False), so
    it is switched on just for this test and restored afterwards.
    """
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _make_llm_response(_SAMPLE_RECIPE)
    allowance = int(settings.RECIPE_PHOTO_RATE_LIMIT.split("/")[0])

    was_enabled = limiter.enabled
    limiter.reset()
    limiter.enabled = True
    try:
        with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
            for _ in range(allowance):
                ok = client.post(
                    IMPORT_PHOTOS_URL,
                    headers=superuser_token_headers,
                    files=_files(JPEG_BYTES),
                )
                assert ok.status_code == 200

            blocked = client.post(
                IMPORT_PHOTOS_URL,
                headers=superuser_token_headers,
                files=_files(JPEG_BYTES),
            )
    finally:
        limiter.enabled = was_enabled
        limiter.reset()

    assert blocked.status_code == 429


def test_import_recipe_photos_limit_is_per_user(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    """One user exhausting their allowance must not block anybody else.

    This is what the custom key function buys over the default IP key: the two
    users here share a client address.
    """
    llm_mock = MagicMock()
    llm_mock.invoke.return_value = _make_llm_response(_SAMPLE_RECIPE)
    allowance = int(settings.RECIPE_PHOTO_RATE_LIMIT.split("/")[0])

    was_enabled = limiter.enabled
    limiter.reset()
    limiter.enabled = True
    try:
        with patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock):
            for _ in range(allowance + 1):
                client.post(
                    IMPORT_PHOTOS_URL,
                    headers=superuser_token_headers,
                    files=_files(JPEG_BYTES),
                )
            other_user = client.post(
                IMPORT_PHOTOS_URL,
                headers=normal_user_token_headers,
                files=_files(JPEG_BYTES),
            )
    finally:
        limiter.enabled = was_enabled
        limiter.reset()

    assert other_user.status_code == 200


def test_user_or_ip_key_uses_the_bearer_subject() -> None:
    from app.core import security

    token = security.create_access_token(
        subject="11111111-1111-1111-1111-111111111111",
        expires_delta=__import__("datetime").timedelta(minutes=5),
    )
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    assert user_or_ip_key(request) == "user:11111111-1111-1111-1111-111111111111"


def test_user_or_ip_key_falls_back_to_the_client_ip() -> None:
    request = MagicMock()
    request.headers = {"Authorization": "Bearer not-a-real-token"}
    request.client.host = "203.0.113.7"
    assert user_or_ip_key(request) == "203.0.113.7"


def test_user_or_ip_key_without_a_token() -> None:
    request = MagicMock()
    request.headers = {}
    request.client.host = "203.0.113.8"
    assert user_or_ip_key(request) == "203.0.113.8"


# --------------------------------------------------------------------------- #
# Photo validation unit tests                                                  #
# --------------------------------------------------------------------------- #


def test_sniff_media_type_recognises_supported_formats() -> None:
    assert sniff_media_type(JPEG_BYTES) == "image/jpeg"
    assert sniff_media_type(PNG_BYTES) == "image/png"
    assert sniff_media_type(WEBP_BYTES) == "image/webp"


def test_sniff_media_type_rejects_other_content() -> None:
    assert sniff_media_type(b"GIF89a" + b"\x00" * 20) is None
    assert sniff_media_type(b"") is None
    # RIFF container that is not WebP (e.g. a WAV file)
    assert sniff_media_type(b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 20) is None


def test_validate_photos_returns_typed_inputs() -> None:
    photos = validate_photos([JPEG_BYTES, PNG_BYTES])
    assert photos == [
        PhotoInput(data=JPEG_BYTES, media_type="image/jpeg"),
        PhotoInput(data=PNG_BYTES, media_type="image/png"),
    ]


def test_validate_photos_rejects_an_empty_batch() -> None:
    with pytest.raises(InvalidPhotoError, match="At least one photo"):
        validate_photos([])


# --------------------------------------------------------------------------- #
# Prompt                                                                       #
# --------------------------------------------------------------------------- #


def test_build_system_prompt_photo_source() -> None:
    prompt = build_system_prompt("en", source="photo")
    assert "photographs of a recipe" in prompt
    assert "ONE single recipe" in prompt
    assert '{"title": ""}' in prompt
    # The shared output contract is still present.
    assert '"kcal_per_serving"' in prompt


def test_build_system_prompt_web_source_is_unchanged() -> None:
    prompt = build_system_prompt("en")
    assert "the text content of a recipe web page" in prompt
    assert "Reading photographs" not in prompt


def test_build_system_prompt_photo_source_translates() -> None:
    prompt = build_system_prompt("fr", source="photo")
    assert "Reading photographs" in prompt
    assert "Translate all text fields" in prompt


# --------------------------------------------------------------------------- #
# Vision model selection                                                       #
# --------------------------------------------------------------------------- #


def test_get_llm_vision_uses_the_anthropic_vision_model() -> None:
    from app.services.recipe_import.llm import get_llm

    with (
        patch.object(settings, "AI_PROVIDER", "anthropic"),
        patch.object(settings, "ANTHROPIC_API_KEY", "test-key"),
        patch.object(settings, "ANTHROPIC_VISION_MODEL", "vision-model"),
        patch.object(settings, "ANTHROPIC_MODEL", "text-model"),
        patch("langchain_anthropic.ChatAnthropic") as chat_mock,
    ):
        get_llm(vision=True)
        assert chat_mock.call_args.kwargs["model"] == "vision-model"

        chat_mock.reset_mock()
        get_llm()
        assert chat_mock.call_args.kwargs["model"] == "text-model"


def test_get_llm_vision_uses_the_openai_vision_model() -> None:
    from app.services.recipe_import.llm import get_llm

    with (
        patch.object(settings, "AI_PROVIDER", "openai"),
        patch.object(settings, "OPENAI_API_KEY", "test-key"),
        patch.object(settings, "OPENAI_VISION_MODEL", "vision-model"),
        patch.object(settings, "OPENAI_MODEL", "text-model"),
        patch("langchain_openai.ChatOpenAI") as chat_mock,
    ):
        get_llm(vision=True)
        assert chat_mock.call_args.kwargs["model"] == "vision-model"

        chat_mock.reset_mock()
        get_llm()
        assert chat_mock.call_args.kwargs["model"] == "text-model"


def test_get_llm_vision_uses_the_google_vision_model() -> None:
    from app.services.recipe_import.llm import get_llm

    with (
        patch.object(settings, "AI_PROVIDER", "google"),
        patch.object(settings, "GOOGLE_API_KEY", "test-key"),
        patch.object(settings, "GOOGLE_VISION_MODEL", "vision-model"),
        patch.object(settings, "GOOGLE_MODEL", "text-model"),
        patch("langchain_google_genai.ChatGoogleGenerativeAI") as chat_mock,
    ):
        get_llm(vision=True)
        assert chat_mock.call_args.kwargs["model"] == "vision-model"

        chat_mock.reset_mock()
        get_llm()
        assert chat_mock.call_args.kwargs["model"] == "text-model"


# --------------------------------------------------------------------------- #
# Consent gate                                                                 #
# --------------------------------------------------------------------------- #


def test_recipe_create_photo_import_requires_consent() -> None:
    with pytest.raises(ValidationError, match="import_consent is required"):
        RecipeCreate(title="From a photo", import_source=ImportSource.PHOTO)


def test_recipe_create_photo_import_with_consent_is_accepted() -> None:
    recipe = RecipeCreate(
        title="From a photo",
        import_source=ImportSource.PHOTO,
        import_consent=True,
    )
    assert recipe.import_source == ImportSource.PHOTO


def test_recipe_create_url_import_still_requires_consent() -> None:
    with pytest.raises(ValidationError, match="import_consent is required"):
        RecipeCreate(title="From a site", source_url="https://example.com/recipe")


def test_recipe_create_handwritten_recipe_needs_no_consent() -> None:
    recipe = RecipeCreate(title="My own recipe")
    assert recipe.import_source is None
    assert recipe.import_consent is False
