/**
 * Cloudflare Worker in front of the frontend's static assets.
 *
 * Static assets are served by the `ASSETS` binding, which applies the
 * `single-page-application` not-found handling declared in `wrangler.jsonc`,
 * so unknown paths fall back to `index.html`.
 *
 * The only thing this Worker adds is the backend-not-found behaviour that
 * `nginx-backend-not-found.conf` provides in the Docker image: API-ish paths
 * must 404 instead of being swallowed by the SPA fallback. This mirrors the
 * `navigateFallbackDenylist` configured for the service worker in
 * `vite.config.ts`.
 */

interface Env {
  ASSETS: { fetch: (request: Request) => Promise<Response> }
}

const BACKEND_PREFIXES = ["/api", "/docs", "/redoc"]

const isBackendPath = (pathname: string): boolean =>
  BACKEND_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { pathname } = new URL(request.url)

    if (isBackendPath(pathname)) {
      return new Response("Not Found", { status: 404 })
    }

    return env.ASSETS.fetch(request)
  },
}
