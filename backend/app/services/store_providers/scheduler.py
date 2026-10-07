"""Refresh every provider-backed store's prices, once a day, in the background.

Users never wait on a retailer: costing a list reads ``IngredientPrice`` rows
through ``PriceBook``, and this job is what keeps those rows current. It runs
inside the backend rather than as an external cron so a deployment needs no
extra setup, which leaves two things to get right:

- **One runner.** The backend runs several workers (``fastapi run --workers
  4``), each with its own copy of this thread. A Postgres advisory lock lets
  exactly one of them work at a time; the others find it taken and go back to
  sleep. The lock lives on the database, so it holds across containers too.
- **Due, not scheduled.** Each tick refreshes the stores whose
  ``prices_refreshed_at`` is older than ``STORE_PRICE_REFRESH_HOURS``. A
  restart, a deploy or a missed night therefore just means the next tick
  catches up — there is no "02:00" to miss.

A store is only stamped after a complete refresh. One whose retailer was
unreachable stays due and is retried on the next hourly tick; that retry is
cheap, because a provider stops at the first failure.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, or_, select

from app.core.background import PeriodicJob, advisory_lock
from app.core.config import settings
from app.models.base import get_datetime_utc
from app.models.ingredient import Ingredient
from app.models.store import Store
from app.services.store_providers.errors import ProviderNotFoundError
from app.services.store_providers.families import openprices_snapshot
from app.services.store_providers.models import Capability
from app.services.store_providers.refresh import RefreshResult, refresh_store_prices
from app.services.store_providers.registry import get_provider

logger = logging.getLogger(__name__)

#: Arbitrary, but fixed: every worker must ask for the same lock.
ADVISORY_LOCK_KEY = 0x53_4E_43_50_52_49_43_45  # "SNCPRICE"
#: How often a worker wakes to look for due stores.
CHECK_SECONDS = 60 * 60
#: Grace after startup, so a deploy or a dev reload is not slowed by a refresh.
STARTUP_DELAY_SECONDS = 5 * 60


def due_stores(session: Session, *, now: datetime, interval: timedelta) -> list[Store]:
    """Active stores with a pricing provider, stalest first."""
    cutoff = now - interval
    stores = session.exec(
        select(Store)
        .where(col(Store.is_active))
        .where(col(Store.provider_slug).is_not(None))
        .where(
            or_(
                col(Store.prices_refreshed_at).is_(None),
                col(Store.prices_refreshed_at) < cutoff,
            )
        )
        .order_by(col(Store.prices_refreshed_at).asc().nulls_first(), col(Store.slug))
    ).all()
    return [store for store in stores if _can_price(store)]


def _can_price(store: Store) -> bool:
    try:
        provider = get_provider(store.provider_slug or "")
    except ProviderNotFoundError:
        # A slug this build no longer registers: a curated store now.
        return False
    return provider.supports(Capability.PRICES)


def refresh_due_stores(
    session: Session,
    *,
    interval: timedelta,
    should_stop: Callable[[], bool] = lambda: False,
) -> list[RefreshResult]:
    """Refresh every due store over the whole ingredient catalogue.

    Assumes the caller holds the advisory lock. A store that raises is logged
    and skipped, so one broken retailer cannot starve the others.
    """
    results: list[RefreshResult] = []
    ingredients = list(
        session.exec(select(Ingredient).order_by(col(Ingredient.name))).all()
    )
    for store in due_stores(session, now=get_datetime_utc(), interval=interval):
        if should_stop():
            break
        provider = get_provider(store.provider_slug or "")
        try:
            result = refresh_store_prices(
                session=session,
                store=store,
                provider=provider,
                ingredients=ingredients,
            )
        except Exception:
            logger.exception("Price refresh failed for store %s", store.slug)
            session.rollback()
            continue

        if not result.stopped_early:
            store.prices_refreshed_at = get_datetime_utc()
            session.add(store)
        # One transaction per store: its prices land together, or not at all.
        session.commit()
        logger.info(
            "Refreshed %s: %d priced, %d skipped%s",
            store.slug,
            result.refreshed_count,
            len(result.skipped),
            " (stopped early: retailer unreachable)" if result.stopped_early else "",
        )
        results.append(result)
    return results


def run_once(
    engine: Engine,
    *,
    interval: timedelta,
    should_stop: Callable[[], bool] = lambda: False,
) -> list[RefreshResult] | None:
    """One tick: take the lock, refresh what is due. ``None`` if another
    worker holds the lock."""
    with advisory_lock(engine, ADVISORY_LOCK_KEY) as acquired:
        if not acquired:
            return None
        try:
            with Session(engine) as session:
                return refresh_due_stores(
                    session, interval=interval, should_stop=should_stop
                )
        finally:
            # Only this run needed the day's price table; free it now rather
            # than hold it in a web worker until tomorrow.
            openprices_snapshot.clear_cache()


def start_price_refresh_scheduler(engine: Engine) -> PeriodicJob | None:
    """Start the background refresh, unless ``STORE_PRICE_REFRESH_HOURS`` is 0."""
    hours = settings.STORE_PRICE_REFRESH_HOURS
    if hours <= 0:
        return None
    interval = timedelta(hours=hours)
    job = PeriodicJob(
        "price-refresh",
        lambda stop: run_once(engine, interval=interval, should_stop=stop.is_set),
        check_seconds=CHECK_SECONDS,
        startup_delay_seconds=STARTUP_DELAY_SECONDS,
    )
    job.start()
    return job
