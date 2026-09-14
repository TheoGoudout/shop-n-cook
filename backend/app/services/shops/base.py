"""The provider contract every shop implements.

Adding a shop means one of two things:

1. It fits an existing family (``families/``) — then it is a line of config in
   ``definitions.py`` and no new code at all.
2. It does not — then it is one subclass here, overriding only the operations
   it can actually perform.

A provider must never override an operation it has not declared in
``capabilities``, and must never declare one it has not overridden. The
registry enforces both at import time (see ``registry.check_provider``), so a
mismatch is a startup failure rather than a 500 in front of a user.
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Mapping, Sequence

from app.services.shops.errors import CapabilityNotSupportedError
from app.services.shops.models import (
    Capability,
    CartPlan,
    CartPlanEntry,
    ExportedList,
    ListExportFormat,
    ListLine,
    PriceStatus,
    ShopProduct,
    ShopPublic,
    ShopStore,
    Transport,
)


class ShopProvider(ABC):
    """One shop, or one family of shops sharing an e-commerce platform."""

    #: Stable identifier used in URLs and stored on user settings.
    slug: str
    display_name: str
    #: ISO 3166-1 alpha-2. Lets the UI show only shops in the user's country.
    country: str = "FR"
    transport: Transport = Transport.SERVER
    capabilities: frozenset[Capability] = frozenset()
    #: Prices and carts are meaningless until the user picks a store/drive.
    requires_store: bool = False
    website_url: str | None = None
    #: Licence or credit line the UI is obliged to display.
    attribution: str | None = None

    def __init__(
        self,
        *,
        slug: str,
        display_name: str,
        country: str = "FR",
        website_url: str | None = None,
        attribution: str | None = None,
    ) -> None:
        self.slug = slug
        self.display_name = display_name
        self.country = country
        self.website_url = website_url
        self.attribution = attribution

    # ----------------------------------------------------------------- #
    # Capability introspection                                           #
    # ----------------------------------------------------------------- #

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    @property
    def unpriced_reason(self) -> PriceStatus:
        """Why a product from this shop may arrive without a price.

        Derived rather than configured, so a provider cannot drift out of sync
        with its own capability set.
        """
        # Most specific explanation wins. A shop that prices per store is not
        # "unable to price" — the user just has to pick one, which is
        # actionable in a way that NOT_SUPPORTED is not.
        if self.requires_store:
            return PriceStatus.REQUIRES_STORE
        if not self.supports(Capability.PRICES):
            return PriceStatus.NOT_SUPPORTED
        return PriceStatus.UNKNOWN

    def to_public(self) -> ShopPublic:
        return ShopPublic(
            slug=self.slug,
            display_name=self.display_name,
            country=self.country,
            transport=self.transport,
            # Sorted so the OpenAPI payload is stable across restarts.
            capabilities=sorted(self.capabilities, key=lambda c: c.value),
            requires_store=self.requires_store,
            requires_extension=self.transport is Transport.EXTENSION,
            website_url=self.website_url,
            attribution=self.attribution,
        )

    # ----------------------------------------------------------------- #
    # Operations — override exactly the ones you declare                 #
    # ----------------------------------------------------------------- #

    def search(
        self, query: str, *, limit: int = 10, store_id: str | None = None
    ) -> list[ShopProduct]:
        """Candidate products for a free-text ingredient name.

        Implementations return products already priced when they can; leaving
        ``price`` unset is a legitimate answer, not a failure.
        """
        raise CapabilityNotSupportedError(
            f"{self.slug} does not support {Capability.SEARCH.value}"
        )

    def attach_prices(
        self, products: Sequence[ShopProduct], *, store_id: str | None = None
    ) -> list[ShopProduct]:
        """Enrich products with prices.

        Separate from :meth:`search` on purpose. Some shops price during
        search; others (a price database keyed on barcode) can price products
        they could never have found from a recipe's wording. Keeping the two
        apart is what will later allow one provider's catalogue to be priced by
        another provider's data.
        """
        raise CapabilityNotSupportedError(
            f"{self.slug} does not support {Capability.PRICES.value}"
        )

    def export_list(
        self,
        lines: Sequence[ListLine],
        *,
        export_format: ListExportFormat = ListExportFormat.TEXT,
        category_labels: Mapping[str, str] | None = None,
    ) -> ExportedList:
        """Render a list to shop from by hand.

        The only capability that needs no retailer at all, which is why a shop
        can declare it and nothing else.
        """
        raise CapabilityNotSupportedError(
            f"{self.slug} does not support {Capability.LIST_EXPORT.value}"
        )

    def stores(self, *, postcode: str, limit: int = 10) -> list[ShopStore]:
        raise CapabilityNotSupportedError(
            f"{self.slug} does not support {Capability.STORE_LOCATOR.value}"
        )

    def cart_link(
        self, entries: Sequence[CartPlanEntry], *, store_id: str | None = None
    ) -> str:
        raise CapabilityNotSupportedError(
            f"{self.slug} does not support {Capability.CART_LINK.value}"
        )

    def cart_plan(
        self, entries: Sequence[CartPlanEntry], *, store_id: str | None = None
    ) -> CartPlan:
        raise CapabilityNotSupportedError(
            f"{self.slug} does not support {Capability.CART_PUSH.value}"
        )
