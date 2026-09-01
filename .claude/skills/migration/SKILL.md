---
name: migration
description: Create or apply an Alembic database migration. Use when the user adds a new column, renames a field, introduces a new model, changes an enum, or talks about altering the database schema.
---

# Database migrations

Migrations live in `backend/app/alembic/versions/` and are managed by
Alembic with autogeneration from the SQLModel metadata.

## Creating a migration

After editing a model under `backend/app/models/`:

```bash
cd backend
uv run alembic revision --autogenerate -m "<short description>"
```

**Always inspect the generated file** — Alembic autogeneration has known
blind spots:
- Enum value changes (Postgres enums need explicit `op.execute()`)
- Server-side defaults
- Index renames
- Column type changes that require a USING clause
- Cascade behavior on relationships

Edit the generated `op.*` calls to add anything Alembic missed, then run
`uv run ruff format app/alembic/versions/<file>.py` to format it.

## Enum-backed columns

SQLModel maps a Python enum field to SQLAlchemy's `Enum` type, which stores
the member **name**, not its value. `ImportSource.URL = "url"` is written to
the database as `URL`. Any literal a migration writes to such a column — a
backfill, a `server_default`, seeded rows — must use the name, or every read
of that row raises
`LookupError: 'url' is not among the defined enum values`.

`tests/models/test_enum_columns.py` scans the migrations for these literals
and fails on a mismatch.

## Applying

```bash
cd backend
uv run alembic upgrade head
```

In Docker, the `prestart` service runs migrations automatically each
time the stack comes up. To apply manually inside the running stack:

```bash
docker compose exec backend alembic upgrade head
```

## Downgrade

```bash
uv run alembic downgrade -1     # one revision back
uv run alembic downgrade <rev>  # to a specific revision
```

## Inspecting current state

```bash
uv run alembic current
uv run alembic history --verbose
```

## Tests

Migrations themselves are not unit-tested. Validate by:
1. Running `uv run alembic upgrade head` against a clean database
2. Running the full pytest suite (which uses the fully-migrated schema)
3. Running `uv run alembic downgrade -1 && uv run alembic upgrade head`
   to confirm the migration is reversible
