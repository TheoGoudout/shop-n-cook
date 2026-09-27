"""How a printed list is ordered.

``market`` and ``printable`` used to be registered as stores, which was wrong:
nobody picks "Printable list" as the supermarket they shop at. They are two
orderings of the same list, so that is what they are here — and removing them
from the registry is part of collapsing store and shop into one idea.

The ordering matters because it is the order the place is actually walked. A
market is produce-and-meat first and the dry goods are an errand afterwards; a
supermarket is laid out fresh-to-shelves. Getting it wrong sends someone back
across the shop.
"""

from __future__ import annotations

from app.services.store_providers.families.list_only import (
    MARKET_AISLES,
    SUPERMARKET_AISLES,
    ListOnlyConfig,
    ListOnlyProvider,
)
from app.services.store_providers.models import AisleLayout

_LAYOUTS: dict[AisleLayout, ListOnlyProvider] = {
    AisleLayout.SUPERMARKET: ListOnlyProvider(
        slug=AisleLayout.SUPERMARKET.value,
        display_name="Supermarket order",
        config=ListOnlyConfig(aisle_order=SUPERMARKET_AISLES),
    ),
    AisleLayout.MARKET: ListOnlyProvider(
        slug=AisleLayout.MARKET.value,
        display_name="Market order",
        config=ListOnlyConfig(aisle_order=MARKET_AISLES),
    ),
}

#: What a list is ordered by when nobody has said otherwise — which is the
#: default state, because no store is selected until a user picks one.
DEFAULT_EXPORT_LAYOUT = _LAYOUTS[AisleLayout.SUPERMARKET]


def get_layout(layout: AisleLayout) -> ListOnlyProvider:
    return _LAYOUTS[layout]
