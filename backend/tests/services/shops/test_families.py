"""The reusable provider families.

HTTP is mocked at the submodule path (``...families.http_client.get_text``),
matching the convention the recipe-import tests use.
"""

from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest

from app.models.ingredient import Unit
from app.services.shops.errors import ShopUnavailableError
from app.services.shops.families.extension import (
    ExtensionProvider,
    ExtensionShopConfig,
)
from app.services.shops.families.html_catalog import (
    HtmlCatalogConfig,
    HtmlCatalogProvider,
)
from app.services.shops.families.magento import MagentoConfig, MagentoProvider
from app.services.shops.families.openprices import OpenPricesProvider
from app.services.shops.models import Capability, CartPlanEntry, Transport

# Trimmed from a real auchan.fr search response: schema.org microdata, the name
# carried only on an image alt, the SKU only in the href, and the availability
# only in a class name.
AUCHAN_HTML = """
<div class="list">
  <article itemscope itemtype="http://schema.org/Product"
           class="product-thumbnail list__item" data-id="uuid-1">
    <a class="productThumbnailLink" href="/tomates-cerises/pr-C1348834">
      <img alt="Tomates cerises rouges 250g" src="https://cdn.test/a.jpg">
    </a>
  </article>
  <article itemscope itemtype="http://schema.org/Product"
           class="product-thumbnail list__item outOfStock" data-id="uuid-2">
    <a class="productThumbnailLink" href="/tomates-grappe/pr-C1348703">
      <img alt="Tomates rondes en grappe 1,5kg" src="https://cdn.test/b.jpg">
    </a>
  </article>
  <article itemscope itemtype="http://schema.org/Product" class="product-thumbnail">
    <a href="/broken"></a>
  </article>
</div>
"""

AUCHAN_CONFIG = HtmlCatalogConfig(
    origin="https://www.auchan.fr",
    search_url_template="https://www.auchan.fr/recherche?text={query}",
    sku_pattern=r"/pr-([A-Za-z0-9]+)",
    out_of_stock_marker="outOfStock",
    prices_require_store=True,
)


def _auchan() -> HtmlCatalogProvider:
    return HtmlCatalogProvider(
        slug="auchan", display_name="Auchan", config=AUCHAN_CONFIG
    )


class TestHtmlCatalog:
    def test_parses_microdata_products(self) -> None:
        with patch(
            "app.services.shops.families.http_client.get_text",
            return_value=AUCHAN_HTML,
        ):
            products = _auchan().search("tomate")

        assert [p.sku for p in products] == ["C1348834", "C1348703"]
        first = products[0]
        assert first.name == "Tomates cerises rouges 250g"
        assert first.url == "https://www.auchan.fr/tomates-cerises/pr-C1348834"
        assert first.pack_quantity == 250
        assert first.pack_unit is Unit.GRAM
        assert first.in_stock is True

    def test_reads_availability_and_decimal_pack_sizes(self) -> None:
        with patch(
            "app.services.shops.families.http_client.get_text",
            return_value=AUCHAN_HTML,
        ):
            products = _auchan().search("tomate")
        second = products[1]
        assert second.in_stock is False
        assert second.pack_quantity == 1.5
        assert second.pack_unit is Unit.KILOGRAM

    def test_products_without_a_name_are_skipped_not_fatal(self) -> None:
        with patch(
            "app.services.shops.families.http_client.get_text",
            return_value=AUCHAN_HTML,
        ):
            assert len(_auchan().search("tomate")) == 2

    def test_limit_is_honoured(self) -> None:
        with patch(
            "app.services.shops.families.http_client.get_text",
            return_value=AUCHAN_HTML,
        ):
            assert len(_auchan().search("tomate", limit=1)) == 1

    def test_no_prices_capability_when_store_gated(self) -> None:
        provider = _auchan()
        assert not provider.supports(Capability.PRICES)
        assert provider.requires_store is True

    def test_transport_failure_propagates_for_the_orchestrator_to_catch(self) -> None:
        with patch(
            "app.services.shops.families.http_client.get_text",
            side_effect=ShopUnavailableError("403"),
        ):
            with pytest.raises(ShopUnavailableError):
                _auchan().search("tomate")

    def test_cart_link_points_at_the_shop_search(self) -> None:
        link = _auchan().cart_link(
            [CartPlanEntry(query="crème fraîche", name="crème fraîche", quantity=1)]
        )
        assert link.startswith("https://www.auchan.fr/recherche?text=")
        assert "%C3%A8" in link, "query must be URL-encoded"


