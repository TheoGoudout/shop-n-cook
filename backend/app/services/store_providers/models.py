"""Schemas shared by every store provider.

The rule that makes this package extensible: a provider never signals a missing
feature by failing a whole use case. It declares what it supports up front
(``Capability``), and every aggregate result carries an explicit per-item
status, so a store that cannot search, cannot price, or is simply down still
produces a usable, partial answer the UI can render honestly.

Three status enums encode the three ways a store can fall short:

- ``MatchStatus``  — could we map the ingredient onto a product at all?
- ``PriceStatus``  — could we attach a price to that product?
- ``PackStatus``   — could we work out how many packs to buy?

None of them is an error. They are the answer.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from app.models.ingredient import IngredientCategory, Unit

# --------------------------------------------------------------------------- #
# Capability / transport declarations                                          #
# --------------------------------------------------------------------------- #


class Capability(str, Enum):
    """A discrete thing a store can do. Providers declare a subset."""

    SEARCH = "search"
    """Map a free-text ingredient name onto candidate products."""

    PRICES = "prices"
    """Attach a price to a product. Independent of SEARCH: Auchan can search
    but not price (its catalogue is priceless without a store session), and a
    price database can price a barcode it cannot search by recipe wording."""

    STORE_LOCATOR = "store_locator"
    """Resolve a postcode to concrete branches / drives."""

    CART_LINK = "cart_link"
    """Produce a URL that lands the user on a pre-filled basket or search."""

    CART_PUSH = "cart_push"
    """Write items into the user's real basket. Extension transport only."""

    LIST_EXPORT = "list_export"
    """Produce a tidy, human-readable list to shop from by hand.

    The capability for stores with no digital presence at all — a farmers'
    market, a village grocer, a butcher. Nothing is contacted; the list itself
    is the deliverable, merged and grouped by aisle so it can be read off a
    phone at a stall."""


class Transport(str, Enum):
    """Who talks to the retailer."""

    SERVER = "server"
    """The backend calls the retailer directly."""

    EXTENSION = "extension"
    """The backend emits a declarative plan; the browser extension executes it
    inside the user's own authenticated session. The only workable transport
    for retailers behind Akamai / DataDome."""

    OFFLINE = "offline"
    """Nobody is contacted. The user is the transport: they take the list and
    go. Modelling this as a transport rather than a special case is what lets
    a farmers' market sit in the same picker as Carrefour."""


# --------------------------------------------------------------------------- #
# Per-item outcome statuses                                                    #
# --------------------------------------------------------------------------- #


class MatchStatus(str, Enum):
    MATCHED = "matched"
    LOW_CONFIDENCE = "low_confidence"
    NO_CANDIDATES = "no_candidates"
    SEARCH_UNSUPPORTED = "search_unsupported"
    STORE_UNAVAILABLE = "store_unavailable"


class PriceStatus(str, Enum):
    PRICED = "priced"
    NOT_SUPPORTED = "not_supported"
    """The store has no price capability at all."""

    REQUIRES_BRANCH = "requires_branch"
    """The store prices per branch and no branch was selected."""

    UNKNOWN = "unknown"
    """Priceable in principle, but this product had no price on record."""


class PackStatus(str, Enum):
    EXACT = "exact"
    ROUNDED_UP = "rounded_up"
    ASSUMED_SINGLE = "assumed_single"
    """Recipe unit and pack unit are not inter-convertible, so we buy one and
    say so rather than guessing. Covers mass against volume (no density on the
    ingredient) and any two different discrete units — a bunch is not a piece.
    ``app.core.units.convert`` decides; this is what it returning ``None``
    means for a basket."""

    UNKNOWN_PACK_SIZE = "unknown_pack_size"
    """The store did not tell us the net content of the pack."""


