"""Transport failures must all arrive as ``ProviderUnavailableError``.

The orchestrator's degradation depends on that single exception type: anything
leaking through as a raw httpx error would become a 500 instead of a partial
result.
"""

from unittest.mock import Mock, patch

import httpx
import pytest

from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families.http_client import (
    USER_AGENT,
    get_json,
    get_text,
)

URL = "https://shop.test/search"


def _response(*, json_body: object = None, text: str = "") -> Mock:
    response = Mock(spec=httpx.Response)
    response.raise_for_status = Mock()
    response.text = text
    if json_body is None:
        response.json = Mock(side_effect=ValueError("not json"))
    else:
        response.json = Mock(return_value=json_body)
    return response


def test_get_json_returns_decoded_body() -> None:
    with patch("httpx.get", return_value=_response(json_body={"items": []})):
        assert get_json(URL) == {"items": []}


def test_get_text_returns_body() -> None:
    with patch("httpx.get", return_value=_response(text="<html></html>")):
        assert get_text(URL) == "<html></html>"


def test_identifies_itself() -> None:
    with patch("httpx.get", return_value=_response(text="ok")) as mock_get:
        get_text(URL)
    assert mock_get.call_args.kwargs["headers"]["User-Agent"] == USER_AGENT


def test_extra_headers_are_merged() -> None:
    with patch("httpx.get", return_value=_response(text="ok")) as mock_get:
        get_text(URL, headers={"Authorization": "Bearer x"})
    headers = mock_get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer x"
    assert headers["User-Agent"] == USER_AGENT


def test_non_json_body_is_unavailable() -> None:
    with patch("httpx.get", return_value=_response()):
        with pytest.raises(ProviderUnavailableError, match="did not return JSON"):
            get_json(URL)


def test_anti_bot_403_becomes_unavailable() -> None:
    """Carrefour / Intermarché / Leclerc all answer a server request this way."""
    response = Mock(spec=httpx.Response)
    response.status_code = 403
    response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError("403", request=Mock(), response=response)
    )
    with patch("httpx.get", return_value=response):
        with pytest.raises(ProviderUnavailableError, match="403"):
            get_text(URL)


def test_network_error_becomes_unavailable() -> None:
    with patch("httpx.get", side_effect=httpx.ConnectTimeout("timed out")):
        with pytest.raises(ProviderUnavailableError, match="could not be reached"):
            get_text(URL)
