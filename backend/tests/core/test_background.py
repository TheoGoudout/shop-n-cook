"""The building blocks every background job shares."""

import threading

from sqlalchemy import text

from app.core.background import PeriodicJob, advisory_lock
from app.core.db import engine

KEY = 0x54_45_53_54  # "TEST"


def test_a_held_lock_is_refused_then_released() -> None:
    with advisory_lock(engine, KEY) as first:
        assert first
        with advisory_lock(engine, KEY) as second:
            assert not second
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": KEY}
        ).scalar()
        connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": KEY})


def test_the_lock_is_released_when_the_block_raises() -> None:
    try:
        with advisory_lock(engine, KEY):
            raise RuntimeError("the job failed")
    except RuntimeError:
        pass
    with advisory_lock(engine, KEY) as acquired:
        assert acquired


def test_a_job_ticks_until_stopped_even_when_a_tick_fails() -> None:
    ticked = threading.Event()

    def tick(_stop: threading.Event) -> None:
        ticked.set()
        raise RuntimeError("a failed tick must not kill the thread")

    job = PeriodicJob("test", tick, check_seconds=0.01, startup_delay_seconds=0)
    job.start()
    assert ticked.wait(timeout=5)
    job.stop()
    assert not job._thread.is_alive()


def test_stop_is_heard_during_the_startup_delay() -> None:
    job = PeriodicJob(
        "test", lambda _stop: None, check_seconds=60, startup_delay_seconds=60
    )
    job.start()
    job.stop(timeout=5)
    assert not job._thread.is_alive()
