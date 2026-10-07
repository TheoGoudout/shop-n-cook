"""What the background jobs (price refresh, recipe crawl, reimport) share.

Every backend worker runs the same threads. A Postgres advisory lock lets one
of them do a job at a time, and a ``PeriodicJob`` checks every so often
whether the job is due.
"""

import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


@contextmanager
def advisory_lock(engine: Engine, key: int) -> Iterator[bool]:
    """Try to take advisory lock ``key`` for the block; yield whether it was.

    The lock belongs to a connection of its own, held for the whole block and
    released however it ends. Its transaction is ended at once, so that
    connection never sits "idle in transaction" while the job runs.
    """
    with engine.connect() as connection:
        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
            ).scalar()
        )
        connection.commit()
        try:
            yield acquired
        finally:
            if acquired:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                )
                connection.commit()


class PeriodicJob:
    """A daemon thread calling ``tick`` every ``check_seconds``.

    ``tick`` is handed the job's stop event: a long job checks ``is_set()``
    between steps, and waits on it rather than sleeping, so ``stop()`` is
    heard at once. A tick that raises is logged; the next one still runs.
    """

    def __init__(
        self,
        name: str,
        tick: Callable[[threading.Event], object],
        *,
        check_seconds: float,
        startup_delay_seconds: float,
    ) -> None:
        self.name = name
        self._tick = tick
        self._check_seconds = check_seconds
        self._startup_delay_seconds = startup_delay_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name=name, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Ask the loop to end. Work in flight finishes its current step; the
        thread is a daemon, so it never holds up shutdown."""
        self._stop.set()
        self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        if self._stop.wait(self._startup_delay_seconds):
            return
        while True:
            try:
                self._tick(self._stop)
            except Exception:
                logger.exception("%s tick failed", self.name)
            if self._stop.wait(self._check_seconds):
                return
