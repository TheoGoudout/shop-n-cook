"""The sitemap catalogue: search from a product sitemap, price from the page.

Page fixtures are trimmed from the live sites: Monoprix's schema.org JSON-LD,
and Picard's Tag Manager data layer with its cross-sell tiles in the same
format as the product itself.
"""

from collections.abc import Iterator
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.models.ingredient import Unit
from app.services.store_providers.errors import ProviderUnavailableError
from app.services.store_providers.families.http_client import FetchedPage
from app.services.store_providers.families.sitemap_catalog import (
    SitemapCatalogConfig,
    SitemapCatalogProvider,
    SitemapEntry,
    SitemapIndex,
    datalayer_product,
    gtm_product,
    json_ld_product,
    slug_to_name,
)
from app.services.store_providers.models import Capability, StoreProduct

ORIGIN = "https://courses.monoprix.fr"

INDEX_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>{ORIGIN}/sitemaps/sitemap-categories-part1.xml</loc></sitemap>
  <sitemap><loc>{ORIGIN}/sitemaps/sitemap-products-part1.xml</loc></sitemap>
</sitemapindex>"""

PRODUCTS_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{ORIGIN}/products/monoprix-beurre-doux-125g/MPX_1120136</loc></url>
  <url><loc>{ORIGIN}/products/monoprix-beurre-doux-250g/MPX_1816533</loc></url>
  <url><loc>{ORIGIN}/products/campbell-s-sablés-beurre-au-gingembre-125g/MPX_2309191</loc></url>
  <url><loc>{ORIGIN}/products/coca-cola-1-5l/MPX_4</loc></url>
  <url><loc>{ORIGIN}/products/monoprix-beurre-doux-125g/MPX_1120136</loc></url>
  <url><loc>{ORIGIN}/categories/cremerie/beurre/abc</loc></url>
  <url><loc>https://elsewhere.test/products/beurre/MPX_9</loc></url>
  <url><loc>{ORIGIN}/products/a-&amp;-b/MPX_5</loc></url>
</urlset>"""

MONOPRIX_PAGE = """<html><head>
<script type="application/ld+json">{"@context":"https://schema.org",
 "@type":"Organization","name":"Monoprix"}</script>
<script data-test="product-details-structured-data" type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","sku":"MPX_1120136",
 "name":"Monoprix Beurre doux 125g","brand":"Monoprix","size":"125g",
 "image":["https://courses.monoprix.fr/images/1.jpg"],
 "offers":{"@type":"Offer","price":"1.79","priceCurrency":"EUR",
 "availability":"https://schema.org/InStock"}}
</script></head><body></body></html>"""

PICARD_PAGE = """<html><body>
<div class="pi-ProductPage js-gtm-Product"
     data-gtm='{"item_name":"1K HARICOT BEURRE EXT.FIN","item_id":"000000000000001915",
     "price":3.3,"item_availability":"en stock","item_brand":"PICARD",
     "item_format":"le sachet de 1&amp;#160;kg","currency":"EUR"}'>
  <h1>Haricots beurre extra-fins, France</h1>
</div>
<ul>
  <li class="pi-CrossSell-item" data-gtm='{"item_id":"000000000000006542",
      "price":2.49,"item_format":"le sachet de 1&amp;#160;kg"}'></li>
</ul>
</body></html>"""


def _monoprix(**overrides: object) -> SitemapCatalogProvider:
    settings: dict[str, object] = {"min_request_interval": 0, **overrides}
    config = SitemapCatalogConfig(
        origin=ORIGIN,
        sitemap_url=f"{ORIGIN}/sitemaps/sitemap_index.xml",
        sitemap_url_filter=r"sitemap-products",
        product_url_pattern=r"/products/(?P<slug>[^/]+)/(?P<sku>MPX_\d+)$",
        **settings,  # type: ignore[arg-type]
    )
    return SitemapCatalogProvider(
        slug="monoprix", display_name="Monoprix", config=config
    )


