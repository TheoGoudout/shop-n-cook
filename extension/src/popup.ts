import "./popup.css"
import { parsedRecipeToCreate } from "./api"
import { LoginService, OpenAPI, RecipesService, UsersService } from "./client"
import { clearAuthData, getAuthData, saveAuthData } from "./storage"

type State =
  | { kind: "loading" }
  | { kind: "login"; error?: string }
  | { kind: "authenticated"; email: string; baseUrl: string }
  | { kind: "importing"; email: string; baseUrl: string }
  | {
      kind: "success"
      email: string
      baseUrl: string
      title: string
      recipeId: string
    }
  | { kind: "error"; email: string; baseUrl: string; message: string }

let currentState: State = { kind: "loading" }

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag)
  if (className) e.className = className
  return e
}

function append(parent: Element, ...children: (Element | Text)[]): void {
  for (const child of children) parent.appendChild(child)
}

function formGroup(labelText: string, input: HTMLInputElement): HTMLDivElement {
  const group = el("div", "form-group")
  const label = el("label")
  label.htmlFor = input.id
  label.textContent = labelText
  append(group, label, input)
  return group
}

function render(state: State) {
  currentState = state
  const main = document.getElementById("main")!
  const header = document.querySelector("header")!

  header.querySelector(".user-info")?.remove()

  if (
    state.kind === "authenticated" ||
    state.kind === "importing" ||
    state.kind === "success" ||
    state.kind === "error"
  ) {
    const userInfo = el("div", "user-info")
    const emailSpan = el("span")
    emailSpan.textContent = state.email
    const logoutBtn = el("button", "btn-ghost")
    logoutBtn.textContent = "Logout"
    logoutBtn.addEventListener("click", handleLogout)
    append(userInfo, emailSpan, logoutBtn)
    header.appendChild(userInfo)
  }

  main.textContent = ""

  switch (state.kind) {
    case "loading":      renderLoading(main);                           break
    case "login":        renderLogin(main, state.error);                break
    case "authenticated": renderAuthenticated(main, state.baseUrl);     break
    case "importing":    renderImporting(main);                         break
    case "success":      renderSuccess(main, state.baseUrl, state.title, state.recipeId); break
    case "error":        renderError(main, state.message);              break
  }
}

function renderLoading(main: HTMLElement) {
  const div = el("div")
  div.setAttribute("style", "text-align:center;padding:20px;color:#9ca3af;")
  div.textContent = "Loading…"
  main.appendChild(div)
}

function renderLogin(main: HTMLElement, error?: string) {
  const urlInput = el("input")
  urlInput.id = "base-url"
  urlInput.type = "url"
  urlInput.placeholder = "http://localhost:8000"
  urlInput.value = "http://localhost:8000"

  const emailInput = el("input")
  emailInput.id = "email"
  emailInput.type = "email"
  emailInput.placeholder = "you@example.com"

  const passwordInput = el("input")
  passwordInput.id = "password"
  passwordInput.type = "password"
  passwordInput.placeholder = "••••••••"

  const loginBtn = el("button", "btn-primary")
  loginBtn.id = "login-btn"
  loginBtn.textContent = "Sign in"
  loginBtn.addEventListener("click", handleLogin)
  passwordInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleLogin()
  })

  append(
    main,
    formGroup("Server URL", urlInput),
    formGroup("Email", emailInput),
    formGroup("Password", passwordInput),
  )

  if (error) {
    const errDiv = el("div", "error-msg")
    errDiv.textContent = error
    main.appendChild(errDiv)
  }

  main.appendChild(loginBtn)
}

function renderAuthenticated(main: HTMLElement, baseUrl: string) {
  const consentBox = el("div", "consent-box")
  const label = el("label", "consent-label")
  const checkbox = el("input")
  checkbox.type = "checkbox"
  checkbox.id = "import-consent"
  const consentText = el("span")
  consentText.textContent =
    "The recipe is sourced from a third-party website. By importing, you confirm you have the right to store and reformat this content for personal use and will respect the original author's intellectual property rights. This app does not claim any rights over imported content and always links back to the original source."
  append(label, checkbox, consentText)
  consentBox.appendChild(label)

  const importBtn = el("button", "import-btn")
  importBtn.id = "import-btn"
  importBtn.disabled = true
  const arrowSpan = el("span")
  arrowSpan.textContent = "⬇"
  const importLabel = el("span")
  importLabel.textContent = "Import Recipe"
  append(importBtn, arrowSpan, importLabel)

  checkbox.addEventListener("change", () => {
    importBtn.disabled = !checkbox.checked
  })
  importBtn.addEventListener("click", handleImport)

  const hint = el("p", "hint")
  hint.textContent = baseUrl

  append(main, consentBox, importBtn, hint)
}

