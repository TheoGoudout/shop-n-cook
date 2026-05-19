import { resolve } from "node:path"
import { defineConfig, loadEnv } from "vite"

export default defineConfig(({ mode }) => {
  // Load .env from the project root (one level up) so the extension build
  // shares the same API_URL as the rest of the stack.
  const env = loadEnv(mode, resolve(__dirname, ".."), "")

  return {
    define: {
      __API_URL__: JSON.stringify(env.API_URL ?? "https://api.shop-n-cook.com"),
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
      rollupOptions: {
        input: {
          popup: resolve(__dirname, "popup.html"),
        },
      },
    },
    test: {
      setupFiles: ["./src/__tests__/setup.ts"],
    },
  }
})
