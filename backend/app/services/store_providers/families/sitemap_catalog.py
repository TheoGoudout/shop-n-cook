"""Catalogues read the way a retailer invites robots to read them.

Every French grocer surveyed fences off its on-site search in robots.txt, and
several of those same retailers publish a *product sitemap* for search engines
— the whole catalogue, one URL per product, with the product's name spelled out
in the URL slug:

    https://courses.monoprix.fr/products/monoprix-beurre-doux-125g/MPX_1120136

That is enough to search on. This family downloads the sitemap once, indexes
the slugs locally, and so answers SEARCH without a single request to the
retailer's search. PRICES then reads only the product pages actually chosen —
pages robots.txt allows and which carry the price in structured data. Search is
free, and a list of twenty lines costs twenty page views, not twenty searches
times ten results.

Two page formats are supported, as extractors a store picks by config:

- ``json_ld_product`` — schema.org ``Product`` in JSON-LD (Monoprix), the
  standard and therefore the default;
- ``gtm_product`` — the Google Tag Manager data layer on ``data-gtm``
  attributes (Picard's Salesforce Commerce storefront), for stores that carry no
  ``Product`` JSON-LD at all.

Every fetch passes through ``robots.ensure_allowed`` first, so a retailer that
later fences off its product pages stops this family rather than being
ignored by it.
"""

from __future__ import annotations

import html
import json
import re
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup, Tag

from app.models.ingredient import Unit
from app.services.pricing import quantize_money
from app.services.store_providers.base import StoreProvider
from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families import http_client, robots
from app.services.store_providers.matching import (
    normalize,
    parse_quantity,
    score_name,
    tokenize,
)
from app.services.store_providers.models import Capability, StoreProduct, Transport

# --------------------------------------------------------------------------- #
# Product-page extraction                                                      #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PageProduct:
    """What a product page told us. Every field may be missing."""

    price: Decimal | None = None
    currency: str | None = None
    name: str | None = None
    pack_quantity: float | None = None
    pack_unit: Unit | None = None
    in_stock: bool | None = None
    barcode: str | None = None
    brand: str | None = None
    image_url: str | None = None


#: ``(html, sku) -> PageProduct | None``. ``None`` means "not a product page".
Extractor = Callable[[str, str], PageProduct | None]


