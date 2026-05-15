export interface AuthData {
  baseUrl: string
  token: string
  email: string
}

const STORAGE_KEY = "auth"

export async function getAuthData(): Promise<AuthData | null> {
  return new Promise((resolve) => {
    chrome.storage.local.get(STORAGE_KEY, (result) => {
      resolve((result[STORAGE_KEY] as AuthData) ?? null)
    })
  })
}

export async function saveAuthData(data: AuthData): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.set({ [STORAGE_KEY]: data }, resolve)
  })
}

export async function clearAuthData(): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.remove(STORAGE_KEY, resolve)
  })
}
