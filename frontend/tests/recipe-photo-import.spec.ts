import path from "node:path"
import { fileURLToPath } from "node:url"
import { expect, type Page, test } from "@playwright/test"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.join(__dirname, "fixtures", "recipe-page.jpg")
const IMPORT_PHOTOS_ROUTE = "**/api/v1/recipes/import-photos"

const PARSED_RECIPE = {
  title: "Tarte Tatin from a Photo",
  description: "Caramelised apple tart",
  servings: 6,
  prep_time_minutes: 25,
  cook_time_minutes: 40,
  source_url: null,
  image_url: null,
  seasons: ["autumn"],
  is_vegan: false,
  is_vegetarian: true,
  is_gluten_free: false,
  is_dairy_free: false,
  kcal_per_serving: 420,
  difficulty: "medium",
  meal_type: "dessert",
  cuisine_type: "French",
  ingredients: [
    {
      name: "sugar",
      name_en: "sugar",
      quantity: 150,
      unit: "g",
      notes: null,
      category: "other",
    },
    {
      name: "apples",
      name_en: "apples",
      quantity: 6,
      unit: "piece",
      notes: null,
      category: "fruits",
    },
  ],
  steps: [
    { instruction: "Caramelise the sugar.", ingredient_names: ["sugar"] },
    { instruction: "Arrange the apples on top.", ingredient_names: ["apples"] },
  ],
}

/** Stub the vision endpoint so the suite never spends a real model call. */
async function stubPhotoImport(
  page: Page,
  body: unknown = PARSED_RECIPE,
  status = 200,
): Promise<void> {
  await page.route(IMPORT_PHOTOS_ROUTE, (route) =>
    route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    }),
  )
}

async function openPhotoImportTab(page: Page): Promise<void> {
  await page.goto("/recipes")
  await page.getByRole("button", { name: /Add Recipe/i }).click()
  await expect(page.getByRole("dialog", { name: "Add Recipe" })).toBeVisible()
  await page.getByRole("tab", { name: /From photos/i }).click()
}

async function selectFixturePhotos(page: Page, count = 1): Promise<void> {
  await page
    .getByLabel("Choose images")
    .setInputFiles(Array.from({ length: count }, () => FIXTURE))
}

test.describe("Recipe import from photos", () => {
  test("fills the form from the parsed photos", async ({ page }) => {
    await stubPhotoImport(page)
    await openPhotoImportTab(page)
    await selectFixturePhotos(page, 2)

    await expect(page.getByText("2 photos selected")).toBeVisible()
    await page.getByRole("button", { name: "Import" }).click()

    await expect(page.getByLabel(/Title/i)).toHaveValue(
      "Tarte Tatin from a Photo",
    )
    await expect(page.getByText("Caramelise the sugar.")).toBeVisible()

    // Both ingredients came across, in order.
    const ingredientNames = page.getByPlaceholder("Ingredient name")
    await expect(ingredientNames).toHaveCount(2)
    await expect(ingredientNames.first()).toHaveValue("sugar")
    await expect(ingredientNames.last()).toHaveValue("apples")
  })

  test("requires consent before a photo import can be saved", async ({
    page,
  }) => {
    await stubPhotoImport(page)
    await openPhotoImportTab(page)
    await selectFixturePhotos(page)
    await page.getByRole("button", { name: "Import" }).click()
    await expect(page.getByLabel(/Title/i)).toHaveValue(
      "Tarte Tatin from a Photo",
    )

    // The consent gate now covers photo imports, which carry no source URL.
    const consent = page.getByRole("checkbox", { name: /third-party source/i })
    await expect(consent).toBeVisible()

    await page.getByRole("button", { name: "Save" }).click()
    await expect(
      page.getByText(/must confirm consent before importing/i),
    ).toBeVisible()
    await expect(page.getByRole("dialog", { name: "Add Recipe" })).toBeVisible()
  })

  test("uploads the photos as multipart form data", async ({ page }) => {
    // Guards the Content-Type interceptor in main.tsx: the generated client
    // sets a boundary-less multipart header, which the server cannot parse.
    let contentType: string | undefined
    await page.route(IMPORT_PHOTOS_ROUTE, (route) => {
      contentType = route.request().headers()["content-type"]
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(PARSED_RECIPE),
      })
    })

    await openPhotoImportTab(page)
    await selectFixturePhotos(page)
    await page.getByRole("button", { name: "Import" }).click()
    await expect(page.getByLabel(/Title/i)).toHaveValue(
      "Tarte Tatin from a Photo",
    )

    expect(contentType).toContain("multipart/form-data")
    expect(contentType).toContain("boundary=")
  })

  test("reports when no recipe could be read", async ({ page }) => {
    await stubPhotoImport(page, { detail: "no_recipe_found" }, 422)
    await openPhotoImportTab(page)
    await selectFixturePhotos(page)
    await page.getByRole("button", { name: "Import" }).click()

    await expect(page.getByText(/No recipe could be read/i)).toBeVisible()
  })

  test("refuses more than three photos", async ({ page }) => {
    await openPhotoImportTab(page)
    await selectFixturePhotos(page, 4)

    await expect(page.getByText(/at most 3 photos/i)).toBeVisible()
    await expect(page.getByText("3 photos selected")).toBeVisible()
  })

  test("a photo can be removed before importing", async ({ page }) => {
    await openPhotoImportTab(page)
    await selectFixturePhotos(page, 2)
    await expect(page.getByText("2 photos selected")).toBeVisible()

    await page.getByRole("button", { name: "Remove photo" }).first().click()
    await expect(page.getByText("1 photo selected")).toBeVisible()
  })

  test("the URL import tab still works", async ({ page }) => {
    await page.route("**/api/v1/recipes/import-url", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...PARSED_RECIPE,
          title: "Tarte Tatin from a URL",
          source_url: "https://example.com/tarte-tatin",
        }),
      }),
    )

    await page.goto("/recipes")
    await page.getByRole("button", { name: /Add Recipe/i }).click()
    await expect(page.getByRole("dialog", { name: "Add Recipe" })).toBeVisible()

    await page
      .getByPlaceholder(/Paste a recipe URL/i)
      .fill("https://example.com/tarte-tatin")
    await page.getByRole("button", { name: "Import" }).click()

    await expect(page.getByLabel(/Title/i)).toHaveValue(
      "Tarte Tatin from a URL",
    )
  })
})