def _sitemaps(url: str, **_: object) -> str:
    return INDEX_XML if url.endswith("sitemap_index.xml") else PRODUCTS_XML


@pytest.fixture(autouse=True)
def _robots_allow_everything() -> Iterator[None]:
    with patch(
        "app.services.store_providers.families.robots.ensure_allowed",
        return_value=None,
    ):
        yield


class TestSlugs:
    def test_slug_reads_as_a_name(self) -> None:
        assert slug_to_name("monoprix-beurre-doux-125g") == "Monoprix beurre doux 125g"

    def test_a_decimal_split_by_the_slug_is_put_back(self) -> None:
        """ "1,5 l" slugs to "1-5l"; read naively that is a 5 litre bottle."""
        assert slug_to_name("coca-cola-1-5l") == "Coca cola 1,5l"

    def test_percent_encoding_is_decoded(self) -> None:
        assert slug_to_name("cr%C3%A8me-fra%C3%AEche") == "Crème fraîche"


class TestIndex:
    def _index(self) -> SitemapIndex:
        index = SitemapIndex()
        for sku, name in [
            ("1", "Monoprix beurre doux 125g"),
            ("2", "Sablés au beurre 125g"),
            ("3", "Lait demi écrémé 1l"),
        ]:
            index.add(SitemapEntry(sku=sku, url=f"/p/{sku}", name=name))
        return index

    def test_best_match_first(self) -> None:
        found = self._index().lookup("beurre doux", limit=5)
        assert [e.sku for e in found] == ["1", "2"]

    def test_nothing_in_common_is_nothing(self) -> None:
        assert self._index().lookup("yuzu", limit=5) == []

    def test_limit(self) -> None:
        assert len(self._index().lookup("beurre", limit=1)) == 1


class TestSearch:
    def test_reads_only_product_sitemaps_on_the_store_origin(self) -> None:
        with patch(
            "app.services.store_providers.families.http_client.get_xml",
            side_effect=_sitemaps,
        ) as get_xml:
            products = _monoprix().search("beurre doux", limit=10)

        read = [c.args[0] for c in get_xml.call_args_list]
        assert read == [
            f"{ORIGIN}/sitemaps/sitemap_index.xml",
            f"{ORIGIN}/sitemaps/sitemap-products-part1.xml",
        ]
        skus = [p.sku for p in products]
        assert skus[:2] == ["MPX_1120136", "MPX_1816533"]
        assert "MPX_9" not in skus, "a URL off the store's origin is ignored"
        assert len(skus) == len(set(skus)), "a URL listed twice is one product"

    def test_search_is_unpriced_and_sized_from_the_name(self) -> None:
        with patch(
            "app.services.store_providers.families.http_client.get_xml",
            side_effect=_sitemaps,
        ):
            product = _monoprix().search("beurre doux", limit=1)[0]
        assert product.price is None
        assert product.url == f"{ORIGIN}/products/monoprix-beurre-doux-125g/MPX_1120136"
        assert (product.pack_quantity, product.pack_unit) == (125, Unit.GRAM)

    def test_the_index_is_downloaded_once(self) -> None:
        provider = _monoprix()
        with patch(
            "app.services.store_providers.families.http_client.get_xml",
            side_effect=_sitemaps,
        ) as get_xml:
            provider.search("beurre")
            provider.search("coca")
        assert get_xml.call_count == 2, "index + one sitemap file, once"

    def test_the_index_is_refreshed_when_stale(self) -> None:
        provider = _monoprix(index_ttl_seconds=0)
        with patch(
            "app.services.store_providers.families.http_client.get_xml",
            side_effect=_sitemaps,
        ) as get_xml:
            provider.search("beurre")
            provider.search("beurre")
        assert get_xml.call_count == 4

    def test_a_sitemap_with_no_products_is_unavailable_not_empty(self) -> None:
        with patch(
            "app.services.store_providers.families.http_client.get_xml",
            return_value="<urlset></urlset>",
        ):
            with pytest.raises(ProviderUnavailableError, match="no product URLs"):
                _monoprix().search("beurre")

    def test_robots_is_consulted_for_every_sitemap(self) -> None:
        with (
            patch(
                "app.services.store_providers.families.robots.ensure_allowed",
                side_effect=ProviderUnavailableError("robots.txt disallows"),
            ),
            patch(
                "app.services.store_providers.families.http_client.get_xml"
            ) as get_xml,
        ):
            with pytest.raises(ProviderUnavailableError, match="robots"):
                _monoprix().search("beurre")
        get_xml.assert_not_called()

    def test_capabilities(self) -> None:
        provider = _monoprix()
        assert provider.supports(Capability.SEARCH)
        assert provider.supports(Capability.PRICES)
        assert not provider.requires_branch


