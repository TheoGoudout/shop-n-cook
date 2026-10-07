"""Bring recipes imported by an older pipeline up to ``IMPORT_VERSION``.

A recipe is *stale* when it was imported from a URL (``import_source`` is
``URL``) by a pipeline older than ``recipe_import.IMPORT_VERSION`` — or before
versions were tracked at all. An admin reimports them a batch at a time; each
batch runs in the background, one worker at a time (a Postgres advisory lock),
and every recipe it reaches is stamped with the current version, so the stale
count is the progress bar.

What a reimport may change depends on who could have edited the recipe:

- **Crawled recipes** (a ``CrawledRecipe`` row points at them) belong to the
  crawler's account and nobody curates them: they are **replaced** with the
  fresh import. A reply missing a title, ingredients or steps replaces nothing.
- **Everyone else's** were reviewed, and maybe corrected, before being saved:
  they are only **completed** — fields still empty get the fresh import's
  value, and nothing already there is touched (``mapping.parsed_to_fill``).

Every recipe is read in the language it was first imported in
(``Recipe.import_language``), so a reimport never translates it. A recipe
imported before that was recorded falls back to its site's language if it was
crawled, and to the admin's otherwise; the language used is then recorded.

Fetching is a background job's, not a person's, so it follows the crawler's
rules: robots.txt first, ``RECIPE_CRAWL_DELAY_SECONDS`` between two requests
to one host, and a host that throttles, shields or fails is left alone for the
rest of the batch with nothing recorded against its recipes. A recipe that
fails for its own reasons (robots.txt, a dead page, an unusable reply) moves to
the back of the queue (``reimport_attempted_at``) and stays stale, so the next
batch tries the others first.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, and_, col, func, or_, select

from app import crud
from app.core.config import settings
from app.models import CrawledRecipe, Recipe, RecipeUpdate
from app.models.base import get_datetime_utc
from app.models.recipe import ImportSource
from app.services.ingredient_image import fetch_and_update_ingredients_batch
from app.services.recipe_crawler.sites import SITES
from app.services.recipe_import import IMPORT_VERSION, import_recipe_from_html
from app.services.recipe_import.mapping import parsed_to_fill, parsed_to_update
from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families import http_client, robots

logger = logging.getLogger(__name__)

ADVISORY_LOCK_KEY = 0x53_4E_43_52_45_49_4D_50  # "SNCREIMP"

#: Waits up to the given seconds; returns ``True`` if the batch should stop.
Pause = Callable[[float], bool]


def _sleep(seconds: float) -> bool:
    time.sleep(seconds)
    return False


def is_stale() -> ColumnElement[bool]:
    return and_(
        col(Recipe.import_source) == ImportSource.URL,
        col(Recipe.source_url).is_not(None),
        or_(
            col(Recipe.import_version).is_(None),
            col(Recipe.import_version) < IMPORT_VERSION,
        ),
    )


def count_stale(session: Session) -> tuple[int, int]:
    """How many recipes are stale, and how many of those a batch already tried."""
    stale, tried = session.exec(
        select(
            func.count(),
            func.count(col(Recipe.reimport_attempted_at)),
        ).where(is_stale())
    ).one()
    return stale, tried


@dataclass
class ReimportReport:
    updated: int = 0
    failed: int = 0
    #: Left for a later batch because their host was unavailable.
    skipped: int = 0


class _HostUnavailableError(Exception):
    """The host stopped answering, or its robots.txt cannot be read."""


class _PageRefusedError(Exception):
    """This page cannot be imported: robots.txt forbids it, or it is gone."""


class _PoliteFetcher:
    """robots.txt first, then at most one request per ``delay`` per host."""

    def __init__(self, *, delay: float, pause: Pause) -> None:
        self._delay = delay
        self._pause = pause
        self._last_request: dict[str, float] = {}

    def get(self, url: str, origin: str) -> str:
        try:
            policy = robots.policy_for(origin)
        except ProviderUnavailableError as exc:
            raise _HostUnavailableError(str(exc)) from exc
        if policy.disallow_all:
            raise _HostUnavailableError(f"{origin}/robots.txt is unavailable")
        if not policy.allows(url):
            raise _PageRefusedError("robots.txt disallows")

        last = self._last_request.get(origin)
        if last is not None:
            wait = self._delay - (time.monotonic() - last)
            if wait > 0 and self._pause(wait):
                raise _HostUnavailableError("batch stopped")
        try:
            page = http_client.fetch(url)
        except ProviderUnavailableError as exc:
            raise _HostUnavailableError(str(exc)) from exc
        finally:
            self._last_request[origin] = time.monotonic()
        if page.status_code in (403, 429) or page.status_code >= 500:
            raise _HostUnavailableError(f"{url} returned HTTP {page.status_code}")
        if page.status_code != 200:
            raise _PageRefusedError(f"HTTP {page.status_code}")
        return page.text


def _crawled_languages(
    session: Session, recipe_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str | None]:
    """Every crawled recipe among ``recipe_ids``, with its site's language
    (``None`` for a site since dropped from ``SITES``)."""
    languages = {site.slug: site.language for site in SITES}
    rows = session.exec(
        select(CrawledRecipe.recipe_id, CrawledRecipe.site).where(
            col(CrawledRecipe.recipe_id).in_(recipe_ids)
        )
    ).all()
    return {rid: languages.get(site) for rid, site in rows if rid is not None}


def _reimport_one(
    session: Session, recipe: Recipe, html: str, *, language: str | None, replace: bool
) -> RecipeUpdate:
    url = recipe.source_url or ""
    parsed = import_recipe_from_html(url, html, language=language)
    if replace:
        recipe_in = parsed_to_update(parsed)
        if not recipe_in.title or not recipe_in.ingredients or not recipe_in.steps:
            raise ValueError("the model returned an incomplete recipe")
    else:
        recipe_in = parsed_to_fill(parsed, recipe)
    recipe.import_version = IMPORT_VERSION
    recipe.import_language = parsed.language
    recipe.reimport_attempted_at = get_datetime_utc()
    crud.update_recipe(session=session, db_recipe=recipe, recipe_in=recipe_in)
    return recipe_in


def reimport_stale(
    session: Session,
    *,
    limit: int,
    language: str | None,
    delay_seconds: float,
    pause: Pause = _sleep,
) -> ReimportReport:
    """Reimport up to ``limit`` stale recipes, the least recently tried first.

    ``language`` is the one to read pages in when neither the recipe nor its
    crawled site says.
    """
    report = ReimportReport()
    recipes = session.exec(
        select(Recipe)
        .where(is_stale())
        .order_by(
            col(Recipe.reimport_attempted_at).asc().nulls_first(),
            col(Recipe.created_at).asc(),
        )
        .limit(limit)
    ).all()
    if not recipes:
        return report
    crawled = _crawled_languages(session, [r.id for r in recipes])
    fetcher = _PoliteFetcher(delay=delay_seconds, pause=pause)
    unavailable: set[str] = set()
    ingredient_ids: list[uuid.UUID] = []

    for recipe in recipes:
        url = recipe.source_url or ""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in unavailable:
            report.skipped += 1
            continue
        try:
            html = fetcher.get(url, origin)
            recipe_in = _reimport_one(
                session,
                recipe,
                html,
                language=recipe.import_language or crawled.get(recipe.id) or language,
                replace=recipe.id in crawled,
            )
        except _HostUnavailableError as exc:
            logger.warning("Recipe reimport: skipping %s: %s", origin, exc)
            unavailable.add(origin)
            report.skipped += 1
            continue
        except Exception as exc:
            if not isinstance(exc, _PageRefusedError):
                logger.exception("Recipe reimport: %s failed", url)
            session.rollback()
            recipe.reimport_attempted_at = get_datetime_utc()
            session.add(recipe)
            session.commit()
            report.failed += 1
            continue
        if recipe_in.ingredients:
            ids = crud.sync_ingredient_catalog(
                session=session, ingredients=recipe_in.ingredients
            )
            ingredient_ids.extend(i for i in ids if i not in ingredient_ids)
        # The recipe and the catalogue entries it needs land together.
        session.commit()
        report.updated += 1

    if ingredient_ids:
        fetch_and_update_ingredients_batch(ingredient_ids)
    logger.info("Recipe reimport: %s", report)
    return report


def is_running(engine: Engine) -> bool:
    """Whether a batch holds the lock right now, on any worker."""
    with engine.connect() as connection:
        acquired = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
        ).scalar()
        if acquired:
            connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY}
            )
        connection.commit()
    return not acquired


def run_batch(
    engine: Engine, *, limit: int, language: str | None
) -> ReimportReport | None:
    """Take the lock and run one batch. ``None`` if another batch holds it."""
    with engine.connect() as lock_connection:
        acquired = lock_connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
        ).scalar()
        lock_connection.commit()
        if not acquired:
            return None
        try:
            with Session(engine) as session:
                return reimport_stale(
                    session,
                    limit=limit,
                    language=language,
                    delay_seconds=settings.RECIPE_CRAWL_DELAY_SECONDS,
                )
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY}
            )
            lock_connection.commit()
