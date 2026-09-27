/**
 * Bridges the web app and the extension.
 *
 * Injected only on our own frontend. The app posts a message on its own
 * window; this forwards it to the service worker and posts the reply back.
 * Using `window.postMessage` rather than `externally_connectable` keeps one
 * code path working across Chrome, Firefox, Edge, Opera and Safari.
 */

import type { PlanResult } from "../shops"

/** Only messages carrying this marker are forwarded. */
const APP_SOURCE = "shop-n-cook-app"
const EXTENSION_SOURCE = "shop-n-cook-extension"

interface AppMessage {
  source: typeof APP_SOURCE
  requestId: string
  payload: unknown
}

function isAppMessage(data: unknown): data is AppMessage {
  if (typeof data !== "object" || data === null) return false
  const candidate = data as Partial<AppMessage>
  return (
    candidate.source === APP_SOURCE && typeof candidate.requestId === "string"
  )
}

window.addEventListener("message", (event: MessageEvent) => {
  // Same-window only: a message from an iframe or another origin is not ours,
  // and forwarding it would let any embedded page drive the user's basket.
  if (event.source !== window) return
  if (event.origin !== window.location.origin) return
  if (!isAppMessage(event.data)) return

  const { requestId, payload } = event.data
  chrome.runtime.sendMessage(payload, (response: PlanResult | undefined) => {
    window.postMessage(
      {
        source: EXTENSION_SOURCE,
        requestId,
        response: response ?? null,
        error: chrome.runtime.lastError?.message ?? null,
      },
      window.location.origin,
    )
  })
})

// Lets the app detect the extension without a round trip.
document.documentElement.dataset.shopNCookExtension = "1"
