import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/static/app/",
  build: { outDir: "../src/howlet/static/app", emptyOutDir: true },
  server: { proxy: { "/api": "http://localhost:8813" } },
  test: { environment: "jsdom", globals: true },
});
