"""Stores reachable only through the user's own browser.

Carrefour (Cloudflare), Intermarché and Leclerc Drive (DataDome) return 403 to any
server-side request, and no amount of header spoofing changes that. The
extension transport sidesteps the problem rather than fighting it: the backend
emits a declarative ``CartPlan`` and the extension executes it inside the
session the user is already signed into, so the traffic is a real browser
because it *is* a real browser.

The division of labour is deliberate and is what keeps this maintainable:

- the **backend** owns *what* to buy (SKUs, quantities, search terms);
- the **extension** owns *how* (selectors, waits, retries), in an adapter keyed
  on ``store_slug``.

A retailer redesign therefore ships as an extension update, not a backend
deploy — which matters because the DOM is the part that breaks.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import quote, urljoin

from app.services.store_providers.base import StoreProvider
from app.services.store_providers.errors import ProviderConfigurationError
from app.services.store_providers.models import (
    Capability,
    CartPlan,
    CartPlanEntry,
    StoreProduct,
    Transport,
)


@dataclass(frozen=True)
class ExtensionStoreConfig:
    origin: str
    """Scheme + host the extension operates on."""
    search_url_template: str
    """Must contain ``{query}``. Used both for the link fallback and by the
    extension adapter when an entry has no SKU."""
    cart_url: str | None = None
    requires_branch: bool = False


class ExtensionProvider(StoreProvider):
    """A store whose basket is filled by the browser extension.

    Note the capability set: no SEARCH. The backend genuinely cannot search
    these retailers, and saying so is the point — the orchestrator then builds
    plan entries from the raw list wording and lets the extension resolve each
    one on-site, instead of pretending to a catalogue we do not have.
    """

    transport = Transport.EXTENSION
    capabilities = frozenset({Capability.CART_LINK, Capability.CART_PUSH})

    def __init__(
        self,
        *,
        slug: str,
        display_name: str,
        config: ExtensionStoreConfig,
        country: str = "FR",
    ) -> None:
        super().__init__(
            slug=slug,
            display_name=display_name,
            country=country,
            website_url=config.origin,
        )
        self.config = config
        self.requires_branch = config.requires_branch

    def cart_link(
        self, entries: Sequence[CartPlanEntry], *, branch_id: str | None = None
    ) -> str:
        """Where to send a user who does not have the extension installed."""
        if self.config.cart_url:
            return self.config.cart_url
        query = entries[0].query if entries else ""
        return self.config.search_url_template.format(query=quote(query))

    def cart_plan(
        self, entries: Sequence[CartPlanEntry], *, branch_id: str | None = None
    ) -> CartPlan:
        return CartPlan(
            store_slug=self.slug,
            origin=self.config.origin,
            branch_id=branch_id,
            entries=[self._on_origin(entry) for entry in entries],
        )

    def _on_origin(self, entry: CartPlanEntry) -> CartPlanEntry:
        """Drop a product URL that points anywhere but this retailer.

        The extension navigates to ``product_url`` and runs its add-to-cart
        script there, so a link from a price source (an Open Prices page) must
        never reach it. Without one it searches on-site for ``query`` instead.
        """
        if entry.product_url is None:
            return entry
        absolute = urljoin(self.config.origin + "/", entry.product_url)
        if absolute.startswith(self.config.origin + "/"):
            return entry
        return entry.model_copy(update={"product_url": None})


class PricedExtensionProvider(ExtensionProvider):
    """An extension store whose prices come from somewhere lawful to read.

    The retailer's own site refuses server requests, so its basket is filled by
    the extension exactly as before. What it cannot give us — a catalogue and
    prices — comes from ``price_source``, typically an ``OpenPricesProvider``
    restricted to this chain's shops. The basket still resolves every line
    on-site, in the user's session: a barcode from a price database is not the
    retailer's own product id (see ``orchestrator._build_entries``).
    """

    capabilities = frozenset(
        {
            Capability.CART_LINK,
            Capability.CART_PUSH,
            Capability.SEARCH,
            Capability.PRICES,
        }
    )

    def __init__(
        self,
        *,
        slug: str,
        display_name: str,
        config: ExtensionStoreConfig,
        price_source: StoreProvider,
        country: str = "FR",
    ) -> None:
        if not (
            price_source.supports(Capability.SEARCH)
            and price_source.supports(Capability.PRICES)
        ):
            raise ProviderConfigurationError(
                f"{slug}: price source {price_source.slug!r} must search and price"
            )
        super().__init__(
            slug=slug, display_name=display_name, config=config, country=country
        )
        self.price_source = price_source
        self.attribution = price_source.attribution

    def search(
        self, query: str, *, limit: int = 10, branch_id: str | None = None
    ) -> list[StoreProduct]:
        return self.price_source.search(query, limit=limit, branch_id=branch_id)

    def attach_prices(
        self, products: Sequence[StoreProduct], *, branch_id: str | None = None
    ) -> list[StoreProduct]:
        return self.price_source.attach_prices(products, branch_id=branch_id)
