/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the API is proxied, so the browser sees one origin and the
// HttpOnly session cookies work without any CORS configuration.
const API_TARGET = process.env.APPLYXAI_API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    // Bind IPv4 as well as IPv6 on Windows (otherwise only [::1]:5173 works, not 127.0.0.1:5173).
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
        timeout: 120_000,
        proxyTimeout: 120_000,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