class TestOpenPrices:
    PRODUCTS: dict[str, Any] = {
        "items": [
            {
                "code": "3329489901583",
                "product_name": "Tomates pelées Bio",
                "brands": "Bio Village",
                "product_quantity": 400,
                "product_quantity_unit": "g",
                "image_url": "https://img.test/t.jpg",
            },
            {"code": None, "product_name": "broken"},
        ]
    }

    def test_search_maps_products(self) -> None:
        with patch(
            "app.services.shops.families.http_client.get_json",
            return_value=self.PRODUCTS,
        ):
            products = OpenPricesProvider().search("tomate")
        assert len(products) == 1
        assert products[0].barcode == "3329489901583"
        assert products[0].pack_quantity == 400
        assert products[0].pack_unit is Unit.GRAM

    def test_attach_prices_fills_in_by_barcode(self) -> None:
        provider = OpenPricesProvider()
        with patch(
            "app.services.shops.families.http_client.get_json",
            side_effect=[self.PRODUCTS, {"items": [{"price": "1.29"}]}],
        ):
            products = provider.search("tomate")
            priced = provider.attach_prices(products)
        assert priced[0].price == Decimal("1.29")

    def test_missing_price_leaves_the_product_intact(self) -> None:
        provider = OpenPricesProvider()
        with patch(
            "app.services.shops.families.http_client.get_json",
            side_effect=[self.PRODUCTS, {"items": []}],
        ):
            products = provider.search("tomate")
            priced = provider.attach_prices(products)
        assert priced[0].price is None

    def test_attribution_is_declared(self) -> None:
        """ODbL obliges the UI to credit the source."""
        assert "ODbL" in (OpenPricesProvider().attribution or "")


class TestMagento:
    RESPONSE: dict[str, Any] = {
        "data": {
            "products": {
                "items": [
                    {
                        "sku": "BIO-123",
                        "name": "Lentilles vertes bio 500 g",
                        "url_key": "lentilles-vertes-bio",
                        "stock_status": "IN_STOCK",
                        "small_image": {"url": "https://img.test/l.jpg"},
                        "price_range": {
                            "minimum_price": {
                                "final_price": {"value": 3.45, "currency": "EUR"}
                            }
                        },
                    }
                ]
            }
        }
    }

    def _provider(self) -> MagentoProvider:
        return MagentoProvider(
            slug="biocoop",
            display_name="Biocoop",
            config=MagentoConfig(origin="https://www.biocoop.fr", access_token="token"),
        )

    def test_search_maps_graphql_items(self) -> None:
        provider = self._provider()
        with patch.object(provider, "_graphql", return_value=self.RESPONSE):
            products = provider.search("lentilles")
        assert products[0].sku == "BIO-123"
        assert products[0].price == Decimal("3.45")
        assert products[0].pack_quantity == 500
        assert products[0].in_stock is True
        assert products[0].url == "https://www.biocoop.fr/lentilles-vertes-bio.html"

    def test_one_implementation_serves_any_magento_domain(self) -> None:
        """The point of a family: a second shop is config, not code."""
        naturalia = MagentoProvider(
            slug="naturalia",
            display_name="Naturalia",
            config=MagentoConfig(origin="https://www.naturalia.fr"),
        )
        with patch.object(naturalia, "_graphql", return_value=self.RESPONSE):
            products = naturalia.search("lentilles")
        assert products[0].url.startswith("https://www.naturalia.fr/")


class TestExtensionFamily:
    def _provider(self) -> ExtensionProvider:
        return ExtensionProvider(
            slug="carrefour",
            display_name="Carrefour",
            config=ExtensionShopConfig(
                origin="https://www.carrefour.fr",
                search_url_template="https://www.carrefour.fr/s?q={query}",
                cart_url="https://www.carrefour.fr/mon-panier",
                requires_store=True,
            ),
        )

    def test_declares_no_search_because_the_server_truly_cannot(self) -> None:
        provider = self._provider()
        assert not provider.supports(Capability.SEARCH)
        assert provider.supports(Capability.CART_PUSH)
        assert provider.transport is Transport.EXTENSION

    def test_plan_carries_origin_and_entries(self) -> None:
        entries = [
            CartPlanEntry(query="lait", name="lait", quantity=2, sku="SKU1"),
        ]
        plan = self._provider().cart_plan(entries, store_id="store-9")
        assert plan.origin == "https://www.carrefour.fr"
        assert plan.store_id == "store-9"
        assert plan.entries[0].quantity == 2

    def test_cart_link_is_the_fallback_for_users_without_the_extension(self) -> None:
        assert self._provider().cart_link([]) == "https://www.carrefour.fr/mon-panier"


