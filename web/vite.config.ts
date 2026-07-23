/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The dev server proxies API and health calls to the local FastAPI process so the
// browser talks to a single origin, matching the packaged build.
export default defineConfig({
  plugins: [react()],
  // Build straight into the Python package so `clipfetch web` serves the bundle with no copy step.
  // emptyOutDir is off so the tracked .gitignore that marks the directory survives rebuilds.
  build: {
    outDir: "../clipfetch/webui",
    emptyOutDir: false,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: false,
  },
});
