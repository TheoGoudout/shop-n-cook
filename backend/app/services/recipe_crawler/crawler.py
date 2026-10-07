"""One crawler pass: judge new recipes on each site, then import the best.

A pass has two halves.

**Judge.** For each site in ``SITES``: read its popularity pages and list the
recipe URLs they link to, in rank order; drop every URL already judged (see
``_is_settled``) and every one a public recipe already cites; read the next
``max_pages_per_site`` of the rest and judge each with ``quality.assess``.
Every verdict is recorded — ``REJECTED`` with its reason, or ``QUALIFIED`` with
its score — so no page is judged twice, and each run carries on down the list
where the last one stopped.

**Import.** The ``QUALIFIED`` rows (and ``FAILED`` ones due for a retry) are
the backlog. Up to ``max_imports`` of them are imported, best score first,
taking turns between sites so one site cannot fill a run. Each import is one
LLM call through ``recipe_import``; the result becomes a public recipe owned by
the crawler's account, and its row turns ``IMPORTED`` for good.

Every URL is checked against the site's robots.txt before it is fetched, and
requests to one site are spaced by ``delay_seconds``. A site that stops
answering is dropped for the rest of the run, with nothing recorded against
its recipes.

Republishing: an imported recipe is the model's restructuring of the page
(ingredients normalised to our units, steps split one action each), always
credits its page through ``source_url``, and points at the site's own
``og:image`` rather than copying it. The site still owns its text and photos;
whether a given site's recipes may be shown publicly is for the operator to
confirm before turning the crawler on (it is off by default).
"""

from __future__ import annotations

import logging
import secrets
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, or_, select

from app import crud
from app.core.config import settings
from app.models import (
    CrawledRecipe,
    CrawlStatus,
    Recipe,
    RecipeCrawlRun,
    User,
    UserCreate,
)
from app.models.base import get_datetime_utc
from app.services.ingredient_image import fetch_and_update_ingredients_batch
from app.services.recipe_crawler import discovery, quality
from app.services.recipe_crawler.fetcher import (
    Pause,
    PoliteFetcher,
    SiteUnavailableError,
    sleep,
)
from app.services.recipe_crawler.sites import SITES, RecipeSite
from app.services.recipe_import import import_recipe_from_html
from app.services.recipe_import import llm as llm_module
from app.services.recipe_import.mapping import parsed_to_create

logger = logging.getLogger(__name__)

#: Ratings move; a recipe turned down today may qualify next season.
REJECTED_RECHECK_AFTER = timedelta(days=90)
#: An import that broke (model timeout, unusable output) is retried the next
#: day, and given up on after this many attempts.
FAILED_RETRY_AFTER = timedelta(days=1)
MAX_FAILED_ATTEMPTS = 3


@dataclass(frozen=True)
class Outcome:
    site: str
    url: str
    status: CrawlStatus
    title: str | None = None
    reason: str | None = None
    score: float | None = None


@dataclass
class CrawlReport:
    pages_fetched: int = 0
    outcomes: list[Outcome] = field(default_factory=list)

    def with_status(self, status: CrawlStatus) -> list[Outcome]:
        return [o for o in self.outcomes if o.status == status]


# --------------------------------------------------------------------------- #
# What the crawler already knows                                              #
# --------------------------------------------------------------------------- #


def _is_settled(row: CrawledRecipe, now: datetime) -> bool:
    """Whether a page judged before should be left alone by discovery.

    Only an old rejection is judged again. Everything else is either done
    (``IMPORTED``) or already waiting in the backlog (``QUALIFIED``, ``FAILED``).
    """
    if row.status == CrawlStatus.REJECTED:
        return now - row.last_attempt_at < REJECTED_RECHECK_AFTER
    return True


def _public_source_urls(session: Session, urls: Sequence[str]) -> set[str]:
    """Pages a public recipe already cites, whoever imported it."""
    if not urls:
        return set()
    return {
        url
        for url in session.exec(
            select(Recipe.source_url).where(
                col(Recipe.is_public), col(Recipe.source_url).in_(urls)
            )
        ).all()
        if url
    }


def _settled_urls(session: Session, urls: Sequence[str], now: datetime) -> set[str]:
    """The URLs, among ``urls``, that need no judging."""
    if not urls:
        return set()
    rows = session.exec(
        select(CrawledRecipe).where(col(CrawledRecipe.url).in_(urls))
    ).all()
    settled = {row.url for row in rows if _is_settled(row, now)}
    # Imported by hand, or before the crawler existed: importing it again would
    # only duplicate it.
    return settled | _public_source_urls(session, urls)


