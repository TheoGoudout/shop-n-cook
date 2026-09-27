"""Shared HTTP access for server-transport providers.

Every outbound call a provider makes goes through here so that timeouts, the
user agent and — most importantly — failure translation are uniform. Any
transport-level problem becomes ``ProviderUnavailableError``, which the
orchestrator degrades into a partial result instead of a 500.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.services.store_providers.errors import ProviderUnavailableError

DEFAULT_TIMEOUT = 15.0
#: The conventional crawler format: "Mozilla/5.0 (compatible; <bot>; +<url>)".
#: Still says exactly who we are, but some WAFs (Monoprix's AWS WAF) refuse any
#: agent that does not open with "Mozilla/5.0", however honest it is.
USER_AGENT = "Mozilla/5.0 (compatible; shop-n-cook/1.0; +https://shop-n-cook.com)"
#: The token robots.txt groups are matched against.
ROBOTS_USER_AGENT = "shop-n-cook"


@dataclass(frozen=True)
class FetchedPage:
    """A response the caller wants to judge itself, status and all."""

    status_code: int
    text: str


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    parse_float: Callable[[str], Any] | None = None,
) -> Any:
    """GET a URL and decode JSON, or raise ``ProviderUnavailableError``.

    Pass ``parse_float=Decimal`` when the body carries money: the number is
    then read straight from its JSON text and never passes through a float.
    """
    response = _get(url, params=params, headers=headers, timeout=timeout)
    try:
        if parse_float is not None:
            return json.loads(response.text, parse_float=parse_float)
        return response.json()
    except ValueError as exc:
        raise ProviderUnavailableError(f"{url} did not return JSON") from exc


def get_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """GET a URL and return its body as text, or raise ``ProviderUnavailableError``."""
    return _get(url, params=params, headers=headers, timeout=timeout).text


def get_xml(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> str:
    """GET an XML document such as a sitemap, gunzipping a ``.xml.gz`` body.

    Sitemaps are allowed to be served gzipped as a *file*, which is distinct
    from HTTP content-encoding and which httpx therefore does not undo.
    """
    content = _get(url, params=None, headers=None, timeout=timeout).content
    if content[:2] == b"\x1f\x8b":
        try:
            content = gzip.decompress(content)
        except (OSError, EOFError) as exc:
            raise ProviderUnavailableError(f"{url} is not valid gzip") from exc
    return content.decode("utf-8", errors="replace")


def fetch(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> FetchedPage:
    """GET a URL and return it whatever its HTTP status.

    For callers to whom a 4xx is an answer rather than an outage: a robots.txt
    that 404s means "no rules", and a product page that 404s means one delisted
    product, not a store that is down. Transport failures still raise.
    """
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        raise ProviderUnavailableError(f"{url} could not be reached: {exc}") from exc
    return FetchedPage(status_code=response.status_code, text=response.text)


def _get(
    url: str,
    *,
    params: dict[str, Any] | None,
    headers: dict[str, str] | None,
    timeout: float,
) -> httpx.Response:
    merged = {"User-Agent": USER_AGENT, **(headers or {})}
    try:
        response = httpx.get(
            url,
            params=params,
            headers=merged,
            timeout=timeout,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # 403 here is the anti-bot shield (Cloudflare / DataDome) that makes some
        # retailers reachable only through the extension transport.
        raise ProviderUnavailableError(
            f"{url} returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ProviderUnavailableError(f"{url} could not be reached: {exc}") from exc
    return response
