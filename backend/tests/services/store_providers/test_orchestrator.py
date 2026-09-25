"""Degradation: what each store produces when it cannot do the whole job."""

from decimal import Decimal

import pytest

from app.models.ingredient import Unit
from app.services.store_providers.base import StoreProvider
from app.services.store_providers.errors import (
    CapabilityNotSupportedError,
    ProviderUnavailableError,
)
from app.services.store_providers.models import (
    Capability,
    CartPlanEntry,
    DegradationNote,
    ListLine,
    MatchStatus,
    PriceStatus,
    StoreProduct,
    Transport,
)
from app.services.store_providers.orchestrator import (
    build_cart_handoff,
    price_shopping_list,
)

LINES = [
    ListLine(name="tomates cerises", quantity=500, unit=Unit.GRAM),
    ListLine(name="lait demi-écrémé", quantity=1, unit=Unit.LITER),
    ListLine(name="zeste de yuzu", quantity=1, unit=Unit.PIECE),
]

CATALOGUE = {
    "tomates cerises": StoreProduct(
        sku="A1",
        name="Tomates cerises rouges 250g",
        price=Decimal("2.49"),
        pack_quantity=250,
        pack_unit=Unit.GRAM,
    ),
    "lait demi-écrémé": StoreProduct(
        sku="A2",
        name="Lait demi-écrémé 1 L",
        price=Decimal("1.15"),
        pack_quantity=1,
        pack_unit=Unit.LITER,
    ),
}


class _FullStore(StoreProvider):
    capabilities = frozenset(
        {Capability.SEARCH, Capability.PRICES, Capability.CART_LINK}
    )

    def search(
        self, query: str, *, limit: int = 10, branch_id: str | None = None
    ) -> list[StoreProduct]:
        product = CATALOGUE.get(query)
        return [product] if product else []

    def attach_prices(self, products, *, branch_id=None):  # type: ignore[no-untyped-def]
        return list(products)

    def cart_link(self, entries, *, branch_id=None) -> str:  # type: ignore[no-untyped-def]
        return "https://example.test/cart"


class _SearchOnlyStore(StoreProvider):
    """Auchan's shape: a real catalogue, priceless without a store session."""

    capabilities = frozenset({Capability.SEARCH})
    requires_branch = True

    def search(
        self, query: str, *, limit: int = 10, branch_id: str | None = None
    ) -> list[StoreProduct]:
        product = CATALOGUE.get(query)
        return [product.model_copy(update={"price": None})] if product else []


class _DownStore(StoreProvider):
    capabilities = frozenset({Capability.SEARCH})

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.calls = 0

    def search(
        self, query: str, *, limit: int = 10, branch_id: str | None = None
    ) -> list[StoreProduct]:
        self.calls += 1
        raise ProviderUnavailableError("403 from the anti-bot shield")


class _PushStore(StoreProvider):
    """Carrefour's shape: no server search at all, extension-only basket."""

    transport = Transport.EXTENSION
    capabilities = frozenset({Capability.CART_PUSH})
    requires_branch = True

    def cart_plan(self, entries, *, branch_id=None):  # type: ignore[no-untyped-def]
        from app.services.store_providers.models import CartPlan

        return CartPlan(
            store_slug=self.slug,
            origin="https://example.test",
            branch_id=branch_id,
            entries=list(entries),
        )


class _InertStore(StoreProvider):
    capabilities = frozenset()


class TestPricing:
    def test_full_store_prices_what_it_can_and_flags_the_rest(self) -> None:
        result = price_shopping_list(
            provider=_FullStore(slug="full", display_name="Full"), lines=LINES
        )
        assert result.total == Decimal("6.13")
        assert result.priced_item_count == 2
        assert result.unpriced_item_count == 1
        assert result.partial is True
        assert DegradationNote.SOME_ITEMS_UNMATCHED in result.notes
        assert result.items[0].pack_count == 2

    def test_search_without_prices_yields_products_but_no_total(self) -> None:
        result = price_shopping_list(
            provider=_SearchOnlyStore(slug="so", display_name="SO"), lines=LINES
        )
        assert result.total is None
        assert result.items[0].product is not None
        assert result.items[0].match_status is MatchStatus.MATCHED
        assert result.items[0].price_status is PriceStatus.REQUIRES_BRANCH
        assert DegradationNote.PRICES_REQUIRE_BRANCH in result.notes

    def test_unreachable_store_stops_after_one_failure(self) -> None:
        provider = _DownStore(slug="down", display_name="Down")
        result = price_shopping_list(provider=provider, lines=LINES)
        assert provider.calls == 1, "should not time out once per line"
        assert all(
            item.match_status is MatchStatus.STORE_UNAVAILABLE for item in result.items
        )
        assert DegradationNote.STORE_UNAVAILABLE in result.notes

    def test_store_without_search_still_returns_every_line(self) -> None:
        result = price_shopping_list(
            provider=_PushStore(slug="push", display_name="Push"), lines=LINES
        )
        assert len(result.items) == len(LINES)
        assert all(
            item.match_status is MatchStatus.SEARCH_UNSUPPORTED for item in result.items
        )
        assert result.notes == [DegradationNote.SEARCH_UNSUPPORTED]

    def test_empty_list_is_not_partial(self) -> None:
        result = price_shopping_list(
            provider=_FullStore(slug="full", display_name="Full"), lines=[]
        )
        assert result.items == []
        assert result.partial is False
        assert result.total is None


