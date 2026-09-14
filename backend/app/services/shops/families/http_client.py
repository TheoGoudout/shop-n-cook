"""Shared HTTP access for server-transport providers.

Every outbound call a provider makes goes through here so that timeouts, the
user agent and — most importantly — failure translation are uniform. Any
transport-level problem becomes ``ShopUnavailableError``, which the
orchestrator degrades into a partial result instead of a 500.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.services.shops.errors import ShopUnavailableError

DEFAULT_TIMEOUT = 15.0
USER_AGENT = "shop-n-cook/1.0 (+https://shop-n-cook.com)"


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """GET a URL and decode JSON, or raise ``ShopUnavailableError``."""
    response = _get(url, params=params, headers=headers, timeout=timeout)
    try:
        return response.json()
    except ValueError as exc:
        raise ShopUnavailableError(f"{url} did not return JSON") from exc


def get_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """GET a URL and return its body as text, or raise ``ShopUnavailableError``."""
    return _get(url, params=params, headers=headers, timeout=timeout).text


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
        # 403 here is the anti-bot shield (Akamai / DataDome) that makes some
        # retailers reachable only through the extension transport.
        raise ShopUnavailableError(
            f"{url} returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ShopUnavailableError(f"{url} could not be reached: {exc}") from exc
    return response
