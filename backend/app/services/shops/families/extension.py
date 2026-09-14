"""Shops reachable only through the user's own browser.

Carrefour (Akamai), Intermarché and Leclerc Drive (DataDome) return 403 to any
server-side request, and no amount of header spoofing changes that. The
extension transport sidesteps the problem rather than fighting it: the backend
emits a declarative ``CartPlan`` and the extension executes it inside the
session the user is already signed into, so the traffic is a real browser
because it *is* a real browser.

The division of labour is deliberate and is what keeps this maintainable:

- the **backend** owns *what* to buy (SKUs, quantities, search terms);
- the **extension** owns *how* (selectors, waits, retries), in an adapter keyed
  on ``shop_slug``.

A retailer redesign therefore ships as an extension update, not a backend
deploy — which matters because the DOM is the part that breaks.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import quote

from app.services.shops.base import ShopProvider
from app.services.shops.models import (
    Capability,
    CartPlan,
    CartPlanEntry,
    Transport,
)


@dataclass(frozen=True)
class ExtensionShopConfig:
    origin: str
    """Scheme + host the extension operates on."""
    search_url_template: str
    """Must contain ``{query}``. Used both for the link fallback and by the
    extension adapter when an entry has no SKU."""
    cart_url: str | None = None
    requires_store: bool = False


class ExtensionProvider(ShopProvider):
    """A shop whose basket is filled by the browser extension.

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
        config: ExtensionShopConfig,
        country: str = "FR",
    ) -> None:
        super().__init__(
            slug=slug,
            display_name=display_name,
            country=country,
            website_url=config.origin,
        )
        self.config = config
        self.requires_store = config.requires_store

    def cart_link(
        self, entries: Sequence[CartPlanEntry], *, store_id: str | None = None
    ) -> str:
        """Where to send a user who does not have the extension installed."""
        if self.config.cart_url:
            return self.config.cart_url
        query = entries[0].query if entries else ""
        return self.config.search_url_template.format(query=quote(query))

    def cart_plan(
        self, entries: Sequence[CartPlanEntry], *, store_id: str | None = None
    ) -> CartPlan:
        return CartPlan(
            shop_slug=self.slug,
            origin=self.config.origin,
            store_id=store_id,
            entries=list(entries),
        )
