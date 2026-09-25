"""The guard that turns a provider mistake into a failed startup."""

import pytest

from app.services.store_providers.base import StoreProvider
from app.services.store_providers.errors import (
    ProviderConfigurationError,
    ProviderNotFoundError,
)
from app.services.store_providers.models import Capability, StoreProduct
from app.services.store_providers.registry import (
    CAPABILITY_METHODS,
    check_provider,
    get_provider,
    iter_providers,
)


class _Declared(StoreProvider):
    """Declares SEARCH without implementing it."""

    capabilities = frozenset({Capability.SEARCH})


class _Undeclared(StoreProvider):
    """Implements search() without declaring it."""

    capabilities = frozenset()

    def search(
        self, query: str, *, limit: int = 10, branch_id: str | None = None
    ) -> list[StoreProduct]:
        return []


class _Consistent(StoreProvider):
    capabilities = frozenset({Capability.SEARCH})

    def search(
        self, query: str, *, limit: int = 10, branch_id: str | None = None
    ) -> list[StoreProduct]:
        return []


def test_every_capability_maps_to_a_method() -> None:
    assert set(CAPABILITY_METHODS) == set(Capability)


def test_declared_but_unimplemented_is_rejected() -> None:
    with pytest.raises(ProviderConfigurationError, match="does not override"):
        check_provider(_Declared(slug="a", display_name="A"))


def test_implemented_but_undeclared_is_rejected() -> None:
    """Otherwise the feature exists but the capability-gated UI never shows it."""
    with pytest.raises(ProviderConfigurationError, match="does not declare"):
        check_provider(_Undeclared(slug="b", display_name="B"))


def test_consistent_provider_passes() -> None:
    check_provider(_Consistent(slug="c", display_name="C"))


def test_empty_slug_is_rejected() -> None:
    with pytest.raises(ProviderConfigurationError, match="empty slug"):
        check_provider(_Consistent(slug="", display_name="D"))


def test_unknown_store_raises() -> None:
    with pytest.raises(ProviderNotFoundError):
        get_provider("does-not-exist")


def test_default_stores_are_registered_and_consistent() -> None:
    providers = iter_providers()
    slugs = {p.slug for p in providers}
    assert {"auchan", "carrefour", "openprices"} <= slugs
    for provider in providers:
        check_provider(provider)


def test_country_filter() -> None:
    """Country narrows the registry to retailers that operate there.

    Nothing survives a foreign filter any more: printing a list is a layout,
    not a store, so there is no longer a country-agnostic member.
    """
    assert {p.slug for p in iter_providers(country="ZZ")} == set()
    assert {"auchan", "carrefour"} <= {p.slug for p in iter_providers(country="FR")}