class TestHtmlCatalogExtraction:
    """Shops vary in where they put the name, the price and the image.
    The family handles the standard placements so a new shop needs no code."""

    MICRODATA = """
    <div itemscope itemtype="https://schema.org/Product" class="card">
      <a href="/p/sku-9"><span itemprop="name">Lentilles vertes 500 g</span></a>
      <meta itemprop="image" content="https://img.test/l.jpg">
      <meta itemprop="price" content="3,45">
    </div>
    """

    CUSTOM = """
    <div class="tile" data-sku="XYZ">
      <a href="/p/xyz"><h3 class="title">Farine T55 1kg</h3></a>
      <img src="https://img.test/f.jpg">
      <span class="amount">2,10 €</span>
    </div>
    """

    def test_reads_microdata_name_price_and_image(self) -> None:
        provider = HtmlCatalogProvider(
            slug="m",
            display_name="M",
            supports_prices=True,
            config=HtmlCatalogConfig(
                origin="https://m.test",
                search_url_template="https://m.test/s?q={query}",
                sku_pattern=r"/p/([A-Za-z0-9-]+)",
            ),
        )
        with patch(
            "app.services.shops.families.http_client.get_text",
            return_value=self.MICRODATA,
        ):
            products = provider.search("lentilles")
        assert products[0].name == "Lentilles vertes 500 g"
        assert products[0].price == Decimal("3.45")
        assert products[0].image_url == "https://img.test/l.jpg"
        assert provider.supports(Capability.PRICES)

    def test_custom_selectors_cover_a_non_microdata_shop(self) -> None:
        provider = HtmlCatalogProvider(
            slug="c",
            display_name="C",
            supports_prices=True,
            config=HtmlCatalogConfig(
                origin="https://c.test",
                search_url_template="https://c.test/s?q={query}",
                product_selector=".tile",
                name_selector=".title",
                price_selector=".amount",
            ),
        )
        with patch(
            "app.services.shops.families.http_client.get_text",
            return_value=self.CUSTOM,
        ):
            products = provider.search("farine")
        assert products[0].sku == "XYZ"
        assert products[0].name == "Farine T55 1kg"
        assert products[0].price == Decimal("2.10")
        assert products[0].image_url == "https://img.test/f.jpg"
        assert products[0].pack_quantity == 1.0
        assert products[0].pack_unit is Unit.KILOGRAM

    def test_unparseable_price_is_absent_not_zero(self) -> None:
        provider = HtmlCatalogProvider(
            slug="b",
            display_name="B",
            supports_prices=True,
            config=HtmlCatalogConfig(
                origin="https://b.test",
                search_url_template="https://b.test/s?q={query}",
                price_selector=".amount",
            ),
        )
        html = (
            '<div itemscope itemtype="https://schema.org/Product">'
            '<a href="/p/1"><span itemprop="name">Sel</span></a>'
            '<meta itemprop="price" content="indisponible">'
            '<span class="amount">prix non communiqué</span></div>'
        )
        with patch(
            "app.services.shops.families.http_client.get_text", return_value=html
        ):
            products = provider.search("sel")
        assert products[0].price is None


class TestMagentoFailures:
    def test_http_error_becomes_shop_unavailable(self) -> None:
        provider = MagentoProvider(
            slug="x",
            display_name="X",
            config=MagentoConfig(origin="https://x.test"),
        )
        with patch("httpx.post", side_effect=httpx.ConnectTimeout("nope")):
            with pytest.raises(ShopUnavailableError):
                provider.search("lentilles")

    def test_auth_gated_storefront_becomes_shop_unavailable(self) -> None:
        """Biocoop and Naturalia both answer 401 without a token."""
        response = Mock(spec=httpx.Response)
        response.status_code = 401
        response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError("401", request=Mock(), response=response)
        )
        provider = MagentoProvider(
            slug="x",
            display_name="X",
            config=MagentoConfig(origin="https://x.test"),
        )
        with patch("httpx.post", return_value=response):
            with pytest.raises(ShopUnavailableError, match="401"):
                provider.search("lentilles")

    def test_malformed_items_are_skipped(self) -> None:
        provider = MagentoProvider(
            slug="x",
            display_name="X",
            config=MagentoConfig(origin="https://x.test"),
        )
        payload: dict[str, Any] = {
            "data": {
                "products": {
                    "items": [
                        {"sku": None, "name": "no sku"},
                        "not-a-dict",
                        {
                            "sku": "OK",
                            "name": "Sel fin",
                            "price_range": {
                                "minimum_price": {"final_price": {"value": "bad"}}
                            },
                        },
                    ]
                }
            }
        }
        with patch.object(provider, "_graphql", return_value=payload):
            products = provider.search("sel")
        assert [p.sku for p in products] == ["OK"]
        assert products[0].price is None
