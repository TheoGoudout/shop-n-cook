import { expect, type Page, test } from "@playwright/test"

const uniqueTitle = () => `Playwright Recipe ${Date.now()}`

async function createRecipe(page: Page, title: string): Promise<string> {
  await page.getByRole("button", { name: /Add Recipe/i }).click()
  await expect(page.getByRole("dialog", { name: "Add Recipe" })).toBeVisible()
  await page.getByLabel(/Title/i).fill(title)
  await page.getByRole("button", { name: "Save" }).click()
  await expect(
    page.getByRole("dialog", { name: "Add Recipe" }),
  ).not.toBeVisible()
  await expect(page.getByRole("link", { name: title })).toBeVisible()
  const href = await page
    .getByRole("link", { name: title })
    .getAttribute("href")
  return href!.split("/").pop()!
}

async function deleteRecipeFromDetail(page: Page): Promise<void> {
  // The recipe actions menu lives in the page; the header holds the theme and
  // account menus
  await page.getByRole("main").locator('button[aria-haspopup="menu"]').click()
  await page.getByRole("menuitem", { name: /Delete/i }).click()
  await page
    .getByRole("button", { name: /Delete/i })
    .last()
    .click()
}

test.describe("Recipes list page", () => {
  test("shows heading and Add Recipe button", async ({ page }) => {
    await page.goto("/recipes")
    await expect(page.getByRole("heading", { name: "Recipes" })).toBeVisible()
    await expect(
      page.getByRole("button", { name: /Add Recipe/i }),
    ).toBeVisible()
  })

  test("shows validation error when title is empty", async ({ page }) => {
    await page.goto("/recipes")
    await page.getByRole("button", { name: /Add Recipe/i }).click()
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText(/Title is required/i)).toBeVisible()
  })

  test("adds a recipe successfully and shows it in the list", async ({
    page,
  }) => {
    const title = uniqueTitle()
    await page.goto("/recipes")
    const id = await createRecipe(page, title)

    // Cleanup
    await page.goto(`/recipes/${id}`)
    await deleteRecipeFromDetail(page)
  })
})

test.describe("Recipe detail page — client-side navigation", () => {
  test("navigates to detail when clicking the recipe title link", async ({
    page,
  }) => {
    const title = uniqueTitle()
    await page.goto("/recipes")
    const id = await createRecipe(page, title)

    await page.getByRole("link", { name: title }).click()
    await page.waitForURL(`/recipes/${id}`)
    await expect(
      page.getByRole("heading", { name: title, level: 1 }),
    ).toBeVisible()

    await deleteRecipeFromDetail(page)
  })

  test("detail page shows Ingredients and Instructions cards", async ({
    page,
  }) => {
    const title = uniqueTitle()
    await page.goto("/recipes")
    const id = await createRecipe(page, title)

    await page.goto(`/recipes/${id}`)
    await expect(
      page
        .locator('[data-slot="card-title"]')
        .filter({ hasText: "Ingredients" }),
    ).toBeVisible()
    await expect(
      page
        .locator('[data-slot="card-title"]')
        .filter({ hasText: "Instructions" }),
    ).toBeVisible()

    await deleteRecipeFromDetail(page)
  })
})

test.describe("Recipe detail page — direct URL navigation", () => {
  test("loads correctly when opening the URL directly", async ({ page }) => {
    const title = uniqueTitle()
    await page.goto("/recipes")
    const id = await createRecipe(page, title)

    // Navigate away then back via direct URL (simulates opening in a new tab)
    await page.goto("/")
    await page.goto(`/recipes/${id}`)
    await expect(
      page.getByRole("heading", { name: title, level: 1 }),
    ).toBeVisible()

    await deleteRecipeFromDetail(page)
  })

  test("back button returns to the recipes list", async ({ page }) => {
    const title = uniqueTitle()
    await page.goto("/recipes")
    const id = await createRecipe(page, title)

    await page.goto(`/recipes/${id}`)
    await page.getByRole("link", { name: /Back to Recipes/i }).click()
    await expect(page).toHaveURL("/recipes")
    await expect(page.getByRole("heading", { name: "Recipes" })).toBeVisible()

    // Cleanup
    await page.goto(`/recipes/${id}`)
    await deleteRecipeFromDetail(page)
  })
})

test.describe("Add a recipe to a shopping list", () => {
  test("adds the recipe from its detail page to the chosen list", async ({
    page,
  }) => {
    const listName = `Playwright List ${Date.now()}`
    await page.goto("/shopping-lists")
    await page.getByRole("button", { name: /New List/i }).click()
    await page.getByLabel(/Name/i).fill(listName)
    await page.getByRole("button", { name: "Create" }).click()
    await expect(page.getByText(listName)).toBeVisible()

    const title = uniqueTitle()
    await page.goto("/recipes")
    const id = await createRecipe(page, title)
    await page.goto(`/recipes/${id}`)

    await page.getByRole("button", { name: "Add to shopping list" }).click()
    const dialog = page.getByRole("dialog", { name: "Add to shopping list" })
    await expect(dialog).toBeVisible()
    await dialog.getByRole("combobox").click()
    await page.getByRole("option", { name: listName }).click()
    await dialog.getByLabel("Servings").fill("2")
    await dialog.getByRole("button", { name: "Add" }).click()
    await expect(dialog).not.toBeVisible()
    await expect(page.getByText(`Added to “${listName}”`)).toBeVisible()

    await page.goto("/shopping-lists")
    await page
      .locator("[data-slot='card']")
      .filter({ hasText: listName })
      .getByRole("link", { name: /Open/i })
      .click()
    await page.getByRole("tab", { name: /Meals/i }).click()
    await expect(page.getByText(title)).toBeVisible()

    await page.goto(`/recipes/${id}`)
    await deleteRecipeFromDetail(page)
  })

  test("opens from a recipe card without following the card link", async ({
    page,
  }) => {
    const title = uniqueTitle()
    await page.goto("/recipes")
    const id = await createRecipe(page, title)

    await page
      .locator("article")
      .filter({ hasText: title })
      .getByRole("button", { name: "Add to shopping list" })
      .click()
    await expect(
      page.getByRole("dialog", { name: "Add to shopping list" }),
    ).toBeVisible()
    await expect(page).toHaveURL("/recipes")
    await page.getByRole("button", { name: "Cancel" }).click()

    await page.goto(`/recipes/${id}`)
    await deleteRecipeFromDetail(page)
  })
})
