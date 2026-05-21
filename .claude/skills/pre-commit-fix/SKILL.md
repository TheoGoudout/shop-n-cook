---
name: pre-commit-fix
description: Run and fix the project's pre-commit hooks (ruff, mypy, biome, OpenAPI client regen). Use when commits are blocked by hook failures or before opening a PR.
---

# Pre-commit hooks

The project uses `prek` (a faster reimplementation of pre-commit). Hooks
are defined in `.pre-commit-config.yaml`:

- `ruff check` and `ruff format` (Python)
- `mypy --strict` (Python, excludes alembic)
- `biome check` (TypeScript / JavaScript / JSON)
- OpenAPI client regen check (both `frontend/` and `extension/`)

## Run all hooks against the whole tree

```bash
prek run --all-files
```

## Run a single hook

```bash
prek run ruff --all-files
prek run biome --all-files
prek run mypy --all-files
```

## Common failures and fixes

**`ruff` complains about formatting**:
```bash
cd backend && uv run ruff format app tests
```

**`ruff` complains about lint rules** (unused imports, etc.):
```bash
cd backend && uv run ruff check --fix app tests
```

**`mypy` complains about types**: read the error; common causes:
- Missing `Optional` / `| None` on a default-None field
- SQLModel relationships need `# type: ignore[arg-type]` on
  `selectinload(...)` (existing pattern in the codebase)
- A new helper needs return type annotation

**`biome` complains**:
```bash
cd frontend && bun run lint
# or: ../node_modules/.bin/biome check --write src/
```

**OpenAPI client out of sync**:
```bash
cd frontend && bun run generate-client
```
Backend must be running for this to work.

## Don't bypass

**Never** commit with `--no-verify`. If a hook is blocking work, fix
the underlying issue. If a hook is fundamentally broken or
misconfigured, that's a real bug worth raising — but bypass is not the
answer.
