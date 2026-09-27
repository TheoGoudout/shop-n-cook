"""The background price refresh: what is due, who runs it, and when it stops.

Runs against the real database, because the part most worth testing — only
one worker refreshing at a time — is a Postgres advisory lock.
"""

import threading
from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import text
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.models.base import get_datetime_utc
from app.models.store import Store, StoreCreate
from app.services.store_providers import scheduler
from app.services.store_providers.families import openprices_snapshot
from app.services.store_providers.refresh import RefreshResult
from tests.utils.utils import random_lower_string

DAY = timedelta(hours=24)
SCHEDULER = "app.services.store_providers.scheduler"


def _store(
    db: Session,
    *,
    provider_slug: str | None = "openprices",
    refreshed_hours_ago: float | None = None,
    is_active: bool = True,
) -> Store:
    store = crud.create_store(
        session=db,
        store_in=StoreCreate(
            slug=f"sched-{random_lower_string()[:10]}",
            name="Scheduled",
            provider_slug=provider_slug,
            is_active=is_active,
        ),
    )
    if refreshed_hours_ago is not None:
        store.prices_refreshed_at = get_datetime_utc() - timedelta(
            hours=refreshed_hours_ago
        )
        db.add(store)
        db.commit()
        db.refresh(store)
    return store


def _result(store: Store, *, stopped_early: bool = False) -> RefreshResult:
    return RefreshResult(
        store_id=str(store.id),
        store_name=store.name,
        provider_slug=store.provider_slug or "",
        refreshed_count=3,
        stopped_early=stopped_early,
    )


class TestDueStores:
    def test_never_refreshed_and_stale_stores_are_due_fresh_ones_are_not(
        self, db: Session
    ) -> None:
        never = _store(db)
        stale = _store(db, refreshed_hours_ago=25)
        fresh = _store(db, refreshed_hours_ago=1)
        due = scheduler.due_stores(db, now=get_datetime_utc(), interval=DAY)
        ids = [s.id for s in due]
        assert never.id in ids
        assert stale.id in ids
        assert fresh.id not in ids
        assert ids.index(never.id) < ids.index(stale.id), "never-refreshed first"

    def test_stores_that_cannot_be_refreshed_are_never_due(self, db: Session) -> None:
        curated = _store(db, provider_slug=None)
        removed = _store(db, provider_slug="a-provider-that-was-removed")
        inactive = _store(db, is_active=False)
        ids = {
            s.id for s in scheduler.due_stores(db, now=get_datetime_utc(), interval=DAY)
        }
        assert not ids & {curated.id, removed.id, inactive.id}


class TestRefreshDueStores:
    def test_a_complete_refresh_is_stamped(self, db: Session) -> None:
        store = _store(db)
        with (
            patch(f"{SCHEDULER}.due_stores", return_value=[store]),
            patch(
                f"{SCHEDULER}.refresh_store_prices", return_value=_result(store)
            ) as refresh,
        ):
            results = scheduler.refresh_due_stores(db, interval=DAY)
        assert [r.store_id for r in results] == [str(store.id)]
        assert refresh.call_args.kwargs["store"] is store
        db.refresh(store)
        assert store.prices_refreshed_at is not None

    def test_an_interrupted_refresh_stays_due(self, db: Session) -> None:
        store = _store(db)
        with (
            patch(f"{SCHEDULER}.due_stores", return_value=[store]),
            patch(
                f"{SCHEDULER}.refresh_store_prices",
                return_value=_result(store, stopped_early=True),
            ),
        ):
            scheduler.refresh_due_stores(db, interval=DAY)
        db.refresh(store)
        assert store.prices_refreshed_at is None

    def test_one_broken_store_does_not_starve_the_others(self, db: Session) -> None:
        broken, fine = _store(db), _store(db)

        def refresh(**kwargs: object) -> RefreshResult:
            store = kwargs["store"]
            assert isinstance(store, Store)
            if store.id == broken.id:
                raise RuntimeError("a parser bug")
            return _result(store)

        with (
            patch(f"{SCHEDULER}.due_stores", return_value=[broken, fine]),
            patch(f"{SCHEDULER}.refresh_store_prices", side_effect=refresh),
        ):
            results = scheduler.refresh_due_stores(db, interval=DAY)
        assert [r.store_id for r in results] == [str(fine.id)]

    def test_a_stop_request_ends_the_run_between_stores(self, db: Session) -> None:
        first, second = _store(db), _store(db)
        calls: list[Store] = []

        def refresh(**kwargs: object) -> RefreshResult:
            store = kwargs["store"]
            assert isinstance(store, Store)
            calls.append(store)
            return _result(store)

        with (
            patch(f"{SCHEDULER}.due_stores", return_value=[first, second]),
            patch(f"{SCHEDULER}.refresh_store_prices", side_effect=refresh),
        ):
            scheduler.refresh_due_stores(
                db, interval=DAY, should_stop=lambda: len(calls) == 1
            )
        assert calls == [first]


