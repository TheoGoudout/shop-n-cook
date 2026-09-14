"""The guard that turns a provider mistake into a failed startup."""

import pytest

from app.services.shops.base import ShopProvider
from app.services.shops.errors import ShopConfigurationError, ShopNotFoundError
from app.services.shops.models import Capability, ShopProduct
from app.services.shops.registry import (
    CAPABILITY_METHODS,
    check_provider,
    get_provider,
    iter_providers,
)


class _Declared(ShopProvider):
    """Declares SEARCH without implementing it."""

    capabilities = frozenset({Capability.SEARCH})


class _Undeclared(ShopProvider):
    """Implements search() without declaring it."""

    capabilities = frozenset()

    def search(
        self, query: str, *, limit: int = 10, store_id: str | None = None
    ) -> list[ShopProduct]:
        return []


class _Consistent(ShopProvider):
    capabilities = frozenset({Capability.SEARCH})

    def search(
        self, query: str, *, limit: int = 10, store_id: str | None = None
    ) -> list[ShopProduct]:
        return []


def test_every_capability_maps_to_a_method() -> None:
    assert set(CAPABILITY_METHODS) == set(Capability)


def test_declared_but_unimplemented_is_rejected() -> None:
    with pytest.raises(ShopConfigurationError, match="does not override"):
        check_provider(_Declared(slug="a", display_name="A"))


def test_implemented_but_undeclared_is_rejected() -> None:
    """Otherwise the feature exists but the capability-gated UI never shows it."""
    with pytest.raises(ShopConfigurationError, match="does not declare"):
        check_provider(_Undeclared(slug="b", display_name="B"))


def test_consistent_provider_passes() -> None:
    check_provider(_Consistent(slug="c", display_name="C"))


def test_empty_slug_is_rejected() -> None:
    with pytest.raises(ShopConfigurationError, match="empty slug"):
        check_provider(_Consistent(slug="", display_name="D"))


def test_unknown_shop_raises() -> None:
    with pytest.raises(ShopNotFoundError):
        get_provider("does-not-exist")


def test_default_shops_are_registered_and_consistent() -> None:
    providers = iter_providers()
    slugs = {p.slug for p in providers}
    assert {"auchan", "carrefour", "openprices"} <= slugs
    for provider in providers:
        check_provider(provider)


def test_country_filter() -> None:
    """Country narrows the retailers but never hides the list-only shops,
    which carry ``ANY_COUNTRY`` because a list you take with you needs no
    local presence."""
    elsewhere = {p.slug for p in iter_providers(country="ZZ")}
    assert not {"auchan", "carrefour", "openprices"} & elsewhere
    assert {"market", "printable"} <= elsewhere
    assert {"auchan", "carrefour"} <= {p.slug for p in iter_providers(country="FR")}
