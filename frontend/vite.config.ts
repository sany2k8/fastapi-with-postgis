import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Vite dev server proxies /api to the FastAPI backend, so frontend source
// never hardcodes the backend host/port.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5199,
    proxy: {
      "/api": "http://localhost:8850",
    },
  },
});
