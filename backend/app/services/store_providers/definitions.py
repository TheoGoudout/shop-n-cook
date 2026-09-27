"""The stores themselves — configuration, not code.

Adding a chain that fits an existing family is a single ``register(...)`` call
here. Only a store that fits none of them needs a new class.

Each entry records *why* it has the capabilities it has, because those were
established by probing the live sites (last on 2026-09-27) and are the kind of
fact that silently rots. Two rules decided every entry:

1. **A 200 is not permission.** Every grocer surveyed disallows its on-site
   search in robots.txt — Auchan ``/recherche``, Picard ``*/recherche``,
   Monoprix ``/search?q=`` and ``/api/``, Lidl ``*search?q=*``, Intermarché
   ``/recherche/*`` — including the ones that answer it. Nothing here reads a
   disallowed path; ``families/robots.py`` enforces that at request time.
2. **No anti-bot evasion.** Carrefour and Système U sit behind Cloudflare,
   Intermarché, Leclerc Drive and Netto behind DataDome, Franprix and Casino
   behind CDNetworks. Each 403s a server request; we take that as the answer.

What that leaves, per chain:

- **Monoprix** (``courses.monoprix.fr``) and **Picard** publish a product
  sitemap and allow their product pages, which carry the price. SEARCH comes
  from the sitemap, PRICES from the chosen product's own page — the retailer's
  live online price. ``sitemap_catalog``.
- **Carrefour, Auchan, E.Leclerc, Intermarché, Super U, Franprix** get
  SEARCH + PRICES from Open Prices, restricted to the chain's own shops: real
  till prices recorded by contributors, ODbL, not live. Each had thousands of
  undiscounted barcode prices in the year to the survey (Carrefour ~18k,
  Leclerc ~14k, Auchan ~10k, Intermarché ~8k, Système U ~5k, Franprix ~3.5k).
  Carrefour keeps its extension basket on top. Auchan's previous provider read
  ``/recherche``, which its robots.txt disallows; its product pages are allowed
  but carry no price without a store session, so Open Prices replaced it.
- **Not registered**, because nothing lawful carries enough data: Lidl (search
  robots-blocked; its site lists only the week's offers; ~370 Open Prices
  prices a year), Aldi (product pages have no prices; ~70), Netto (DataDome;
  ~60), Grand Frais (a product sitemap, but its ~400 pages carry no prices;
  ~7), Casino (CDNetworks; ~200).
  They stay perfectly good stores with hand-curated prices.
- **Biocoop / Naturalia** both run stock Magento 2 and answer ``/rest/V1/...``
  with 401 rather than 404 — the API is there, behind auth. With a token the
  Magento provider is used. Without one they fall back to their product
  sitemaps, which robots.txt allows: Naturalia's pages carry schema.org JSON-LD
  with price and EAN (~6,000 products); Biocoop's carry the national
  reference price in the analytics ``dataLayer`` (~15,000 national products;
  its co-op stores set their own shelf prices, so this is the web price).
- **Blocked, checked 2026-09-27**: Chronodrive (Cloudflare 403 on every path
  including robots.txt; 4 Open Prices prices a year), Bio c' Bon (its site is
  a store locator with no catalogue; ~210 Open Prices prices a year).

Printing a list to carry is deliberately *not* a store here — see
``layouts.py``. Nobody picks "Printable list" as the supermarket they shop at.
"""

from __future__ import annotations

from app.core.config import settings
from app.services.store_providers.families.extension import (
    ExtensionStoreConfig,
    PricedExtensionProvider,
)
from app.services.store_providers.families.magento import MagentoConfig, MagentoProvider
from app.services.store_providers.families.openprices import (
    ChainFilter,
    OpenPricesProvider,
)
from app.services.store_providers.families.sitemap_catalog import (
    SitemapCatalogConfig,
    SitemapCatalogProvider,
    datalayer_product,
    gtm_product,
    json_ld_product,
)
from app.services.store_providers.registry import register

#: Open Prices chain filters. Brands are compared after ``matching.normalize``
#: and must match exactly, which is how the convenience formats (Carrefour
#: City / Express, My Auchan, U Express, Intermarché Express / Contact) are
#: kept out: they price above the super- and hypermarkets the seeded store
#: stands for. Every value below was read off real Open Prices locations.
CHAINS: dict[str, tuple[str, str, ChainFilter]] = {
    "auchan": (
        "Auchan",
        "https://www.auchan.fr",
        ChainFilter(
            name_queries=("Auchan",),
            brands=frozenset({"auchan", "auchan drive", "auchan supermarche"}),
        ),
    ),
    "e-leclerc": (
        "E.Leclerc",
        "https://www.e.leclerc",
        ChainFilter(
            name_queries=("Leclerc",),
            brands=frozenset(
                {
                    "e leclerc",
                    "e leclerc drive",
                    "e leclerc express",
                    "centre commercial e leclerc",
                    "leclerc",
                }
            ),
        ),
    ),
    "franprix": (
        "Franprix",
        "https://www.franprix.fr",
        ChainFilter(name_queries=("Franprix",), brands=frozenset({"franprix"})),
    ),
    "intermarche": (
        "Intermarché",
        "https://www.intermarche.com",
        ChainFilter(
            # Unaccented: matches "Intermarché" whatever the API's collation.
            name_queries=("Intermarch",),
            brands=frozenset(
                {
                    "intermarche",
                    "intermarche super",
                    "intermarche hyper",
                    "intermarche drive",
                }
            ),
        ),
    ),
    "super-u": (
        "Super U",
        "https://www.magasins-u.com",
        ChainFilter(
            name_queries=("Super U", "Hyper U"),
            brands=frozenset({"super u", "hyper u", "systeme u"}),
        ),
    ),
}

