"""Shop integration endpoints.

Everything here is capability-driven: ``GET /shops/`` tells the client exactly
what each shop can do, and the client renders from that rather than from a
hardcoded list of chains. Adding a shop therefore changes no frontend code.

Note the deliberate asymmetry in error handling. ``/search`` is a thin
pass-through, so an unreachable shop is a 502. ``/price-list`` is a use case,
so an unreachable shop is a *degraded 200* — the user still sees their list,
annotated with what could not be determined.
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.api.routes.shopping_lists import _check_list_access
from app.services.shops import (
    Capability,
    CartHandoff,
    ExportedList,
    ListExportRequest,
    ListLine,
    PricedList,
    ShopListRequest,
    ShopProvider,
    ShopSearchResults,
    ShopsPublic,
    build_cart_handoff,
    export_shopping_list,
    get_provider,
    iter_providers,
    price_shopping_list,
)
from app.services.shops.errors import (
    CapabilityNotSupportedError,
    ShopNotFoundError,
    ShopUnavailableError,
)

router = APIRouter(prefix="/shops", tags=["shops"])


def _provider_or_404(slug: str) -> ShopProvider:
    try:
        return get_provider(slug)
    except ShopNotFoundError:
        raise HTTPException(status_code=404, detail="Unknown shop") from None


def _require(provider: ShopProvider, capability: Capability) -> None:
    if not provider.supports(capability):
        raise HTTPException(
            status_code=409,
            detail=f"{provider.display_name} does not support {capability.value}",
        )


def _lines_for_list(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    shopping_list_id: uuid.UUID,
) -> list[ListLine]:
    shopping_list = crud.get_shopping_list(
        session=session, shopping_list_id=shopping_list_id
    )
    # `session` is what lets the household rule apply; without it a member of
    # the owner's household is refused a list they can open everywhere else.
    shopping_list = _check_list_access(
        shopping_list, current_user, shopping_list_id, session
    )
    # Checked-off items are already in the basket or the cupboard.
    items = [item for item in shopping_list.items if not item.is_checked]

    # Aisle comes from the ingredient catalogue. Looked up here rather than in
    # the service so the shop layer keeps no database dependency, and resolved
    # in one query instead of one per line.
    categories = crud.get_ingredient_categories_by_name(
        session=session, names=[item.name for item in items]
    )
    return [
        ListLine(
            name=item.name,
            quantity=item.quantity,
            unit=item.unit,
            category=categories.get(item.name.strip().lower()),
            note=item.notes,
        )
        for item in items
    ]


@router.get("/", response_model=ShopsPublic)
def read_shops(
    _current_user: CurrentUser,
    country: str | None = Query(default=None, max_length=2),
) -> Any:
    """List the available shops and what each one can actually do."""
    providers = iter_providers(country=country)
    return ShopsPublic(
        data=[provider.to_public() for provider in providers], count=len(providers)
    )


@router.get("/{slug}/search", response_model=ShopSearchResults)
def search_shop(
    _current_user: CurrentUser,
    slug: str,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
    store_id: str | None = None,
) -> Any:
    """Search one shop's catalogue for a free-text ingredient name."""
    provider = _provider_or_404(slug)
    _require(provider, Capability.SEARCH)
    try:
        products = provider.search(q, limit=limit, store_id=store_id)
    except ShopUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ShopSearchResults(
        shop_slug=provider.slug, query=q, products=products, count=len(products)
    )


@router.post("/{slug}/price-list", response_model=PricedList)
def price_list_at_shop(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    slug: str,
    request: ShopListRequest,
) -> Any:
    """Cost a shopping list at one shop.

    Always 200 for a shop that exists. A shop that cannot search, cannot price,
    or is unreachable returns a partial ``PricedList`` whose ``notes`` and
    per-item statuses say precisely what is missing.
    """
    provider = _provider_or_404(slug)
    lines = _lines_for_list(
        session=session,
        current_user=current_user,
        shopping_list_id=request.shopping_list_id,
    )
    return price_shopping_list(
        provider=provider, lines=lines, store_id=request.store_id
    )


@router.post("/{slug}/cart", response_model=CartHandoff)
def build_cart(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    slug: str,
    request: ShopListRequest,
) -> Any:
    """Hand a shopping list over to the shop.

    Returns either a URL (server transport) or a ``CartPlan`` for the browser
    extension to execute (extension transport). The client branches on
    ``transport``.
    """
    provider = _provider_or_404(slug)
    lines = _lines_for_list(
        session=session,
        current_user=current_user,
        shopping_list_id=request.shopping_list_id,
    )
    try:
        return build_cart_handoff(
            provider=provider, lines=lines, store_id=request.store_id
        )
    except CapabilityNotSupportedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ShopUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{slug}/export", response_model=ExportedList)
def export_list_for_shop(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    slug: str,
    request: ListExportRequest,
) -> Any:
    """Render a shopping list to carry, for a shop with nothing to integrate.

    Merges duplicate lines, scales quantities for reading, and groups by aisle
    in the order that shop is actually walked. Returns both the structured
    groups (for the app to render with its own translations) and a rendered
    string (to copy, print or send to whoever is going).
    """
    provider = _provider_or_404(slug)
    _require(provider, Capability.LIST_EXPORT)
    lines = _lines_for_list(
        session=session,
        current_user=current_user,
        shopping_list_id=request.shopping_list_id,
    )
    return export_shopping_list(
        provider=provider,
        lines=lines,
        export_format=request.format,
        category_labels=request.category_labels,
    )
