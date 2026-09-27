/**
 * Types mirroring the backend's shop handoff contract.
 *
 * Kept hand-written rather than generated because the extension consumes only
 * this slice of the API; the generated client in `src/client/` stays reserved
 * for the recipe-import surface it already covers.
 */

export interface CartPlanEntry {
  sku: string | null
  /** What to search for on-site when there is no SKU to add directly. */
  query: string
  name: string
  /** Number of packs to add. */
  quantity: number
  product_url: string | null
  requested_quantity: number | null
  requested_unit: string | null
}

export interface CartPlan {
  shop_slug: string
  /** Scheme + host the plan must be executed against. */
  origin: string
  store_id: string | null
  entries: CartPlanEntry[]
}

/**
 * Per-entry outcome, mirroring the backend's philosophy: a line that could not
 * be added reports why, rather than failing the whole run.
 */
export type EntryOutcome = "added" | "not_found" | "failed" | "skipped"

export interface EntryResult {
  query: string
  outcome: EntryOutcome
  /** How many packs actually went in, which may be fewer than requested. */
  added: number
  requested: number
  detail?: string
}

export type PlanOutcome =
  | "completed"
  | "partial"
  | "unsupported_shop"
  | "wrong_origin"
  | "failed"

export interface PlanResult {
  shop_slug: string
  outcome: PlanOutcome
  entries: EntryResult[]
  detail?: string
}

/** Message the web app sends to the extension to execute a plan. */
export interface ExecuteCartPlanMessage {
  type: "EXECUTE_CART_PLAN"
  plan: CartPlan
}

/** Message the web app sends to discover what the extension can drive. */
export interface CartCapabilitiesMessage {
  type: "CART_CAPABILITIES"
}

export type ExtensionMessage = ExecuteCartPlanMessage | CartCapabilitiesMessage

export function isExecuteCartPlanMessage(
  message: unknown,
): message is ExecuteCartPlanMessage {
  if (typeof message !== "object" || message === null) return false
  const candidate = message as Partial<ExecuteCartPlanMessage>
  if (candidate.type !== "EXECUTE_CART_PLAN") return false
  const plan = candidate.plan
  return (
    typeof plan === "object" &&
    plan !== null &&
    typeof plan.shop_slug === "string" &&
    typeof plan.origin === "string" &&
    Array.isArray(plan.entries)
  )
}
