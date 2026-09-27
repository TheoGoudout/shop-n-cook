/**
 * Per-retailer DOM adapters.
 *
 * The backend decides *what* to buy; this file is the only place that knows
 * *how* a given retailer's page works. That split is deliberate: selectors are
 * the part that breaks when a shop redesigns, and keeping them here means the
 * fix ships as an extension update rather than a backend deploy.
 *
 * Adding a retailer is one entry in `ADAPTERS`. Nothing else in the extension
 * changes — the runner is entirely generic.
 *
 * ---------------------------------------------------------------------------
 * SELECTORS ARE UNVERIFIED.
 *
 * These retailers answer server-side requests with an anti-bot 403 (Akamai for
 * Carrefour, DataDome for Intermarché and Leclerc), which is the whole reason
 * this transport exists — and it also means the selectors below could not be
 * confirmed against the live markup during development. Treat them as the
 * shape of the answer, not the answer. Each must be checked in a real browser
 * before the feature is enabled for users; `resultTimeoutMs` and the selector
 * strings are the only things that should need changing.
 * ---------------------------------------------------------------------------
 */

export interface ShopCartAdapter {
  slug: string
  /** Scheme + host. Must match the plan's origin or the run is refused. */
  origin: string
  /** Builds the on-site search URL for an entry's query. */
  searchUrl: (query: string) => string
  selectors: {
    /** A single product tile in a search result list. */
    resultItem: string
    /** The add-to-cart control, looked up within a result tile. */
    addToCart: string
    /** Optional consent banner to dismiss before interacting. */
    cookieAccept?: string
    /** Optional element proving the page finished loading results. */
    resultsReady?: string
  }
  /** How long to wait for search results before giving up on an entry. */
  resultTimeoutMs: number
}

const ADAPTER_LIST: ShopCartAdapter[] = [
  {
    slug: "carrefour",
    origin: "https://www.carrefour.fr",
    searchUrl: (query) =>
      `https://www.carrefour.fr/s?q=${encodeURIComponent(query)}`,
    selectors: {
      resultItem: "[data-testid='product-card'], .product-grid-item",
      addToCart: "[data-testid='add-to-cart'], button.add-to-cart",
      cookieAccept: "#onetrust-accept-btn-handler",
      resultsReady: "[data-testid='product-list'], .product-grid",
    },
    resultTimeoutMs: 10_000,
  },
]

const ADAPTERS = new Map(ADAPTER_LIST.map((adapter) => [adapter.slug, adapter]))

export function getAdapter(slug: string): ShopCartAdapter | null {
  return ADAPTERS.get(slug) ?? null
}

/** Slugs this build can drive. The web app gates its UI on this. */
export function supportedSlugs(): string[] {
  return [...ADAPTERS.keys()].sort()
}