class TestRunOnce:
    def test_runs_and_releases_the_lock_and_the_snapshot(self) -> None:
        with (
            patch(f"{SCHEDULER}.refresh_due_stores", return_value=[]) as refresh,
            patch.object(openprices_snapshot, "clear_cache") as clear,
        ):
            assert scheduler.run_once(engine, interval=DAY) == []
        refresh.assert_called_once()
        clear.assert_called_once()
        with engine.connect() as connection:
            acquired = connection.execute(
                text("SELECT pg_try_advisory_lock(:k)"),
                {"k": scheduler.ADVISORY_LOCK_KEY},
            ).scalar()
            connection.execute(
                text("SELECT pg_advisory_unlock(:k)"),
                {"k": scheduler.ADVISORY_LOCK_KEY},
            )
        assert acquired is True, "the lock must be free once the run is over"

    def test_another_worker_holding_the_lock_means_this_one_skips(self) -> None:
        with engine.connect() as other_worker:
            other_worker.execute(
                text("SELECT pg_advisory_lock(:k)"),
                {"k": scheduler.ADVISORY_LOCK_KEY},
            )
            try:
                with patch(f"{SCHEDULER}.refresh_due_stores") as refresh:
                    assert scheduler.run_once(engine, interval=DAY) is None
                refresh.assert_not_called()
            finally:
                other_worker.execute(
                    text("SELECT pg_advisory_unlock(:k)"),
                    {"k": scheduler.ADVISORY_LOCK_KEY},
                )

    def test_the_lock_is_released_even_when_the_run_fails(self) -> None:
        with patch(f"{SCHEDULER}.refresh_due_stores", side_effect=RuntimeError("x")):
            try:
                scheduler.run_once(engine, interval=DAY)
            except RuntimeError:
                pass
        with patch(f"{SCHEDULER}.refresh_due_stores", return_value=[]):
            assert scheduler.run_once(engine, interval=DAY) == []


class TestThread:
    def test_disabled_when_the_interval_is_zero(self) -> None:
        assert settings.STORE_PRICE_REFRESH_HOURS == 0, "tests run with it off"
        assert scheduler.start_price_refresh_scheduler(engine) is None

    def test_ticks_until_stopped(self) -> None:
        ticked = threading.Event()

        def run_once(*_: object, **__: object) -> None:
            ticked.set()
            raise RuntimeError("a failed tick must not kill the thread")

        with patch(f"{SCHEDULER}.run_once", side_effect=run_once) as tick:
            job = scheduler.PriceRefreshScheduler(
                engine, interval=DAY, check_seconds=0.01, startup_delay_seconds=0
            )
            job.start()
            assert ticked.wait(timeout=5)
            job.stop()
        assert tick.call_count >= 1
        assert not job._thread.is_alive()

    def test_started_when_enabled(self) -> None:
        with (
            patch.object(settings, "STORE_PRICE_REFRESH_HOURS", 24),
            patch.object(scheduler.PriceRefreshScheduler, "start") as start,
        ):
            job = scheduler.start_price_refresh_scheduler(engine)
        assert job is not None
        assert job._interval == DAY
        start.assert_called_once()
