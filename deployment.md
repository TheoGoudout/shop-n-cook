# Shop n Cook - Deployment

Shop n Cook is deployed in two halves:

- **`frontend/` and `landing/`** — static sites deployed to
  [Cloudflare Workers](https://developers.cloudflare.com/workers/static-assets/),
  via GitHub Actions.
- **`backend/` and the database** — deployed by [Coolify](https://coolify.io),
  a self-hosted PaaS that manages Docker Compose deployments.

There are two environments, **staging** and **production**.

## Domains

| | production | staging |
|---|---|---|
| Landing | `shop-n-cook.com`, `www.shop-n-cook.com` | `staging.shop-n-cook.com` |
| Frontend | `app.shop-n-cook.com` | `app.staging.shop-n-cook.com` |
| Backend | `api.shop-n-cook.com` | `api.staging.shop-n-cook.com` |

The frontend and landing hostnames are attached to their Workers by hand in the
Cloudflare dashboard — see [Custom domains](#custom-domains). The `api.*` records
point at the Coolify host and are managed there.

---

## Cloudflare Workers (frontend + landing)

### Release flow

`.github/workflows/deploy-cloudflare.yml` deploys both projects:

| Trigger | Environment |
|---|---|
| Push to `master` | staging |
| Called by [`release.yml`](.github/workflows/release.yml) when a release is published | production |
| `workflow_dispatch` | whichever you pick |

Production deploys alongside the extension and app stores, driven by the
published release rather than by the tag push — see the
[release skill](.claude/skills/release/SKILL.md). Pre-releases do not reach
production.

Each environment maps to a GitHub Environment of the same name, so production
can carry a required-reviewers approval gate.

### Required GitHub secrets

Set these on both the `staging` and `production` GitHub Environments:

| Secret | Description |
|---|---|
| `CLOUDFLARE_API_TOKEN` | API token — see [permissions](#api-token-permissions) below |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |

#### API token permissions

Create the token at
[dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens).
One account-scoped permission is enough:

| Scope | Permission | Needed for |
|---|---|---|
| Account | Workers Scripts: Edit | Uploading the Worker and its static assets |

No zone permissions are required, and the token deliberately does not carry any.
That is only true because neither `wrangler.jsonc` declares `routes` — see
[Custom domains](#custom-domains) for the reasoning and for the one-time manual
setup it implies.

### Custom domains

Custom domains are **not** managed by wrangler. Neither `wrangler.jsonc`
declares a `routes` key; each hostname is bound to its Worker once, by hand, in
the Cloudflare dashboard under **Workers & Pages → \<worker\> → Settings →
Domains & Routes → Add → Custom domain**.

| Hostname | Worker |
|---|---|
| `shop-n-cook.com` | `shop-n-cook-landing` |
| `www.shop-n-cook.com` | `shop-n-cook-landing` |
| `staging.shop-n-cook.com` | `shop-n-cook-landing-staging` |
| `app.shop-n-cook.com` | `shop-n-cook-frontend` |
| `app.staging.shop-n-cook.com` | `shop-n-cook-frontend-staging` |

Cloudflare creates the DNS record and certificate when you add the binding. A
Worker has to exist before you can bind a hostname to it, so the order is
*deploy first, bind second* — the staging pair after the first push to `master`,
the production pair after the first published release.

**Why not declare them in `wrangler.jsonc`?** Because wrangler treats the config
as authoritative and reconciles `routes` against the zone on *every* deploy, not
just the first. That would require the CI token to hold `Workers Routes: Edit`
and `DNS: Edit` on `shop-n-cook.com` — enough to repoint `api.shop-n-cook.com`
at anything, including the Coolify-hosted backend, if the token ever leaked.
Binding by hand keeps the CI token account-scoped.

The cost is drift: the hostname → Worker mapping lives only in the dashboard and
in the table above. Renaming a `name` in either `wrangler.jsonc` orphans its
binding silently — the deploy will succeed and the site will keep serving the
old Worker. Change the two together.

`workers_dev` is set to `false` in both configs so a Worker with no custom
domain attached is not quietly reachable at a `*.workers.dev` URL.

### Environment files

Build-time configuration lives in committed env files — they contain public URLs
only, never secrets. Anything in a `VITE_*` variable is inlined into the client
bundle and is therefore public by construction.

| File | Variables |
|---|---|
| `frontend/.env` | local development defaults |
| `frontend/.env.staging` | `VITE_API_URL`, `VITE_PROJECT_NAME` |
| `frontend/.env.production` | `VITE_API_URL`, `VITE_PROJECT_NAME` |
| `landing/.env.staging` | `FRONTEND_URL` |
| `landing/.env.production` | `FRONTEND_URL` |

The frontend uses Vite's mode mechanism (`vite build --mode staging` loads
`.env.staging` on top of `.env`). The landing page has no bundler: the build
script `scripts/build-landing.mjs` reads `landing/.env.<mode>` and substitutes
`${FRONTEND_URL}` into `landing/index.html`. Inline environment variables win
over both, so CI can override a value without editing a file.

### Deploying by hand

```bash
bun install

# Staging
bun run --filter frontend build:staging && bun run --filter frontend deploy:staging
bun run --filter landing  build:staging && bun run --filter landing  deploy:staging

# Production
bun run --filter frontend build:production && bun run --filter frontend deploy:production
bun run --filter landing  build:production && bun run --filter landing  deploy:production
```

Wrangler needs `CLOUDFLARE_API_TOKEN` (or an interactive `wrangler login`) and
`CLOUDFLARE_ACCOUNT_ID` in the environment. Add `--dry-run` to the deploy step to
validate the config without touching the account.

### Troubleshooting

**`Authentication error [code: 10000]` on `/zones/<zone-id>/workers/routes`**

```
✘ [ERROR] A request to the Cloudflare API (/zones/<zone-id>/workers/routes) failed.
  Authentication error [code: 10000]
```

Something reintroduced a `routes` key into `frontend/wrangler.jsonc` or
`landing/wrangler.jsonc`. The account-scoped token cannot edit zone routes by
design, so wrangler fails the moment it tries to reconcile them. The giveaway is
*where* it fails: the asset upload and the `Uploaded shop-n-cook-frontend-staging`
line succeed, and the error lands on the step immediately after.

Remove the `routes` key and bind the hostname in the dashboard instead — see
[Custom domains](#custom-domains).

**A deploy succeeds but the site is unchanged**

The Worker was updated; the hostname is pointing somewhere else. Either the
custom domain was never bound, or a `name` in `wrangler.jsonc` was changed and
the dashboard binding still points at the old Worker. Check the hostname against
the table in [Custom domains](#custom-domains). Nothing needs rolling back — a
deploy that uploads is already live for whatever hostname is bound to it.

### How the static sites are served

Both projects deploy as Workers static assets rather than containers, so the
Nginx configuration in `frontend/nginx.conf` and `landing/nginx.conf` does not
apply in staging or production. The equivalents are:

| Nginx behaviour | Workers equivalent |
|---|---|
| SPA fallback (`try_files $uri /index.html`) | `assets.not_found_handling: "single-page-application"` |
| `/api`, `/docs`, `/redoc` return 404 | `frontend/worker/index.ts` |
| `sw.js` served with `no-store` | `frontend/public/_headers` |
| `.webmanifest` content type | built in to Workers static assets |
| `/privacy` resolves to `privacy.html` | default `html_handling: "auto-trailing-slash"` |

The Nginx/Docker path is still used for local development and for anyone
self-hosting the stack — see [Local Development](#local-development).

---

## Coolify (backend + database)

Coolify builds from source, so **whichever git ref a Coolify application tracks
is the version running in that environment**. The two environments track
different things on purpose:

| | Tracks | Moved by |
|---|---|---|
| staging | `master` | The Coolify GitHub App, automatically, on every push |
| production | the released tag, e.g. `v1.5.0` | [`deploy-coolify.yml`](.github/workflows/deploy-coolify.yml), called by `release.yml` |

Staging needs no GitHub Actions workflow or webhook configuration — the GitHub
App integration redeploys it on every push to `master`.

Production has that auto-deploy webhook **off**, so master pushes cannot reach
it. Instead, publishing a release runs `deploy-coolify.yml`, which:

1. resolves the tag to a commit and reads the expected version out of
   `backend/pyproject.toml` at that commit,
2. `PATCH`es the Coolify application's git ref (`git_branch`) to the tag,
3. triggers a deployment and polls it to completion,
4. waits for `https://api.shop-n-cook.com/api/v1/utils/health-check/`, then
   asserts that `/api/v1/openapi.json` reports the released version.

The backend therefore deploys *before* the Cloudflare frontend in the same
release run — `release.yml` sequences them that way so the API is upgraded ahead
of its clients. Pre-releases do not reach production.

### Required GitHub secrets

Set these on the `production` GitHub Environment (and on `staging` too if you
want the manual dispatch to work there):

| Secret | Description |
|---|---|
| `COOLIFY_URL` | Base URL of the Coolify panel, no trailing slash. A secret rather than a variable so the hostname stays out of run logs. |
| `COOLIFY_API_TOKEN` | Coolify API token with write access to the application |
| `COOLIFY_APP_UUID` | The application's UUID — the last path segment of its Coolify dashboard URL |

The workflow fails loudly when any of these is missing, rather than skipping the
way the store publishers do: a backend that silently did not deploy leaves the
frontend talking to the wrong API.

The Coolify host must be reachable from GitHub-hosted runners. If it sits behind
an IP allowlist or Cloudflare Access, the API calls will fail and you will need
either a Cloudflare Access service token or a self-hosted runner.

### Rolling back

Dispatch [`deploy-coolify.yml`](.github/workflows/deploy-coolify.yml) with
`environment: production` and `ref` set to the previous tag. It re-pins and
redeploys, and the version assertion confirms the rollback actually took. Coolify
also keeps previous deploys around for a redeploy from its dashboard.

Use `force: true` when re-running against a ref the application is already
pinned to — otherwise Coolify may decide there is nothing to rebuild.

### The stack

`compose.yml` defines the stack Coolify deploys:

- `db` — PostgreSQL 18
- `prestart` — Runs database migrations (`alembic upgrade head`) on startup
- `backend` — FastAPI application

No reverse proxy is included — Coolify handles routing and HTTPS termination.

Staging and production are two separate Coolify deployments of the same
`compose.yml`, differing only in their environment variables.

### Environment Variables

Most variables are handled automatically by Coolify's [special variables](https://coolify.io/docs/knowledge-base/environment-variables) — you only need to set a small number manually.

#### Required (set manually in Coolify)

| Variable | Description |
|----------|-------------|
| `FRONTEND_HOST` | Public URL of the Cloudflare-hosted frontend — `https://app.shop-n-cook.com` (production) or `https://app.staging.shop-n-cook.com` (staging). Used for links in emails, and always an allowed CORS origin. |
| `ENVIRONMENT` | `production` or `staging` |
| `FIRST_SUPERUSER` | Email of the first admin user |
| `AI_PROVIDER` | `anthropic`, `openai`, or `google` |
| `ANTHROPIC_API_KEY` | Required if `AI_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | Required if `AI_PROVIDER=openai` |
| `GOOGLE_API_KEY` | Required if `AI_PROVIDER=google` |

#### Auto-generated by Coolify Special Variables

These are resolved automatically by Coolify — no manual configuration needed. You can view their generated values in the Coolify dashboard under **Service → Environment Variables**.

| Coolify Variable | Replaces | Description |
|---|---|---|
| `SERVICE_PASSWORD_SECRET` | `SECRET_KEY` | Auto-generated JWT signing secret |
| `SERVICE_PASSWORD_DB` | `POSTGRES_PASSWORD` | Auto-generated database password |
| `SERVICE_USER_DB` | `POSTGRES_USER` | Auto-generated database username |
| `SERVICE_PASSWORD_SUPERUSER` | `FIRST_SUPERUSER_PASSWORD` | Auto-generated admin password |

`FRONTEND_HOST` and `ENVIRONMENT` default to their production values, so in
practice only the staging deployment has to set them.

Other variables with built-in defaults (no need to set in Coolify):

| Variable | Default |
|---|---|
| `PROJECT_NAME` | `Shop n Cook` |
| `POSTGRES_DB` | `app` |

#### Optional

| Variable | Description |
|----------|-------------|
| `BACKEND_CORS_ORIGINS` | Comma-separated extra CORS origins. `FRONTEND_HOST` is always allowed, so this is only needed for additional clients. |
| `SENTRY_DSN` | Sentry DSN for error tracking |
| `SMTP_HOST` | SMTP server host for email sending |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |
| `EMAILS_FROM_EMAIL` | Sender email address |
| `LANGCHAIN_TRACING_V2` | Set to `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | LangSmith API key |
| `LANGCHAIN_PROJECT` | LangSmith project name (default: `shop-n-cook`) |
| `LANGCHAIN_ENDPOINT` | LangSmith API endpoint (use `https://eu.api.smith.langchain.com` for EU) |

---

## Local Development

For local development, set variables in `.env` (copy from `.env.example`). The
`compose.yml` fallback pattern means Coolify special variables are ignored
locally — your `.env` values take precedence.

`compose.override.yml` adds the development-only `frontend`, `landing`,
`mailcatcher` and `playwright` services on top of `compose.yml`. Compose loads it
automatically, so `docker compose up -d` still brings up the whole stack:

- Frontend (Vite dev server): `http://localhost:5173`
- Backend: `http://localhost:8000`
- Landing (Nginx): `http://localhost:8080`
- Mailcatcher: `http://localhost:1080`

The landing container stores `index.html` as a template and runs `envsubst` at
startup to inject `FRONTEND_URL` (from `FRONTEND_HOST` in your `.env`), so the
"Open the App" button points at your local frontend. This is the same
substitution `scripts/build-landing.mjs` performs at build time for Cloudflare.

To preview either project exactly as Cloudflare will serve it:

```bash
bun run --filter landing build:staging && cd landing && bunx wrangler dev --env staging
```
