"""The default retailer list, and the idempotent seeding of it.

Stores are configuration rather than user content, so they ship with the app
and are reconciled on every startup through ``init_db``.

``price_index`` is a coarse position on the discount-to-premium axis, used only
where a store has no curated price of its own for an ingredient. It is a
starting point for the estimate, not a claim about any particular product:
real per-ingredient prices always win over it.
"""

from app.models.store import StoreCreate
from app.services.store_providers import iter_providers

#: (slug, display name, price index) for the French chains covered at launch.
DEFAULT_STORES: tuple[tuple[str, str, float], ...] = (
    ("aldi", "Aldi", 0.85),
    ("auchan", "Auchan", 1.00),
    ("carrefour", "Carrefour", 1.05),
    ("e-leclerc", "E.Leclerc", 0.95),
    ("franprix", "Franprix", 1.20),
    ("grand-frais", "Grand Frais", 1.10),
    ("intermarche", "Intermarché", 1.00),
    ("lidl", "Lidl", 0.85),
    ("monoprix", "Monoprix", 1.25),
    ("netto", "Netto", 0.85),
    ("picard", "Picard", 1.15),
    ("super-u", "Super U", 1.00),
)


def default_store_payloads() -> list[StoreCreate]:
    """The seeded stores, each linked to a provider when one exists for it.

    The link is by slug and nothing more: register a provider under ``lidl``
    and the Lidl row picks it up on the next startup, with no second list to
    keep in step. A store with no provider is not lesser — it just means its
    prices are curated by hand, which is how every one of these starts.
    """
    provider_slugs = {p.slug for p in iter_providers()}
    return [
        StoreCreate(
            slug=slug,
            name=name,
            country="FR",
            currency="EUR",
            price_index=idx,
            provider_slug=slug if slug in provider_slugs else None,
        )
        for slug, name, idx in DEFAULT_STORES
    ]
