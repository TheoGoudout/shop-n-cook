"""The stores themselves — configuration, not code.

Adding a chain that fits an existing family is a single ``register(...)`` call
here. Only a store that fits none of them needs a new class.

Each entry records *why* it has the capabilities it has, because those were
established by probing the live sites and are the kind of fact that silently
rots:

- **Auchan** serves a fully parseable, server-rendered catalogue, but its
  search page carries no prices and marks everything out of stock until a
  store is chosen in-session (31 products, 0 prices, 30 ``outOfStock`` on a
  plain request). Hence SEARCH without PRICES, and ``prices_require_branch``.
- **Carrefour** answers every server-side request with an Akamai 403. There is
  no server transport to be had, so it is extension-only and has no SEARCH.
  Intermarché (``https://www.intermarche.com``) and Leclerc Drive both sit
  behind DataDome and would be added here the same way, one call each, once
  their extension adapters exist.
- **Open Prices** is the only openly licensed source in the set: real search,
  real prices, ODbL attribution obligations, and sparse community coverage.
Printing a list to carry is deliberately *not* a store here — see
``layouts.py``. Nobody picks "Printable list" as the supermarket they shop at.
- **Biocoop / Naturalia** both run stock Magento 2 and answer ``/rest/V1/...``
  with 401 rather than 404 — the API is there, behind auth. They register only
  when a token is configured, so the UI is never offered a capability that
  would fail on every call.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.store_providers.families.extension import (
    ExtensionProvider,
    ExtensionStoreConfig,
)
from app.services.store_providers.families.html_catalog import (
    HtmlCatalogConfig,
    HtmlCatalogProvider,
)
from app.services.store_providers.families.magento import MagentoConfig, MagentoProvider
from app.services.store_providers.families.openprices import OpenPricesProvider
from app.services.store_providers.registry import register


def register_default_providers() -> None:
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
                prices_require_branch=True,
            ),
        )
    )

    register(
        ExtensionProvider(
            slug="carrefour",
            display_name="Carrefour",
            config=ExtensionStoreConfig(
                origin="https://www.carrefour.fr",
                search_url_template="https://www.carrefour.fr/s?q={query}",
                cart_url="https://www.carrefour.fr/mon-panier",
                requires_branch=True,
            ),
        )
    )

    _register_magento_stores()


def _register_magento_stores() -> None:
    """Register Magento storefronts for which we hold credentials."""
    magento_stores = (
        ("biocoop", "Biocoop", "https://www.biocoop.fr", settings.BIOCOOP_API_TOKEN),
        (
            "naturalia",
            "Naturalia",
            "https://www.naturalia.fr",
            settings.NATURALIA_API_TOKEN,
        ),
    )
    for slug, display_name, origin, token in magento_stores:
        if not token:
            continue
        register(
            MagentoProvider(
                slug=slug,
                display_name=display_name,
                config=MagentoConfig(origin=origin, access_token=token),
            )
        )
