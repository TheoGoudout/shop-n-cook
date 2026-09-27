"""Open Prices as one chain's price source.

HTTP is mocked at ``http_client.get_json`` with a router on the endpoint, so
each test states exactly what the API answered.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest

from app.services.store_providers.definitions import CARREFOUR_CHAIN, CHAINS
from app.services.store_providers.errors import ProviderConfigurationError
from app.services.store_providers.families.extension import (
    ExtensionProvider,
    ExtensionStoreConfig,
    PricedExtensionProvider,
)
from app.services.store_providers.families.openprices import (
    CODES_PER_REQUEST,
    ChainFilter,
    OpenPricesProvider,
)
from app.services.store_providers.models import (
    Capability,
    CartPlanEntry,
    StoreProduct,
    Transport,
)

CHAIN = ChainFilter(
    name_queries=("Carrefour",),
    brands=frozenset({"carrefour", "carrefour market"}),
)

LOCATIONS: list[dict[str, Any]] = [
    {
        "id": 1,
        "osm_brand": "Carrefour",
        "osm_address_country_code": "FR",
        "price_count": 50,
    },
    {
        "id": 2,
        "osm_brand": "Carrefour Market",
        "osm_address_country_code": "FR",
        "price_count": 900,
    },
    # A convenience format: priced higher, so deliberately not the chain.
    {
        "id": 3,
        "osm_brand": "Carrefour City",
        "osm_address_country_code": "FR",
        "price_count": 800,
    },
    # Same brand, another country.
    {
        "id": 4,
        "osm_brand": "Carrefour",
        "osm_address_country_code": "BE",
        "price_count": 700,
    },
    # No brand tag: the name decides, and must match exactly.
    {
        "id": 5,
        "osm_brand": None,
        "osm_name": "Carrefour",
        "osm_address_country_code": "FR",
        "price_count": 3,
    },
    {
        "id": 6,
        "osm_brand": None,
        "osm_name": "Parking Carrefour",
        "osm_address_country_code": "FR",
        "price_count": 1,
    },
]

PRODUCTS: dict[str, Any] = {
    "items": [
        {
            "code": "111",
            "product_name": "Beurre doux",
            "product_quantity": Decimal("250"),
            "product_quantity_unit": "g",
        },
        {
            "code": "222",
            "product_name": "Beurre demi-sel",
            "product_quantity": 250,
            "product_quantity_unit": "g",
        },
        {"code": "333", "product_name": "Beurre de cacahuète"},
    ]
}


def _router(
    prices: list[dict[str, Any]] | Callable[[dict[str, Any]], dict[str, Any]],
    calls: list[tuple[str, dict[str, Any]]],
) -> Callable[..., Any]:
    def get_json(url: str, *, params: dict[str, Any] | None = None, **_: Any) -> Any:
        params = params or {}
        calls.append((url, params))
        if url.endswith("/locations"):
            return {"items": LOCATIONS, "pages": 1}
        if url.endswith("/products"):
            return PRODUCTS
        if url.endswith("/prices"):
            if callable(prices):
                return prices(params)
            return {"items": prices, "pages": 1}
        raise AssertionError(url)

    return get_json


def _patch(router: Callable[..., Any]) -> Any:
    return patch(
        "app.services.store_providers.families.http_client.get_json",
        side_effect=router,
    )


def _chain() -> OpenPricesProvider:
    return OpenPricesProvider(slug="carrefour", display_name="Carrefour", chain=CHAIN)


class TestChainLocations:
    def test_only_the_chains_own_french_shops(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        with _patch(_router([], calls)):
            ids = _chain()._chain_location_ids()
        assert ids == [1, 2, 5]

    def test_resolved_once_then_cached(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        provider = _chain()
        with _patch(_router([], calls)):
            provider._chain_location_ids()
            provider._chain_location_ids()
        assert sum(1 for url, _ in calls if url.endswith("/locations")) == 1

    def test_locations_are_paged(self) -> None:
        pages = {
            1: {"items": LOCATIONS[:2], "pages": 2},
            2: {"items": LOCATIONS[2:], "pages": 2},
        }
        with patch(
            "app.services.store_providers.families.http_client.get_json",
            side_effect=lambda url, *, params, **_: pages[params["page"]],
        ):
            assert _chain()._chain_location_ids() == [1, 2, 5]


class TestChainSearch:
    def test_keeps_only_products_the_chain_has_a_price_for(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        prices = [
            {"product_code": "222", "price": Decimal("2.35")},
            {"product_code": "111", "price": Decimal("1.95")},
        ]
        with _patch(_router(prices, calls)):
            products = _chain().search("beurre", limit=10)

        assert [(p.sku, p.price) for p in products] == [
            ("111", Decimal("1.95")),
            ("222", Decimal("2.35")),
        ]
        _, params = next(c for c in calls if c[0].endswith("/prices"))
        assert params["location_id__in"] == "1,2,5"
        assert params["product_code__in"] == "111,222,333"
        assert params["currency"] == "EUR"
        assert params["price_is_discounted"] == "false"
        assert params["order_by"] == "-date"
        assert "date__gte" in params, "an undated or old price is not a price"

    def test_the_newest_price_wins(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        prices = [
            {"product_code": "111", "price": Decimal("1.95")},
            {"product_code": "111", "price": Decimal("1.50")},
        ]
        with _patch(_router(prices, calls)):
            products = _chain().search("beurre")
        assert products[0].price == Decimal("1.95")

    @pytest.mark.parametrize(
        "row",
        [
            {"product_code": "111", "price": Decimal("4.20"), "price_per": "KILOGRAM"},
            {"product_code": "111", "price": Decimal("0")},
            {"product_code": "111", "price": None},
            {"product_code": "111", "price": True},
            {"product_code": None, "price": Decimal("1.00")},
        ],
    )
    def test_rows_that_are_not_a_unit_price_are_ignored(
        self, row: dict[str, Any]
    ) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        with _patch(_router([row], calls)):
            assert _chain().search("beurre") == []

    def test_a_chain_with_no_shops_asks_for_no_prices(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        provider = OpenPricesProvider(
            slug="x",
            display_name="X",
            chain=ChainFilter(name_queries=("X",), brands=frozenset({"nobody"})),
        )
        with _patch(_router([], calls)):
            assert provider.search("beurre") == []
        assert not any(url.endswith("/prices") for url, _ in calls)


class TestChainPricing:
    def test_barcodes_are_priced_in_batches(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        codes = [str(1000 + i) for i in range(CODES_PER_REQUEST + 3)]

        def prices(params: dict[str, Any]) -> dict[str, Any]:
            batch = params["product_code__in"].split(",")
            return {
                "items": [{"product_code": c, "price": "1.00"} for c in batch],
                "pages": 1,
            }

        products = [StoreProduct(sku=c, name=c, barcode=c) for c in codes]
        with _patch(_router(prices, calls)):
            priced = _chain().attach_prices(products)

        price_calls = [p for url, p in calls if url.endswith("/prices")]
        assert len(price_calls) == 2
        assert all(p.price == Decimal("1.00") for p in priced)

    def test_paging_stops_once_every_code_is_found(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []

        def prices(_params: dict[str, Any]) -> dict[str, Any]:
            return {"items": [{"product_code": "111", "price": "2.00"}], "pages": 9}

        with _patch(_router(prices, calls)):
            _chain().attach_prices([StoreProduct(sku="111", name="b", barcode="111")])
        assert sum(1 for url, _ in calls if url.endswith("/prices")) == 1

    def test_paging_is_bounded(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []

        def prices(_params: dict[str, Any]) -> dict[str, Any]:
            return {"items": [{"product_code": "999", "price": "2.00"}], "pages": 50}

        with _patch(_router(prices, calls)):
            priced = _chain().attach_prices(
                [StoreProduct(sku="111", name="b", barcode="111")]
            )
        assert priced[0].price is None
        assert sum(1 for url, _ in calls if url.endswith("/prices")) == 4

    def test_products_without_a_barcode_or_with_a_price_are_left_alone(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        products = [
            StoreProduct(sku="a", name="no barcode"),
            StoreProduct(sku="b", name="priced", barcode="1", price=Decimal("3.00")),
        ]
        with _patch(_router([], calls)):
            assert _chain().attach_prices(products) == products
        assert calls == [], "nothing to price, nothing asked"


class TestGenericProvider:
    def test_filters_currency_and_age_but_not_location(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        with _patch(_router([{"product_code": "111", "price": "1.29"}], calls)):
            priced = OpenPricesProvider().attach_prices(
                [StoreProduct(sku="111", name="b", barcode="111")]
            )
        assert priced[0].price == Decimal("1.29")
        _, params = calls[0]
        assert params["currency"] == "EUR"
        assert "date__gte" in params
        assert "location_id__in" not in params

    def test_search_does_not_filter_by_price(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        with _patch(_router([], calls)):
            products = OpenPricesProvider().search("beurre", limit=2)
        assert [p.sku for p in products] == ["111", "222"]
        assert all(p.price is None for p in products)
        assert [url for url, _ in calls] == [
            "https://prices.openfoodfacts.org/api/v1/products"
        ]


class TestDefinitions:
    @pytest.mark.parametrize("slug", sorted(CHAINS))
    def test_every_chain_is_registered_with_search_and_prices(self, slug: str) -> None:
        from app.services.store_providers import get_provider

        provider = get_provider(slug)
        assert provider.supports(Capability.SEARCH)
        assert provider.supports(Capability.PRICES)
        assert not provider.requires_branch
        assert "ODbL" in (provider.attribution or "")

    def test_convenience_formats_are_not_the_chain(self) -> None:
        assert "carrefour city" not in CARREFOUR_CHAIN.brands
        assert "carrefour express" not in CARREFOUR_CHAIN.brands


class TestPricedExtension:
    CONFIG = ExtensionStoreConfig(
        origin="https://www.carrefour.fr",
        search_url_template="https://www.carrefour.fr/s?q={query}",
        cart_url="https://www.carrefour.fr/mon-panier",
    )

    def _provider(self) -> PricedExtensionProvider:
        return PricedExtensionProvider(
            slug="carrefour",
            display_name="Carrefour",
            config=self.CONFIG,
            price_source=_chain(),
        )

    def test_keeps_the_basket_and_gains_search_and_prices(self) -> None:
        provider = self._provider()
        assert provider.transport is Transport.EXTENSION
        assert provider.capabilities >= {
            Capability.CART_PUSH,
            Capability.CART_LINK,
            Capability.SEARCH,
            Capability.PRICES,
        }
        assert "ODbL" in (provider.attribution or "")
        assert provider.to_public().requires_extension is True

    def test_search_and_prices_are_the_sources(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []
        with _patch(_router([{"product_code": "111", "price": "1.95"}], calls)):
            products = self._provider().search("beurre")
            priced = self._provider().attach_prices(
                [StoreProduct(sku="111", name="b", barcode="111")]
            )
        assert [p.sku for p in products] == ["111"]
        assert priced[0].price == Decimal("1.95")

    def test_a_source_that_cannot_price_is_refused(self) -> None:
        with pytest.raises(ProviderConfigurationError, match="must search and price"):
            PricedExtensionProvider(
                slug="carrefour",
                display_name="Carrefour",
                config=self.CONFIG,
                price_source=ExtensionProvider(
                    slug="x", display_name="X", config=self.CONFIG
                ),
            )

    @pytest.mark.parametrize(
        ("url", "kept"),
        [
            ("https://prices.openfoodfacts.org/products/111", None),
            ("https://www.carrefour.fr.evil.test/p/1", None),
            ("/p/beurre-doux-111", "/p/beurre-doux-111"),
            ("https://www.carrefour.fr/p/beurre", "https://www.carrefour.fr/p/beurre"),
        ],
    )
    def test_the_plan_never_points_the_extension_off_site(
        self, url: str, kept: str | None
    ) -> None:
        entry = CartPlanEntry(
            query="beurre", name="beurre", quantity=1, product_url=url
        )
        plan = self._provider().cart_plan([entry])
        assert plan.entries[0].product_url == kept
