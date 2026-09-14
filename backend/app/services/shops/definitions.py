"""The shops themselves — configuration, not code.

Adding a chain that fits an existing family is a single ``register(...)`` call
here. Only a shop that fits none of them needs a new class.

Each entry records *why* it has the capabilities it has, because those were
established by probing the live sites and are the kind of fact that silently
rots:

- **Auchan** serves a fully parseable, server-rendered catalogue, but its
  search page carries no prices and marks everything out of stock until a
  store is chosen in-session (31 products, 0 prices, 30 ``outOfStock`` on a
  plain request). Hence SEARCH without PRICES, and ``prices_require_store``.
- **Carrefour** answers every server-side request with an Akamai 403. There is
  no server transport to be had, so it is extension-only and has no SEARCH.
  Intermarché (``https://www.intermarche.com``) and Leclerc Drive both sit
  behind DataDome and would be added here the same way, one call each, once
  their extension adapters exist.
- **Open Prices** is the only openly licensed source in the set: real search,
  real prices, ODbL attribution obligations, and sparse community coverage.
- **Market / Printable** contact nobody. They exist for the shopper who only
  ever wanted the list — a farmers' market, a butcher, a village grocer — and
  they are the reason ``LIST_EXPORT`` is a capability rather than a separate
  feature bolted on beside shops. They differ only in aisle order, which is
  what makes them one family and two lines of config.
- **Biocoop / Naturalia** both run stock Magento 2 and answer ``/rest/V1/...``
  with 401 rather than 404 — the API is there, behind auth. They register only
  when a token is configured, so the UI is never offered a capability that
  would fail on every call.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.shops.families.extension import (
    ExtensionProvider,
    ExtensionShopConfig,
)
from app.services.shops.families.html_catalog import (
    HtmlCatalogConfig,
    HtmlCatalogProvider,
)
from app.services.shops.families.list_only import (
    MARKET_AISLES,
    SUPERMARKET_AISLES,
    ListOnlyConfig,
    ListOnlyProvider,
)
from app.services.shops.families.magento import MagentoConfig, MagentoProvider
from app.services.shops.families.openprices import OpenPricesProvider
from app.services.shops.registry import register


def register_default_shops() -> None:
    """Populate the registry. Called once, from the package ``__init__``."""

    register(OpenPricesProvider())

    register(
        HtmlCatalogProvider(
            slug="auchan",
            display_name="Auchan",
            supports_prices=False,
            config=HtmlCatalogConfig(
                origin="https://www.auchan.fr",
                search_url_template="https://www.auchan.fr/recherche?text={query}",
                sku_pattern=r"/pr-([A-Za-z0-9]+)",
                out_of_stock_marker="outOfStock",
                prices_require_store=True,
            ),
        )
    )

    register(
        ExtensionProvider(
            slug="carrefour",
            display_name="Carrefour",
            config=ExtensionShopConfig(
                origin="https://www.carrefour.fr",
                search_url_template="https://www.carrefour.fr/s?q={query}",
                cart_url="https://www.carrefour.fr/mon-panier",
                requires_store=True,
            ),
        )
    )

    # Two shops, one family, zero new code — and the only two that work in
    # every country, because a list you carry needs no local presence.
    register(
        ListOnlyProvider(
            slug="market",
            display_name="Market / Local shops",
            config=ListOnlyConfig(aisle_order=MARKET_AISLES),
        )
    )
    register(
        ListOnlyProvider(
            slug="printable",
            display_name="Printable list",
            config=ListOnlyConfig(aisle_order=SUPERMARKET_AISLES),
        )
    )

    _register_magento_shops()


def _register_magento_shops() -> None:
    """Register Magento storefronts for which we hold credentials."""
    magento_shops = (
        ("biocoop", "Biocoop", "https://www.biocoop.fr", settings.BIOCOOP_API_TOKEN),
        (
            "naturalia",
            "Naturalia",
            "https://www.naturalia.fr",
            settings.NATURALIA_API_TOKEN,
        ),
    )
    for slug, display_name, origin, token in magento_shops:
        if not token:
            continue
        register(
            MagentoProvider(
                slug=slug,
                display_name=display_name,
                config=MagentoConfig(origin=origin, access_token=token),
            )
        )