class TestAttachPrices:
    PRODUCT = StoreProduct(
        sku="MPX_1120136",
        name="Monoprix beurre doux 125g",
        url=f"{ORIGIN}/products/monoprix-beurre-doux-125g/MPX_1120136",
    )

    def _fetch(self, status: int = 200, text: str = MONOPRIX_PAGE) -> object:
        return patch(
            "app.services.store_providers.families.http_client.fetch",
            return_value=FetchedPage(status_code=status, text=text),
        )

    def test_price_and_details_come_from_the_page(self) -> None:
        with self._fetch():
            priced = _monoprix().attach_prices([self.PRODUCT])[0]
        assert priced.price == Decimal("1.79")
        assert priced.name == "Monoprix Beurre doux 125g"
        assert (priced.pack_quantity, priced.pack_unit) == (125, Unit.GRAM)
        assert priced.in_stock is True
        assert priced.brand == "Monoprix"

    def test_pages_are_cached(self) -> None:
        provider = _monoprix()
        with self._fetch() as fetch:
            provider.attach_prices([self.PRODUCT])
            provider.attach_prices([self.PRODUCT])
        fetch.assert_called_once()

    def test_a_delisted_product_stays_unpriced(self) -> None:
        with self._fetch(status=404):
            priced = _monoprix().attach_prices([self.PRODUCT])[0]
        assert priced.price is None

    def test_a_refusal_stops_the_store(self) -> None:
        with self._fetch(status=403):
            with pytest.raises(ProviderUnavailableError, match="403"):
                _monoprix().attach_prices([self.PRODUCT])

    def test_a_price_in_another_currency_is_not_taken(self) -> None:
        page = MONOPRIX_PAGE.replace('"priceCurrency":"EUR"', '"priceCurrency":"GBP"')
        with self._fetch(text=page):
            priced = _monoprix().attach_prices([self.PRODUCT])[0]
        assert priced.price is None

    def test_a_url_off_the_store_origin_is_never_fetched(self) -> None:
        stray = self.PRODUCT.model_copy(update={"url": "https://elsewhere.test/p/1"})
        with self._fetch() as fetch:
            priced = _monoprix().attach_prices([stray])[0]
        fetch.assert_not_called()
        assert priced.price is None

    def test_already_priced_and_url_less_products_are_left_alone(self) -> None:
        priced = self.PRODUCT.model_copy(update={"price": Decimal("9.99")})
        url_less = self.PRODUCT.model_copy(update={"url": None})
        with self._fetch() as fetch:
            result = _monoprix().attach_prices([priced, url_less])
        fetch.assert_not_called()
        assert result == [priced, url_less]

    def test_requests_are_spaced_out(self) -> None:
        provider = _monoprix(min_request_interval=10.0)
        other = self.PRODUCT.model_copy(
            update={"sku": "MPX_2", "url": f"{ORIGIN}/products/other/MPX_2"}
        )
        with (
            self._fetch(),
            patch(
                "app.services.store_providers.families.sitemap_catalog.time.sleep"
            ) as sleep,
        ):
            provider.attach_prices([self.PRODUCT, other])
        assert sleep.call_count == 1
        assert 0 < sleep.call_args.args[0] <= 10.0


