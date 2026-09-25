"""The provider registry, and the consistency check that guards it.

Registration is the single place a store becomes visible to the API, so it is
also the right place to refuse an inconsistent one. ``check_provider`` verifies
in both directions that declared capabilities and implemented methods agree:

- declaring a capability without overriding its method would 500 at runtime;
- overriding a method without declaring the capability would make the feature
  invisible to the UI, which gates everything on ``capabilities``.

Both raise ``ProviderConfigurationError`` at import time. A mistake here is a
failed startup, never a broken page.
"""

from __future__ import annotations

from app.services.store_providers.base import StoreProvider
from app.services.store_providers.errors import (
    ProviderConfigurationError,
    ProviderNotFoundError,
)
from app.services.store_providers.models import Capability

#: Capability -> the method on ``StoreProvider`` that implements it.
CAPABILITY_METHODS: dict[Capability, str] = {
    Capability.SEARCH: "search",
    Capability.PRICES: "attach_prices",
    Capability.STORE_LOCATOR: "stores",
    Capability.CART_LINK: "cart_link",
    Capability.CART_PUSH: "cart_plan",
    Capability.LIST_EXPORT: "export_list",
}

#: A provider serving every country — a list you shop from by hand needs no
#: local presence, so it must not be filtered out of any country's picker.
ANY_COUNTRY = "*"

_REGISTRY: dict[str, StoreProvider] = {}


def check_provider(provider: StoreProvider) -> None:
    """Raise if the provider's declarations and implementation disagree."""
    if not provider.slug:
        raise ProviderConfigurationError("Provider has an empty slug")

    unknown = set(provider.capabilities) - set(CAPABILITY_METHODS)
    if unknown:
        raise ProviderConfigurationError(
            f"{provider.slug} declares unknown capabilities: {sorted(unknown)}"
        )

    for capability, method_name in CAPABILITY_METHODS.items():
        declared = capability in provider.capabilities
        implemented = getattr(type(provider), method_name) is not getattr(
            StoreProvider, method_name
        )
        if declared and not implemented:
            raise ProviderConfigurationError(
                f"{provider.slug} declares {capability.value!r} but does not "
                f"override {method_name}()"
            )
        if implemented and not declared:
            raise ProviderConfigurationError(
                f"{provider.slug} overrides {method_name}() but does not "
                f"declare {capability.value!r}; the UI would never offer it"
            )


def register(provider: StoreProvider) -> StoreProvider:
    """Validate and add a provider. Returns it, so definitions can chain."""
    check_provider(provider)
    if provider.slug in _REGISTRY:
        raise ProviderConfigurationError(f"Duplicate store slug: {provider.slug!r}")
    _REGISTRY[provider.slug] = provider
    return provider


def get_provider(slug: str) -> StoreProvider:
    try:
        return _REGISTRY[slug]
    except KeyError:
        raise ProviderNotFoundError(f"Unknown store: {slug!r}") from None


def iter_providers(*, country: str | None = None) -> list[StoreProvider]:
    """All registered providers, ordered by display name for a stable UI."""
    providers = list(_REGISTRY.values())
    if country is not None:
        providers = [p for p in providers if p.country in (country, ANY_COUNTRY)]
    return sorted(providers, key=lambda p: p.display_name.lower())


def clear_registry() -> None:
    """Test helper. Not used by application code."""
    _REGISTRY.clear()
