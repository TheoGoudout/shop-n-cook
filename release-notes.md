# Release Notes

## Latest Changes

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