class DegradationNote(str, Enum):
    """Stable machine codes explaining why a result is partial.

    Codes rather than sentences: the frontend translates them through the i18n
    layer, so the backend never ships user-facing prose.
    """

    SEARCH_UNSUPPORTED = "search_unsupported"
    PRICES_UNSUPPORTED = "prices_unsupported"
    PRICES_REQUIRE_BRANCH = "prices_require_branch"
    STORE_UNAVAILABLE = "store_unavailable"
    SOME_ITEMS_UNMATCHED = "some_items_unmatched"


# --------------------------------------------------------------------------- #
# Core value objects                                                           #
# --------------------------------------------------------------------------- #


class ListLine(BaseModel):
    """One line of a shopping list, as the store layer sees it.

    Deliberately not ``ShoppingListItem``: the service must stay usable for a
    recipe preview or an ad-hoc list, so it never depends on a DB row.
    """

    name: str
    quantity: float
    unit: Unit
    category: IngredientCategory | None = None
    """Aisle, when the ingredient catalogue knows it. Populated by the route
    layer so this module stays free of database access."""
    note: str | None = None


class StoreProduct(BaseModel):
    """One purchasable product at one store.

    ``price`` is deliberately optional: a provider with SEARCH but not PRICES
    returns fully-formed products with no price rather than nothing at all.
    """

    sku: str
    name: str
    brand: str | None = None
    url: str | None = None
    image_url: str | None = None
    price: Decimal | None = None
    """Decimal, never float — a price is exact money, not a measurement.
    Serialises as a JSON string, which `frontend/src/lib/money.ts` expects."""
    currency: str = "EUR"
    pack_quantity: float | None = None
    """Net content of one pack, in ``pack_unit``."""
    pack_unit: Unit | None = None
    in_stock: bool | None = None
    barcode: str | None = None


class StoreLocation(BaseModel):
    branch_id: str
    name: str
    postcode: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ResolvedItem(BaseModel):
    """One shopping-list line, resolved against one store.

    Every field that can be absent has a status explaining *why*, so the caller
    never has to guess whether ``price is None`` means "free", "unknown" or
    "this store does not do prices".
    """

    item_name: str
    requested_quantity: float
    requested_unit: Unit

    product: StoreProduct | None = None
    match_status: MatchStatus = MatchStatus.NO_CANDIDATES
    match_score: float = 0.0

    pack_count: int = 1
    pack_status: PackStatus = PackStatus.ASSUMED_SINGLE

    line_total: Decimal | None = None
    price_status: PriceStatus = PriceStatus.UNKNOWN

    alternatives: list[StoreProduct] = Field(default_factory=list)


class PricedList(BaseModel):
    """The aggregate answer for "cost this list at this store"."""

    store_slug: str
    store_name: str
    branch_id: str | None = None
    currency: str = "EUR"

    items: list[ResolvedItem] = Field(default_factory=list)

    total: Decimal | None = None
    """Sum of the priced lines only. ``None`` when nothing could be priced —
    never ``0``, which would read as free."""
    priced_item_count: int = 0
    unpriced_item_count: int = 0
    partial: bool = False
    """True when at least one line is missing a product or a price. The UI
    should say so rather than presenting the total as complete."""
    notes: list[DegradationNote] = Field(default_factory=list)
    """Why this result is partial, as stable codes for the frontend to translate."""


# --------------------------------------------------------------------------- #
# Cart handoff                                                                 #
# --------------------------------------------------------------------------- #


class CartPlanEntry(BaseModel):
    """One line of work for the extension to perform on the retailer's site."""

    sku: str | None = None
    query: str
    """Search term the extension uses when there is no SKU to add directly.
    For an extension-transport store this is the only handle we have, because
    the backend cannot search those retailers at all."""
    name: str
    quantity: int = Field(ge=1)
    """Number of packs to add."""
    product_url: str | None = None
    requested_quantity: float | None = None
    requested_unit: Unit | None = None
    """The original recipe amount, passed through so an on-site adapter can
    work out pack counts from a pack size only the live page knows."""


