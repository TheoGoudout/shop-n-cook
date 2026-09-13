/**
 * Formatting for the costs the backend computes.
 *
 * The backend returns money as a decimal *string* so no precision is lost in
 * transit, and returns `null` — never 0 — when something could not be priced.
 * Both facts have to survive into the UI: an unpriced item must never render
 * as "€0.00".
 */

/** A cost as it arrives from the API. */
export type Money = string | number | null | undefined

/** Used when a response omits its (server-defaulted) currency field. */
export const DEFAULT_CURRENCY = "EUR"

/**
 * Format a cost for display, or return null when there is nothing to show.
 *
 * Returning null rather than a placeholder lets each caller decide how an
 * unpriced value should read in its own context.
 */
export function formatMoney(
  value: Money,
  // Fields with a server-side default arrive as optional in the generated
  // client, so the currency has to tolerate being absent.
  currency: string | undefined,
  locale: string,
): string | null {
  if (value === null || value === undefined || value === "") return null
  const amount = typeof value === "string" ? Number.parseFloat(value) : value
  if (!Number.isFinite(amount)) return null

  const code = currency || DEFAULT_CURRENCY
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: code,
      // Guard against a currency code the runtime does not know.
    }).format(amount)
  } catch {
    return `${amount.toFixed(2)} ${code}`
  }
}

/** Parse a cost into a number for arithmetic, treating unpriced as 0. */
export function toAmount(value: Money): number {
  if (value === null || value === undefined || value === "") return 0
  const amount = typeof value === "string" ? Number.parseFloat(value) : value
  return Number.isFinite(amount) ? amount : 0
}

/** Whether a cost is actually present, as opposed to genuinely zero. */
export function isPriced(value: Money): boolean {
  return value !== null && value !== undefined && value !== ""
}