function renderImporting(main: HTMLElement) {
  const hint = el("p", "hint")
  hint.textContent = "Analyzing the page with AI…"

  const importBtn = el("button", "import-btn")
  importBtn.disabled = true
  const spinner = el("span", "spinner")
  const importLabel = el("span")
  importLabel.textContent = "Importing…"
  append(importBtn, spinner, importLabel)

  append(main, hint, importBtn)
}

function renderSuccess(
  main: HTMLElement,
  baseUrl: string,
  title: string,
  recipeId: string,
) {
  const icon = el("div", "success-icon")
  icon.textContent = "✅"

  const titleP = el("p", "success-title")
  titleP.textContent = title

  const actionsRow = el("div", "actions-row")

  const link = el("a")
  link.href = `${baseUrl}/recipes/${recipeId}`
  link.target = "_blank"
  link.rel = "noopener noreferrer"
  const openBtn = el("button", "btn-secondary")
  openBtn.textContent = "Open in app ↗"
  link.appendChild(openBtn)

  const anotherBtn = el("button", "btn-secondary")
  anotherBtn.id = "import-another-btn"
  anotherBtn.textContent = "Import another"
  anotherBtn.addEventListener("click", () => {
    if (currentState.kind === "success") {
      render({
        kind: "authenticated",
        email: currentState.email,
        baseUrl: currentState.baseUrl,
      })
    }
  })

  append(actionsRow, link, anotherBtn)
  append(main, icon, titleP, actionsRow)
}

function renderError(main: HTMLElement, message: string) {
  const errDiv = el("div", "error-msg")
  errDiv.textContent = message

  const retryBtn = el("button", "btn-primary")
  retryBtn.id = "retry-btn"
  retryBtn.textContent = "Try again"
  retryBtn.addEventListener("click", () => {
    if (currentState.kind === "error") {
      render({
        kind: "authenticated",
        email: currentState.email,
        baseUrl: currentState.baseUrl,
      })
    }
  })

  append(main, errDiv, retryBtn)
}

async function handleLogin() {
  const baseUrl = (
    document.querySelector<HTMLInputElement>("#base-url")?.value ?? ""
  ).trim()
  const email = (
    document.querySelector<HTMLInputElement>("#email")?.value ?? ""
  ).trim()
  const password = (
    document.querySelector<HTMLInputElement>("#password")?.value ?? ""
  ).trim()

  if (!baseUrl || !email || !password) {
    render({ kind: "login", error: "Please fill in all fields." })
    return
  }

  const loginBtn = document.querySelector<HTMLButtonElement>("#login-btn")
  if (loginBtn) {
    loginBtn.disabled = true
    loginBtn.textContent = "Signing in…"
  }

  try {
    OpenAPI.BASE = baseUrl
    const tokenResp = await LoginService.loginAccessToken({
      formData: { username: email, password },
    })
    OpenAPI.TOKEN = tokenResp.access_token

    const user = await UsersService.readUserMe()
    await saveAuthData({
      baseUrl,
      token: tokenResp.access_token,
      email: user.email,
    })
    render({ kind: "authenticated", email: user.email, baseUrl })
  } catch {
    render({
      kind: "login",
      error: "Login failed. Check your credentials and server URL.",
    })
  }
}

async function handleLogout() {
  await clearAuthData()
  render({ kind: "login" })
}

async function handleImport() {
  if (currentState.kind !== "authenticated") return

  const { email, baseUrl } = currentState
  render({ kind: "importing", email, baseUrl })

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    const url = tab?.url
    if (!url || !url.startsWith("http")) {
      render({
        kind: "error",
        email,
        baseUrl,
        message: "Cannot import from this page. Navigate to a recipe URL first.",
      })
      return
    }

    const parsed = await RecipesService.importRecipeUrl({
      requestBody: { url },
    })
    const recipeCreate = parsedRecipeToCreate(parsed)
    const saved = await RecipesService.createRecipe({
      requestBody: recipeCreate,
    })

    render({
      kind: "success",
      email,
      baseUrl,
      title: saved.title,
      recipeId: String(saved.id),
    })
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "An unexpected error occurred."
    render({ kind: "error", email, baseUrl, message })
  }
}

async function init() {
  render({ kind: "loading" })

  const auth = await getAuthData()
  if (!auth) {
    render({ kind: "login" })
    return
  }

  OpenAPI.BASE = auth.baseUrl
  OpenAPI.TOKEN = auth.token

  try {
    const user = await UsersService.readUserMe()
    render({ kind: "authenticated", email: user.email, baseUrl: auth.baseUrl })
  } catch {
    await clearAuthData()
    render({ kind: "login", error: "Session expired. Please sign in again." })
  }
}

init()
