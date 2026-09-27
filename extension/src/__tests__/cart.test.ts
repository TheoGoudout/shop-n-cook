import { beforeEach, describe, expect, it, vi } from "vitest"
import { getAdapter, supportedSlugs } from "../cart/adapters"
import { executeCartPlan } from "../cart/runner"
import { type CartPlan, isExecuteCartPlanMessage } from "../shops"

const CARREFOUR_ORIGIN = "https://www.carrefour.fr"

function makePlan(overrides: Partial<CartPlan> = {}): CartPlan {
  return {
    shop_slug: "carrefour",
    origin: CARREFOUR_ORIGIN,
    store_id: null,
    entries: [
      {
        sku: null,
        query: "tomates cerises",
        name: "tomates cerises",
        quantity: 2,
        product_url: null,
        requested_quantity: 500,
        requested_unit: "g",
      },
    ],
    ...overrides,
  }
}

let executeScript: ReturnType<typeof vi.fn>
let tabsCreate: ReturnType<typeof vi.fn>
let tabsUpdate: ReturnType<typeof vi.fn>

function pageResult(outcome: string, added: number, detail?: string) {
  return [{ result: { outcome, added, detail } }]
}

beforeEach(() => {
  executeScript = vi.fn().mockResolvedValue(pageResult("added", 2))
  tabsCreate = vi.fn().mockResolvedValue({ id: 42 })
  tabsUpdate = vi.fn().mockResolvedValue({ id: 42 })

  global.chrome.tabs = {
    create: tabsCreate,
    update: tabsUpdate,
    onUpdated: {
      // Resolve the load wait immediately; the runner clears its own timeout.
      addListener: vi.fn(
        (cb: (id: number, info: { status: string }) => void) => {
          queueMicrotask(() => cb(42, { status: "complete" }))
        },
      ),
      removeListener: vi.fn(),
    },
  } as unknown as typeof chrome.tabs

  global.chrome.scripting = {
    executeScript,
  } as unknown as typeof chrome.scripting
})

describe("adapters", () => {
  it("resolves a registered retailer", () => {
    const adapter = getAdapter("carrefour")
    expect(adapter?.origin).toBe(CARREFOUR_ORIGIN)
    expect(adapter?.searchUrl("crème fraîche")).toContain(
      encodeURIComponent("crème fraîche"),
    )
  })

  it("returns null for a retailer this build cannot drive", () => {
    expect(getAdapter("intermarche")).toBeNull()
  })

  it("reports what it supports so the app can gate its UI", () => {
    expect(supportedSlugs()).toContain("carrefour")
  })
})

describe("executeCartPlan", () => {
  it("adds every entry and reports completion", async () => {
    const result = await executeCartPlan(makePlan())

    expect(result.outcome).toBe("completed")
    expect(result.entries).toHaveLength(1)
    expect(result.entries[0]).toMatchObject({
      outcome: "added",
      added: 2,
      requested: 2,
    })
    expect(executeScript).toHaveBeenCalledTimes(1)
  })

  it("passes the retailer's selectors and quantity into the page", async () => {
    await executeCartPlan(makePlan())

    const call = executeScript.mock.calls[0][0]
    const adapter = getAdapter("carrefour")
    expect(call.target).toEqual({ tabId: 42 })
    expect(call.args[0]).toBe(adapter?.selectors.resultItem)
    expect(call.args[1]).toBe(adapter?.selectors.addToCart)
    expect(call.args[4]).toBe(2)
  })

  it("navigates to the on-site search for an entry with no SKU", async () => {
    await executeCartPlan(makePlan())
    const navigations = tabsUpdate.mock.calls
      .map((c) => c[1]?.url)
      .filter(Boolean)
    expect(navigations[0]).toContain("/s?q=")
  })

  it("goes straight to a product URL when the backend resolved one", async () => {
    const plan = makePlan()
    plan.entries[0].product_url = "/p/lait-demi-ecreme"
    await executeCartPlan(plan)
    const navigations = tabsUpdate.mock.calls
      .map((c) => c[1]?.url)
      .filter(Boolean)
    expect(navigations[0]).toBe(`${CARREFOUR_ORIGIN}/p/lait-demi-ecreme`)
  })

  it("refuses a shop it has no adapter for", async () => {
    const result = await executeCartPlan(
      makePlan({
        shop_slug: "intermarche",
        origin: "https://www.intermarche.com",
      }),
    )
    expect(result.outcome).toBe("unsupported_shop")
    expect(tabsCreate).not.toHaveBeenCalled()
  })

  it("refuses a plan pointing at an origin the adapter does not own", async () => {
    const result = await executeCartPlan(
      makePlan({ origin: "https://evil.test" }),
    )
    expect(result.outcome).toBe("wrong_origin")
    expect(tabsCreate).not.toHaveBeenCalled()
  })

  it("does nothing for an empty plan", async () => {
    const result = await executeCartPlan(makePlan({ entries: [] }))
    expect(result.outcome).toBe("completed")
    expect(tabsCreate).not.toHaveBeenCalled()
  })

  it("keeps going when one line cannot be found", async () => {
    const plan = makePlan()
    plan.entries.push({
      sku: null,
      query: "zeste de yuzu",
      name: "zeste de yuzu",
      quantity: 1,
      product_url: null,
      requested_quantity: 1,
      requested_unit: "piece",
    })
    executeScript
      .mockResolvedValueOnce(pageResult("added", 2))
      .mockResolvedValueOnce(pageResult("not_found", 0))

    const result = await executeCartPlan(plan)

    expect(result.outcome).toBe("partial")
    expect(result.entries.map((e) => e.outcome)).toEqual(["added", "not_found"])
  })

  it("survives an injection failure on one line", async () => {
    const plan = makePlan()
    plan.entries.push({ ...plan.entries[0], query: "lait" })
    executeScript
      .mockRejectedValueOnce(new Error("frame removed"))
      .mockResolvedValueOnce(pageResult("added", 2))

    const result = await executeCartPlan(plan)

    expect(result.outcome).toBe("partial")
    expect(result.entries[0].outcome).toBe("failed")
    expect(result.entries[0].detail).toContain("frame removed")
    expect(result.entries[1].outcome).toBe("added")
  })

  it("reports a failure when no tab can be opened", async () => {
    tabsCreate.mockResolvedValue({ id: undefined })
    const result = await executeCartPlan(makePlan())
    expect(result.outcome).toBe("failed")
  })

  it("brings the basket to the front once it is done", async () => {
    await executeCartPlan(makePlan())
    expect(tabsUpdate).toHaveBeenLastCalledWith(42, { active: true })
  })
})

describe("isExecuteCartPlanMessage", () => {
  it("accepts a well-formed plan message", () => {
    expect(
      isExecuteCartPlanMessage({ type: "EXECUTE_CART_PLAN", plan: makePlan() }),
    ).toBe(true)
  })

  it.each([
    null,
    undefined,
    "EXECUTE_CART_PLAN",
    { type: "SOMETHING_ELSE", plan: makePlan() },
    { type: "EXECUTE_CART_PLAN" },
    { type: "EXECUTE_CART_PLAN", plan: { shop_slug: "x" } },
    { type: "EXECUTE_CART_PLAN", plan: { shop_slug: "x", origin: "y" } },
  ])("rejects malformed input %#", (input) => {
    expect(isExecuteCartPlanMessage(input)).toBe(false)
  })
})
