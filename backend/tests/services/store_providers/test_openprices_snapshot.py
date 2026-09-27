"""The daily Open Prices snapshot, and the provider reading prices from it.

Parquet fixtures are built in memory with the dump's own column types, so the
decimal and date handling under test is the real one.
"""

import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families import openprices_snapshot
from app.services.store_providers.families.openprices import (
    ChainFilter,
    OpenPricesProvider,
)
from app.services.store_providers.families.openprices_snapshot import (
    PriceSnapshot,
    get_snapshot,
    parse,
)
from app.services.store_providers.models import StoreProduct

TODAY = date.today()
RECENT = TODAY - timedelta(days=10)
SINCE = TODAY - timedelta(days=365)

SCHEMA = pa.schema(
    [
        ("id", pa.int64()),
        ("type", pa.string()),
        ("product_code", pa.string()),
        ("price", pa.decimal128(10, 3)),
        ("price_is_discounted", pa.bool_()),
        ("price_per", pa.string()),
        ("currency", pa.string()),
        ("location_id", pa.int32()),
        ("date", pa.date32()),
        # A column the snapshot does not read, as the real dump has dozens.
        ("owner", pa.string()),
    ]
)


def _row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": 1,
        "type": "PRODUCT",
        "product_code": "111",
        "price": Decimal("1.250"),
        "price_is_discounted": False,
        "price_per": None,
        "currency": "EUR",
        "location_id": 10,
        "date": RECENT,
        "owner": "someone",
    }
    row.update(overrides)
    return row


def _parquet(rows: list[dict[str, Any]]) -> bytes:
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), buffer)
    return buffer.getvalue()


def _latest(rows: list[dict[str, Any]], **kwargs: Any) -> dict[str, Decimal]:
    snapshot = parse(_parquet(rows), since=SINCE)
    params: dict[str, Any] = {"currency": "EUR", "since": SINCE, **kwargs}
    return snapshot.latest(["111"], **params)


class TestParse:
    def test_price_is_exact_money(self) -> None:
        prices = _latest([_row()])
        assert prices == {"111": Decimal("1.25")}
        assert str(prices["111"]) == "1.25"

    @pytest.mark.parametrize(
        "row",
        [
            _row(price_is_discounted=True),
            _row(price_is_discounted=None),
            _row(price_per="KILOGRAM"),
            _row(type="CATEGORY"),
            _row(product_code=None),
            _row(date=None),
            _row(location_id=None),
            _row(currency=None),
            _row(price=Decimal("0")),
            _row(date=SINCE - timedelta(days=1)),
        ],
    )
    def test_rows_that_are_not_a_current_unit_price_are_dropped(
        self, row: dict[str, Any]
    ) -> None:
        assert _latest([row]) == {}

    def test_a_per_unit_price_is_kept(self) -> None:
        assert _latest([_row(price_per="UNIT")]) == {"111": Decimal("1.25")}

    def test_the_newest_observation_wins(self) -> None:
        rows = [
            _row(id=1, date=RECENT - timedelta(days=5), price=Decimal("1.00")),
            _row(id=2, date=RECENT, price=Decimal("2.00")),
        ]
        assert _latest(rows) == {"111": Decimal("2.00")}

    def test_on_the_same_day_the_later_record_wins(self) -> None:
        rows = [
            _row(id=9, price=Decimal("3.00")),
            _row(id=4, price=Decimal("2.00")),
        ]
        assert _latest(rows) == {"111": Decimal("3.00")}

    def test_currency_and_shops_filter_the_answer(self) -> None:
        rows = [
            _row(id=3, currency="CHF", price=Decimal("9.00")),
            _row(id=2, location_id=99, price=Decimal("8.00")),
            _row(id=1, location_id=10, price=Decimal("1.00")),
        ]
        assert _latest(rows, location_ids=frozenset({10})) == {"111": Decimal("1.00")}
        assert _latest(rows) == {"111": Decimal("8.00")}
        assert _latest(rows, currency="CHF") == {"111": Decimal("9.00")}

    def test_a_later_since_hides_older_prices(self) -> None:
        snapshot = parse(_parquet([_row()]), since=SINCE)
        assert snapshot.latest(["111"], currency="EUR", since=TODAY) == {}

    def test_garbage_is_unavailable_not_a_crash(self) -> None:
        with pytest.raises(ProviderUnavailableError, match="unreadable"):
            parse(b"not parquet")


