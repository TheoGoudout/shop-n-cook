import { vi } from "vitest"

const mockStorage: Record<string, unknown> = {}

global.chrome = {
  storage: {
    local: {
      get: vi.fn(
        (key: string, callback: (result: Record<string, unknown>) => void) => {
          callback({ [key]: mockStorage[key] })
        },
      ),
      set: vi.fn((items: Record<string, unknown>, callback?: () => void) => {
        Object.assign(mockStorage, items)
        callback?.()
      }),
      remove: vi.fn((key: string, callback?: () => void) => {
        delete mockStorage[key]
        callback?.()
      }),
    },
  },
  tabs: {
    query: vi.fn(),
  },
} as unknown as typeof chrome

export { mockStorage }
