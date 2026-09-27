"""robots.txt, honoured before any page is scraped.

A retailer's robots.txt is the one statement of intent it publishes to
automated clients, and most French grocers use it to fence off exactly the
pages a scraper would reach for first: their on-site search (Auchan's
``/recherche``, Picard's ``*/recherche``, Monoprix's ``/search?q=``, Lidl's
``*search?q=*``). Every one of those answered a plain request with a 200 — so
"it works" is not the test. This module is.

Implements RFC 9309 rather than wrapping ``urllib.robotparser``, which ignores
the ``*`` and ``$`` wildcards every one of those files relies on:

- the group naming our product token wins; otherwise the ``*`` group applies;
- the longest matching rule decides, and ``Allow`` wins a tie;
- a 4xx robots.txt means no rules; a 5xx or an unreachable one means
  *everything* is disallowed until it can be read.

Results are cached per origin for at most 24 hours, the RFC's ceiling.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families import http_client

#: RFC 9309 §2.5: crawlers must parse at least 500 KiB and may ignore the rest.
MAX_ROBOTS_BYTES = 500 * 1024
#: RFC 9309 §2.4: a cached robots.txt should not be used for more than 24 hours.
CACHE_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class _Rule:
    allow: bool
    pattern: str
    regex: re.Pattern[str]


def _compile(pattern: str) -> re.Pattern[str]:
    """``*`` matches any run of characters; a trailing ``$`` anchors the end."""
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = ".*".join(re.escape(part) for part in body.split("*"))
    return re.compile(regex + ("$" if anchored else ""))


@dataclass
class RobotsPolicy:
    """The rules that apply to one user agent on one origin."""

    rules: list[_Rule] = field(default_factory=list)
    disallow_all: bool = False
    """Set when robots.txt could not be read for a server-side reason."""

    @classmethod
    def parse(cls, text: str, *, user_agent: str) -> RobotsPolicy:
        token = user_agent.lower()
        groups: list[tuple[list[str], list[_Rule]]] = []
        agents: list[str] = []
        rules: list[_Rule] = []
        last_was_agent = False

        for raw_line in text[:MAX_ROBOTS_BYTES].splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key == "user-agent":
                if not last_was_agent and agents:
                    groups.append((agents, rules))
                    agents, rules = [], []
                agents.append(value.lower())
                last_was_agent = True
                continue

            last_was_agent = False
            if key not in ("allow", "disallow") or not agents or not value:
                # An empty Disallow allows everything, which is the default.
                continue
            # A rule not rooted at "/" is read as matching anywhere. Stricter
            # than ignoring it, which is the safe side to err on here.
            pattern = value if value.startswith(("/", "*")) else "*" + value
            rules.append(
                _Rule(allow=key == "allow", pattern=pattern, regex=_compile(pattern))
            )
        if agents:
            groups.append((agents, rules))

        specific = [r for names, rs in groups if token in names for r in rs]
        if specific or any(token in names for names, _ in groups):
            return cls(rules=specific)
        return cls(rules=[r for names, rs in groups if "*" in names for r in rs])

    def allows(self, url: str) -> bool:
        if self.disallow_all:
            return False
        parts = urlsplit(url)
        target = unquote(parts.path or "/")
        if parts.query:
            target += "?" + unquote(parts.query)

        best: _Rule | None = None
        for rule in self.rules:
            if not rule.regex.match(target):
                continue
            if (
                best is None
                or len(rule.pattern) > len(best.pattern)
                or (len(rule.pattern) == len(best.pattern) and rule.allow)
            ):
                best = rule
        return best is None or best.allow


_cache: dict[str, tuple[float, RobotsPolicy]] = {}
_lock = threading.Lock()


def policy_for(origin: str) -> RobotsPolicy:
    """The (cached) policy for ``origin``, e.g. ``https://www.picard.fr``."""
    now = time.monotonic()
    with _lock:
        cached = _cache.get(origin)
        if cached is not None and now - cached[0] < CACHE_SECONDS:
            return cached[1]

    page = http_client.fetch(f"{origin}/robots.txt")
    if 200 <= page.status_code < 300:
        policy = RobotsPolicy.parse(page.text, user_agent=http_client.ROBOTS_USER_AGENT)
    elif 400 <= page.status_code < 500:
        policy = RobotsPolicy()
    else:
        policy = RobotsPolicy(disallow_all=True)

    with _lock:
        _cache[origin] = (now, policy)
    return policy


def ensure_allowed(url: str) -> None:
    """Raise ``ProviderUnavailableError`` if robots.txt forbids ``url``.

    Unavailable rather than a new error type on purpose: to the orchestrator a
    page we may not read is exactly as absent as one that timed out, and it
    already degrades that case into an honest partial result.
    """
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if not policy_for(origin).allows(url):
        raise ProviderUnavailableError(f"robots.txt disallows {url}")


def clear_cache() -> None:
    """Test helper. Not used by application code."""
    with _lock:
        _cache.clear()
