# Shop n Cook - Deployment

Shop n Cook is deployed in two halves:

- **`frontend/` and `landing/`** — static sites deployed to
  [Cloudflare Workers](https://developers.cloudflare.com/workers/static-assets/),
  via GitHub Actions.
- **`backend/` and the database** — deployed by [Coolify](https://coolify.io),
  a self-hosted PaaS that manages Docker Compose deployments.

There are three environments, and what deploys each is the one thing that
differs between them:

| Environment | Deployed by | When |
|---|---|---|
| **dev** | Coolify and Cloudflare Workers Builds, watching `master` | every push to `master` |
| **staging** | [`release.yml`](.github/workflows/release.yml) | every published pre-release and release |
| **production** | [`release.yml`](.github/workflows/release.yml) | every published release (not pre-releases) |

Staging and production run the same jobs —
[`deploy-environment.yml`](.github/workflows/deploy-environment.yml), the backend
then the frontend and landing — with a different GitHub Environment, so each
reads its own secrets and protection rules. A release deploys both side by side.
Dev never goes through Actions: see [Dev](#dev).

## Domains

| | production | staging | dev |
|---|---|---|---|
| Landing | `shop-n-cook.com`, `www.shop-n-cook.com` | `staging.shop-n-cook.com` | `dev.shop-n-cook.com` |
| Frontend | `app.shop-n-cook.com` | `app.staging.shop-n-cook.com` | `app.dev.shop-n-cook.com` |
| Backend | `api.shop-n-cook.com` | `api.staging.shop-n-cook.com` | `api.dev.shop-n-cook.com` |

The frontend and landing hostnames are attached to their Workers by hand in the
Cloudflare dashboard — see [Custom domains](#custom-domains). The `api.*` records
point at the Coolify host and are managed there.

---

## Cloudflare Workers (frontend + landing)

### Release flow

`.github/workflows/deploy-cloudflare.yml` deploys both projects:

| Trigger | Environment |
|---|---|
| Called by [`release.yml`](.github/workflows/release.yml) (through `deploy-environment.yml`), after that environment's backend | staging for a pre-release; staging and production for a release |
| Called by [`rollback.yml`](.github/workflows/rollback.yml) | whichever you pick |
| `workflow_dispatch` | whichever you pick |

Releases deploy alongside the extension and app stores, driven by the published
release rather than by the tag push — see the
[release skill](.claude/skills/release/SKILL.md). Pre-releases reach staging,
never production. Dev is deployed by Workers Builds instead — see [Dev](#dev).

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
| `dev.shop-n-cook.com` | `shop-n-cook-landing-dev` |
| `app.shop-n-cook.com` | `shop-n-cook-frontend` |
| `app.staging.shop-n-cook.com` | `shop-n-cook-frontend-staging` |
| `app.dev.shop-n-cook.com` | `shop-n-cook-frontend-dev` |

Cloudflare creates the DNS record and certificate when you add the binding. A
Worker has to exist before you can bind a hostname to it, so the order is
*deploy first, bind second* — the dev pair after Workers Builds' first deploy,
the staging pair after the first published pre-release or release, the
production pair after the first published release.

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
| `frontend/.env.dev` | `VITE_API_URL`, `VITE_PROJECT_NAME` |
| `frontend/.env.staging` | `VITE_API_URL`, `VITE_PROJECT_NAME` |
| `frontend/.env.production` | `VITE_API_URL`, `VITE_PROJECT_NAME` |
| `landing/.env.dev` | `FRONTEND_URL` |
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

# Dev (normally Workers Builds' job)
bun run --filter frontend build:dev && bun run --filter frontend deploy:dev
bun run --filter landing  build:dev && bun run --filter landing  deploy:dev

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

**Nothing is built on the Coolify host.** [`images.yml`](.github/workflows/images.yml)
builds `backend/Dockerfile` on a GitHub runner and publishes it to GHCR as
`ghcr.io/theogoudout/shop-n-cook-backend`, tagged `sha-<short commit>` (plus the
release tag for a release or pre-release). `compose.yml` names that
image and carries no `build:` section, so Coolify only pulls. Its `TAG`
variable picks the image; CI owns it, so do not set it by hand.

Every deploy pins the immutable `sha-<short>` tag rather than `latest`: a tag
that never moves is one Docker cannot mistake for an image it already has.

| | Tracks | Moved by |
|---|---|---|
| staging | the latest pre-release or release tag, e.g. `v1.5.0-rc1` | [`deploy-coolify.yml`](.github/workflows/deploy-coolify.yml), called by `release.yml` after the image build |
| production | the latest release tag, e.g. `v1.5.0` | the same, for releases only |
| dev | `master` | Coolify itself — see [Dev](#dev) |

**Turn Coolify's auto-deploy off on the staging and production applications**
(*Advanced → Auto Deploy*): `release.yml` moves them, after the release's image
exists.

Each deploy runs `deploy-coolify.yml`, which:

1. resolves the ref to a commit and reads the expected version out of
   `backend/pyproject.toml` at that commit,
2. checks, anonymously, that the commit's image is on GHCR — the same view the
   host has when it pulls,
3. `PATCH`es the Coolify application's git ref (`git_branch`) to the ref — it is
   where Coolify reads `compose.yml` from — and sets its `TAG` variable to the
   image tag,
4. triggers a deployment and polls it to completion,
5. waits for `https://api.shop-n-cook.com/api/v1/utils/health-check/`, then
   asserts that `/api/v1/openapi.json` reports the released version.

**The GHCR package must be public**, because the host pulls without
credentials. The repository is public, but check it once after the first build:
GitHub → your profile → *Packages* → `shop-n-cook-backend` → *Package settings*
→ *Change visibility*. Step 2 above fails with that hint if it is not.

The backend therefore deploys *before* the Cloudflare frontend in the same
release run — `deploy-environment.yml` sequences them that way, per environment,
so the API is upgraded ahead of its clients. Pre-releases reach staging only.

> **Coolify 4.2 or newer is required.** 4.2 made every state-changing API
> endpoint `POST`-only, `/api/v1/deploy` among them, and answers the older `GET`
> form with `405 This endpoint has changed to a POST request.` The workflow
> sends `POST`, so an instance older than 4.2 will reject the deploy instead.

### Required GitHub secrets

Set these on both the `staging` and `production` GitHub Environments, each
pointing at its own application. The `staging` Environment must allow
deployments from `v*` tags, since every release now deploys it from its tag:

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

Dispatch [`rollback.yml`](.github/workflows/rollback.yml) with the environment
and the tag to return to. It rolls the frontend back first and the backend
second — the reverse of a release — through the same reusable workflows, so the
version assertion confirms the rollback actually took. To move the backend on
its own, dispatch [`deploy-coolify.yml`](.github/workflows/deploy-coolify.yml)
instead. Coolify also keeps previous deploys around for a redeploy from its
dashboard.

Use `force: true` when re-running against a ref the application is already
pinned to — otherwise Coolify may decide there is nothing to redeploy.

A ref deploys only once its image exists. Releases from before images were
published to GHCR have none: dispatch the **Backend image** workflow
(`images.yml`) with that tag first, then roll back to it.

### The stack

`compose.yml` defines the stack Coolify deploys:

- `db` — PostgreSQL 18
- `prestart` — Runs database migrations (`alembic upgrade head`) on startup
- `backend` — FastAPI application

`prestart` and `backend` both run the GHCR image. `compose.override.yml`, which
Coolify never reads, adds their `build:` sections back for local development
and CI.

No reverse proxy is included — Coolify handles routing and HTTPS termination.

Staging and production are two separate Coolify deployments of the same
`compose.yml`, differing only in their environment variables. Dev is a third,
deployed from `compose.dev.yml` — see [Dev](#dev).

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
| `WEB_CONCURRENCY` | `1` API (uvicorn) worker process, each a full copy of the app — sized for a small host shared with other stacks. Raise it on a bigger one. |
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
| `ANTHROPIC_VISION_MODEL` | Model used to read recipes from photos (default: `claude-sonnet-5`) |
| `OPENAI_VISION_MODEL` | Model used to read recipes from photos (default: `gpt-4o`) |
| `GOOGLE_VISION_MODEL` | Model used to read recipes from photos (default: `gemini-2.5-flash`) |
| `RECIPE_PHOTO_MAX_COUNT` | Photos accepted per import (default: `3`) |
| `RECIPE_PHOTO_MAX_BYTES` | Maximum size of a single uploaded photo (default: `8388608`, i.e. 8 MiB) |
| `RECIPE_PHOTO_RATE_LIMIT` | Per-user limit on photo imports (default: `10/hour`) |
| `STORE_PRICE_REFRESH_HOURS` | Hours between two background refreshes of each provider-backed store's prices (default: `24`; `0` turns it off). See below. |
| `BIOCOOP_API_TOKEN` / `NATURALIA_API_TOKEN` | Magento API tokens. Optional: without one, the store is read from its public product sitemap instead. |
| `RECIPE_CRAWL_HOURS` | Hours between two runs of the recipe crawler (default: `0`, off). See below. |
| `RECIPE_CRAWL_MAX_IMPORTS` | Recipes imported per run, across all sites — one LLM call each (default: `10`) |
| `RECIPE_CRAWL_MAX_PAGES_PER_SITE` | Recipe pages read per site and per run to judge their rating (default: `20`) |
| `RECIPE_CRAWL_DELAY_SECONDS` | Pause between two requests to the same recipe site (default: `5`) |
| `RECIPE_CRAWL_OWNER_EMAIL` | Account that owns crawled recipes, created inactive on first run (default: `recipes@shop-n-cook.com`) |

#### Background price refresh

Every backend worker runs a small thread that wakes hourly and refreshes the
stores whose prices are older than `STORE_PRICE_REFRESH_HOURS`
(`app/services/store_providers/scheduler.py`). A Postgres advisory lock lets
only one worker in the whole deployment work at a time, and the first run
waits five minutes after startup. `Store.prices_refreshed_at` records the last
complete refresh per store.

What to expect from a run:

- **Outbound traffic**: one ~33 MB download of the Open Prices dump from
  `huggingface.co`, `prices.openfoodfacts.org` for catalogue searches, and the
  retailers' sitemaps and product pages (`courses.monoprix.fr`,
  `www.picard.fr`, `www.biocoop.fr`, `www.naturalia.fr`), throttled to at most
  four requests a second per retailer and checked against each robots.txt.
- **Memory**: the worker running it peaks about 160 MB above its usual size
  while reading the dump, and frees it when the run ends.
- **Duration**: measured at about 10 seconds per ingredient across all eleven
  stores — ~3 s for the Open Prices catalogue search (slow on their side, then
  cached and shared by all six chains that use it) and ~1–2 s per sitemap store
  for one product page. 300 ingredients is therefore roughly 50 minutes, once
  a day, in the background.

#### Recipe crawler

Off unless `RECIPE_CRAWL_HOURS` is set. Each run (one worker at a time, via its
own Postgres advisory lock; the first waits 15 minutes after startup):

1. reads the popularity pages of the sites in
   `app/services/recipe_crawler/sites.py` (Marmiton, Journal des Femmes Cuisine,
   750g), checked against each robots.txt and spaced by
   `RECIPE_CRAWL_DELAY_SECONDS`;
2. judges up to `RECIPE_CRAWL_MAX_PAGES_PER_SITE` recipes per site it has not
   judged before, on their readers' rating (e.g. Marmiton: at least 4.5/5 from
   200+ votes);
3. imports up to `RECIPE_CRAWL_MAX_IMPORTS` of the best qualified recipes as
   public recipes, through the configured `AI_PROVIDER`.

Every verdict is stored in `crawledrecipe`, keyed by canonical URL, so a recipe
is never imported twice and a page is never judged twice (rejections are
re-judged after 90 days, since ratings move). `recipecrawlrun` logs each run.
No AI key means no run. To try it or top up the catalogue by hand:

```bash
docker compose exec backend python -m app.services.recipe_crawler --dry-run
docker compose exec backend python -m app.services.recipe_crawler
```

Imported recipes credit their page (`source_url`) and link to its image, but
the text is still the site's: confirm you may publish a site's recipes before
turning the crawler on.

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

---

## Dev

Dev follows `master` without GitHub Actions: Coolify and Cloudflare Workers
Builds each watch the repository and deploy every push themselves. Nothing
orders the two, so for a few minutes after a push the dev frontend can run
ahead of the dev API — acceptable for dev, and the reason staging and
production are deployed by `release.yml` instead.

### Backend (Coolify)

A third Coolify application, set up like the other two except:

1. **Compose file: `/compose.dev.yml`**, git branch `master`, and
   **auto-deploy on**.
2. `compose.dev.yml` is `compose.yml` with the backend image built from the
   checkout (`build:` and `pull_policy: build`) instead of pulled from GHCR —
   dev is the one environment whose Coolify host builds. It is generated:
   after changing `compose.yml`, run `scripts/generate-compose-dev.sh` and
   commit the result. `test-docker-compose.yml` fails while it is stale.
3. Do not set `TAG`: nothing pulls by tag here.
4. Domain `https://api.dev.shop-n-cook.com:8000` on the `backend` service.
5. Environment variables as for staging, with
   `FRONTEND_HOST=https://app.dev.shop-n-cook.com`. `ENVIRONMENT` stays
   `staging`: the backend knows only `local`, `staging` and `production`, and
   dev should behave like a deployed non-production environment.

### Frontend and landing (Cloudflare Workers Builds)

Connect the repository to each dev Worker in the Cloudflare dashboard
(**Workers & Pages → the Worker → Settings → Builds → Connect**), on branch
`master`:

| Worker | Root directory | Build command | Deploy command |
|---|---|---|---|
| `shop-n-cook-frontend-dev` | `/` | `bun install --frozen-lockfile && bun run --filter frontend build:dev` | `cd frontend && bunx wrangler deploy --env dev` |
| `shop-n-cook-landing-dev` | `/` | `bun install --frozen-lockfile && bun run --filter landing build:dev` | `cd landing && bunx wrangler deploy --env dev` |

Set `BUN_VERSION` (the value in `.bun-version`) as a build variable on both.
The URLs come from the committed `frontend/.env.dev` and `landing/.env.dev`, and
`test-frontend.yml` builds the dev variant of each on every pull request. Turn
the builds' preview deployments for non-`master` branches off unless you want
them: they would deploy pull-request code under the dev Workers.

A Worker has to exist before it can be connected, so create each with one
manual deploy first (`bun run --filter frontend build:dev && bun run --filter
frontend deploy:dev`, and the same for `landing`), then bind its custom domain.