def _backlog(
    session: Session, sites: Sequence[RecipeSite], now: datetime
) -> list[CrawledRecipe]:
    """Recipes waiting to be imported on ``sites``, best score first."""
    if not sites:
        return []
    return list(
        session.exec(
            select(CrawledRecipe)
            .where(col(CrawledRecipe.site).in_([site.slug for site in sites]))
            .where(
                or_(
                    col(CrawledRecipe.status) == CrawlStatus.QUALIFIED,
                    and_(
                        col(CrawledRecipe.status) == CrawlStatus.FAILED,
                        col(CrawledRecipe.attempts) < MAX_FAILED_ATTEMPTS,
                        col(CrawledRecipe.last_attempt_at) <= now - FAILED_RETRY_AFTER,
                    ),
                )
            )
            .order_by(
                col(CrawledRecipe.score).desc().nulls_last(),
                col(CrawledRecipe.first_seen_at),
            )
        ).all()
    )


def _record(
    session: Session,
    *,
    site: RecipeSite,
    url: str,
    status: CrawlStatus,
    assessment: quality.Assessment | None = None,
    score: float | None = None,
    reason: str | None = None,
    recipe_id: uuid.UUID | None = None,
    import_attempt: bool = False,
) -> None:
    row = session.exec(select(CrawledRecipe).where(CrawledRecipe.url == url)).first()
    if row is None:
        row = CrawledRecipe(site=site.slug, url=url, status=status)
    row.status = status
    row.reason = reason[:500] if reason else None
    row.last_attempt_at = get_datetime_utc()
    if import_attempt:
        row.attempts += 1
    if assessment is not None:
        row.title = assessment.title
        if assessment.rating is not None:
            row.rating_value = assessment.rating.value
            row.rating_count = assessment.rating.count
    if score is not None:
        row.score = score
    if recipe_id is not None:
        row.recipe_id = recipe_id
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        # Another runner recorded the same URL first; its verdict stands.
        session.rollback()


# --------------------------------------------------------------------------- #
# Judging                                                                     #
# --------------------------------------------------------------------------- #


def _judge_site(
    session: Session,
    site: RecipeSite,
    *,
    fetcher: PoliteFetcher,
    report: CrawlReport,
    pages: dict[str, str],
    max_pages: int,
    dry_run: bool,
    should_stop: Callable[[], bool],
) -> None:
    """Judge the next ``max_pages`` unjudged recipes one site ranks.

    Keeps the HTML of every qualifying page in ``pages``, so importing it later
    in the same run needs no second request.
    """
    links: list[str] = []
    for seed in site.seed_urls:
        page = fetcher.get(seed, site.origin)
        if page is None or page.status_code != 200:
            logger.warning(
                "Recipe crawl: cannot read %s (%s)",
                seed,
                "robots.txt" if page is None else f"HTTP {page.status_code}",
            )
            continue
        links.extend(
            url
            for url in discovery.recipe_links(page.text, page_url=seed, site=site)
            if url not in links
        )

    now = get_datetime_utc()
    settled = _settled_urls(session, links, now)
    fresh = [url for url in links if url not in settled]
    logger.info(
        "Recipe crawl: %s lists %d recipes, %d not yet judged",
        site.slug,
        len(links),
        len(fresh),
    )

    judged: set[str] = set()
    for url in fresh[:max_pages]:
        if should_stop():
            return
        page = fetcher.get(url, site.origin)
        if page is None or page.status_code != 200:
            reason = (
                "robots.txt disallows" if page is None else f"HTTP {page.status_code}"
            )
            report.outcomes.append(
                Outcome(site.slug, url, CrawlStatus.REJECTED, reason=reason)
            )
            if not dry_run:
                _record(
                    session,
                    site=site,
                    url=url,
                    status=CrawlStatus.REJECTED,
                    reason=reason,
                )
            continue

        canonical = discovery.canonical_url(page.text, fetched_url=url, site=site)
        if canonical in judged or (
            canonical != url and canonical in _settled_urls(session, [canonical], now)
        ):
            # Two listed URLs for one page: judge, and import, it once.
            continue
        judged.add(canonical)

        assessment = quality.assess(page.text, site)
        if assessment.rating is not None and assessment.qualifies:
            status = CrawlStatus.QUALIFIED
            score: float | None = quality.score(assessment.rating, site)
            pages[canonical] = page.text
        else:
            status, score = CrawlStatus.REJECTED, None
        report.outcomes.append(
            Outcome(
                site.slug,
                canonical,
                status,
                title=assessment.title,
                reason=assessment.rejection,
                score=score,
            )
        )
        if not dry_run:
            _record(
                session,
                site=site,
                url=canonical,
                status=status,
                assessment=assessment,
                score=score,
                reason=assessment.rejection,
            )


