import { beforeEach, describe, expect, it, vi } from "vitest"
import {
  type AuthData,
  clearAuthData,
  getAuthData,
  saveAuthData,
} from "../storage"
import { mockStorage } from "./setup"

describe("storage helpers", () => {
  beforeEach(() => {
    // Clear mock storage and reset call history before each test
    for (const key of Object.keys(mockStorage)) {
      delete mockStorage[key]
    }
    vi.clearAllMocks()
  })

  const sampleAuth: AuthData = {
    baseUrl: "http://localhost:8000",
    token: "test-jwt-token",
    email: "user@example.com",
  }

  describe("getAuthData", () => {
    it("returns null when storage is empty", async () => {
      const result = await getAuthData()
      expect(result).toBeNull()
    })

    it("returns stored auth data", async () => {
      mockStorage.auth = sampleAuth
      const result = await getAuthData()
      expect(result).toEqual(sampleAuth)
    })
  })

  describe("saveAuthData", () => {
    it("stores auth data under the correct key", async () => {
      await saveAuthData(sampleAuth)
      expect(chrome.storage.local.set).toHaveBeenCalledWith(
        { auth: sampleAuth },
        expect.any(Function),
      )
    })

    it("persists data that can be retrieved", async () => {
      await saveAuthData(sampleAuth)
      const result = await getAuthData()
      expect(result).toEqual(sampleAuth)
    })
  })

  describe("clearAuthData", () => {
    it("removes the auth key from storage", async () => {
      mockStorage.auth = sampleAuth
      await clearAuthData()
      expect(chrome.storage.local.remove).toHaveBeenCalledWith(
        "auth",
        expect.any(Function),
      )
    })

    it("causes getAuthData to return null after clearing", async () => {
      await saveAuthData(sampleAuth)
      await clearAuthData()
      const result = await getAuthData()
      expect(result).toBeNull()
    })
  })
})