class TestJsonLd:
    def test_reads_the_product_not_the_organisation(self) -> None:
        page = json_ld_product(MONOPRIX_PAGE, "MPX_1120136")
        assert page is not None
        assert page.price == Decimal("1.79")
        assert page.currency == "EUR"
        assert page.image_url == "https://courses.monoprix.fr/images/1.jpg"

    def test_the_name_quantity_beats_a_drained_weight_size(self) -> None:
        page_html = MONOPRIX_PAGE.replace(
            '"name":"Monoprix Beurre doux 125g"', '"name":"Tomates pelées 400g"'
        ).replace('"size":"125g"', '"size":"0.24kg"')
        page = json_ld_product(page_html, "MPX_1120136")
        assert page is not None
        assert (page.pack_quantity, page.pack_unit) == (400, Unit.GRAM)

    def test_size_is_the_fallback_when_the_name_has_none(self) -> None:
        page_html = MONOPRIX_PAGE.replace(
            '"name":"Monoprix Beurre doux 125g"', '"name":"Beurre doux"'
        )
        page = json_ld_product(page_html, "MPX_1120136")
        assert page is not None
        assert (page.pack_quantity, page.pack_unit) == (125, Unit.GRAM)

    def test_graph_offers_list_numeric_price_and_gtin(self) -> None:
        page_html = """<script type="application/ld+json">
        {"@graph":[{"@type":["Product"],"sku":"X","name":"Farine T55 1kg",
          "gtin13":"3017620422003","brand":{"@type":"Brand","name":"Francine"},
          "offers":[{"price":1.15,"priceCurrency":"EUR",
                     "availability":"https://schema.org/OutOfStock"}]}]}
        </script>"""
        page = json_ld_product(page_html, "X")
        assert page is not None
        assert page.price == Decimal("1.15")
        assert str(page.price) == "1.15", "never through a float"
        assert page.barcode == "3017620422003"
        assert page.brand == "Francine"
        assert page.in_stock is False

    @pytest.mark.parametrize("price", ['"0"', '"n/a"', "null", "true", '"-1"'])
    def test_an_unusable_price_is_absent_not_zero(self, price: str) -> None:
        page_html = MONOPRIX_PAGE.replace('"price":"1.79"', f'"price":{price}')
        page = json_ld_product(page_html, "MPX_1120136")
        assert page is not None
        assert page.price is None

    def test_no_product_is_none(self) -> None:
        assert json_ld_product("<html></html>", "X") is None

    def test_broken_json_ld_is_skipped(self) -> None:
        page_html = (
            '<script type="application/ld+json">{broken</script>' + MONOPRIX_PAGE
        )
        page = json_ld_product(page_html, "MPX_1120136")
        assert page is not None
        assert page.price == Decimal("1.79")


class TestGtm:
    def test_reads_its_own_product_not_a_cross_sell_tile(self) -> None:
        page = gtm_product(PICARD_PAGE, "000000000000001915")
        assert page is not None
        assert page.price == Decimal("3.3")
        assert page.name == "Haricots beurre extra-fins, France"
        assert (page.pack_quantity, page.pack_unit) == (1, Unit.KILOGRAM)
        assert page.in_stock is True
        assert page.brand == "PICARD"

    def test_a_cross_sell_tile_is_found_only_by_its_own_id(self) -> None:
        page = gtm_product(PICARD_PAGE, "000000000000006542")
        assert page is not None
        assert page.price == Decimal("2.49")

    def test_an_unknown_id_is_none(self) -> None:
        assert gtm_product(PICARD_PAGE, "000000000000000000") is None