class TestCartHandoff:
    def test_extension_transport_emits_a_plan_from_raw_wording(self) -> None:
        handoff = build_cart_handoff(
            provider=_PushStore(slug="push", display_name="Push"), lines=LINES
        )
        assert handoff.transport is Transport.EXTENSION
        assert handoff.url is None
        assert handoff.plan is not None
        assert [e.query for e in handoff.plan.entries] == [line.name for line in LINES]
        # Nothing is "unresolved": the extension resolves on-site, so claiming
        # a failure here would be wrong.
        assert handoff.unresolved_item_names == []
        assert handoff.plan.entries[0].requested_quantity == 500

    def test_server_transport_returns_a_url_and_names_what_it_dropped(self) -> None:
        handoff = build_cart_handoff(
            provider=_FullStore(slug="full", display_name="Full"), lines=LINES
        )
        assert handoff.transport is Transport.SERVER
        assert handoff.url == "https://example.test/cart"
        assert handoff.unresolved_item_names == ["zeste de yuzu"]

    def test_store_with_no_handoff_at_all_raises(self) -> None:
        with pytest.raises(CapabilityNotSupportedError):
            build_cart_handoff(
                provider=_InertStore(slug="inert", display_name="Inert"), lines=LINES
            )


def test_calling_an_undeclared_capability_raises() -> None:
    """The primitives stay strict even though the use cases degrade."""
    provider = _InertStore(slug="inert", display_name="Inert")
    with pytest.raises(CapabilityNotSupportedError):
        provider.search("tomates")
    with pytest.raises(CapabilityNotSupportedError):
        provider.attach_prices([])
    with pytest.raises(CapabilityNotSupportedError):
        provider.stores(postcode="75002")
    with pytest.raises(CapabilityNotSupportedError):
        provider.cart_link([CartPlanEntry(query="x", name="x", quantity=1)])
    with pytest.raises(CapabilityNotSupportedError):
        provider.cart_plan([])


class _LatePricingStore(StoreProvider):
    """Search and pricing are separate calls, as with a barcode price database."""

    capabilities = frozenset({Capability.SEARCH, Capability.PRICES})

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.price_calls = 0
        self.fail_pricing = False

    def search(
        self, query: str, *, limit: int = 10, branch_id: str | None = None
    ) -> list[StoreProduct]:
        product = CATALOGUE.get(query)
        return [product.model_copy(update={"price": None})] if product else []

    def attach_prices(self, products, *, branch_id=None):  # type: ignore[no-untyped-def]
        self.price_calls += 1
        if self.fail_pricing:
            raise ProviderUnavailableError("price service down")
        return [p.model_copy(update={"price": Decimal("2.00")}) for p in products]


class TestLatePricing:
    def test_prices_are_fetched_once_for_the_whole_list(self) -> None:
        provider = _LatePricingStore(slug="late", display_name="Late")
        result = price_shopping_list(provider=provider, lines=LINES)
        assert provider.price_calls == 1, "one batch call, not one call per line"
        assert result.priced_item_count == 2
        # 500 g of cherry tomatoes in 250 g packs = 2 x 2.00, plus 1 L of milk
        # in 1 L packs = 1 x 2.00. The unmatched third line contributes nothing.
        assert result.total == Decimal("6.00")

    def test_line_total_uses_the_pack_count(self) -> None:
        provider = _LatePricingStore(slug="late", display_name="Late")
        result = price_shopping_list(provider=provider, lines=LINES[:1])
        # 500 g wanted, 250 g packs, 2.00 each.
        assert result.items[0].pack_count == 2
        assert result.items[0].line_total == Decimal("4.00")
        assert result.items[0].price_status is PriceStatus.PRICED

    def test_pricing_failure_degrades_rather_than_raises(self) -> None:
        provider = _LatePricingStore(slug="late", display_name="Late")
        provider.fail_pricing = True
        result = price_shopping_list(provider=provider, lines=LINES)
        assert DegradationNote.STORE_UNAVAILABLE in result.notes
        assert result.total is None
        # The products themselves were found, and are still worth showing.
        assert result.items[0].product is not None

    def test_nothing_to_price_skips_the_call(self) -> None:
        provider = _LatePricingStore(slug="late", display_name="Late")
        result = price_shopping_list(provider=provider, lines=[LINES[2]])
        assert provider.price_calls == 0
        assert result.items[0].product is None
