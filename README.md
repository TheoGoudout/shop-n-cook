# Shop n Cook

[![GreenSecOps](http://localhost:8000/api/v1/badges/TheoGoudout/shop-n-cook/master.svg)](http://localhost:5173/repositories/d6aa51a2-62d6-4a5a-8458-04296416695f)

A full-stack web application for managing recipes, ingredients, and shopping lists — with AI-powered recipe import.

## Technology Stack and Features

- [**FastAPI**](https://fastapi.tiangolo.com) for the Python backend API.
  - [SQLModel](https://sqlmodel.tiangolo.com) for the Python SQL database interactions (ORM).
  - [Pydantic](https://docs.pydantic.dev), used by FastAPI, for data validation and settings management.
  - [PostgreSQL](https://www.postgresql.org) as the SQL database.
  - [LangChain](https://www.langchain.com) for AI-powered recipe import (Anthropic, OpenAI, or Google).
- [React](https://react.dev) for the frontend.
  - TypeScript, hooks, [Vite](https://vitejs.dev), and other parts of a modern frontend stack.
  - [Tailwind CSS](https://tailwindcss.com) and [shadcn/ui](https://ui.shadcn.com) for components.
  - [Recharts](https://recharts.org) for dashboard data visualizations.
  - [i18next](https://www.i18next.com) for internationalization (English and French).
  - [vite-plugin-pwa](https://vite-pwa-org.netlify.app) for Progressive Web App support.
  - An automatically generated frontend client (OpenAPI-TS).
  - [Playwright](https://playwright.dev) for End-to-End testing.
  - Dark mode support.
- A [browser extension](./extension/) for one-click recipe import (Chrome, Firefox, Edge, Opera, Safari).
  - Built with TypeScript and [Bun](https://bun.sh), sharing the same OpenAPI-generated client.
  - Published automatically to all major browser stores on each GitHub release.
- [Docker Compose](https://www.docker.com) for development and production.
- Secure password hashing by default.
- JWT (JSON Web Token) authentication.
- Email-based password recovery.
- [Mailcatcher](https://mailcatcher.me) for local email testing during development.
- Tests with [Pytest](https://pytest.org).
- CI (continuous integration) with GitHub Actions; CD via [Coolify](https://coolify.io) GitHub App.

## Application Features

### Recipe Management
Create and manage recipes with structured ingredient lists (quantities, units, notes). Supports full CRUD operations. Recipes can be marked public or private — public recipes are accessible without an account.

### AI Recipe Import
Import recipes automatically from any URL. The backend fetches the page, parses it with an LLM, and returns a structured recipe ready to save. Supports Anthropic, OpenAI, and Google Gemini as AI providers.

### Recipe Search
Search recipes by title and description from the recipe list.

### Browser Extension
Import recipes into Shop n Cook with one click while browsing the web. Available for Chrome, Firefox, Edge, Opera, and Safari.

### PWA & Web Share Target
Install the app as a Progressive Web App on mobile or desktop. On mobile, you can share any recipe URL directly to Shop n Cook via the system share sheet to trigger an instant import.

### Shopping List Management
Create shopping lists from your recipes. Adding a recipe to a list automatically populates it with the required ingredients. Track item completion as you shop.

### Household Settings
Configure household size, shopping frequency (daily, weekly, monthly), and budget preferences per user.

### Profile Pages
Each user has a public profile page listing their public recipes.

### Dashboard
A stats overview showing total counts for recipes, ingredients, and shopping lists, with a bar chart visualization.

### Internationalization
The interface is available in English and French, with automatic language detection from the browser.

## Quick Start

```bash
# Clone the repository
git clone git@github.com:theogoudout/shop-n-cook.git
cd shop-n-cook

# Set up environment variables
cp .env.example .env
# Edit .env and fill in your SECRET_KEY, POSTGRES_PASSWORD, FIRST_SUPERUSER_PASSWORD
# and an AI provider API key (ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY)

# Start the stack
docker compose watch
```

Open your browser at:
- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs

### Generate Secret Keys

For environment variables that require a secret key, generate one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Backend Development

Backend docs: [backend/README.md](./backend/README.md).

## Frontend Development

Frontend docs: [frontend/README.md](./frontend/README.md).

## Deployment

Deployment docs: [deployment.md](./deployment.md).

## Development

General development docs: [development.md](./development.md).

This includes using Docker Compose, Mailcatcher, local development servers, `.env` configuration, and pre-commit hooks.

## Release Notes

Check the file [release-notes.md](./release-notes.md).

## For AI assistants

If you're an AI assistant (Claude Code, Cursor, etc.) working in this repo,
see [CLAUDE.md](./CLAUDE.md) for project conventions: the shared primitives
(`<RecipeForm>`, `<UnitSelect>`, `<ConfirmDialog>`, `useCrudMutation`),
the recipe-import package layout, i18n rules, pre-commit hooks, and the
CI pipelines. Claude Code skills covering common workflows live under
[`.claude/skills/`](./.claude/skills/).

## License

The Shop n Cook project is licensed under the terms of the MIT license.
