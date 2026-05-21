---
name: dev-up
description: Bring up the local Shop'n'Cook development stack. Use when the user asks to start the app, run locally, spin up Docker, or test changes against a running backend.
---

# Bring up the local stack

Shop'n'Cook runs as a Docker Compose stack:
- `db` — Postgres 18
- `mailcatcher` — local SMTP sink (UI on port 1080)
- `prestart` — runs Alembic migrations + seeds the first superuser
- `backend` — FastAPI on port 8000
- `frontend` — Vite dev server on port 5173

## First-time setup

```bash
cp .env.example .env
```

Fill in at minimum: `FIRST_SUPERUSER_PASSWORD`, `POSTGRES_PASSWORD`,
`SECRET_KEY`, and (if recipe import is to be tested) one of
`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` with the
matching `AI_PROVIDER`.

## Start

```bash
docker compose up -d
docker compose logs -f backend frontend   # tail
```

URLs:
- Frontend: http://localhost:5173
- Backend OpenAPI docs: http://localhost:8000/docs
- Mailcatcher: http://localhost:1080
- Adminer (if enabled): http://localhost:8080

The dev override (`compose.override.yml`) mounts source into both
containers and enables auto-reload — no rebuild needed for code changes.

## Stop

```bash
docker compose down       # keep volumes
docker compose down -v    # nuke volumes (resets the database)
```

## Further reading

`development.md` at the repo root covers Mailcatcher, pre-commit
setup with `prek`, and VS Code debugging.