class CartPlan(BaseModel):
    """A declarative, retailer-agnostic script the extension executes.

    The extension owns *how* (selectors, waits, retries) via its own adapter
    keyed on ``store_slug``; the backend owns *what*. Keeping the selectors out
    of the backend means a retailer redesign ships as an extension update, not
    a backend deploy.
    """

    store_slug: str
    origin: str
    """Scheme + host the extension must operate on, e.g. https://www.carrefour.fr"""
    branch_id: str | None = None
    entries: list[CartPlanEntry] = Field(default_factory=list)


class CartHandoff(BaseModel):
    """How the user gets from our list into the store's basket.

    Exactly one of ``url`` / ``plan`` is set, selected by ``transport``. Both
    transports share this one return type so the frontend branches once, in the
    render layer, instead of everywhere.
    """

    store_slug: str
    transport: Transport
    url: str | None = None
    plan: CartPlan | None = None
    unresolved_item_names: list[str] = Field(default_factory=list)
    """Lines that could not be matched to a product and are therefore absent
    from the handoff. The user still has to buy these."""


# --------------------------------------------------------------------------- #
# API-facing store descriptors                                                  #
# --------------------------------------------------------------------------- #


class ProviderPublic(BaseModel):
    slug: str
    display_name: str
    country: str
    transport: Transport
    capabilities: list[Capability]
    requires_branch: bool = False
    """True when prices/cart are meaningless until a store is chosen."""
    requires_extension: bool = False
    website_url: str | None = None
    attribution: str | None = None
    """Licence / credit line a provider must display, e.g. Open Prices' ODbL."""


class ProvidersPublic(BaseModel):
    data: list[ProviderPublic]
    count: int


class AisleLayout(str, Enum):
    """Which walking order to print a list in.

    Not a store: nobody shops at "Printable list". See ``layouts.py``.
    """

    SUPERMARKET = "supermarket"
    MARKET = "market"


class ListExportFormat(str, Enum):
    """How an exported list renders its output."""

    TEXT = "text"
    MARKDOWN = "markdown"
    CSV = "csv"


class ExportedListItem(BaseModel):
    name: str
    quantity: float
    unit: Unit
    note: str | None = None
    """Already scaled for reading: 1500 g comes back as 1.5 kg."""
    merged_from: int = 1
    """How many list lines collapsed into this one. >1 means two recipes both
    wanted this ingredient and the amounts were added together."""


class ExportedListGroup(BaseModel):
    category: IngredientCategory
    items: list[ExportedListItem] = Field(default_factory=list)


class ExportedList(BaseModel):
    """A list to shop from by hand.

    Carries both a structured form (``groups``, for the app to render natively)
    and a rendered one (``content``, to copy, print or send to someone else).
    Producing both avoids the frontend having to reimplement the aisle ordering
    just to show the same thing twice.
    """

    store_slug: str
    store_name: str
    format: ListExportFormat
    groups: list[ExportedListGroup] = Field(default_factory=list)
    content: str = ""
    item_count: int = 0
    merged_line_count: int = 0
    """Lines that were combined, e.g. two recipes each needing onions."""


class ListExportRequest(BaseModel):
    format: ListExportFormat = ListExportFormat.TEXT
    layout: AisleLayout = AisleLayout.SUPERMARKET
    category_labels: dict[str, str] | None = None
    """Optional aisle headings for the rendered ``content``, keyed by
    ``IngredientCategory`` value. The backend ships no user-facing prose, so a
    client that wants a French heading passes one; ``groups`` is always
    available for the client to render with its own i18n instead."""


class StoreListRequest(BaseModel):
    """Ask a store to take delivery of one of the user's lists."""

    shopping_list_id: uuid.UUID
    branch_id: str | None = None
    """The retailer's own branch or drive, when it has several and prices or
    stock differ between them. Not our ``Store`` id — that is the path."""


class ProviderSearchResults(BaseModel):
    store_slug: str
    query: str
    products: list[StoreProduct] = Field(default_factory=list)
    count: int = 0


class StoreLocations(BaseModel):
    store_slug: str
    data: list[StoreLocation] = Field(default_factory=list)
    count: int = 0
