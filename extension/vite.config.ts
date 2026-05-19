import { execSync } from "node:child_process"
import { resolve } from "node:path"
import { defineConfig, loadEnv } from "vite"

function getVersion(): string {
  if (process.env.VITE_APP_VERSION) return process.env.VITE_APP_VERSION
  try {
    return execSync("git describe --tags --always", {
      stdio: ["pipe", "pipe", "pipe"],
    })
      .toString()
      .trim()
  } catch {
    return "dev"
  }
}

export default defineConfig(({ mode }) => {
  // Load .env from the project root (one level up) so the extension build
  // shares the same API_URL as the rest of the stack.
  const env = loadEnv(mode, resolve(__dirname, ".."), "")

  return {
    define: {
      __API_URL__: JSON.stringify(env.API_URL ?? "https://api.shop-n-cook.com"),
      __FRONTEND_URL__: JSON.stringify(env.FRONTEND_HOST ?? "https://app.shop-n-cook.com"),
      __APP_VERSION__: JSON.stringify(getVersion()),
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
