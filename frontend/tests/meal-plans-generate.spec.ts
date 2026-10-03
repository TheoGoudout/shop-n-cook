import { expect, type Page, test } from "@playwright/test"

const API = process.env.VITE_API_URL ?? "http://localhost:8000"

/** Make sure the library has something to compose a menu from. */
async function seedRecipes(page: Page): Promise<void> {
  await page.goto("/")
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  for (let i = 0; i < 4; i++) {
    const response = await page.request.post(`${API}/api/v1/recipes/`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        title: `Playwright Menu Recipe ${Date.now()}-${i}`,
        servings: 2,
        ingredients: [],
      },
    })
    expect(response.ok()).toBeTruthy()
  }
}

test.describe("Generate a menu", () => {
  test.beforeEach(async ({ page }) => {
    await seedRecipes(page)
  })

  test("is reached from the meal plans page", async ({ page }) => {
    await page.goto("/meal-plans")
    await page.getByRole("link", { name: "Generate a menu" }).first().click()
    await expect(page).toHaveURL(/\/meal-plans\/generate$/)
    await expect(
      page.getByRole("heading", { name: "Generate a menu" }),
    ).toBeVisible()
  })

  test("proposes a menu as soon as the page opens", async ({ page }) => {
    await page.goto("/meal-plans/generate")
    await expect(page.getByText("Estimated cost")).toBeVisible()
    await expect(
      page.getByRole("button", { name: "Create menu" }),
    ).toBeEnabled()
  })

  test("portions can be changed per meal", async ({ page }) => {
    await page.goto("/meal-plans/generate")
    await page.locator("#gen-servings").fill("2")
    await page
      .getByRole("button", { name: "Generate a new menu" })
      .first()
      .click()
    await expect(page.getByText("Estimated cost")).toBeVisible()

    const firstStepper = page
      .getByRole("group", { name: /^Portions of/ })
      .first()
    await expect(firstStepper.getByText("2 portions")).toBeVisible()
    await firstStepper.getByRole("button", { name: "More portions" }).click()
    await expect(firstStepper.getByText("3 portions")).toBeVisible()
  })

  test("changing preferences flags the menu as out of date", async ({
    page,
  }) => {
    await page.goto("/meal-plans/generate")
    await expect(page.getByText("Estimated cost")).toBeVisible()
    await page.getByRole("button", { name: "Cook for 2" }).click()
    await expect(
      page.getByText("Your preferences changed since this menu was made."),
    ).toBeVisible()
    await expect(
      page.getByRole("button", { name: "Create menu" }),
    ).toBeDisabled()
  })

  test("batch cooking plans leftovers and saves them", async ({ page }) => {
    await page.goto("/meal-plans/generate")
    await expect(page.getByText("Estimated cost")).toBeVisible()
    await page.getByRole("button", { name: "Cook for 2" }).click()
    await page
      .getByRole("button", { name: "Generate a new menu" })
      .first()
      .click()
    await expect(
      page.getByText("Leftovers", { exact: true }).first(),
    ).toBeVisible()

    await page.getByRole("button", { name: "Create menu" }).click()
    await expect(page).toHaveURL(/\/meal-plans\/[0-9a-f-]{36}$/)
    await expect(page.getByText(/^Leftovers from /).first()).toBeVisible()
  })
})
