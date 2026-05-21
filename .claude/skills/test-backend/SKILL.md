---
name: test-backend
description: Run the backend pytest suite for Shop'n'Cook. Use when verifying changes to FastAPI routes, CRUD functions, services, or any Python code under backend/app/.
---

# Backend tests

Backend uses pytest with coverage reporting. A 90% line coverage gate is
enforced in CI (`test-backend.yml`).

## Run everything

```bash
cd backend
uv run pytest --cov=app --cov-report=term-missing
```

For an HTML coverage report:

```bash
uv run pytest --cov=app --cov-report=html
# Open backend/htmlcov/index.html
```

## Run a subset

```bash
uv run pytest tests/api/routes/test_recipes.py
uv run pytest tests/api/routes/test_recipes.py::test_create_recipe
uv run pytest -k "shopping_list"
```

## Layout

- `tests/api/routes/` — FastAPI route integration tests (uses TestClient
  + a real Postgres database)
- `tests/crud/` — direct CRUD function tests
- `tests/services/` — service-layer tests (ingredient_image,
  recipe_import)
- `tests/scripts/` — prestart / setup utilities
- `tests/conftest.py` — shared fixtures: `client`,
  `superuser_token_headers`, `normal_user_token_headers`, `db`

## Mocking the LLM

When testing anything that calls into `app.services.recipe_import`,
patch at the submodule paths:

```python
with (
    patch("app.services.recipe_import.scraper.fetch_page", return_value=("text", None)),
    patch("app.services.recipe_import.llm.get_llm", return_value=llm_mock),
):
    ...
```

Do **not** patch `app.services.recipe_import._get_llm` or
`app.services.recipe_import._fetch_page` — those names are obsolete.

## Database

Tests require a running Postgres. With Docker Compose up, the test DB
is the same as the dev DB (`POSTGRES_DB=app`). The `client` fixture
applies Alembic migrations and seeds the superuser on first use.

## Linting and type-checking

```bash
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy app
```