# --------------------------------------------------------------------------- #
# Importing                                                                   #
# --------------------------------------------------------------------------- #


def crawler_owner(session: Session) -> User:
    """The account crawled recipes belong to, created on first use.

    Inactive, with a password nobody knows: it exists to own recipes and to
    put a name on them, never to log in.
    """
    email = str(settings.RECIPE_CRAWL_OWNER_EMAIL)
    user = crud.get_user_by_email(session=session, email=email)
    if user is not None:
        return user
    user = crud.create_user(
        session=session,
        user_create=UserCreate(
            email=email,
            password=secrets.token_urlsafe(32),
            full_name=settings.PROJECT_NAME,
            is_active=False,
        ),
    )
    # Committed on its own: a failed import rolls back, and must not take the
    # account every later import is owned by with it.
    session.commit()
    return user


def llm_configured() -> bool:
    try:
        llm_module.get_llm()
    except ValueError:
        return False
    return True


def _take_turns(backlog: list[CrawledRecipe], limit: int) -> list[CrawledRecipe]:
    """Up to ``limit`` rows, one site at a time, the best site first.

    ``backlog`` is sorted best first, so each site's queue is too.
    """
    queues: dict[str, list[CrawledRecipe]] = {}
    for row in backlog:
        queues.setdefault(row.site, []).append(row)
    ordered = list(queues.values())  # dicts keep insertion order: best site first
    picked: list[CrawledRecipe] = []
    while len(picked) < limit and any(ordered):
        for queue in ordered:
            if queue and len(picked) < limit:
                picked.append(queue.pop(0))
    return picked


def _import(
    session: Session, *, url: str, html: str, site: RecipeSite, owner: User
) -> tuple[Recipe, list[uuid.UUID]]:
    parsed = import_recipe_from_html(url, html, language=site.language)
    recipe_in = parsed_to_create(parsed, is_public=True)
    if not recipe_in.title.strip() or not recipe_in.ingredients or not recipe_in.steps:
        raise ValueError("the model returned an incomplete recipe")
    recipe = crud.create_recipe(session=session, recipe_in=recipe_in, owner_id=owner.id)
    ids = crud.sync_ingredient_catalog(
        session=session, ingredients=recipe_in.ingredients
    )
    return recipe, ids


def _settle(
    session: Session,
    report: CrawlReport,
    row: CrawledRecipe,
    site: RecipeSite,
    status: CrawlStatus,
    *,
    reason: str | None = None,
    recipe: Recipe | None = None,
) -> None:
    """Report and record what became of one backlog entry."""
    report.outcomes.append(
        Outcome(
            site.slug,
            row.url,
            status,
            title=recipe.title if recipe else row.title,
            reason=reason,
            score=row.score,
        )
    )
    _record(
        session,
        site=site,
        url=row.url,
        status=status,
        reason=reason,
        recipe_id=recipe.id if recipe else None,
        import_attempt=status in (CrawlStatus.IMPORTED, CrawlStatus.FAILED),
    )


