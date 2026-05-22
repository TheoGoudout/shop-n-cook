# Contributing

Thank you for your interest in contributing to Shop n Cook!

## Discussions First

For **big changes** (new features, architectural changes, significant refactoring), please start by opening a [GitHub Discussion](https://github.com/theogoudout/shop-n-cook/discussions) first. This allows the maintainers to provide feedback on the approach before you invest significant time in implementation.

For small, straightforward changes, you can go directly to a Pull Request without starting a discussion first. This includes:

- Typos and grammatical fixes
- Small reproducible bug fixes
- Fixing lint warnings or type errors
- Minor code improvements (e.g., removing unused code)

## Developing

For detailed instructions on setting up your development environment, running the stack, linting, pre-commit hooks, and more, see the [Development Guide](development.md).

## Conventions

Before adding new UI or backend code, please skim [CLAUDE.md](./CLAUDE.md) for
the project's conventions and shared primitives. Common patterns:

- Use `useCrudMutation` for mutations that follow the success-toast /
  error-toast / invalidate-key pattern.
- Use `<ConfirmDialog>` for destructive confirmation flows.
- Use `<UnitSelect>` for any unit picker — read units from
  `UnitSchema.enum`, never hardcode.
- Use `<RecipeForm>` (via `AddRecipe` / `EditRecipe`) when extending the
  recipe shape — update `recipeFormSchema.ts` in one place.
- Backend public schemas are built via the `*_to_public` helpers in
  `crud/recipe.py` and `crud/shopping_list.py` — reuse them.
- New i18n strings must land in both `en` and `fr` locale files in the
  same commit.
- Visual tokens are OKLCH-based and exposed as Tailwind utility classes
  (`bg-primary`, `text-destructive`, …). See
  [VISUAL_IDENTITY.md](./VISUAL_IDENTITY.md) — never hardcode hex.

## Pull Requests

When submitting a pull request:

1. Make sure all tests pass before submitting.
2. Keep PRs focused on a single change.
3. Update tests if you're changing functionality.
4. Reference any related issues in your PR description.
5. Never use `git commit --no-verify` — if a pre-commit hook fails, fix
   the underlying issue.

## Questions?

If you have questions about contributing, feel free to open a [GitHub Discussion](https://github.com/theogoudout/shop-n-cook/discussions).
