"""Run the recipe crawler every ``RECIPE_CRAWL_HOURS``, in the background.

Built like the store price refresh (``store_providers/scheduler.py``), for the
same reasons:

- **One runner.** Every backend worker runs this thread; a Postgres advisory
  lock (a different key from the price refresh's) lets one of them crawl at a
  time. The unique URL on ``CrawledRecipe`` backs it up: even two runners
  could not import one page twice.
- **Due, not scheduled.** A run is due once the latest ``RecipeCrawlRun``
  started more than ``RECIPE_CRAWL_HOURS`` ago, so a restart or a deploy just
  means the next hourly check catches up.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.core.background import PeriodicJob, advisory_lock
from app.core.config import settings
from app.models import RecipeCrawlRun
from app.models.base import get_datetime_utc
from app.services.recipe_crawler.crawler import CrawlReport, run_crawl
from app.services.recipe_crawler.fetcher import Pause

logger = logging.getLogger(__name__)

ADVISORY_LOCK_KEY = 0x53_4E_43_52_45_43_49_50  # "SNCRECIP"
CHECK_SECONDS = 60 * 60
#: Longer than the price refresh's, so the two do not start together.
STARTUP_DELAY_SECONDS = 15 * 60


def is_due(session: Session, *, now: datetime, interval: timedelta) -> bool:
    last_started = session.exec(
        select(RecipeCrawlRun.started_at)
        .order_by(col(RecipeCrawlRun.started_at).desc())
        .limit(1)
    ).first()
    return last_started is None or now - last_started >= interval


def run_once(
    engine: Engine,
    *,
    interval: timedelta,
    pause: Pause,
    should_stop: Callable[[], bool] = lambda: False,
) -> CrawlReport | None:
    """One tick: take the lock and crawl if a run is due. ``None`` if another
    worker holds the lock, no run is due, or the crawl was skipped."""
    with advisory_lock(engine, ADVISORY_LOCK_KEY) as acquired:
        if not acquired:
            return None
        with Session(engine) as session:
            if not is_due(session, now=get_datetime_utc(), interval=interval):
                return None
            return run_crawl(session, pause=pause, should_stop=should_stop)


def start_recipe_crawl_scheduler(engine: Engine) -> PeriodicJob | None:
    """Start the background crawl, unless ``RECIPE_CRAWL_HOURS`` is 0."""
    hours = settings.RECIPE_CRAWL_HOURS
    if hours <= 0:
        return None
    interval = timedelta(hours=hours)
    job = PeriodicJob(
        "recipe-crawl",
        # Waiting on the stop event between requests is what lets stop() be
        # heard mid-crawl; an LLM call in flight finishes first.
        lambda stop: run_once(
            engine, interval=interval, pause=stop.wait, should_stop=stop.is_set
        ),
        check_seconds=CHECK_SECONDS,
        startup_delay_seconds=STARTUP_DELAY_SECONDS,
    )
    job.start()
    return job
