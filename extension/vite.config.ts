import { resolve } from "node:path"
import { defineConfig } from "vite"

export default defineConfig({
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
})
