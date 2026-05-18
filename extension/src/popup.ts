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

function render(state: State) {
  currentState = state
  const main = document.getElementById("main")!
  const header = document.querySelector("header")!

  const existing = header.querySelector(".user-info")
  if (existing) existing.remove()

  if (
    state.kind === "authenticated" ||
    state.kind === "importing" ||
    state.kind === "success" ||
    state.kind === "error"
  ) {
    const userInfo = document.createElement("div")
    userInfo.className = "user-info"
    userInfo.innerHTML = `<span>${escapeHtml(state.email)}</span>`
    const logoutBtn = document.createElement("button")
    logoutBtn.className = "btn-ghost"
    logoutBtn.textContent = "Logout"
    logoutBtn.addEventListener("click", handleLogout)
    userInfo.appendChild(logoutBtn)
    header.appendChild(userInfo)
  }

  main.innerHTML = ""

  switch (state.kind) {
    case "loading":
      renderLoading(main)
      break
    case "login":
      renderLogin(main, state.error)
      break
    case "authenticated":
      renderAuthenticated(main, state.baseUrl)
      break
    case "importing":
      renderImporting(main)
      break
    case "success":
      renderSuccess(main, state.baseUrl, state.title, state.recipeId)
      break
    case "error":
      renderError(main, state.baseUrl, state.message)
      break
  }
}

function renderLoading(main: HTMLElement) {
  main.innerHTML = `<div style="text-align:center;padding:20px;color:#9ca3af;">Loading…</div>`
}

function renderLogin(main: HTMLElement, error?: string) {
  main.innerHTML = `
    <div class="form-group">
      <label for="base-url">Server URL</label>
      <input id="base-url" type="url" placeholder="http://localhost:8000" value="http://localhost:8000" />
    </div>
    <div class="form-group">
      <label for="email">Email</label>
      <input id="email" type="email" placeholder="you@example.com" />
    </div>
    <div class="form-group">
      <label for="password">Password</label>
      <input id="password" type="password" placeholder="••••••••" />
    </div>
    ${error ? `<div class="error-msg">${escapeHtml(error)}</div>` : ""}
    <button class="btn-primary" id="login-btn">Sign in</button>
  `

  const loginBtn = main.querySelector("#login-btn")!
  const passwordInput = main.querySelector<HTMLInputElement>("#password")!

  loginBtn.addEventListener("click", handleLogin)
  passwordInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleLogin()
  })
}

function renderAuthenticated(main: HTMLElement, baseUrl: string) {
  main.innerHTML = `
    <div class="consent-box">
      <label class="consent-label">
        <input type="checkbox" id="import-consent" />
        <span>The recipe is sourced from a third-party website. By importing, you confirm you have the right to store and reformat this content for personal use and will respect the original author's intellectual property rights. This app does not claim any rights over imported content and always links back to the original source.</span>
      </label>
    </div>
    <button class="import-btn" id="import-btn" disabled>
      <span>⬇</span>
      <span>Import Recipe</span>
    </button>
    <p class="hint">${escapeHtml(baseUrl)}</p>
  `
  const consentCheckbox =
    main.querySelector<HTMLInputElement>("#import-consent")!
  const importBtn = main.querySelector<HTMLButtonElement>("#import-btn")!
  consentCheckbox.addEventListener("change", () => {
    importBtn.disabled = !consentCheckbox.checked
  })
  importBtn.addEventListener("click", handleImport)
}

function renderImporting(main: HTMLElement) {
  main.innerHTML = `
    <p class="hint">Analyzing the page with AI…</p>
    <button class="import-btn" disabled>
      <span class="spinner"></span>
      <span>Importing…</span>
    </button>
  `
}

function renderSuccess(
  main: HTMLElement,
  baseUrl: string,
  title: string,
  recipeId: string,
) {
  const appUrl = `${baseUrl}/recipes/${recipeId}`
  main.innerHTML = `
    <div class="success-icon">✅</div>
    <p class="success-title">${escapeHtml(title)}</p>
    <div class="actions-row">
      <a href="${escapeHtml(appUrl)}" target="_blank" rel="noopener noreferrer">
        <button class="btn-secondary">Open in app ↗</button>
      </a>
      <button class="btn-secondary" id="import-another-btn">Import another</button>
    </div>
  `
  main.querySelector("#import-another-btn")!.addEventListener("click", () => {
    if (currentState.kind === "success") {
      render({
        kind: "authenticated",
        email: currentState.email,
        baseUrl: currentState.baseUrl,
      })
    }
  })
}

function renderError(main: HTMLElement, _baseUrl: string, message: string) {
  main.innerHTML = `
    <div class="error-msg">${escapeHtml(message)}</div>
    <button class="btn-primary" id="retry-btn">Try again</button>
  `
  main.querySelector("#retry-btn")!.addEventListener("click", () => {
    if (currentState.kind === "error") {
      render({
        kind: "authenticated",
        email: currentState.email,
        baseUrl: currentState.baseUrl,
      })
    }
  })
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
        message:
          "Cannot import from this page. Navigate to a recipe URL first.",
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

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
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