def _import_backlog(
    session: Session,
    sites: Sequence[RecipeSite],
    *,
    fetcher: PoliteFetcher,
    report: CrawlReport,
    pages: dict[str, str],
    max_imports: int,
    should_stop: Callable[[], bool],
) -> None:
    by_slug = {site.slug: site for site in sites}
    picked = _take_turns(_backlog(session, sites, get_datetime_utc()), max_imports)
    if not picked:
        return
    owner = crawler_owner(session)
    unavailable: set[str] = set()
    ingredient_ids: list[uuid.UUID] = []

    for row in picked:
        if should_stop() or fetcher.stopped:
            break
        site = by_slug[row.site]
        url = row.url
        if site.slug in unavailable:
            continue
        if url in _public_source_urls(session, [url]):
            _settle(
                session,
                report,
                row,
                site,
                CrawlStatus.REJECTED,
                reason="already a public recipe",
            )
            continue
        html = pages.get(url)
        if html is None:
            try:
                page = fetcher.get(url, site.origin)
            except SiteUnavailableError as exc:
                logger.warning("Recipe crawl: skipping %s: %s", site.slug, exc)
                unavailable.add(site.slug)
                continue
            if page is None or page.status_code != 200:
                _settle(
                    session,
                    report,
                    row,
                    site,
                    CrawlStatus.REJECTED,
                    reason="robots.txt disallows"
                    if page is None
                    else f"HTTP {page.status_code}",
                )
                continue
            html = page.text

        try:
            recipe, ids = _import(session, url=url, html=html, site=site, owner=owner)
        except Exception as exc:
            logger.exception("Recipe crawl: importing %s failed", url)
            session.rollback()
            _settle(
                session,
                report,
                row,
                site,
                CrawlStatus.FAILED,
                reason=f"{type(exc).__name__}: {exc}",
            )
            continue
        ingredient_ids.extend(i for i in ids if i not in ingredient_ids)
        _settle(session, report, row, site, CrawlStatus.IMPORTED, recipe=recipe)
        logger.info("Recipe crawl: imported %r from %s", recipe.title, url)

    if ingredient_ids:
        fetch_and_update_ingredients_batch(ingredient_ids)


# --------------------------------------------------------------------------- #
# The pass                                                                    #
# --------------------------------------------------------------------------- #


def crawl(
    session: Session,
    *,
    sites: Sequence[RecipeSite],
    max_imports: int,
    max_pages_per_site: int,
    delay_seconds: float,
    pause: Pause = sleep,
    should_stop: Callable[[], bool] = lambda: False,
    dry_run: bool = False,
) -> CrawlReport:
    """Run one pass. With ``dry_run``, judge but neither record nor import."""
    report = CrawlReport()
    fetcher = PoliteFetcher(delay=delay_seconds, pause=pause)
    pages: dict[str, str] = {}
    reachable: list[RecipeSite] = []

    for site in sites:
        if should_stop() or fetcher.stopped:
            break
        try:
            _judge_site(
                session,
                site,
                fetcher=fetcher,
                report=report,
                pages=pages,
                max_pages=max_pages_per_site,
                dry_run=dry_run,
                should_stop=should_stop,
            )
        except SiteUnavailableError as exc:
            logger.warning("Recipe crawl: skipping %s: %s", site.slug, exc)
            continue
        reachable.append(site)

    if not dry_run and not fetcher.stopped and not should_stop():
        _import_backlog(
            session,
            reachable,
            fetcher=fetcher,
            report=report,
            pages=pages,
            max_imports=max_imports,
            should_stop=should_stop,
        )
    report.pages_fetched = fetcher.pages_fetched
    return report


def run_crawl(
    session: Session,
    *,
    pause: Pause = sleep,
    should_stop: Callable[[], bool] = lambda: False,
) -> CrawlReport | None:
    """A logged pass with the configured limits. ``None`` when no AI provider
    is configured, since nothing could be imported."""
    if settings.RECIPE_CRAWL_MAX_IMPORTS == 0 or not llm_configured():
        logger.warning("Recipe crawl skipped: no imports allowed or no AI provider")
        return None
    run = RecipeCrawlRun()
    session.add(run)
    session.commit()
    report = crawl(
        session,
        sites=SITES,
        max_imports=settings.RECIPE_CRAWL_MAX_IMPORTS,
        max_pages_per_site=settings.RECIPE_CRAWL_MAX_PAGES_PER_SITE,
        delay_seconds=settings.RECIPE_CRAWL_DELAY_SECONDS,
        pause=pause,
        should_stop=should_stop,
    )
    run.finished_at = get_datetime_utc()
    run.pages_fetched = report.pages_fetched
    run.qualified_count = len(report.with_status(CrawlStatus.QUALIFIED))
    run.imported_count = len(report.with_status(CrawlStatus.IMPORTED))
    run.rejected_count = len(report.with_status(CrawlStatus.REJECTED))
    run.failed_count = len(report.with_status(CrawlStatus.FAILED))
    session.add(run)
    session.commit()
    logger.info(
        "Recipe crawl done: %d pages read, %d qualified, %d imported, "
        "%d rejected, %d failed",
        run.pages_fetched,
        run.qualified_count,
        run.imported_count,
        run.rejected_count,
        run.failed_count,
    )
    return report
