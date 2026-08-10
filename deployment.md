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

The frontend and landing hostnames are declared as custom domains in
`frontend/wrangler.jsonc` and `landing/wrangler.jsonc`; Cloudflare creates and
manages the DNS records and certificates for them on first deploy. The `api.*`
records point at the Coolify host and are managed there.

---

## Cloudflare Workers (frontend + landing)

### Release flow

`.github/workflows/deploy-cloudflare.yml` deploys both projects:

| Trigger | Environment |
|---|---|
| Push to `master` | staging |
| Push of a `v*` tag (see [`bump-version.yml`](.github/workflows/bump-version.yml)) | production |
| `workflow_dispatch` | whichever you pick |

Each environment maps to a GitHub Environment of the same name, so production
can carry a required-reviewers approval gate.

### Required GitHub secrets

Set these on both the `staging` and `production` GitHub Environments:

| Secret | Description |
|---|---|
| `CLOUDFLARE_API_TOKEN` | API token with **Workers Scripts: Edit** and **Workers Routes: Edit**, plus **DNS: Edit** on the zone so custom domains can be provisioned |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |

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

Pushing to the `master` branch triggers an automatic deployment. Coolify watches
the repository via its GitHub App integration and redeploys the stack on every
push to `master` — no GitHub Actions workflow or manual webhook configuration is
required.

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
