---
name: regen-client
description: Regenerate the OpenAPI client for the frontend (and extension if relevant). Use whenever the backend's Pydantic/SQLModel schemas, route signatures, or response models change, or when types in src/client/ look stale.
---

# Regenerate the OpenAPI client

The frontend and extension both consume an auto-generated TypeScript
client at `frontend/src/client/` and `extension/src/client/`. These
files are sourced from the backend's `/api/v1/openapi.json`.

**Never hand-edit anything under `src/client/`.**

## When to regenerate

- Backend `app/models/*.py` changes (new field, renamed enum, etc.)
- Backend route signatures change (new endpoint, new query param,
  changed request body / response shape)
- A type error in the frontend/extension after pulling backend changes

## Procedure

The backend must be running OR `openapi.json` must be reachable. The
default config in `openapi-ts.config.ts` points at the local backend.

```bash
# Make sure backend is reachable (docker compose up -d)
cd frontend && bun run generate-client
cd extension && bun run generate-client    # if it has the script
```

After generation, run biome to fix imports and formatting:

```bash
cd frontend && bun run lint
```

Verify with a build:

```bash
cd frontend && bun run build
```

The pre-commit hook (`prek run --all-files`) also regenerates the
client and will fail CI if the committed files drift from the backend
spec.
