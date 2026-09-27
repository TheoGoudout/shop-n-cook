/**
 * Service worker: receives cart plans and runs them.
 *
 * Plans arrive from the web app through the content-script bridge rather than
 * `externally_connectable`, because Firefox does not support the latter and
 * this extension ships to Chrome, Firefox, Edge, Opera and Safari from one
 * manifest.
 */

import { supportedSlugs } from "./cart/adapters"
import { executeCartPlan } from "./cart/runner"
import { isExecuteCartPlanMessage } from "./shops"

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (isExecuteCartPlanMessage(message)) {
    // Returning true keeps the message channel open for the async reply; the
    // run takes seconds, well past this listener returning.
    executeCartPlan(message.plan).then(sendResponse)
    return true
  }

  if (
    typeof message === "object" &&
    message !== null &&
    (message as { type?: string }).type === "CART_CAPABILITIES"
  ) {
    // Lets the web app hide a "send to shop" button this build cannot honour.
    sendResponse({ supported_slugs: supportedSlugs() })
    return false
  }

  return false
})
