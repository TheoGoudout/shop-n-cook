import { readFileSync, writeFileSync } from "node:fs"
import { resolve } from "node:path"
import { defineConfig, loadEnv, type Plugin } from "vite"
import pkg from "./package.json"

function extensionBuildPlugin(): Plugin {
  return {
    name: "extension-build",
    apply: "build",
    closeBundle() {
      const distDir = resolve(__dirname, "dist")
      const manifest = JSON.parse(
        readFileSync(`${distDir}/manifest.json`, "utf8"),
      )

      // In CI, VITE_APP_VERSION is not set and the manifest version comes from
      // the committed manifest.json (already correct). Only update locally.
      if (!process.env.VITE_APP_VERSION) {
        const match = pkg.version.match(/^(\d+\.\d+\.\d+)/)
        manifest.version = match ? match[1] : "0.0.0"
      }

      if (this.meta.watchMode) {
        manifest.background = { service_worker: "dev-reload.js" }
        writeFileSync(
          `${distDir}/manifest.json`,
          JSON.stringify(manifest, null, 2),
        )

        writeFileSync(`${distDir}/build-time.txt`, Date.now().toString())
        writeFileSync(
          `${distDir}/dev-reload.js`,
          `let t=null;async function p(){try{const r=await fetch(chrome.runtime.getURL("build-time.txt")+"?_="+Date.now());const s=await r.text();if(t===null)t=s;else if(t!==s){chrome.runtime.reload();return;}}catch(_){}setTimeout(p,1000);}p();`,
        )
      } else {
        writeFileSync(
          `${distDir}/manifest.json`,
          JSON.stringify(manifest, null, 2),
        )
      }
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, resolve(__dirname, ".."), "")

  return {
    define: {
      __API_URL__: JSON.stringify(env.API_URL ?? "https://api.shop-n-cook.com"),
      __FRONTEND_URL__: JSON.stringify(
        env.FRONTEND_HOST ?? "https://app.shop-n-cook.com",
      ),
      __APP_VERSION__: JSON.stringify(
        mode === "development" ? "dev" : pkg.version,
      ),
    },
    plugins: [extensionBuildPlugin()],
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