class TestDownload:
    def test_downloaded_once_then_reused(self) -> None:
        with patch(
            "app.services.store_providers.families.http_client.get_bytes",
            return_value=_parquet([_row()]),
        ) as get_bytes:
            first = get_snapshot()
            second = get_snapshot()
        assert first is second
        get_bytes.assert_called_once()
        assert get_bytes.call_args.args[0] == openprices_snapshot.DUMP_URL

    def test_a_failure_is_not_retried_straight_away(self) -> None:
        with patch(
            "app.services.store_providers.families.http_client.get_bytes",
            side_effect=ProviderUnavailableError("503"),
        ) as get_bytes:
            with pytest.raises(ProviderUnavailableError):
                get_snapshot()
            with pytest.raises(ProviderUnavailableError, match="recently"):
                get_snapshot()
        get_bytes.assert_called_once()

    def test_a_stale_snapshot_is_downloaded_again(self) -> None:
        with (
            patch(
                "app.services.store_providers.families.http_client.get_bytes",
                return_value=_parquet([_row()]),
            ) as get_bytes,
            patch(
                "app.services.store_providers.families.openprices_snapshot.time.monotonic",
                side_effect=[0.0, openprices_snapshot.SNAPSHOT_SECONDS + 1],
            ),
        ):
            get_snapshot()
            get_snapshot()
        assert get_bytes.call_count == 2


LOCATIONS = {
    "items": [
        {"id": 10, "osm_brand": "Carrefour", "osm_address_country_code": "FR"},
        {"id": 99, "osm_brand": "Carrefour City", "osm_address_country_code": "FR"},
    ],
    "pages": 1,
}
PRODUCTS = {"items": [{"code": "111", "product_name": "Beurre doux"}]}


class TestProviderOnTheSnapshot:
    def _snapshot(self) -> PriceSnapshot:
        return parse(
            _parquet(
                [
                    _row(id=2, location_id=99, price=Decimal("2.40")),
                    _row(id=1, location_id=10, price=Decimal("1.95")),
                ]
            ),
            since=SINCE,
        )

    def _get_json(self, calls: list[str]) -> Any:
        def get_json(url: str, **_: Any) -> Any:
            calls.append(url)
            if url.endswith("/locations"):
                return LOCATIONS
            if url.endswith("/products"):
                return PRODUCTS
            raise AssertionError(f"the snapshot should have answered: {url}")

        return get_json

    def test_chain_prices_come_from_the_snapshot_not_the_api(self) -> None:
        calls: list[str] = []
        provider = OpenPricesProvider(
            slug="carrefour",
            display_name="Carrefour",
            chain=ChainFilter(
                name_queries=("Carrefour",), brands=frozenset({"carrefour"})
            ),
        )
        with (
            patch(
                "app.services.store_providers.families.openprices_snapshot.get_snapshot",
                return_value=self._snapshot(),
            ),
            patch(
                "app.services.store_providers.families.http_client.get_json",
                side_effect=self._get_json(calls),
            ),
        ):
            products = provider.search("beurre")
        # Carrefour City's 2.40 is another chain's price.
        assert [(p.sku, p.price) for p in products] == [("111", Decimal("1.95"))]
        assert not any(url.endswith("/prices") for url in calls)

    def test_the_generic_provider_takes_any_shop(self) -> None:
        with patch(
            "app.services.store_providers.families.openprices_snapshot.get_snapshot",
            return_value=self._snapshot(),
        ):
            priced = OpenPricesProvider().attach_prices(
                [StoreProduct(sku="111", name="b", barcode="111")]
            )
        assert priced[0].price == Decimal("2.40")

    def test_one_catalogue_search_serves_every_chain(self) -> None:
        calls: list[str] = []
        chains = [
            OpenPricesProvider(
                slug=slug,
                display_name=slug,
                chain=ChainFilter(name_queries=("Carrefour",), brands=frozenset({b})),
            )
            for slug, b in (("a", "carrefour"), ("b", "carrefour city"))
        ]
        with (
            patch(
                "app.services.store_providers.families.openprices_snapshot.get_snapshot",
                return_value=self._snapshot(),
            ),
            patch(
                "app.services.store_providers.families.http_client.get_json",
                side_effect=self._get_json(calls),
            ),
        ):
            first = chains[0].search("Beurre")
            second = chains[1].search("beurre")
        assert first[0].price == Decimal("1.95")
        assert second[0].price == Decimal("2.40")
        assert sum(1 for url in calls if url.endswith("/products")) == 1
