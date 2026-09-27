"""Open Prices (Open Food Facts) — the one openly licensed source in this set.

Endpoints used (all verified against the live API):

- ``GET /api/v1/products?product_name__like=<q>``  — catalogue search
- ``GET /api/v1/prices?product_code__in=<eans>``   — recorded prices
- ``GET /api/v1/locations?osm_name__like=<chain>`` — the shops prices were
  recorded in, each an OpenStreetMap node carrying the chain's brand

Prices come from the daily Parquet dump of the whole table
(``openprices_snapshot``) — one download a day instead of a request per batch
per chain — with the ``/prices`` endpoint as the fallback when the dump cannot
be had. Catalogue searches are cached for a day and shared by every chain.

Coverage is community-contributed and therefore sparse and per-location, so
this provider is a supplement and a legal fallback, not a substitute for a
retailer's own catalogue. Data is ODbL: ``attribution`` is not decorative, the
UI is obliged to show it.

**Per-chain prices.** Every price is recorded at a location, and every location
is an OSM shop with a brand. Restricting prices to the locations of one brand
turns the database into a price source for that chain — the only lawful one
available for retailers whose sites refuse any automated client (Carrefour,
Leclerc, Intermarché, Système U, Franprix) or publish no prices without a
store session (Auchan). The ``location__osm_name__contains`` filter the API
advertises returns nothing for any value, so the chain's locations are resolved
here, by id, and passed as ``location_id__in``.

What a price here means, stated so nobody over-reads it: the most recent
undiscounted till price a contributor recorded for that barcode, in euros, at
one of the chain's shops, within ``openprices_snapshot.MAX_PRICE_AGE_DAYS``.
It is not a live shelf price and it is not branch-specific.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.ingredient import Unit
from app.services.pricing import quantize_money
from app.services.store_providers.base import StoreProvider
from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families import http_client, openprices_snapshot
from app.services.store_providers.matching import normalize
from app.services.store_providers.models import Capability, StoreProduct, Transport

BASE_URL = "https://prices.openfoodfacts.org/api/v1"
ATTRIBUTION = "Price data © Open Food Facts contributors, ODbL"

#: Barcodes priced per request, and result pages read per batch. Bounds one
#: lookup on a popular product with thousands of observations.
CODES_PER_REQUEST = 25
MAX_PRICE_PAGES = 4
PAGE_SIZE = 100
#: Products fetched from the catalogue before keeping the ones this chain has
#: a price for. Wide on purpose: the chain filter discards most of them.
CHAIN_SEARCH_POOL = 50
#: How long a catalogue search is reused, and how many are remembered.
SEARCH_CACHE_SECONDS = 24 * 60 * 60
MAX_CACHED_SEARCHES = 5000
#: A bound on the location list sent as ``location_id__in``: the busiest shops
#: carry nearly every price, and the URL must stay a sane length.
MAX_CHAIN_LOCATIONS = 300
LOCATION_CACHE_SECONDS = 24 * 60 * 60

#: Open Prices reports net content as a number plus a written unit.
_UNIT_BY_NAME: dict[str, Unit] = {
    "g": Unit.GRAM,
    "kg": Unit.KILOGRAM,
    "ml": Unit.MILLILITER,
    "cl": Unit.CENTILITER,
    "l": Unit.LITER,
}


@dataclass(frozen=True)
class ChainFilter:
    """Which Open Prices locations belong to one chain.

    ``brands`` are compared after ``matching.normalize`` and must match
    exactly — the OSM ``brand`` tag, or the shop's name when it has none. Exact
    on purpose: "Carrefour City" must not count as "Carrefour", because the
    convenience formats price above the hypermarkets.
    """

    name_queries: tuple[str, ...]
    """``osm_name__like`` values that together find every candidate shop."""
    brands: frozenset[str]
    country_code: str = "FR"


class OpenPricesProvider(StoreProvider):
    """Search and price by barcode against the Open Prices database.

    Without a ``chain`` this prices a barcode from any shop in the country's
    currency. With one, it is that chain's price source: search keeps only
    products the chain has a recorded price for, and prices come only from the
    chain's shops.
    """

    transport = Transport.SERVER
    capabilities = frozenset({Capability.SEARCH, Capability.PRICES})
    requires_branch = False

    def __init__(
        self,
        *,
        slug: str = "openprices",
        display_name: str = "Open Prices",
        country: str = "FR",
        base_url: str = BASE_URL,
        currency: str = "EUR",
        chain: ChainFilter | None = None,
        website_url: str = "https://prices.openfoodfacts.org",
    ) -> None:
        super().__init__(
            slug=slug,
            display_name=display_name,
            country=country,
            website_url=website_url,
            attribution=ATTRIBUTION,
        )
        self.base_url = base_url.rstrip("/")
        self.currency = currency
        self.chain = chain
        self._location_ids: tuple[float, list[int]] | None = None
        self._location_lock = threading.Lock()

    # ----------------------------------------------------------------- #

    def search(
        self, query: str, *, limit: int = 10, branch_id: str | None = None
    ) -> list[StoreProduct]:
        items = _catalogue_search(self.base_url, query)
        products = [
            product
            for product in (self._to_product(raw) for raw in items)
            if product is not None
        ]
        if self.chain is None:
            return products[:limit]

        # A product the chain has never been seen selling is not "at" it.
        prices = self._latest_prices(p.sku for p in products)
        return [
            product.model_copy(update={"price": prices[product.sku]})
            for product in products
            if product.sku in prices
        ][:limit]

    def attach_prices(
        self, products: Sequence[StoreProduct], *, branch_id: str | None = None
    ) -> list[StoreProduct]:
        """Fill in ``price`` for any product carrying a barcode.

        Products without a barcode, or with no price on record, are returned
        untouched — a missing price is data, not a failure.
        """
        prices = self._latest_prices(
            p.barcode for p in products if p.price is None and p.barcode
        )
        return [
            product.model_copy(update={"price": prices[product.barcode]})
            if product.price is None and product.barcode and product.barcode in prices
            else product
            for product in products
        ]

    # ----------------------------------------------------------------- #

    def _latest_prices(self, codes: Iterable[str]) -> dict[str, Decimal]:
        """The most recent qualifying price per barcode.

        Read from the daily snapshot of the whole price table; the API is the
        fallback for a day the snapshot cannot be downloaded.
        """
        wanted = list(dict.fromkeys(code for code in codes if code))
        if not wanted:
            return {}
        try:
            snapshot = openprices_snapshot.get_snapshot()
        except ProviderUnavailableError:
            return self._latest_prices_from_api(wanted)

        location_ids: frozenset[int] | None = None
        if self.chain is not None:
            location_ids = frozenset(self._busiest_chain_locations())
            if not location_ids:
                return {}
        return snapshot.latest(
            wanted,
            currency=self.currency,
            since=openprices_snapshot.oldest_price_date(),
            location_ids=location_ids,
        )

    def _latest_prices_from_api(self, wanted: list[str]) -> dict[str, Decimal]:
        base_params: dict[str, Any] = {
            "currency": self.currency,
            "price_is_discounted": "false",
            "date__gte": openprices_snapshot.oldest_price_date().isoformat(),
            # Newest first. The date filter above also drops undated rows,
            # which a descending sort would otherwise put first.
            "order_by": "-date",
            "size": PAGE_SIZE,
        }
        if self.chain is not None:
            location_ids = self._chain_location_ids()
            if not location_ids:
                return {}
            base_params["location_id__in"] = ",".join(map(str, location_ids))

        found: dict[str, Decimal] = {}
        for start in range(0, len(wanted), CODES_PER_REQUEST):
            batch = wanted[start : start + CODES_PER_REQUEST]
            for page in range(1, MAX_PRICE_PAGES + 1):
                payload = http_client.get_json(
                    f"{self.base_url}/prices",
                    params={
                        **base_params,
                        "product_code__in": ",".join(batch),
                        "page": page,
                    },
                    parse_float=Decimal,
                )
                if not isinstance(payload, dict):
                    break
                for raw in payload.get("items", []):
                    code, price = _price_row(raw)
                    if code is not None and price is not None:
                        found.setdefault(code, price)
                pages = payload.get("pages")
                if (
                    all(code in found for code in batch)
                    or not isinstance(pages, int)
                    or page >= pages
                ):
                    break
        return found

    def _chain_location_ids(self) -> list[int]:
        """The shops sent to the API, which needs a URL of sane length."""
        return sorted(self._busiest_chain_locations()[:MAX_CHAIN_LOCATIONS])

    def _busiest_chain_locations(self) -> list[int]:
        """Every shop of the chain, busiest first. Cached for a day."""
        assert self.chain is not None
        now = time.monotonic()
        with self._location_lock:
            cached = self._location_ids
            if cached is not None and now - cached[0] < LOCATION_CACHE_SECONDS:
                return cached[1]

            by_id: dict[int, int] = {}
            for query in self.chain.name_queries:
                for raw in self._locations_named(query):
                    if _belongs_to(raw, self.chain):
                        by_id[int(raw["id"])] = int(raw.get("price_count") or 0)
            busiest = sorted(by_id, key=lambda i: (-by_id[i], i))
            self._location_ids = (now, busiest)
            return busiest

    def _locations_named(self, query: str) -> Iterable[dict[str, Any]]:
        page = 1
        while True:
            payload = http_client.get_json(
                f"{self.base_url}/locations",
                params={
                    "osm_name__like": query,
                    "price_count__gte": 1,
                    "size": PAGE_SIZE,
                    "page": page,
                },
            )
            if not isinstance(payload, dict):
                return
            for raw in payload.get("items", []):
                if isinstance(raw, dict):
                    yield raw
            pages = payload.get("pages")
            if not isinstance(pages, int) or page >= pages:
                return
            page += 1

    def _to_product(self, raw: Any) -> StoreProduct | None:
        if not isinstance(raw, dict):
            return None
        code = raw.get("code")
        name = raw.get("product_name")
        if not code or not name:
            return None

        pack_quantity: float | None = None
        pack_unit: Unit | None = None
        quantity = raw.get("product_quantity")
        unit_name = (raw.get("product_quantity_unit") or "").lower()
        if quantity is not None and unit_name in _UNIT_BY_NAME:
            try:
                pack_quantity = float(quantity)
                pack_unit = _UNIT_BY_NAME[unit_name]
            except (TypeError, ValueError):
                pack_quantity = None
                pack_unit = None
            if pack_quantity is not None and pack_quantity <= 0:
                pack_quantity, pack_unit = None, None

        return StoreProduct(
            sku=str(code),
            barcode=str(code),
            name=str(name),
            brand=raw.get("brands") or None,
            url=f"https://prices.openfoodfacts.org/products/{code}",
            image_url=raw.get("image_url") or None,
            currency=self.currency,
            pack_quantity=pack_quantity,
            pack_unit=pack_unit,
        )


_search_lock = threading.Lock()
_search_cache: dict[tuple[str, str], tuple[float, list[Any]]] = {}


def _catalogue_search(base_url: str, query: str) -> list[Any]:
    """``/products`` matches for ``query``, cached for a day.

    Shared by every chain on purpose: the catalogue does not depend on the
    chain, so six chains refreshing the same ingredient cost one request, not
    six. Always fetches the full pool, so every caller can share the answer
    whatever ``limit`` it wants.
    """
    key = (base_url, normalize(query))
    now = time.monotonic()
    with _search_lock:
        cached = _search_cache.get(key)
        if cached is not None and now - cached[0] < SEARCH_CACHE_SECONDS:
            return cached[1]

    payload = http_client.get_json(
        f"{base_url}/products",
        params={
            "product_name__like": query,
            "size": CHAIN_SEARCH_POOL,
            "order_by": "-price_count",
        },
        parse_float=Decimal,
    )
    items = payload.get("items", []) if isinstance(payload, dict) else []
    items = items if isinstance(items, list) else []
    with _search_lock:
        _search_cache[key] = (now, items)
        if len(_search_cache) > MAX_CACHED_SEARCHES:
            # Dicts keep insertion order, so this drops the oldest entry.
            _search_cache.pop(next(iter(_search_cache)))
    return items


def clear_caches() -> None:
    """Test helper. Not used by application code."""
    with _search_lock:
        _search_cache.clear()


def _price_row(raw: Any) -> tuple[str | None, Decimal | None]:
    """A barcode and its price, or ``None`` for a row that is not a unit price."""
    if not isinstance(raw, dict):
        return None, None
    code = raw.get("product_code")
    # A barcode is priced per item. A row priced per kilogram describes loose
    # produce and would silently be read as the price of one pack.
    if not code or raw.get("price_per") not in (None, "UNIT"):
        return None, None
    raw_price = raw.get("price")
    if raw_price is None or isinstance(raw_price, bool):
        return str(code), None
    try:
        # Parsed straight from the JSON text (``parse_float=Decimal``), never
        # via float: a price is exact money and 1.15 must not arrive as
        # 1.14999999999999991.
        price = Decimal(str(raw_price))
    except (InvalidOperation, ValueError):
        return str(code), None
    if not price.is_finite() or price <= 0:
        return str(code), None
    return str(code), quantize_money(price)


def _belongs_to(raw: dict[str, Any], chain: ChainFilter) -> bool:
    country = raw.get("osm_address_country_code")
    if country and str(country).upper() != chain.country_code:
        return False
    label = raw.get("osm_brand") or raw.get("osm_name") or ""
    return normalize(str(label)) in chain.brands
