"""Shop integrations: cost a shopping list, or push it into a retailer's basket.

Structure mirrors ``recipe_import``: sibling modules by concern, with an
orchestrator tying them together.

- ``models.py``       — capabilities, transports, and the three per-item status
                        enums that let a partial answer stay honest
- ``errors.py``       — faults, as distinct from unsupported features
- ``matching.py``     — units and ingredient -> product resolution, shared by
                        every store so twelve retailers cannot produce twelve
                        different answers for one list
- ``base.py``         — the provider contract
- ``registry.py``     — registration plus the import-time consistency check
- ``families/``       — reusable provider implementations, parameterised by
                        config (html_catalog, magento, extension, openprices)
- ``definitions.py``  — the actual stores, as configuration
- ``orchestrator.py`` — the use cases, and all the degradation logic

The load-bearing idea: **capabilities are declared data**. A provider says what
it can do; the orchestrator shapes the best available answer around what it
cannot. Nothing in the stack discovers a missing feature by catching an
exception, and the UI gates on the same declared set, so a store that can search
but not price renders correctly without a single store-specific branch.
"""

from app.services.store_providers.base import StoreProvider
from app.services.store_providers.definitions import register_default_providers
from app.services.store_providers.errors import (
    CapabilityNotSupportedError,
    ProviderConfigurationError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
)
from app.services.store_providers.models import (
    AisleLayout,
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
    ProviderPublic,
    ProviderSearchResults,
    ProvidersPublic,
    ResolvedItem,
    StoreListRequest,
    StoreLocation,
    StoreLocations,
    StoreProduct,
    Transport,
)
from app.services.store_providers.orchestrator import (
    build_cart_handoff,
    export_shopping_list,
    price_shopping_list,
)
from app.services.store_providers.registry import get_provider, iter_providers, register

register_default_providers()

__all__ = [
    "AisleLayout",
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
    "ProviderConfigurationError",
    "ProviderError",
    "StoreListRequest",
    "ProviderNotFoundError",
    "StoreProduct",
    "StoreProvider",
    "ProviderPublic",
    "ProviderSearchResults",
    "StoreLocation",
    "StoreLocations",
    "ProviderUnavailableError",
    "ProvidersPublic",
    "Transport",
    "build_cart_handoff",
    "export_shopping_list",
    "get_provider",
    "iter_providers",
    "price_shopping_list",
    "register",
]