BIOCOOP_PAGE = """<script>
dataLayer.push({"event":"trackView","magasinClient":"Biocoop national"});
</script><script>
dataLayer.push({"event":"productView","ecommerce":{"currencyCode":"EUR",
 "detail":{"actionField":{"list":"Product_list"},"products":[{
 "name":"Beurre doux 250g","id":"AD7044_000","price":3.25,
 "brand":"G\\u00e9rentes","dimension1":"ref_national"}]}}});
</script>"""


class TestDataLayer:
    def test_reads_the_product_view(self) -> None:
        page = datalayer_product(BIOCOOP_PAGE, "ad7044-000")
        assert page is not None
        assert page.price == Decimal("3.25")
        assert str(page.price) == "3.25", "never through a float"
        assert page.currency == "EUR"
        assert page.name == "Beurre doux 250g"
        assert page.brand == "Gérentes"
        assert (page.pack_quantity, page.pack_unit) == (250, Unit.GRAM)

    def test_a_single_product_is_taken_even_if_its_id_carries_a_suffix(self) -> None:
        """The URL says fel4089-000, the page says FEL4089_000_355."""
        page = datalayer_product(
            BIOCOOP_PAGE.replace("AD7044_000", "AD7044_000_355"), "ad7044-000"
        )
        assert page is not None
        assert page.price == Decimal("3.25")

    def test_a_zero_price_is_no_price(self) -> None:
        """Biocoop publishes 0 for products it does not price on the web."""
        page = datalayer_product(
            BIOCOOP_PAGE.replace('"price":3.25', '"price":0'), "ad7044-000"
        )
        assert page is not None
        assert page.price is None

    def test_no_product_view_is_none(self) -> None:
        assert datalayer_product("<script>dataLayer.push({})</script>", "x") is None
        assert datalayer_product("<script>dataLayer.push(broken</script>", "x") is None

    def test_several_products_and_none_ours_is_none(self) -> None:
        two = BIOCOOP_PAGE.replace(
            '"dimension1":"ref_national"}]',
            '"dimension1":"ref_national"},{"id":"ZZ0000_000","price":1}]',
        ).replace("AD7044_000", "YY1111_000")
        assert datalayer_product(two, "ad7044-000") is None


class TestRegisteredSitemapStores:
    @pytest.mark.parametrize(
        ("slug", "url", "sku"),
        [
            (
                "monoprix",
                "https://courses.monoprix.fr/products/monoprix-beurre-doux-125g/MPX_1120136",
                "MPX_1120136",
            ),
            (
                "picard",
                "https://www.picard.fr/produits/haricots-beurre-extra-fins-000000000000001915.html",
                "000000000000001915",
            ),
            (
                "biocoop",
                "https://www.biocoop.fr/radis-botte-rose-fel4089-000-355.html",
                "fel4089-000",
            ),
            (
                "naturalia",
                "https://www.naturalia.fr/produit/ptit-beurre-cereales-150g",
                "ptit-beurre-cereales-150g",
            ),
        ],
    )
    def test_real_product_urls_are_recognised(
        self, slug: str, url: str, sku: str
    ) -> None:
        from app.services.store_providers import get_provider

        provider = get_provider(slug)
        assert isinstance(provider, SitemapCatalogProvider)
        entry = provider._entry(url)
        assert entry is not None
        assert entry.sku == sku

    @pytest.mark.parametrize(
        ("slug", "url"),
        [
            # A store-local Biocoop line has no national price.
            ("biocoop", "https://www.biocoop.fr/creme-glacee-kim-loc-002508-000.html"),
            ("biocoop", "https://www.biocoop.fr/cremerie/oeufs-beurres-cremes.html"),
            # robots.txt disallows /catalog/.
            ("naturalia", "https://www.naturalia.fr/catalog/product/view/id/45355"),
        ],
    )
    def test_other_urls_are_not_products(self, slug: str, url: str) -> None:
        from app.services.store_providers import get_provider

        provider = get_provider(slug)
        assert isinstance(provider, SitemapCatalogProvider)
        assert provider._entry(url) is None
