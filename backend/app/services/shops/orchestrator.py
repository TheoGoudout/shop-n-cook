"""Use-case layer: cost a list, or hand it off to a basket.

This is where "the shop cannot do that" stops being an error and becomes an
answer. The primitives in ``base.py`` are strict — call an undeclared
capability and they raise. The functions here are the opposite: they check
capabilities first and shape the best result the shop can actually produce,
annotating exactly what is missing and why.

The three degradations that matter, all exercised by shops we actually
surveyed:

- **no search** (Carrefour, behind Akamai) — the backend cannot look anything
  up, so cart entries carry the list's own wording for the extension to
  resolve on-site.
- **no prices** (Auchan, whose catalogue is priceless until a store is picked)
  — products resolve fine, every line reports ``REQUIRES_STORE``, and the
  total is ``None`` rather than a misleading zero.
- **shop down** — the first transport failure stops further calls, and the
  remaining lines are marked rather than each waiting out its own timeout.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.services.pricing import quantize_money
from app.services.shops.base import ShopProvider
from app.services.shops.errors import (
    CapabilityNotSupportedError,
    ShopUnavailableError,
)
from app.services.shops.matching import resolve_item
from app.services.shops.models import (
    Capability,
    CartHandoff,
    CartPlanEntry,
    DegradationNote,
    ExportedList,
    ListExportFormat,
    ListLine,
    MatchStatus,
    PricedList,
    PriceStatus,
    ResolvedItem,
    ShopProduct,
    Transport,
)

#: Candidates fetched per line. Enough for the ranker to have a real choice
#: without turning one list into a crawl.
SEARCH_LIMIT = 10

#: Statuses that mean we have a product good enough to put in a basket.
_USABLE_MATCHES = frozenset({MatchStatus.MATCHED, MatchStatus.LOW_CONFIDENCE})


def price_shopping_list(
    *,
    provider: ShopProvider,
    lines: Sequence[ListLine],
    store_id: str | None = None,
) -> PricedList:
    """Cost a list at one shop, degrading rather than failing."""
    result = PricedList(
        shop_slug=provider.slug,
        shop_name=provider.display_name,
        store_id=store_id,
    )

    if not provider.supports(Capability.SEARCH):
        result.items = [
            ResolvedItem(
                item_name=line.name,
                requested_quantity=line.quantity,
                requested_unit=line.unit,
                match_status=MatchStatus.SEARCH_UNSUPPORTED,
                price_status=provider.unpriced_reason,
            )
            for line in lines
        ]
        result.unpriced_item_count = len(lines)
        result.partial = True
        result.notes = [DegradationNote.SEARCH_UNSUPPORTED]
        return result

    result.items = _resolve_lines(
        provider=provider, lines=lines, store_id=store_id, result=result
    )

    if provider.supports(Capability.PRICES):
        _attach_missing_prices(
            provider=provider, items=result.items, store_id=store_id, result=result
        )

    _finalise(provider=provider, result=result, store_id=store_id)
    return result


def build_cart_handoff(
    *,
    provider: ShopProvider,
    lines: Sequence[ListLine],
    store_id: str | None = None,
) -> CartHandoff:
    """Turn a list into either a link or an extension plan.

    Both transports return the same type, so the frontend branches once in its
    render layer instead of everywhere.
    """
    if not provider.supports(Capability.CART_PUSH) and not provider.supports(
        Capability.CART_LINK
    ):
        raise CapabilityNotSupportedError(
            f"{provider.slug} offers no way to hand a list over"
        )

    entries, unresolved = _build_entries(
        provider=provider, lines=lines, store_id=store_id
    )

    if provider.supports(Capability.CART_PUSH):
        return CartHandoff(
            shop_slug=provider.slug,
            transport=provider.transport,
            plan=provider.cart_plan(entries, store_id=store_id),
            unresolved_item_names=unresolved,
        )

    return CartHandoff(
        shop_slug=provider.slug,
        transport=Transport.SERVER,
        url=provider.cart_link(entries, store_id=store_id),
        unresolved_item_names=unresolved,
    )


def export_shopping_list(
    *,
    provider: ShopProvider,
    lines: Sequence[ListLine],
    export_format: ListExportFormat = ListExportFormat.TEXT,
    category_labels: Mapping[str, str] | None = None,
) -> ExportedList:
    """Render a list to shop from by hand.

    Unlike the other use cases there is nothing here to degrade: no network, no
    catalogue, nothing to be unavailable. A provider that declares
    ``LIST_EXPORT`` can always deliver, which is precisely why it is the right
    fallback to offer for a shop we cannot integrate with at all.
    """
    if not provider.supports(Capability.LIST_EXPORT):
        raise CapabilityNotSupportedError(
            f"{provider.slug} cannot produce a standalone list"
        )
    return provider.export_list(
        lines, export_format=export_format, category_labels=category_labels
    )


# --------------------------------------------------------------------------- #
# Internals                                                                    #
# --------------------------------------------------------------------------- #


def _resolve_lines(
    *,
    provider: ShopProvider,
    lines: Sequence[ListLine],
    store_id: str | None,
    result: PricedList,
) -> list[ResolvedItem]:
    items: list[ResolvedItem] = []
    shop_down = False

    for line in lines:
        if shop_down:
            items.append(_unavailable_item(line, provider.unpriced_reason))
            continue

        try:
            candidates = provider.search(
                line.name, limit=SEARCH_LIMIT, store_id=store_id
            )
        except ShopUnavailableError:
            # One failure is enough to conclude the shop is unreachable; making
            # the remaining lines each wait out a timeout helps nobody.
            shop_down = True
            result.notes.append(DegradationNote.SHOP_UNAVAILABLE)
            items.append(_unavailable_item(line, provider.unpriced_reason))
            continue

        items.append(
            resolve_item(
                item_name=line.name,
                quantity=line.quantity,
                unit=line.unit,
                candidates=candidates,
                unpriced_reason=provider.unpriced_reason,
            )
        )
    return items


def _unavailable_item(line: ListLine, unpriced_reason: PriceStatus) -> ResolvedItem:
    return ResolvedItem(
        item_name=line.name,
        requested_quantity=line.quantity,
        requested_unit=line.unit,
        match_status=MatchStatus.SHOP_UNAVAILABLE,
        price_status=unpriced_reason,
    )


def _attach_missing_prices(
    *,
    provider: ShopProvider,
    items: Sequence[ResolvedItem],
    store_id: str | None,
    result: PricedList,
) -> None:
    """Price every still-unpriced product in one call, not one call per line."""
    pending: list[ShopProduct] = [
        item.product
        for item in items
        if item.product is not None and item.product.price is None
    ]
    if not pending:
        return

    try:
        priced = provider.attach_prices(pending, store_id=store_id)
    except ShopUnavailableError:
        if DegradationNote.SHOP_UNAVAILABLE not in result.notes:
            result.notes.append(DegradationNote.SHOP_UNAVAILABLE)
        return

    price_by_sku = {p.sku: p.price for p in priced if p.price is not None}
    for item in items:
        if item.product is None or item.product.price is not None:
            continue
        price = price_by_sku.get(item.product.sku)
        if price is None:
            continue
        item.product = item.product.model_copy(update={"price": price})
        item.price_status = PriceStatus.PRICED
        item.line_total = quantize_money(price * item.pack_count)


def _finalise(
    *, provider: ShopProvider, result: PricedList, store_id: str | None
) -> None:
    """Compute totals and say plainly how complete the answer is."""
    priced = [item for item in result.items if item.line_total is not None]
    result.priced_item_count = len(priced)
    result.unpriced_item_count = len(result.items) - len(priced)
    result.total = (
        quantize_money(
            sum((item.line_total or Decimal(0) for item in priced), Decimal(0))
        )
        if priced
        else None
    )

    if result.items and result.currency == "EUR":
        for item in result.items:
            if item.product is not None:
                result.currency = item.product.currency
                break

    unmatched = [
        item for item in result.items if item.match_status not in _USABLE_MATCHES
    ]
    if unmatched and DegradationNote.SOME_ITEMS_UNMATCHED not in result.notes:
        result.notes.append(DegradationNote.SOME_ITEMS_UNMATCHED)

    # Same ordering as ``ShopProvider.unpriced_reason``: tell the user the
    # thing they can act on before the thing they cannot.
    if provider.requires_store and store_id is None:
        result.notes.append(DegradationNote.PRICES_REQUIRE_STORE)
    elif not provider.supports(Capability.PRICES):
        result.notes.append(DegradationNote.PRICES_UNSUPPORTED)

    result.partial = bool(unmatched) or result.unpriced_item_count > 0


def _build_entries(
    *,
    provider: ShopProvider,
    lines: Sequence[ListLine],
    store_id: str | None,
) -> tuple[list[CartPlanEntry], list[str]]:
    """Plan entries, using the catalogue when there is one and the list's own
    wording when there is not."""
    if not provider.supports(Capability.SEARCH):
        # Nothing to resolve against: hand the extension the words and let it
        # search on-site, where it has a session and we do not.
        return [
            CartPlanEntry(
                query=line.name,
                name=line.name,
                quantity=1,
                requested_quantity=line.quantity,
                requested_unit=line.unit,
            )
            for line in lines
        ], []

    priced = price_shopping_list(provider=provider, lines=lines, store_id=store_id)
    entries: list[CartPlanEntry] = []
    unresolved: list[str] = []
    for item in priced.items:
        if item.product is None or item.match_status not in _USABLE_MATCHES:
            unresolved.append(item.item_name)
            continue
        entries.append(
            CartPlanEntry(
                sku=item.product.sku,
                query=item.item_name,
                name=item.product.name,
                quantity=item.pack_count,
                product_url=item.product.url,
                requested_quantity=item.requested_quantity,
                requested_unit=item.requested_unit,
            )
        )
    return entries, unresolved
