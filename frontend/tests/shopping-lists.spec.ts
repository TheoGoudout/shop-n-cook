import { type Page, expect, test } from "@playwright/test"

const uniqueName = () => `Playwright List ${Date.now()}`

async function createList(page: Page, name: string): Promise<string> {
  await page.getByRole("button", { name: /New List/i }).click()
  await expect(
    page.getByRole("dialog", { name: "New Shopping List" }),
  ).toBeVisible()
  await page.getByLabel(/Name/i).fill(name)
  await page.getByRole("button", { name: "Create" }).click()
  await expect(
    page.getByRole("dialog", { name: "New Shopping List" }),
  ).not.toBeVisible()
  await expect(page.getByText(name)).toBeVisible()

  // Capture list ID from the Open link in the newest card
  const openLink = page.getByRole("link", { name: /Open/i }).last()
  const href = await openLink.getAttribute("href")
  return href!.split("/").pop()!
}

async function deleteListFromCard(page: Page, name: string): Promise<void> {
  // The card header has two icon buttons: pencil (rename) then trash (delete)
  const card = page.locator("[data-slot='card']").filter({ hasText: name })
  await card.locator("button").nth(1).click()
  await page.getByRole("button", { name: /Delete/i }).last().click()
}

test.describe("Shopping lists page", () => {
  test("shows heading and New List button", async ({ page }) => {
    await page.goto("/shopping-lists")
    await expect(
      page.getByRole("heading", { name: "Shopping Lists" }),
    ).toBeVisible()
    await expect(page.getByRole("button", { name: /New List/i })).toBeVisible()
  })

  test("New List dialog pre-fills a week-based default name", async ({
    page,
  }) => {
    await page.goto("/shopping-lists")
    await page.getByRole("button", { name: /New List/i }).click()
    await expect(
      page.getByRole("dialog", { name: "New Shopping List" }),
    ).toBeVisible()

    const value = await page.getByLabel(/Name/i).inputValue()
    expect(value).toMatch(/Week #\d+/)

    await page.getByRole("button", { name: "Cancel" }).click()
  })

  test("New List dialog pre-fills start and end dates for the current week", async ({
    page,
  }) => {
    await page.goto("/shopping-lists")
    await page.getByRole("button", { name: /New List/i }).click()

    const startDate = await page.getByLabel(/Start date/i).inputValue()
    const endDate = await page.getByLabel(/End date/i).inputValue()
    expect(startDate).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(endDate).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(new Date(endDate).getTime()).toBeGreaterThan(
      new Date(startDate).getTime(),
    )

    await page.getByRole("button", { name: "Cancel" }).click()
  })

  test("creates a shopping list successfully", async ({ page }) => {
    const name = uniqueName()
    await page.goto("/shopping-lists")
    const id = await createList(page, name)
    await deleteListFromCard(page, name)
  })
})

test.describe("Shopping list detail page — client-side navigation", () => {
  test("navigates to detail page when clicking the list name link", async ({
    page,
  }) => {
    const name = uniqueName()
    await page.goto("/shopping-lists")
    const id = await createList(page, name)

    await page.getByRole("link", { name }).click()
    await page.waitForURL(`/shopping-lists/${id}`)
    await expect(page.getByRole("heading", { name })).toBeVisible()

    await page.getByRole("link", { name: /Back to Shopping Lists/i }).click()
    await deleteListFromCard(page, name)
  })

  test("navigates to detail page when clicking Open", async ({ page }) => {
    const name = uniqueName()
    await page.goto("/shopping-lists")
    const id = await createList(page, name)

    const card = page
      .locator("[data-slot='card']")
      .filter({ hasText: name })
    await card.getByRole("link", { name: /Open/i }).click()
    await page.waitForURL(`/shopping-lists/${id}`)
    await expect(page.getByRole("heading", { name })).toBeVisible()

    await page.getByRole("link", { name: /Back to Shopping Lists/i }).click()
    await deleteListFromCard(page, name)
  })

  test("detail page shows Shopping and Meals tabs", async ({ page }) => {
    const name = uniqueName()
    await page.goto("/shopping-lists")
    const id = await createList(page, name)

    await page.goto(`/shopping-lists/${id}`)
    await expect(page.getByRole("tab", { name: /Shopping/i })).toBeVisible()
    await expect(page.getByRole("tab", { name: /Meals/i })).toBeVisible()

    await page.getByRole("link", { name: /Back to Shopping Lists/i }).click()
    await deleteListFromCard(page, name)
  })
})

test.describe("Shopping list detail page — direct URL navigation", () => {
  test("loads correctly when opening the URL directly", async ({ page }) => {
    const name = uniqueName()
    await page.goto("/shopping-lists")
    const id = await createList(page, name)

    // Navigate away then back via direct URL
    await page.goto("/")
    await page.goto(`/shopping-lists/${id}`)
    await expect(page.getByRole("heading", { name })).toBeVisible()

    await page.getByRole("link", { name: /Back to Shopping Lists/i }).click()
    await deleteListFromCard(page, name)
  })

  test("back button returns to the shopping lists page", async ({ page }) => {
    const name = uniqueName()
    await page.goto("/shopping-lists")
    const id = await createList(page, name)

    await page.goto(`/shopping-lists/${id}`)
    await page.getByRole("link", { name: /Back to Shopping Lists/i }).click()
    await expect(page).toHaveURL("/shopping-lists")
    await expect(
      page.getByRole("heading", { name: "Shopping Lists" }),
    ).toBeVisible()

    await deleteListFromCard(page, name)
  })
})
