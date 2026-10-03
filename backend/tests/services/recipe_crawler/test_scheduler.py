"""When the crawler runs, and that only one worker runs it."""

from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import text
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine
from app.models import RecipeCrawlRun
from app.models.base import get_datetime_utc
from app.services.recipe_crawler import scheduler
from app.services.recipe_crawler.crawler import CrawlReport

DAY = timedelta(hours=24)
RUN_CRAWL = "app.services.recipe_crawler.scheduler.run_crawl"


def _last_run(db: Session, *, hours_ago: float | None) -> None:
    db.exec(delete(RecipeCrawlRun))
    if hours_ago is not None:
        db.add(
            RecipeCrawlRun(started_at=get_datetime_utc() - timedelta(hours=hours_ago))
        )
    db.commit()


def test_due_when_it_never_ran(db: Session) -> None:
    _last_run(db, hours_ago=None)
    assert scheduler.is_due(db, now=get_datetime_utc(), interval=DAY)


def test_due_once_the_interval_has_passed(db: Session) -> None:
    _last_run(db, hours_ago=25)
    assert scheduler.is_due(db, now=get_datetime_utc(), interval=DAY)
    _last_run(db, hours_ago=2)
    assert not scheduler.is_due(db, now=get_datetime_utc(), interval=DAY)


def test_run_once_crawls_when_due(db: Session) -> None:
    _last_run(db, hours_ago=None)
    report = CrawlReport(pages_fetched=1)
    with patch(RUN_CRAWL, return_value=report) as run_crawl:
        result = scheduler.run_once(engine, interval=DAY, pause=lambda _s: False)
    assert result is report
    run_crawl.assert_called_once()


def test_run_once_does_nothing_when_not_due(db: Session) -> None:
    _last_run(db, hours_ago=1)
    with patch(RUN_CRAWL) as run_crawl:
        assert scheduler.run_once(engine, interval=DAY, pause=lambda _s: False) is None
    run_crawl.assert_not_called()


def test_run_once_leaves_the_crawl_to_the_worker_holding_the_lock(
    db: Session,
) -> None:
    _last_run(db, hours_ago=None)
    with engine.connect() as other_worker:
        other_worker.execute(
            text("SELECT pg_advisory_lock(:key)"),
            {"key": scheduler.ADVISORY_LOCK_KEY},
        )
        try:
            with patch(RUN_CRAWL) as run_crawl:
                assert (
                    scheduler.run_once(engine, interval=DAY, pause=lambda _s: False)
                    is None
                )
            run_crawl.assert_not_called()
        finally:
            other_worker.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": scheduler.ADVISORY_LOCK_KEY},
            )


def test_off_by_default() -> None:
    assert settings.RECIPE_CRAWL_HOURS == 0
    assert scheduler.start_recipe_crawl_scheduler(engine) is None


def test_starts_and_stops_when_enabled() -> None:
    with patch.object(settings, "RECIPE_CRAWL_HOURS", 24):
        started = scheduler.start_recipe_crawl_scheduler(engine)
    assert started is not None
    # The startup delay keeps the thread from crawling before stop() is heard.
    started.stop(timeout=5)
    assert not started._thread.is_alive()
