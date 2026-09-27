"""Transport failures must all arrive as ``ProviderUnavailableError``.

The orchestrator's degradation depends on that single exception type: anything
leaking through as a raw httpx error would become a 500 instead of a partial
result.
"""

import gzip
from decimal import Decimal
from unittest.mock import Mock, patch

import httpx
import pytest

from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families.http_client import (
    USER_AGENT,
    fetch,
    get_json,
    get_text,
    get_xml,
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


def test_money_can_be_decoded_without_a_float() -> None:
    response = _response(text='{"price": 1.15}')
    with patch("httpx.get", return_value=response):
        body = get_json(URL, parse_float=Decimal)
    assert body["price"] == Decimal("1.15")
    assert str(body["price"]) == "1.15"


def test_a_gzipped_sitemap_is_unpacked() -> None:
    response = _response()
    response.content = gzip.compress(b"<urlset><loc>x</loc></urlset>")
    with patch("httpx.get", return_value=response):
        assert get_xml(URL) == "<urlset><loc>x</loc></urlset>"


def test_a_plain_sitemap_is_read_as_is() -> None:
    response = _response()
    response.content = b"<urlset></urlset>"
    with patch("httpx.get", return_value=response):
        assert get_xml(URL) == "<urlset></urlset>"


def test_a_corrupt_gzip_is_unavailable() -> None:
    response = _response()
    response.content = b"\x1f\x8bnot gzip at all"
    with patch("httpx.get", return_value=response):
        with pytest.raises(ProviderUnavailableError, match="gzip"):
            get_xml(URL)


def test_fetch_reports_an_http_error_status_instead_of_raising() -> None:
    response = Mock(spec=httpx.Response)
    response.status_code = 404
    response.text = "gone"
    with patch("httpx.get", return_value=response) as mock_get:
        page = fetch(URL)
    assert (page.status_code, page.text) == (404, "gone")
    assert mock_get.call_args.kwargs["headers"]["User-Agent"] == USER_AGENT


def test_fetch_still_raises_when_the_host_is_unreachable() -> None:
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        with pytest.raises(ProviderUnavailableError, match="could not be reached"):
            fetch(URL)


def test_user_agent_opens_like_a_browser_and_names_us() -> None:
    """Monoprix's WAF 403s any agent not opening with "Mozilla/5.0"."""
    assert USER_AGENT.startswith("Mozilla/5.0 (compatible; shop-n-cook/")
    assert "+https://shop-n-cook.com" in USER_AGENT
