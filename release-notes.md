# Release Notes

## 1.7.3 (2026-10-06)

### Fixes

* Keep desserts, snacks and sauces out of generated menus. PR [#96](https://github.com/TheoGoudout/shop-n-cook/pull/96) by [@TheoGoudout](https://github.com/TheoGoudout).

## 1.7.2 (2026-10-04)

### Features

* feat(frontend): warmer visual identity, top-nav layout and self-hosted fonts. PR [#95](https://github.com/TheoGoudout/shop-n-cook/pull/95) by [@TheoGoudout](https://github.com/TheoGoudout).
* Dev, staging and production environments. PR [#93](https://github.com/TheoGoudout/shop-n-cook/pull/93) by [@TheoGoudout](https://github.com/TheoGoudout).
* feat(deploy): default the API to one worker process. PR [#88](https://github.com/TheoGoudout/shop-n-cook/pull/88) by [@TheoGoudout](https://github.com/TheoGoudout).
* feat(deploy): build the backend image in CI, pull it from GHCR, and fit a small shared host. PR [#87](https://github.com/TheoGoudout/shop-n-cook/pull/87) by [@TheoGoudout](https://github.com/TheoGoudout).

### Fixes

* fix(pricing): estimate missing store prices with medians, not means. PR [#92](https://github.com/TheoGoudout/shop-n-cook/pull/92) by [@TheoGoudout](https://github.com/TheoGoudout).
* fix(db): make the models describe the schema the migrations built. PR [#91](https://github.com/TheoGoudout/shop-n-cook/pull/91) by [@TheoGoudout](https://github.com/TheoGoudout).

### Internal

* Make the staging environment opt-in. PR [#94](https://github.com/TheoGoudout/shop-n-cook/pull/94) by [@TheoGoudout](https://github.com/TheoGoudout).
* ci: share release notes and workflow files with greensecops and prism. PR [#90](https://github.com/TheoGoudout/shop-n-cook/pull/90) by [@TheoGoudout](https://github.com/TheoGoudout).
* ci: harden the pipelines and sequence the staging deploy. PR [#89](https://github.com/TheoGoudout/shop-n-cook/pull/89) by [@TheoGoudout](https://github.com/TheoGoudout).

## 1.7.1

### Features

* Deploy: Default the API to one worker process
* Deploy: Build the backend image in CI and pull it from GHCR
* Deploy: Make API worker count configurable and cap container memory

### Fixes

* Deploy: Default POSTGRES_DB in the db healthcheck
* Dev: Give mailcatcher a healthcheck its image can run

### Internal

* Restore no cache into the publishing and deploy jobs
* Check version drift in pre-commit
* Harden the pipelines and sequence the staging deploy

## 1.7.0

### Features

* Backend: Crawl top-rated recipes from recipe sites
* Meal-plans: A dedicated menu generation page with portions per meal
* Meal-plans: Batch cooking and a review step before saving a menu
* Meal-plans: Choose which meals to generate on each weekday
* Shopping: Check what is already at home before shopping

### Fixes

* Backend: Set the crawler migration's new revision and parent
* Backend: Give the recipe crawler migration its own revision ID
* Pricing: Compare stores on the same items, not on what each one prices

### Internal

* Extension: Format manifest.json as biome expects
* Extension: Format manifest.json the way biome expects

## 1.6.1

### Fixes

* Extension: Give Firefox a background script it can run
* Release: Keep Google Play release notes under its 500-character limit

## 1.6.0

### Features

* Stores: Refresh every store's prices daily in the background
* Stores: Add Biocoop and Naturalia from their product sitemaps
* Stores: Price nine chains lawfully, and fix the extension's plan contract
* Shops: Capability-based shop integration with extension and list-only transports
* Show budget against spend, and correct the docs
* Share shopping lists and meal plans with a household
* Compose a week's menu from the recipes you can cook
* Plan a week of meals, then generate one shopping list
* Compare basket prices across retailers
* Backend: Estimate missing ingredient prices with the LLM
* Frontend: Show what recipes and shopping lists cost
* Backend: Price ingredients, budget households, merge lists by unit

### Fixes

* Shops: Honour household access on the shop endpoints

### Refactors

* One store concept, with providers behind it
* Shops: Adopt the shared unit table and Decimal prices from #78
* CI: Move every step body out of the workflows into .github/scripts/

### Internal

* Name the exact setup-ruby version its pin points to
* Shops: Apply ruff format and hoist test imports
* Extension: Format manifest.json with biome
* No bun cache in the two release jobs that install nothing
* Name the version each action pin actually is
* Make the new hooks pass on the existing tree
* Add a rollback path, and check that a Cloudflare deploy served
* Add zizmor, and fix everything it finds

## 1.5.2

### Fixes

* Backend: Repair enum columns written with the wrong case

## 1.5.1

### Fixes

* CI: POST the Coolify deploy request so the release reaches production

## 1.5.0

### Features

* Recipes: Import recipes from photos

### Fixes

* Docker: Copy every workspace manifest before bun install

### Internal

* Extension: Normalize manifest.json formatting

## 1.4.8

### Features

* CI: Deploy the backend to Coolify as part of the release

## 1.4.7

### Features

* CI: Rework the release pipeline around a draft release

### Fixes

* CI: Stop the release preflight failing on path-filtered workflows

## 1.4.4

### Fixes

* Android: publish stable builds to alpha track; RC builds remain on internal track

## 1.4.3

### Fixes

* Extension: fix Chrome Web Store publishing — switch from OAuth refresh token to service account auth
* Extension: fix YAML syntax in Chrome publish workflow
* Extension: skip store submissions for pre-releases (RC builds no longer queue in review)
* Extension: add version name display for pre-release builds
* Android: fix version code collision between RC and stable builds
* Android: fix beta track precondition on Google Play submission
* CI: add release notes to Firefox, iOS, and Android store submissions
* Android: RC builds now publish to internal track; stable builds publish to beta track

## 1.4.2

### Features

* Shopping list: servings +/- controls — adjust recipe servings directly from the list
* Shopping list: item quantities update automatically when recipe servings change
* Shopping list: improved UX for recipe management, servings display, and list renaming
* Shopping list: ingredient entries now link back to their source recipe
* Ingredient rename: duplicate shopping list items automatically merged after rename

### Fixes

* Android: fix TWA build failure — replace deprecated jcenter() with mavenCentral()
* Android: publish releases to internal track instead of production
* Android: add Play App Signing certificate fingerprint to assetlinks.json
* Security: fix three permission issues found during extension review
* Docker: pass `RATE_LIMIT_ENABLED` into backend container

## 1.4.0

### Features

* Add browser extension for one-click recipe import (Chrome, Firefox, Edge, Opera, Safari)
* Add PWA support — installable as a Progressive Web App with web share target for mobile recipe import
* Add public/private recipes — public recipes are accessible without an account
* Add user profile pages listing each user's public recipes
* Add recipe search by title and description
* Add internationalization — interface available in English and French with automatic browser language detection
* Add Android Web Share Target — share any URL from another app to trigger an import
* Recipe import — consolidated scraping and LLM parsing into a single round-trip, with `name_en` and `category` carried through to recipe creation
* Add `import_consent` field on `RecipeCreate` — explicit consent required when importing from a third-party URL

### Internal

* refactor(frontend): collapse duplicated AddRecipe/EditRecipe (1355 LOC combined) into a single shared `<RecipeForm>` plus a Zod schema factory and create/update payload mappers; URL import is now a decoupled `<RecipeImportPanel>`
* refactor(frontend): add a shared `<UnitSelect>` over `UnitSchema.enum`; remove the hardcoded units array in `ShoppingListCard` (also restores the missing `cl` and `dl` units)
* refactor(frontend): introduce `<ConfirmDialog>` and the `useCrudMutation` hook; migrate the four destructive flows (DeleteRecipe, DeleteUser, DeleteConfirmation, ShoppingListCard delete) and all six ShoppingListCard mutations
* refactor(frontend): decompose `ShoppingListCard` (545 LOC) into focused siblings — `AddItemDialog`, `AddRecipeDialog`, `RenameListDialog`
* refactor(backend): dedup `_ri_to_public` between `crud/recipe.py` and `crud/shopping_list.py`; merge `get_recipes` and `get_public_recipes` behind a single function with `public_only` / `eager_load_owner` flags
* refactor(backend): split `services/recipe_import.py` (323 LOC) into a package by concern — `models.py`, `prompt.py`, `scraper.py`, `llm.py`, `orchestrator.py` — and update tests to patch at the submodule paths
* docs: add `CLAUDE.md` at the repo root capturing project conventions for AI assistants (units via `UnitSchema.enum`, mutations via `useCrudMutation`, destructive flows via `<ConfirmDialog>`, recipe forms via `<RecipeForm>`)
* docs: add 10 Claude Code skills under `.claude/skills/` covering dev-up, regen-client, migration, test-backend, test-frontend-e2e, test-extension, pre-commit-fix, i18n-add, release, brand
* ci: automate extension publishing to all major browser stores on GitHub release (pre-release → test channels, release → public)
* ci: replace `deploy.yml` GitHub Actions workflow with Coolify GitHub App for continuous deployment
* ci: migrate deployment from Traefik self-hosted to Coolify
* ci: remove `.env` from repo; add `.env.example` for CI and local setup
* fix: add `PROJECT_NAME` to `compose.yml` environment
* fix: don't require `VITE_API_URL` in base `compose.yml`

## 0.3.0

### Features

* Add custom chef hat logo (Lucide ChefHat icon) with light/dark mode variants
* Add dashboard stats chart (bar chart via Recharts) showing recipe, ingredient, and shopping list counts

## 0.2.0

### Features

* Add AI recipe import from URL — fetches a recipe page and parses it into a structured recipe using a configurable LLM (Anthropic, OpenAI, or Google Gemini)
* Add household settings — configure shopping frequency, household size, and budget per user

## 0.1.0

### Features

* Add ingredient catalog — full CRUD for ingredients with categories and units
* Add recipe management — full CRUD for recipes with structured ingredient lists
* Add shopping list management — create lists from recipes, track item completion

### Refactors

* Split `models.py` and `crud.py` into packages (`models/`, `crud/`) for better organization
* Remove items placeholder feature from the original template
