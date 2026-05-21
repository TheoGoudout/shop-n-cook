---
name: test-extension
description: Run the browser-extension test suite (Vitest) and type-check + build. Use when changes touch the extension/ workspace.
---

# Extension tests

The extension is a separate Bun workspace at `extension/` and uses
Vitest for unit tests.

## Run

```bash
cd extension
bun test                  # vitest run
bun test --watch          # vitest watch mode
```

## Type-check and build

```bash
cd extension
bunx tsc --noEmit         # type-check
bun run build             # vite build (writes to dist/)
```

CI (`test-extension.yml`) runs all three on every push.

## Specs

- `src/__tests__/api.test.ts` — ParsedRecipeToCreate transformation
- `src/__tests__/storage.test.ts` — Chrome storage wrapper (mocked)

These are unit-level — content scripts, popup interactions, and message
passing are not currently covered.

## OpenAPI client

Same generator as the frontend; regenerate with:

```bash
cd extension && bun run generate-client    # if present in package.json
```

Otherwise the extension uses the frontend's generated client via a
workspace symlink — check `extension/package.json` for the exact
arrangement.

## Auto-publishing

`publish-extension.yml` runs on release tags and publishes to Chrome,
Firefox, Edge, Opera, and Safari stores. Local testing only — don't
attempt to invoke the publish workflow manually.
