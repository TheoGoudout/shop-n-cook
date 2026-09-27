"""Every Open Prices price, from one daily download instead of one call per line.

Open Prices publishes its whole price table as a Parquet file, rebuilt daily:

    https://huggingface.co/datasets/openfoodfacts/open-prices

About 33 MB for ~317,000 prices (2026-09). Pricing a barcode through the API
costs a request per batch per chain; refreshing six chains over a few thousand
ingredients would be tens of thousands of requests a day. The file is one.

What is kept is exactly what ``OpenPricesProvider`` would have asked the API
for: barcode prices, undiscounted, priced per item, dated. Prices are read
from the file's ``decimal128`` column, so they arrive as ``Decimal`` and never
pass through a float.

The file carries no product names for barcodes, which is why catalogue search
still goes to the API (``/products``) — once per query, cached, and shared by
every chain.
"""

from __future__ import annotations

import io
import sys
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from app.services.pricing import quantize_money
from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families import http_client

DUMP_URL = (
    "https://huggingface.co/datasets/openfoodfacts/open-prices"
    "/resolve/main/prices.parquet"
)
#: The dump is rebuilt daily; so is our copy.
SNAPSHOT_SECONDS = 24 * 60 * 60
#: After a failed download, wait this long before trying again. Callers fall
#: back to the API meanwhile, so a bad hour costs speed, not answers.
RETRY_SECONDS = 60 * 60
DOWNLOAD_TIMEOUT = 120.0
#: ~15x today's size. A cap, not an estimate.
MAX_DUMP_BYTES = 512 * 1024 * 1024
#: A price older than this is history, not a price. Also bounds memory: older
#: rows are dropped while the file is read.
MAX_PRICE_AGE_DAYS = 365

_COLUMNS = [
    "id",
    "type",
    "product_code",
    "price",
    "price_is_discounted",
    "price_per",
    "currency",
    "location_id",
    "date",
]


@dataclass(frozen=True, slots=True)
class _Observation:
    day: date
    row_id: int
    location_id: int
    currency: str
    price: Decimal


class PriceSnapshot:
    """Qualifying observations per barcode, newest first."""

    def __init__(self, by_code: dict[str, list[_Observation]]) -> None:
        self._by_code = by_code

    def __len__(self) -> int:
        return sum(len(rows) for rows in self._by_code.values())

    def latest(
        self,
        codes: Iterable[str],
        *,
        currency: str,
        since: date,
        location_ids: frozenset[int] | None = None,
    ) -> dict[str, Decimal]:
        """The newest price per barcode, optionally only from some shops."""
        found: dict[str, Decimal] = {}
        for code in codes:
            for row in self._by_code.get(code, ()):
                if row.day < since:
                    break  # newest first: nothing older can qualify either
                if row.currency != currency:
                    continue
                if location_ids is not None and row.location_id not in location_ids:
                    continue
                found[code] = row.price
                break
        return found


def oldest_price_date() -> date:
    return date.today() - timedelta(days=MAX_PRICE_AGE_DAYS)


def parse(data: bytes, *, since: date | None = None) -> PriceSnapshot:
    """Build a snapshot from the Parquet file's bytes.

    Rows dated before ``since`` (default: ``MAX_PRICE_AGE_DAYS`` ago) are
    dropped. Conversion to Python happens column by column on the survivors
    only, which keeps the peak to a fraction of materialising every row.
    """
    since = since or oldest_price_date()
    try:
        table = pq.read_table(io.BytesIO(data), columns=_COLUMNS)
    except Exception as exc:  # pyarrow raises a family of its own errors
        raise ProviderUnavailableError(
            f"Open Prices dump is unreadable: {exc}"
        ) from exc

    # Filtered in Arrow, before any row becomes a Python object. The same rules
    # as the API path: a barcode, priced per item, undiscounted, dated, located.
    # Comparisons against null are null, which ``filter`` drops — so a row with
    # an unknown discount flag or ``price_per`` only survives where the
    # expression explicitly allows the null.
    keep = (
        (pc.field("type") == "PRODUCT")
        & (pc.field("price_is_discounted") == False)  # noqa: E712 (an Arrow expression)
        & (pc.field("price_per").is_null() | (pc.field("price_per") == "UNIT"))
        & pc.field("product_code").is_valid()
        & (pc.field("date") >= pa.scalar(since, type=pa.date32()))
        & pc.field("location_id").is_valid()
        & pc.field("currency").is_valid()
    )
    kept = table.filter(keep)
    del table
    columns = {
        name: kept.column(name).to_pylist()
        for name in ("id", "product_code", "price", "currency", "location_id", "date")
    }
    del kept

    by_code: dict[str, list[_Observation]] = {}
    for row_id, code, price, currency, location_id, day in zip(
        columns["id"],
        columns["product_code"],
        columns["price"],
        columns["currency"],
        columns["location_id"],
        columns["date"],
        strict=True,
    ):
        if not isinstance(price, Decimal) or not price.is_finite() or price <= 0:
            continue
        by_code.setdefault(str(code), []).append(
            _Observation(
                day=day,
                row_id=int(row_id),
                location_id=int(location_id),
                # One shared "EUR", not 150,000 copies of it.
                currency=sys.intern(str(currency)),
                price=quantize_money(price),
            )
        )
    for observations in by_code.values():
        # Newest first; on the same day, the later-recorded one.
        observations.sort(key=lambda o: (o.day, o.row_id), reverse=True)
    return PriceSnapshot(by_code)


_lock = threading.Lock()
_snapshot: tuple[float, PriceSnapshot] | None = None
_failed_at: float | None = None


def get_snapshot() -> PriceSnapshot:
    """Today's snapshot, downloading it at most once a day.

    Raises ``ProviderUnavailableError`` when it cannot be had, immediately and
    without retrying for ``RETRY_SECONDS`` after a failure, so a caller pricing
    a thousand lines does not download a thousand times.
    """
    global _snapshot, _failed_at
    with _lock:
        now = time.monotonic()
        if _snapshot is not None and now - _snapshot[0] < SNAPSHOT_SECONDS:
            return _snapshot[1]
        if _failed_at is not None and now - _failed_at < RETRY_SECONDS:
            raise ProviderUnavailableError("Open Prices dump failed recently")
        try:
            data = http_client.get_bytes(
                DUMP_URL, timeout=DOWNLOAD_TIMEOUT, max_bytes=MAX_DUMP_BYTES
            )
            snapshot = parse(data)
        except ProviderUnavailableError:
            _failed_at = now
            raise
        _snapshot, _failed_at = (now, snapshot), None
        return snapshot


def clear_cache() -> None:
    """Forget the snapshot.

    The scheduler calls this when a refresh run ends: the snapshot is worth
    ~140 MB and nothing outside that run needs it, so a worker should not
    carry it for the rest of the day.
    """
    global _snapshot, _failed_at
    with _lock:
        _snapshot, _failed_at = None, None
