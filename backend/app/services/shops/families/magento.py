"""Magento 2 storefronts, driven by configuration.

Magento exposes the same GraphQL schema on every installation, so one
implementation covers every Magento merchant — Biocoop and Naturalia both run
it, and adding either is a line of config rather than a new module. That is the
payoff of families: a credential grant from one Magento shop validates the code
path for all of them.

Both of those storefronts currently answer ``/rest/V1/...`` with **401, not
404**: the API exists at the stock path and is merely authentication-gated. So
``definitions.py`` registers a Magento shop only when a token is configured;
registering one without credentials would advertise a capability to the UI that
every call would then fail.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote, urljoin

import httpx

from app.services.pricing import quantize_money
from app.services.shops.base import ShopProvider
from app.services.shops.errors import ShopUnavailableError
from app.services.shops.families.http_client import DEFAULT_TIMEOUT, USER_AGENT
from app.services.shops.matching import parse_quantity
from app.services.shops.models import (
    Capability,
    CartPlanEntry,
    ShopProduct,
    Transport,
)

_SEARCH_QUERY = """
query ProductSearch($search: String!, $pageSize: Int!) {
  products(search: $search, pageSize: $pageSize) {
    items {
      sku
      name
      url_key
      stock_status
      small_image { url }
      price_range { minimum_price { final_price { value currency } } }
    }
  }
}
"""


@dataclass(frozen=True)
class MagentoConfig:
    origin: str
    graphql_path: str = "/graphql"
    product_url_template: str = "{origin}/{url_key}.html"
    search_url_template: str = "{origin}/catalogsearch/result/?q={query}"
    access_token: str | None = None
    """Bearer token. Magento's catalogue is auth-gated on both French organic
    chains we surveyed, so this is normally required."""


class MagentoProvider(ShopProvider):
    """Any Magento 2 storefront, parameterised by domain."""

    transport = Transport.SERVER
    capabilities = frozenset(
        {Capability.SEARCH, Capability.PRICES, Capability.CART_LINK}
    )

    def __init__(
        self,
        *,
        slug: str,
        display_name: str,
        config: MagentoConfig,
        country: str = "FR",
    ) -> None:
        super().__init__(
            slug=slug,
            display_name=display_name,
            country=country,
            website_url=config.origin,
        )
        self.config = config

    # ----------------------------------------------------------------- #

    def search(
        self, query: str, *, limit: int = 10, store_id: str | None = None
    ) -> list[ShopProduct]:
        payload = self._graphql({"search": query, "pageSize": max(1, min(limit, 50))})
        items = (
            payload.get("data", {}).get("products", {}).get("items", [])
            if isinstance(payload, dict)
            else []
        )
        products = [self._to_product(raw) for raw in items]
        return [product for product in products if product is not None][:limit]

    def attach_prices(
        self, products: Sequence[ShopProduct], *, store_id: str | None = None
    ) -> list[ShopProduct]:
        """Magento prices during search, so there is nothing left to fetch.

        Declared all the same: the capability is what the UI reads, and a
        Magento product genuinely does arrive priced.
        """
        return list(products)

    def cart_link(
        self, entries: Sequence[CartPlanEntry], *, store_id: str | None = None
    ) -> str:
        query = entries[0].query if entries else ""
        return self.config.search_url_template.format(
            origin=self.config.origin.rstrip("/"), query=quote(query)
        )

    # ----------------------------------------------------------------- #

    def _graphql(self, variables: dict[str, Any]) -> Any:
        url = urljoin(self.config.origin, self.config.graphql_path)
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        if self.config.access_token:
            headers["Authorization"] = f"Bearer {self.config.access_token}"
        try:
            response = httpx.post(
                url,
                content=json.dumps({"query": _SEARCH_QUERY, "variables": variables}),
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise ShopUnavailableError(
                f"{url} returned HTTP {exc.response.status_code}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ShopUnavailableError(f"{url} could not be read: {exc}") from exc

    def _to_product(self, raw: Any) -> ShopProduct | None:
        if not isinstance(raw, dict):
            return None
        sku = raw.get("sku")
        name = raw.get("name")
        if not sku or not name:
            return None

        price: Decimal | None = None
        currency = "EUR"
        final = (
            raw.get("price_range", {}).get("minimum_price", {}).get("final_price", {})
        )
        if isinstance(final, dict) and final.get("value") is not None:
            try:
                price = quantize_money(Decimal(str(final["value"])))
                currency = final.get("currency") or currency
            except (InvalidOperation, ValueError):
                price = None

        url: str | None = None
        url_key = raw.get("url_key")
        if url_key:
            url = self.config.product_url_template.format(
                origin=self.config.origin.rstrip("/"), url_key=url_key
            )

        image = raw.get("small_image")
        pack = parse_quantity(str(name))
        stock_status = raw.get("stock_status")
        return ShopProduct(
            sku=str(sku),
            name=str(name),
            url=url,
            image_url=image.get("url") if isinstance(image, dict) else None,
            price=price,
            currency=currency,
            pack_quantity=pack[0] if pack else None,
            pack_unit=pack[1] if pack else None,
            in_stock=(stock_status == "IN_STOCK") if stock_status else None,
        )