def _to_price(raw: Any) -> Decimal | None:
    """Money from whatever a page wrote. Never through a float: callers parse
    JSON with ``parse_float=Decimal``, so a number arrives here as a Decimal."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = Decimal(str(raw).strip().replace(",", "."))
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= 0:
        return None
    return quantize_money(value)


def _json_ld_blocks(soup: BeautifulSoup) -> Iterator[Any]:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            yield json.loads(script.get_text(), parse_float=Decimal)
        except ValueError:
            continue


def _find_products(node: Any) -> Iterator[dict[str, Any]]:
    """Every schema.org ``Product`` in a JSON-LD value, however nested."""
    if isinstance(node, list):
        for item in node:
            yield from _find_products(item)
    elif isinstance(node, dict):
        kind = node.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "Product" in kinds:
            yield node
        graph = node.get("@graph")
        if graph is not None:
            yield from _find_products(graph)


def _first_str(value: Any, key: str | None = None) -> str | None:
    """A string out of a JSON-LD value that may be a string, dict or list."""
    if isinstance(value, list):
        value = value[0] if value else None
    if key is not None and isinstance(value, dict):
        value = value.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def json_ld_product(page_html: str, sku: str) -> PageProduct | None:
    """schema.org ``Product`` JSON-LD, preferring the one whose sku is ours."""
    soup = BeautifulSoup(page_html, "html.parser")
    products = [p for block in _json_ld_blocks(soup) for p in _find_products(block)]
    if not products:
        return None
    product = next((p for p in products if str(p.get("sku", "")) == sku), products[0])

    offers = product.get("offers")
    offer = offers[0] if isinstance(offers, list) and offers else offers
    price: Decimal | None = None
    currency: str | None = None
    in_stock: bool | None = None
    if isinstance(offer, dict):
        price = _to_price(offer.get("price"))
        currency = _first_str(offer.get("priceCurrency"))
        availability = _first_str(offer.get("availability"))
        if availability:
            in_stock = availability.rstrip("/").endswith("InStock")

    name = _first_str(product.get("name"))
    size = _first_str(product.get("size"))
    # The name first: it states the net weight a recipe quotes ("tomates
    # pelées 400g"), while ``size`` can be the drained weight — Monoprix
    # publishes 0.24kg for that same tin.
    pack = (parse_quantity(name) if name else None) or (
        parse_quantity(size) if size else None
    )
    barcode = next(
        (
            _first_str(product.get(key))
            for key in ("gtin13", "gtin", "gtin12", "gtin8", "gtin14")
            if _first_str(product.get(key))
        ),
        None,
    )
    return PageProduct(
        price=price,
        currency=currency,
        name=name,
        pack_quantity=pack[0] if pack else None,
        pack_unit=pack[1] if pack else None,
        in_stock=in_stock,
        barcode=barcode,
        brand=_first_str(product.get("brand"), "name")
        or _first_str(product.get("brand")),
        image_url=_first_str(product.get("image")),
    )


def gtm_product(page_html: str, sku: str) -> PageProduct | None:
    """The Tag Manager data layer entry for ``sku``, as Salesforce Commerce
    storefronts render it on ``data-gtm``.

    Only the entry whose ``item_id`` is this page's own product is read: the
    same page carries cross-sell tiles in the identical format, and taking the
    first one would price a different product.
    """
    soup = BeautifulSoup(page_html, "html.parser")
    for element in soup.select("[data-gtm]"):
        raw = element.get("data-gtm")
        if not isinstance(raw, str) or '"item_id"' not in raw:
            continue
        try:
            data = json.loads(raw, parse_float=Decimal)
        except ValueError:
            continue
        if not isinstance(data, dict) or str(data.get("item_id")) != sku:
            continue

        # The format arrives entity-encoded a second time ("1&#160;kg").
        pack_text = html.unescape(str(data.get("item_format") or ""))
        pack = parse_quantity(pack_text) if pack_text else None
        heading = soup.find("h1")
        name = heading.get_text(" ", strip=True) if isinstance(heading, Tag) else None
        availability = str(data.get("item_availability") or "").strip().lower()
        currency = data.get("currency")
        return PageProduct(
            price=_to_price(data.get("price")),
            currency=currency if isinstance(currency, str) and currency else None,
            name=name or None,
            pack_quantity=pack[0] if pack else None,
            pack_unit=pack[1] if pack else None,
            in_stock=(availability == "en stock") if availability else None,
            brand=str(data["item_brand"]) if data.get("item_brand") else None,
        )
    return None


# --------------------------------------------------------------------------- #
# Sitemap index                                                                #
# --------------------------------------------------------------------------- #

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.DOTALL)
#: "1-5l" in a slug is "1,5l" in the name it was made from.
_SLUG_DECIMAL_RE = re.compile(r"(?<=\d)-(?=\d)")
#: Sitemap files followed from one index, at most. A bound on a document the
#: retailer controls, so a malformed index cannot turn into a crawl.
MAX_SITEMAP_FILES = 20
#: Candidates scored in full per query, after the cheap token prefilter.
MAX_SCORED = 400
#: Product pages remembered per store. Bounds memory on a large catalogue.
MAX_CACHED_PAGES = 5000


@dataclass(frozen=True)
class SitemapEntry:
    sku: str
    url: str
    name: str


@dataclass
class SitemapIndex:
    """Product URLs, searchable by the words in their slugs."""

    entries: list[SitemapEntry] = field(default_factory=list)
    _by_token: dict[str, list[int]] = field(default_factory=dict)

    def add(self, entry: SitemapEntry) -> None:
        position = len(self.entries)
        self.entries.append(entry)
        for token in tokenize(entry.name):
            self._by_token.setdefault(token, []).append(position)

    def lookup(self, query: str, *, limit: int) -> list[SitemapEntry]:
        """Best-first entries sharing at least one word with ``query``.

        Prefilters on token overlap so a 25,000-product catalogue costs a few
        hundred full similarity scores rather than 25,000.
        """
        overlap: dict[int, int] = {}
        for token in tokenize(query):
            for position in self._by_token.get(token, ()):
                overlap[position] = overlap.get(position, 0) + 1
        if not overlap:
            return []

        shortlist = sorted(overlap, key=lambda p: (-overlap[p], p))[:MAX_SCORED]
        scored = sorted(
            shortlist,
            key=lambda p: (-score_name(query, self.entries[p].name), p),
        )
        return [self.entries[p] for p in scored[:limit]]


def slug_to_name(slug: str) -> str:
    """``monoprix-beurre-doux-125g`` -> ``Monoprix beurre doux 125g``."""
    text = _SLUG_DECIMAL_RE.sub(",", unquote(slug))
    text = " ".join(text.replace("-", " ").replace("_", " ").split())
    return text[:1].upper() + text[1:]


# --------------------------------------------------------------------------- #
# Provider                                                                     #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SitemapCatalogConfig:
    origin: str
    """Scheme + host. Product URLs off this origin are ignored."""
    sitemap_url: str
    """A ``<sitemapindex>`` or ``<urlset>``; an index is followed one level."""
    product_url_pattern: str
    """Regex with named groups ``slug`` and ``sku``, searched in each URL."""
    extractor: Extractor = json_ld_product
    sitemap_url_filter: str | None = None
    """Regex a sitemap file's URL must match to be read from an index, e.g.
    ``products`` to skip the category and store sitemaps."""
    currency: str = "EUR"
    index_ttl_seconds: float = 24 * 60 * 60
    page_ttl_seconds: float = 6 * 60 * 60
    min_request_interval: float = 0.25
    """Seconds between two requests to this retailer, however many lines a
    list has. A refresh of the whole ingredient catalogue is a batch job; it
    must never look like a burst."""


class SitemapCatalogProvider(StoreProvider):
    """SEARCH from the product sitemap, PRICES from the product page."""

    transport = Transport.SERVER
    capabilities = frozenset({Capability.SEARCH, Capability.PRICES})
    requires_branch = False

    def __init__(
        self,
        *,
        slug: str,
        display_name: str,
        config: SitemapCatalogConfig,
        country: str = "FR",
        website_url: str | None = None,
    ) -> None:
        super().__init__(
            slug=slug,
            display_name=display_name,
            country=country,
            website_url=website_url or config.origin,
        )
        self.config = config
        self._pattern = re.compile(config.product_url_pattern)
        self._index: SitemapIndex | None = None
        self._index_loaded_at = 0.0
        self._pages: dict[str, tuple[float, PageProduct | None]] = {}
        self._last_request = 0.0
        self._lock = threading.Lock()
        self._index_lock = threading.Lock()

    # ----------------------------------------------------------------- #

    def search(
        self, query: str, *, limit: int = 10, branch_id: str | None = None
    ) -> list[StoreProduct]:
        """Products whose names match, unpriced: no page has been read yet."""
        index = self._current_index()
        products: list[StoreProduct] = []
        for entry in index.lookup(query, limit=limit):
            pack = parse_quantity(entry.name)
            products.append(
                StoreProduct(
                    sku=entry.sku,
                    name=entry.name,
                    url=entry.url,
                    currency=self.config.currency,
                    pack_quantity=pack[0] if pack else None,
                    pack_unit=pack[1] if pack else None,
                )
            )
        return products

    def attach_prices(
        self, products: Sequence[StoreProduct], *, branch_id: str | None = None
    ) -> list[StoreProduct]:
        """Read each product's own page for its price and net content.

        The page's pack size replaces one guessed from the slug: the slug is a
        lossy copy of the name, the page is the retailer's statement. A product
        whose page is gone (404/410) simply stays unpriced.
        """
        enriched: list[StoreProduct] = []
        for product in products:
            if product.price is not None or not product.url:
                enriched.append(product)
                continue
            page = self._page(product.url, product.sku)
            if page is None:
                enriched.append(product)
                continue
            if page.currency and page.currency != self.config.currency:
                # A price in another currency is not a price in ours.
                enriched.append(product)
                continue
            update: dict[str, Any] = {"price": page.price}
            if page.pack_quantity is not None and page.pack_unit is not None:
                update["pack_quantity"] = page.pack_quantity
                update["pack_unit"] = page.pack_unit
            if page.name:
                update["name"] = page.name
            for key in ("in_stock", "barcode", "brand", "image_url"):
                value = getattr(page, key)
                if value is not None:
                    update[key] = value
            enriched.append(product.model_copy(update=update))
        return enriched

    # ----------------------------------------------------------------- #

    def _throttled_fetch(self, url: str) -> http_client.FetchedPage:
        robots.ensure_allowed(url)
        with self._lock:
            wait = self.config.min_request_interval - (
                time.monotonic() - self._last_request
            )
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
        return http_client.fetch(url)

    def _current_index(self) -> SitemapIndex:
        # Held across the download so concurrent requests wait for one load
        # instead of each fetching the whole sitemap.
        with self._index_lock:
            now = time.monotonic()
            if (
                self._index is not None
                and now - self._index_loaded_at < self.config.index_ttl_seconds
            ):
                return self._index
            index = self._load_index()
            self._index, self._index_loaded_at = index, now
            return index

    def _load_index(self) -> SitemapIndex:
        root = self._read_sitemap(self.config.sitemap_url)
        if "<sitemapindex" in root:
            file_filter = (
                re.compile(self.config.sitemap_url_filter)
                if self.config.sitemap_url_filter
                else None
            )
            files = [
                url
                for url in _locs(root)
                if file_filter is None or file_filter.search(url)
            ][:MAX_SITEMAP_FILES]
            documents = [self._read_sitemap(url) for url in files]
        else:
            documents = [root]

        index = SitemapIndex()
        seen: set[str] = set()
        for document in documents:
            for url in _locs(document):
                entry = self._entry(url)
                if entry is not None and entry.sku not in seen:
                    seen.add(entry.sku)
                    index.add(entry)
        if not index.entries:
            # An empty catalogue is a broken sitemap, not a store that sells
            # nothing — say so rather than answering every query with nothing.
            raise ProviderUnavailableError(
                f"{self.config.sitemap_url} listed no product URLs"
            )
        return index

    def _read_sitemap(self, url: str) -> str:
        robots.ensure_allowed(url)
        return http_client.get_xml(url)

    def _entry(self, url: str) -> SitemapEntry | None:
        if not url.startswith(self.config.origin + "/"):
            return None
        match = self._pattern.search(url)
        if match is None:
            return None
        name = slug_to_name(match.group("slug"))
        if not normalize(name):
            return None
        return SitemapEntry(sku=match.group("sku"), url=url, name=name)

    def _page(self, url: str, sku: str) -> PageProduct | None:
        absolute = urljoin(self.config.origin, url)
        if not absolute.startswith(self.config.origin + "/"):
            return None
        now = time.monotonic()
        cached = self._pages.get(absolute)
        if cached is not None and now - cached[0] < self.config.page_ttl_seconds:
            return cached[1]

        fetched = self._throttled_fetch(absolute)
        if fetched.status_code in (404, 410):
            page: PageProduct | None = None
        elif 200 <= fetched.status_code < 300:
            page = self.config.extractor(fetched.text, sku)
        else:
            # 403 and 5xx: the retailer is refusing or failing, not telling us
            # about one product. Stop, and let the orchestrator degrade.
            raise ProviderUnavailableError(
                f"{absolute} returned HTTP {fetched.status_code}"
            )
        self._pages[absolute] = (now, page)
        if len(self._pages) > MAX_CACHED_PAGES:
            # Dicts keep insertion order, so this drops the oldest entry.
            self._pages.pop(next(iter(self._pages)))
        return page


def _locs(document: str) -> Iterator[str]:
    """``<loc>`` values, unescaped. A regex rather than an XML parser: sitemaps
    are flat, and this never expands an entity a hostile document declares."""
    for match in _LOC_RE.finditer(document):
        yield html.unescape(match.group(1))
