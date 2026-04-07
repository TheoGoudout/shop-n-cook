# Release Notes

## Latest Changes

### Internal

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
