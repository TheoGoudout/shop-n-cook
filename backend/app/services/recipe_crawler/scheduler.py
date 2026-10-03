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
import threading
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import RecipeCrawlRun
from app.models.base import get_datetime_utc
from app.services.recipe_crawler.crawler import CrawlReport, Pause, run_crawl

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
    with engine.connect() as lock_connection:
        acquired = lock_connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
        ).scalar()
        lock_connection.commit()
        if not acquired:
            return None
        try:
            with Session(engine) as session:
                if not is_due(session, now=get_datetime_utc(), interval=interval):
                    return None
                return run_crawl(session, pause=pause, should_stop=should_stop)
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY}
            )
            lock_connection.commit()


class RecipeCrawlScheduler:
    """A daemon thread calling ``run_once`` every ``check_seconds``."""

    def __init__(
        self,
        engine: Engine,
        *,
        interval: timedelta,
        check_seconds: float = CHECK_SECONDS,
        startup_delay_seconds: float = STARTUP_DELAY_SECONDS,
    ) -> None:
        self._engine = engine
        self._interval = interval
        self._check_seconds = check_seconds
        self._startup_delay_seconds = startup_delay_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, name="recipe-crawl", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Ask the loop to end. The pause between two requests wakes at once;
        an LLM call in flight finishes first, but the thread is a daemon."""
        self._stop.set()
        self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        if self._stop.wait(self._startup_delay_seconds):
            return
        while True:
            try:
                run_once(
                    self._engine,
                    interval=self._interval,
                    pause=self._stop.wait,
                    should_stop=self._stop.is_set,
                )
            except Exception:
                logger.exception("Recipe crawl tick failed")
            if self._stop.wait(self._check_seconds):
                return


def start_recipe_crawl_scheduler(engine: Engine) -> RecipeCrawlScheduler | None:
    """Start the background crawl, unless ``RECIPE_CRAWL_HOURS`` is 0."""
    hours = settings.RECIPE_CRAWL_HOURS
    if hours <= 0:
        return None
    scheduler = RecipeCrawlScheduler(engine, interval=timedelta(hours=hours))
    scheduler.start()
    return scheduler
