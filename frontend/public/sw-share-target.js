/*
 * Web Share Target handler for shared photos.
 *
 * Receiving files requires the manifest's share_target to use POST +
 * multipart/form-data, and a POST share target can only be read by a service
 * worker: the browser dispatches the request at the worker, not at the page.
 * The generated Workbox service worker cannot express this, so this file is
 * pulled in via `workbox.importScripts` and registers its own fetch handler.
 *
 * The payload is stashed in the Cache Storage API under a one-shot key, then
 * the worker redirects to /share-target?shared=<key> so the app can pick it up
 * and clear it.
 */

const SHARE_CACHE = "share-target-payloads"
const SHARE_PATH = "/share-target"

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url)
  if (event.request.method !== "POST" || url.pathname !== SHARE_PATH) {
    return
  }

  event.respondWith(
    (async () => {
      const key = `${Date.now()}-${Math.random().toString(36).slice(2)}`
      try {
        const formData = await event.request.formData()
        const cache = await caches.open(SHARE_CACHE)

        const photos = formData
          .getAll("photos")
          .filter((entry) => entry instanceof File && entry.size > 0)

        await Promise.all(
          photos.map((photo, index) =>
            cache.put(
              `/__share/${key}/photo-${index}`,
              new Response(photo, {
                headers: {
                  "Content-Type": photo.type || "application/octet-stream",
                },
              }),
            ),
          ),
        )

        await cache.put(
          `/__share/${key}/meta`,
          new Response(
            JSON.stringify({
              photoCount: photos.length,
              title: formData.get("title") || "",
              text: formData.get("text") || "",
              url: formData.get("url") || "",
            }),
            { headers: { "Content-Type": "application/json" } },
          ),
        )
      } catch {
        // Fall through: the page shows its "could not read this share" state.
      }

      return Response.redirect(
        `${SHARE_PATH}?shared=${encodeURIComponent(key)}`,
        303,
      )
    })(),
  )
})
