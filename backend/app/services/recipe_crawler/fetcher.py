"""Fetching recipe pages politely: robots.txt first, one request at a time.

Shared by the crawler and the bulk reimport (``services/recipe_reimport.py``),
which read the same kind of page from the same sites.
"""

import time
from collections.abc import Callable

from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families import http_client, robots

#: Waits up to the given seconds; returns ``True`` if the run should stop.
Pause = Callable[[float], bool]


def sleep(seconds: float) -> bool:
    """The ``Pause`` of a run nothing will ask to stop."""
    time.sleep(seconds)
    return False


class SiteUnavailableError(Exception):
    """The site stopped answering, or its robots.txt cannot be read."""


class PoliteFetcher:
    """robots.txt first, then at most one request per ``delay`` per site."""

    def __init__(
        self,
        *,
        delay: float,
        pause: Pause,
    ) -> None:
        self._delay = delay
        self._pause = pause
        self._last_request: dict[str, float] = {}
        #: Requests sent, whatever came back.
        self.pages_fetched = 0
        #: Set once ``pause`` asked the run to stop.
        self.stopped = False

    def get(self, url: str, origin: str) -> http_client.FetchedPage | None:
        """The page at ``url`` on site ``origin``, or ``None`` if robots.txt
        forbids it.

        Raises ``SiteUnavailableError`` if the site or its robots.txt cannot be
        reached, or it throttles or shields itself: a 5xx robots.txt means
        "disallow everything for now", which is an outage, not a verdict on any
        one page.
        """
        try:
            policy = robots.policy_for(origin)
        except ProviderUnavailableError as exc:
            raise SiteUnavailableError(str(exc)) from exc
        if policy.disallow_all:
            raise SiteUnavailableError(f"{origin}/robots.txt is unavailable")
        if not policy.allows(url):
            return None

        last = self._last_request.get(origin)
        if last is not None:
            wait = self._delay - (time.monotonic() - last)
            if wait > 0 and self._pause(wait):
                self.stopped = True
                raise SiteUnavailableError("run stopped")
        try:
            page = http_client.fetch(url)
        except ProviderUnavailableError as exc:
            raise SiteUnavailableError(str(exc)) from exc
        finally:
            self._last_request[origin] = time.monotonic()
            self.pages_fetched += 1
        if page.status_code in (403, 429) or page.status_code >= 500:
            # Throttled, shielded or down: stop asking it for this run.
            raise SiteUnavailableError(f"{url} returned HTTP {page.status_code}")
        return page
