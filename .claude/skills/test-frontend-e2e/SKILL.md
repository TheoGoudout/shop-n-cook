---
name: test-frontend-e2e
description: Run the Playwright E2E suite for Shop'n'Cook. Use when verifying frontend changes, recipe/shopping-list flows, auth, or anything visible in the browser.
---

# Frontend E2E tests (Playwright)

There are no React component unit tests — Playwright E2E specs are the
only frontend test layer. They live in `frontend/tests/`.

## Run

```bash
cd frontend
bun run test                # full suite, single worker locally
bun run test:ui             # Playwright UI mode
```

CI runs with 4-shard parallelism (`playwright.yml`) and retries flaky
tests automatically.

## Run one spec

```bash
bunx playwright test tests/recipes.spec.ts
bunx playwright test tests/recipes.spec.ts:42  # by line number
bunx playwright test --grep "import"           # by title substring
```

## Specs

- `auth.setup.ts` — shared auth fixture (sets up cookies/localStorage)
- `login.spec.ts` — login + password recovery
- `sign-up.spec.ts` — registration
- `recipes.spec.ts` — recipe CRUD (covers Add + Edit + Delete via the
  shared `<RecipeForm>`)
- `shopping-lists.spec.ts` — list CRUD, AddItemDialog, AddRecipeDialog,
  RenameListDialog
- `user-settings.spec.ts` — profile + DeleteConfirmation
- `admin.spec.ts` — admin user management
- `reset-password.spec.ts` — token-based password reset

## Prerequisites

The full stack must be running (`docker compose up -d`). Playwright
connects to `http://localhost:5173` by default. Override with
`FRONTEND_HOST` in `frontend/playwright.config.ts`.

## Debugging a failure

```bash
bunx playwright test tests/recipes.spec.ts --debug   # step through
bunx playwright show-report                          # last HTML report
```

Screenshots + traces from CI failures are uploaded as workflow artifacts
in `playwright.yml`.
