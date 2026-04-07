# Shop n Cook - Deployment

Shop n Cook is deployed via [Coolify](https://coolify.io), a self-hosted PaaS that manages Docker Compose deployments.

## Automated Deployment

Pushing to the `master` branch triggers an automatic deployment via the GitHub Actions workflow in `.github/workflows/deploy.yml`. The workflow sends a webhook request to Coolify, which pulls the latest code and redeploys the stack.

### Required GitHub Secret

| Secret | Description |
|--------|-------------|
| `COOLIFY_DEPLOY_WEBHOOK` | The deploy webhook URL from your Coolify application settings |

## Environment Variables

In production, set the following environment variables in your Coolify application (or equivalent). See `.env.example` for descriptions of each variable.

### Required

| Variable | Description |
|----------|-------------|
| `PROJECT_NAME` | Application name (e.g. `"Shop n Cook"`) |
| `ENVIRONMENT` | Set to `production` |
| `FRONTEND_HOST` | Public URL of the frontend (e.g. `https://app.example.com`) |
| `SECRET_KEY` | Random secret key — generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `FIRST_SUPERUSER` | Email of the first admin user |
| `FIRST_SUPERUSER_PASSWORD` | Password of the first admin user |
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | PostgreSQL database name |
| `VITE_API_URL` | Public URL of the backend API (e.g. `https://api.example.com`) |
| `VITE_PROJECT_NAME` | Project name shown in the browser tab |

### AI Recipe Import

| Variable | Description |
|----------|-------------|
| `AI_PROVIDER` | `anthropic`, `openai`, or `google` |
| `ANTHROPIC_API_KEY` | Required if using Anthropic |
| `ANTHROPIC_MODEL` | Anthropic model ID (default: `claude-haiku-4-5-20251001`) |
| `OPENAI_API_KEY` | Required if using OpenAI |
| `OPENAI_MODEL` | OpenAI model ID (default: `gpt-4o-mini`) |
| `GOOGLE_API_KEY` | Required if using Google Gemini |
| `GOOGLE_MODEL` | Google model ID (default: `gemini-2.0-flash`) |

### Optional

| Variable | Description |
|----------|-------------|
| `SENTRY_DSN` | Sentry DSN for error tracking |
| `SMTP_HOST` | SMTP server host for email sending |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |
| `EMAILS_FROM_EMAIL` | Sender email address |
| `LANGCHAIN_TRACING_V2` | Set to `true` to enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | LangSmith API key |

## Docker Compose

The production stack is defined in `compose.yml`. It includes:

- `db` — PostgreSQL 18
- `prestart` — Runs database migrations (`alembic upgrade head`) on startup
- `backend` — FastAPI application
- `frontend` — React application (built as a static Nginx container)

No reverse proxy is included in the Compose files — Coolify handles routing and HTTPS termination.
