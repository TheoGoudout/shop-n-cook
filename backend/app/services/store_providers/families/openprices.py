"""Open Prices (Open Food Facts) — the one openly licensed source in this set.

Endpoints used (both verified against the live API):

- ``GET /api/v1/products?product_name__like=<q>`` — catalogue search
- ``GET /api/v1/prices?product_code=<ean>``        — most recent prices

Coverage is community-contributed and therefore sparse and per-location, so
this provider is a supplement and a legal fallback, not a substitute for a
retailer's own catalogue. Data is ODbL: ``attribution`` is not decorative, the
UI is obliged to show it.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.ingredient import Unit
from app.services.pricing import quantize_money
from app.services.store_providers.base import StoreProvider
from app.services.store_providers.families import http_client
from app.services.store_providers.models import Capability, StoreProduct, Transport

BASE_URL = "https://prices.openfoodfacts.org/api/v1"

#: Open Prices reports net content as a number plus a written unit.
_UNIT_BY_NAME: dict[str, Unit] = {
    "g": Unit.GRAM,
    "kg": Unit.KILOGRAM,
    "ml": Unit.MILLILITER,
    "cl": Unit.CENTILITER,
    "l": Unit.LITER,
}


class OpenPricesProvider(StoreProvider):
    """Search and price by barcode against the Open Prices database."""

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
    ) -> None:
        super().__init__(
            slug=slug,
            display_name=display_name,
            country=country,
            website_url="https://prices.openfoodfacts.org",
            attribution="Price data © Open Food Facts contributors, ODbL",
        )
        self.base_url = base_url.rstrip("/")
        self.currency = currency

    # ----------------------------------------------------------------- #

    def search(
        self, query: str, *, limit: int = 10, branch_id: str | None = None
    ) -> list[StoreProduct]:
        payload = http_client.get_json(
            f"{self.base_url}/products",
            params={
                "product_name__like": query,
                "size": max(1, min(limit, 50)),
                "order_by": "-price_count",
            },
        )
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return [
            product
            for product in (self._to_product(raw) for raw in items)
            if product is not None
        ]

    def attach_prices(
        self, products: Sequence[StoreProduct], *, branch_id: str | None = None
    ) -> list[StoreProduct]:
        """Fill in ``price`` for any product carrying a barcode.

        Products without a barcode, or with no price on record, are returned
        untouched — a missing price is data, not a failure.
        """
        enriched: list[StoreProduct] = []
        for product in products:
            if product.price is not None or not product.barcode:
                enriched.append(product)
                continue
            price = self._latest_price(product.barcode)
            enriched.append(
                product.model_copy(update={"price": price}) if price else product
            )
        return enriched

    # ----------------------------------------------------------------- #

    def _latest_price(self, barcode: str) -> Decimal | None:
        payload = http_client.get_json(
            f"{self.base_url}/prices",
            params={"product_code": barcode, "size": 1, "order_by": "-date"},
        )
        items = payload.get("items", []) if isinstance(payload, dict) else []
        if not items:
            return None
        raw_price = items[0].get("price")
        if raw_price is None:
            return None
        try:
            # Parsed straight from the string, never via float: a price is
            # exact money and 1.15 must not arrive as 1.14999999999999991.
            return quantize_money(Decimal(str(raw_price)))
        except (InvalidOperation, ValueError):
            return None

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
