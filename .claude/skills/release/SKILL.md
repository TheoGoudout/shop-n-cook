---
name: release
description: Information about how Shop'n'Cook releases work. Use when the user asks how to bump the version, what publishes happen on a tag, or how to roll out a new build to extension stores / app stores.
---

# Release process

Shop'n'Cook follows semantic versioning. Version numbers are kept in
lockstep across:

- Root `package.json`
- `frontend/package.json`
- `extension/package.json`
- `backend/pyproject.toml`
- `extension/public/manifest.json` (auto-injected by the extension Vite
  plugin from `extension/package.json`)

## Bumping the version

The `bump-version.yml` workflow is **manually dispatched** (workflow_dispatch).
It accepts a `version` input (e.g. `1.5.0`), updates all the files above,
commits the change on `master` as `chore: bump version to <X.Y.Z>`, and
creates a Git tag.

**Don't bump versions in a feature PR** — bumps land on `master` via the
workflow after a release-worthy set of changes has merged.

## What runs on a tag

The Git tag created by `bump-version.yml` triggers:

1. `publish-extension.yml` — builds the extension and submits to:
   - Chrome Web Store
   - Firefox Add-ons (AMO)
   - Microsoft Edge Add-ons
   - Opera Add-ons
   - Safari (App Store via Xcode + altool)

2. `publish-stores.yml` — submits the mobile wrappers:
   - Google Play (via Bubblewrap-built AAB)
   - F-Droid (metadata-only, F-Droid builds from source)
   - Apple App Store (iOS wrapper)

All stores require pre-configured secrets in the repository settings
(`CHROME_REFRESH_TOKEN`, `AMO_API_KEY`, `APPLE_API_KEY`, etc.). See
`.github/workflows/publish-extension.yml` for the full list.

## Backend / frontend release

The backend and frontend deploy continuously from `master` via Coolify
— there is **no tagged release** for them. A version bump is purely
about the public-facing extension and mobile builds.

## Pre-release checklist

Before triggering `bump-version.yml`:

1. `master` is green in CI (pre-commit, test-backend, playwright,
   test-extension, test-docker-compose).
2. `release-notes.md` is updated with the new version's changes.
3. Coolify has deployed the latest backend/frontend successfully.
4. Manual smoke-test of the live site for the major flows
   (login, add recipe, add to shopping list).

## Reverting

If a release goes bad, the safest rollback is to bump again to a new
patch version with the fix included. Coolify keeps previous backend
deploys around for fast revert.
