"""Shop integrations: cost a shopping list, or push it into a retailer's basket.

Structure mirrors ``recipe_import``: sibling modules by concern, with an
orchestrator tying them together.

- ``models.py``       — capabilities, transports, and the three per-item status
                        enums that let a partial answer stay honest
- ``errors.py``       — faults, as distinct from unsupported features
- ``matching.py``     — units and ingredient -> product resolution, shared by
                        every shop so twelve retailers cannot produce twelve
                        different answers for one list
- ``base.py``         — the provider contract
- ``registry.py``     — registration plus the import-time consistency check
- ``families/``       — reusable provider implementations, parameterised by
                        config (html_catalog, magento, extension, openprices)
- ``definitions.py``  — the actual shops, as configuration
- ``orchestrator.py`` — the use cases, and all the degradation logic

The load-bearing idea: **capabilities are declared data**. A provider says what
it can do; the orchestrator shapes the best available answer around what it
cannot. Nothing in the stack discovers a missing feature by catching an
exception, and the UI gates on the same declared set, so a shop that can search
but not price renders correctly without a single shop-specific branch.
"""

from app.services.shops.base import ShopProvider
from app.services.shops.definitions import register_default_shops
from app.services.shops.errors import (
    CapabilityNotSupportedError,
    ShopConfigurationError,
    ShopError,
    ShopNotFoundError,
    ShopUnavailableError,
)
from app.services.shops.models import (
    Capability,
    CartHandoff,
    CartPlan,
    CartPlanEntry,
    DegradationNote,
    ExportedList,
    ExportedListGroup,
    ExportedListItem,
    ListExportFormat,
    ListExportRequest,
    ListLine,
    MatchStatus,
    PackStatus,
    PricedList,
    PriceStatus,
    ResolvedItem,
    ShopListRequest,
    ShopProduct,
    ShopPublic,
    ShopSearchResults,
    ShopsPublic,
    ShopStore,
    ShopStores,
    Transport,
)
from app.services.shops.orchestrator import (
    build_cart_handoff,
    export_shopping_list,
    price_shopping_list,
)
from app.services.shops.registry import get_provider, iter_providers, register

register_default_shops()

__all__ = [
    "Capability",
    "CapabilityNotSupportedError",
    "CartHandoff",
    "CartPlan",
    "CartPlanEntry",
    "DegradationNote",
    "ExportedList",
    "ExportedListGroup",
    "ExportedListItem",
    "ListExportFormat",
    "ListExportRequest",
    "ListLine",
    "MatchStatus",
    "PackStatus",
    "PriceStatus",
    "PricedList",
    "ResolvedItem",
    "ShopConfigurationError",
    "ShopError",
    "ShopListRequest",
    "ShopNotFoundError",
    "ShopProduct",
    "ShopProvider",
    "ShopPublic",
    "ShopSearchResults",
    "ShopStore",
    "ShopStores",
    "ShopUnavailableError",
    "ShopsPublic",
    "Transport",
    "build_cart_handoff",
    "export_shopping_list",
    "get_provider",
    "iter_providers",
    "price_shopping_list",
    "register",
]
