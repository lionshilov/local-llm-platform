/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the UI runs on Vite (:5173) and proxies API calls to the gateway;
// in production the gateway serves the built files itself, so there is no CORS at all.
const gateway = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { "/v1": gateway, "/metrics": gateway },
  },
  build: {
    // The markdown/KaTeX/highlight.js chunk is lazy-loaded with the first reply.
    chunkSizeWarningLimit: 700,
  },
  test: {
    environment: "node",
  },
});