CARREFOUR_CHAIN = ChainFilter(
    name_queries=("Carrefour",),
    brands=frozenset({"carrefour", "carrefour market", "carrefour drive"}),
)


def register_default_providers() -> None:
    """Populate the registry. Called once, from the package ``__init__``."""

    register(OpenPricesProvider())

    for slug, (display_name, website_url, chain) in CHAINS.items():
        register(
            OpenPricesProvider(
                slug=slug,
                display_name=display_name,
                chain=chain,
                website_url=website_url,
            )
        )

    register(
        PricedExtensionProvider(
            slug="carrefour",
            display_name="Carrefour",
            config=ExtensionStoreConfig(
                origin="https://www.carrefour.fr",
                search_url_template="https://www.carrefour.fr/s?q={query}",
                cart_url="https://www.carrefour.fr/mon-panier",
                # The basket is filled in the user's own session, where their
                # drive is already chosen, and prices are chain-wide.
                requires_branch=False,
            ),
            price_source=OpenPricesProvider(
                slug="carrefour-openprices",
                display_name="Carrefour",
                chain=CARREFOUR_CHAIN,
                website_url="https://www.carrefour.fr",
            ),
        )
    )

    register(
        SitemapCatalogProvider(
            slug="monoprix",
            display_name="Monoprix",
            config=SitemapCatalogConfig(
                origin="https://courses.monoprix.fr",
                sitemap_url="https://courses.monoprix.fr/sitemaps/sitemap_index.xml",
                sitemap_url_filter=r"sitemap-products",
                product_url_pattern=r"/products/(?P<slug>[^/]+)/(?P<sku>MPX_\d+)$",
                extractor=json_ld_product,
            ),
        )
    )

    register(
        SitemapCatalogProvider(
            slug="picard",
            display_name="Picard",
            config=SitemapCatalogConfig(
                origin="https://www.picard.fr",
                sitemap_url="https://www.picard.fr/sitemap_0.xml",
                product_url_pattern=r"/produits/(?P<slug>.+)-(?P<sku>\d{18})\.html$",
                extractor=gtm_product,
            ),
        )
    )

    _register_magento_stores()


def _register_magento_stores() -> None:
    """Biocoop and Naturalia: the Magento API when we hold a token for it,
    otherwise their product sitemaps.

    A granted API is the retailer's explicit permission and a live answer, so
    it wins; the sitemap route is what is lawful to read without one.
    """
    if settings.BIOCOOP_API_TOKEN:
        register(
            MagentoProvider(
                slug="biocoop",
                display_name="Biocoop",
                config=MagentoConfig(
                    origin="https://www.biocoop.fr",
                    access_token=settings.BIOCOOP_API_TOKEN,
                ),
            )
        )
    else:
        register(
            SitemapCatalogProvider(
                slug="biocoop",
                display_name="Biocoop",
                config=SitemapCatalogConfig(
                    origin="https://www.biocoop.fr",
                    sitemap_url="https://www.biocoop.fr/sitemap.xml",
                    # National references only ("bv5000-000", optionally
                    # followed by an origin or calibre). Store-local lines
                    # ("kim-loc-000081-000") have no national price.
                    product_url_pattern=(
                        r"^https://www\.biocoop\.fr/(?P<slug>[a-z0-9-]+?)"
                        r"-(?P<sku>[a-z]{2,3}\d{4}-\d{3})(?:-[a-z0-9-]+)?\.html$"
                    ),
                    extractor=datalayer_product,
                ),
            )
        )

    if settings.NATURALIA_API_TOKEN:
        register(
            MagentoProvider(
                slug="naturalia",
                display_name="Naturalia",
                config=MagentoConfig(
                    origin="https://www.naturalia.fr",
                    access_token=settings.NATURALIA_API_TOKEN,
                ),
            )
        )
    else:
        register(
            SitemapCatalogProvider(
                slug="naturalia",
                display_name="Naturalia",
                config=SitemapCatalogConfig(
                    origin="https://www.naturalia.fr",
                    sitemap_url="https://www.naturalia.fr/media/sitemap_product.xml",
                    # The URL carries no id; the slug is the product's key.
                    product_url_pattern=r"/produit/(?P<sku>(?P<slug>[a-z0-9-]+))$",
                    extractor=json_ld_product,
                ),
            )
        )
