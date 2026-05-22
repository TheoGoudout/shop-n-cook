# Shop n Cook - Frontend

The frontend is built with [Vite](https://vitejs.dev/), [React](https://reactjs.org/), [TypeScript](https://www.typescriptlang.org/), [TanStack Query](https://tanstack.com/query), [TanStack Router](https://tanstack.com/router), [Tailwind CSS](https://tailwindcss.com/), [i18next](https://www.i18next.com/) for internationalization, and [vite-plugin-pwa](https://vite-pwa-org.netlify.app) for PWA support.

## Requirements

- [Bun](https://bun.sh/) (recommended) or [Node.js](https://nodejs.org/)

## Quick Start

```bash
bun install
bun run dev
```

* Then open your browser at http://localhost:5173/.

Notice that this live server is not running inside Docker, it's for local development, and that is the recommended workflow. Once you are happy with your frontend, you can build the frontend Docker image and start it, to test it in a production-like environment. But building the image at every change will not be as productive as running the local development server with live reload.

Check the file `package.json` to see other available options.

### Removing the frontend

If you are developing an API-only app and want to remove the frontend, you can do it easily:

* Remove the `./frontend` directory.

* In the `compose.yml` file, remove the whole service / section `frontend`.

* In the `compose.override.yml` file, remove the whole service / section `frontend` and `playwright`.

Done, you have a frontend-less (api-only) app. 🤓

---

If you want, you can also remove the `FRONTEND` environment variables from:

* `.env`
* `./scripts/*.sh`

But it would be only to clean them up, leaving them won't really have any effect either way.

## Generate Client

### Automatically

* Activate the backend virtual environment.
* From the top level project directory, run the script:

```bash
bash ./scripts/generate-client.sh
```

This script generates the OpenAPI client for **both** the frontend and the browser extension, then runs the linter. Commit all generated changes together.

### Manually

* Start the Docker Compose stack.

* Download the OpenAPI JSON file from `http://localhost/api/v1/openapi.json` and copy it to a new file `openapi.json` at the root of the `frontend` directory.

* To generate the frontend client, run:

```bash
bun run generate-client
```

* Commit the changes.

Notice that everytime the backend changes (changing the OpenAPI schema), you should follow these steps again to update the frontend client.

## Using a Remote API

If you want to use a remote API, you can set the environment variable `VITE_API_URL` to the URL of the remote API. For example, you can set it in the `frontend/.env` file:

```env
VITE_API_URL=https://api.my-domain.example.com
```

Then, when you run the frontend, it will use that URL as the base URL for the API.

## Code Structure

The frontend code is structured as follows:

* `frontend/src` - The main frontend code.
* `frontend/src/assets` - Static assets.
* `frontend/src/client` - The generated OpenAPI client (auto-generated from backend OpenAPI schema). **Never hand-edit.**
* `frontend/src/components` - The different components of the frontend:
  * `Recipes/` - Recipe list, detail, action menu, and the Add/Edit flow:
    * `AddRecipe.tsx` / `EditRecipe.tsx` are thin wrappers around the shared `RecipeForm.tsx`.
    * `recipeFormSchema.ts` owns the Zod schema factory, `defaultCreateValues`, `buildEditDefaults`, and the `toRecipeCreatePayload` / `toRecipeUpdatePayload` mappers.
    * `RecipeImportPanel.tsx` is the decoupled URL-import box used by `AddRecipe`.
  * `ShoppingLists/` - List cards and per-list dialogs (`ShoppingListCard`, `AddItemDialog`, `AddRecipeDialog`, `RenameListDialog`).
  * `Dashboard/` - Stats overview and bar chart (Recharts).
  * `UserSettings/` - Profile, household settings, and account deletion.
  * `Admin/` - Admin user and ingredient management panel.
  * `Sidebar/` - App sidebar layout and navigation components.
  * `Pending/` - Loading skeleton placeholder components.
  * `Common/` - Shared UI components:
    * `ConfirmDialog.tsx` — destructive/confirm dialog for delete + confirm flows.
    * `UnitSelect.tsx` — unit picker backed by `UnitSchema.enum` from the OpenAPI client.
    * `DataTable.tsx`, `AuthLayout.tsx`, `Footer.tsx`, `Logo.tsx`, `NotFound.tsx`, `ErrorComponent.tsx`, `Appearance.tsx`.
  * `ui/` - shadcn/ui base components (do not hand-edit; regenerate via `npx shadcn add`).
* `frontend/src/hooks` - Custom React hooks (`useAuth`, `useCustomToast`, `useCrudMutation`, `useUnitSystem`, `useIngredientCatalog`, `useMobile`, `useCopyToClipboard`).
* `frontend/src/i18n` - Internationalization setup and locale files under `locales/{en,fr}/<namespace>.json`. Every new key must land in both locales.
* `frontend/src/routes` - File-based TanStack Router pages (the route tree is auto-regenerated at `routeTree.gen.ts`).

### Shared primitives to reuse

When adding new UI, prefer composing these over re-implementing the pattern:

* `useCrudMutation({ mutationFn, invalidateKeys, successMessage, onSuccess })` — wraps `useMutation` with the standard success-toast / error-toast / invalidate-key plumbing. Supports `invalidateKeys: QueryKey | QueryKey[]`.
* `<ConfirmDialog variant="destructive" />` — for any "are you sure?" flow. Supports both controlled mode and a `trigger` slot (e.g. a `DropdownMenuItem`).
* `<UnitSelect />` — for any unit picker. Never hardcode a unit list.
* `<RecipeForm mode="create" | "edit" />` — when extending the recipe shape, update `RecipeFormValues`, `createRecipeFormSchema`, `defaultCreateValues`, `buildEditDefaults`, and both payload mappers in `recipeFormSchema.ts`.

## End-to-End Testing with Playwright

The frontend includes initial end-to-end tests using Playwright. To run the tests, you need to have the Docker Compose stack running. Start the stack with the following command:

```bash
docker compose up -d --wait backend
```

Then, you can run the tests with the following command:

```bash
bunx playwright test
```

You can also run your tests in UI mode to see the browser and interact with it running:

```bash
bunx playwright test --ui
```

To stop and remove the Docker Compose stack and clean the data created in tests, use the following command:

```bash
docker compose down -v
```

To update the tests, navigate to the tests directory and modify the existing test files or add new ones as needed.

For more information on writing and running Playwright tests, refer to the official [Playwright documentation](https://playwright.dev/docs/intro).
