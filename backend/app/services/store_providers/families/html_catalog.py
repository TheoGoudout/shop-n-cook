"""Server-rendered catalogue scraping, driven by configuration.

Most retail search pages are still server-rendered with schema.org Product
microdata. That is a real standard, so one parser plus a small config covers a
whole class of stores rather than one. The defaults below target plain
microdata; a store only needs overrides where it deviates.

This family is for stores that *answer* a plain HTTP request. A store behind
Akamai or DataDome cannot be served from here at any level of cleverness — it
belongs in the ``extension`` family instead.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup, Tag

from app.services.pricing import quantize_money
from app.services.store_providers.base import StoreProvider
from app.services.store_providers.families import http_client
from app.services.store_providers.matching import parse_quantity
from app.services.store_providers.models import (
    Capability,
    CartPlanEntry,
    StoreProduct,
    Transport,
)

_PRICE_RE = re.compile(r"(\d+(?:[.,]\d{1,2})?)")


def _class_list(element: Tag) -> str:
    """The element's class attribute as one string.

    BeautifulSoup types this as ``str | list[str] | None`` depending on whether
    the parser treated the attribute as multi-valued, so all three are handled.
    """
    raw = element.get("class")
    if isinstance(raw, list):
        return " ".join(raw)
    if isinstance(raw, str):
        return raw
    return ""


@dataclass(frozen=True)
class HtmlCatalogConfig:
    """Everything store-specific about a server-rendered catalogue."""

    origin: str
    """Scheme + host, used to absolutise relative links."""
    search_url_template: str
    """Must contain ``{query}``; the value is URL-encoded before substitution."""

    product_selector: str = '[itemtype*="schema.org/Product"]'
    name_selector: str | None = None
    """CSS selector for the name. Falls back to microdata, then image alt."""
    link_selector: str = "a[href]"
    sku_pattern: str | None = None
    """Regex with one group, matched against the product href."""
    price_selector: str | None = None
    out_of_stock_marker: str | None = None
    """Substring of the product element's class list marking unavailability."""
    prices_require_branch: bool = False
    """Set when the store serves a priceless catalogue until a store is picked.
    Drives ``PriceStatus.REQUIRES_BRANCH`` rather than a misleading 'unknown'."""


class HtmlCatalogProvider(StoreProvider):
    """A store whose search results can be read straight out of its HTML."""

    transport = Transport.SERVER

    def __init__(
        self,
        *,
        slug: str,
        display_name: str,
        config: HtmlCatalogConfig,
        country: str = "FR",
        supports_prices: bool = False,
        website_url: str | None = None,
    ) -> None:
        super().__init__(
            slug=slug,
            display_name=display_name,
            country=country,
            website_url=website_url or config.origin,
        )
        self.config = config
        self.requires_branch = config.prices_require_branch
        capabilities = {Capability.SEARCH, Capability.CART_LINK}
        if supports_prices:
            capabilities.add(Capability.PRICES)
        self.capabilities = frozenset(capabilities)

    # ----------------------------------------------------------------- #

    def search(
        self, query: str, *, limit: int = 10, branch_id: str | None = None
    ) -> list[StoreProduct]:
        url = self.config.search_url_template.format(query=quote(query))
        html = http_client.get_text(url)
        soup = BeautifulSoup(html, "html.parser")

        products: list[StoreProduct] = []
        for element in soup.select(self.config.product_selector):
            product = self._to_product(element)
            if product is not None:
                products.append(product)
            if len(products) >= limit:
                break
        return products

    def cart_link(
        self, entries: Sequence[CartPlanEntry], *, branch_id: str | None = None
    ) -> str:
        """Land the user on the store's own search for the first unmatched line.

        Deliberately modest: without a documented basket URL scheme, pretending
        to pre-fill a cart would be a lie. This at least saves typing.
        """
        query = entries[0].query if entries else ""
        return self.config.search_url_template.format(query=quote(query))

    # ----------------------------------------------------------------- #

    def _to_product(self, element: Tag) -> StoreProduct | None:
        link = element.select_one(self.config.link_selector)
        href = link.get("href") if isinstance(link, Tag) else None
        href_str = href if isinstance(href, str) else None

        name = self._extract_name(element)
        if not name:
            return None

        sku = self._extract_sku(element, href_str)
        if not sku:
            return None

        in_stock: bool | None = None
        if self.config.out_of_stock_marker:
            in_stock = self.config.out_of_stock_marker not in _class_list(element)

        pack = parse_quantity(name)
        return StoreProduct(
            sku=sku,
            name=name,
            url=urljoin(self.config.origin, href_str) if href_str else None,
            image_url=self._extract_image(element),
            price=self._extract_price(element),
            pack_quantity=pack[0] if pack else None,
            pack_unit=pack[1] if pack else None,
            in_stock=in_stock,
        )

    def _extract_name(self, element: Tag) -> str | None:
        if self.config.name_selector:
            node = element.select_one(self.config.name_selector)
            if isinstance(node, Tag):
                text = node.get_text(strip=True)
                if text:
                    return text

        microdata = element.select_one('[itemprop="name"]')
        if isinstance(microdata, Tag):
            content = microdata.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            text = microdata.get_text(strip=True)
            if text:
                return text

        # Stores that render the name only as an image alt (Auchan does).
        for node in element.select("img[alt], source[alt]"):
            alt = node.get("alt")
            if isinstance(alt, str) and alt.strip():
                return alt.strip()
        return None

    def _extract_sku(self, element: Tag, href: str | None) -> str | None:
        if self.config.sku_pattern and href:
            match = re.search(self.config.sku_pattern, href)
            if match:
                return match.group(1)
        for attribute in ("data-id", "data-product-id", "data-sku"):
            value = element.get(attribute)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return href

    def _extract_image(self, element: Tag) -> str | None:
        node = element.select_one('[itemprop="image"]')
        if isinstance(node, Tag):
            content = node.get("content") or node.get("src")
            if isinstance(content, str) and content.strip():
                return content.strip()
        image = element.select_one("img[src]")
        if isinstance(image, Tag):
            src = image.get("src")
            if isinstance(src, str):
                return src
        return None

    def _extract_price(self, element: Tag) -> Decimal | None:
        node = element.select_one('[itemprop="price"]')
        if isinstance(node, Tag):
            content = node.get("content")
            if isinstance(content, str):
                try:
                    return quantize_money(Decimal(content.replace(",", ".")))
                except InvalidOperation:
                    pass
        if self.config.price_selector:
            priced = element.select_one(self.config.price_selector)
            if isinstance(priced, Tag):
                match = _PRICE_RE.search(priced.get_text(" ", strip=True))
                if match:
                    try:
                        return quantize_money(Decimal(match.group(1).replace(",", ".")))
                    except InvalidOperation:
                        return None
        return None
