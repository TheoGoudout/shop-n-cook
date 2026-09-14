/**
 * Executes a backend `CartPlan` inside the user's own browser session.
 *
 * This is the whole point of the extension transport: Carrefour, Intermarché
 * and Leclerc answer any server-side request with an anti-bot 403, but they
 * answer a real browser normally — because this *is* a real browser, signed in
 * as the user, with their store already chosen.
 *
 * The runner is completely generic. Everything retailer-specific lives in
 * `adapters.ts`, so supporting another chain adds no code here.
 *
 * Failure handling mirrors the backend: one entry that cannot be added reports
 * its own outcome and the run continues. A shopping list is useful at 9 lines
 * out of 10; it is useless if line 3 aborts the whole thing.
 */

import type { CartPlan, EntryResult, PlanResult } from "../shops"
import { getAdapter, type ShopCartAdapter } from "./adapters"

/** Runs in the page, so it must be fully self-contained — no imports, no closure. */
async function addToCartInPage(
  resultItemSelector: string,
  addToCartSelector: string,
  cookieAcceptSelector: string,
  resultsReadySelector: string,
  quantity: number,
  timeoutMs: number,
): Promise<{ outcome: string; added: number; detail?: string }> {
  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

  const waitFor = async (selector: string, budget: number) => {
    const deadline = Date.now() + budget
    while (Date.now() < deadline) {
      const found = document.querySelector(selector)
      if (found) return found as HTMLElement
      await sleep(150)
    }
    return null
  }

  try {
    if (cookieAcceptSelector) {
      const consent = document.querySelector(cookieAcceptSelector)
      if (consent instanceof HTMLElement) {
        consent.click()
        await sleep(300)
      }
    }

    if (resultsReadySelector) {
      await waitFor(resultsReadySelector, timeoutMs)
    }

    const tile = await waitFor(resultItemSelector, timeoutMs)
    if (!tile) return { outcome: "not_found", added: 0 }

    const button = tile.querySelector(addToCartSelector)
    if (!(button instanceof HTMLElement)) {
      return {
        outcome: "not_found",
        added: 0,
        detail: "no add-to-cart control",
      }
    }

    let added = 0
    for (let i = 0; i < quantity; i++) {
      button.click()
      added += 1
      // Retailers debounce cart writes; clicking faster drops quantities.
      await sleep(600)
    }
    return { outcome: "added", added }
  } catch (error) {
    return {
      outcome: "failed",
      added: 0,
      detail: error instanceof Error ? error.message : String(error),
    }
  }
}

function waitForTabLoad(tabId: number, timeoutMs: number): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(finish, timeoutMs)
    function listener(updatedId: number, info: chrome.tabs.TabChangeInfo) {
      if (updatedId === tabId && info.status === "complete") finish()
    }
    function finish() {
      clearTimeout(timer)
      chrome.tabs.onUpdated.removeListener(listener)
      resolve()
    }
    chrome.tabs.onUpdated.addListener(listener)
  })
}

async function runEntry(
  tabId: number,
  adapter: ShopCartAdapter,
  entry: CartPlan["entries"][number],
): Promise<EntryResult> {
  const base: EntryResult = {
    query: entry.query,
    outcome: "failed",
    added: 0,
    requested: entry.quantity,
  }

  try {
    const url = entry.product_url
      ? new URL(entry.product_url, adapter.origin).toString()
      : adapter.searchUrl(entry.query)
    await chrome.tabs.update(tabId, { url })
    await waitForTabLoad(tabId, adapter.resultTimeoutMs)

    const [injection] = await chrome.scripting.executeScript({
      target: { tabId },
      func: addToCartInPage,
      args: [
        adapter.selectors.resultItem,
        adapter.selectors.addToCart,
        adapter.selectors.cookieAccept ?? "",
        adapter.selectors.resultsReady ?? "",
        entry.quantity,
        adapter.resultTimeoutMs,
      ],
    })

    const result = injection?.result as
      | { outcome: string; added: number; detail?: string }
      | undefined
    if (!result) return { ...base, detail: "no result from page" }

    return {
      ...base,
      outcome: result.outcome as EntryResult["outcome"],
      added: result.added,
      detail: result.detail,
    }
  } catch (error) {
    return {
      ...base,
      detail: error instanceof Error ? error.message : String(error),
    }
  }
}

export async function executeCartPlan(plan: CartPlan): Promise<PlanResult> {
  const adapter = getAdapter(plan.shop_slug)
  if (!adapter) {
    // The backend can offer a shop this build of the extension cannot drive.
    // Saying so is the extension-side mirror of a declared capability.
    return {
      shop_slug: plan.shop_slug,
      outcome: "unsupported_shop",
      entries: [],
      detail: `No adapter for ${plan.shop_slug}`,
    }
  }

  // Never drive an origin the adapter does not own, even if the plan asks.
  if (plan.origin !== adapter.origin) {
    return {
      shop_slug: plan.shop_slug,
      outcome: "wrong_origin",
      entries: [],
      detail: `Plan targets ${plan.origin}, adapter owns ${adapter.origin}`,
    }
  }

  if (plan.entries.length === 0) {
    return { shop_slug: plan.shop_slug, outcome: "completed", entries: [] }
  }

  let tabId: number | undefined
  try {
    const tab = await chrome.tabs.create({ url: adapter.origin, active: false })
    tabId = tab.id
    if (tabId === undefined) {
      return {
        shop_slug: plan.shop_slug,
        outcome: "failed",
        entries: [],
        detail: "Could not open a tab",
      }
    }
    await waitForTabLoad(tabId, adapter.resultTimeoutMs)

    const entries: EntryResult[] = []
    for (const entry of plan.entries) {
      entries.push(await runEntry(tabId, adapter, entry))
    }

    // Bring the basket forward so the user can check it before paying.
    await chrome.tabs.update(tabId, { active: true })

    const allAdded = entries.every((e) => e.outcome === "added")
    return {
      shop_slug: plan.shop_slug,
      outcome: allAdded ? "completed" : "partial",
      entries,
    }
  } catch (error) {
    return {
      shop_slug: plan.shop_slug,
      outcome: "failed",
      entries: [],
      detail: error instanceof Error ? error.message : String(error),
    }
  }
}
