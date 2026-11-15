import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    __BUILD_SHA__: JSON.stringify(
      process.env.VERCEL_GIT_COMMIT_SHA?.slice(0, 7) || "dev",
    ),
  },
  server: {
    proxy: {
      "/sites": "http://127.0.0.1:8000",
      "/route": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/ask": "http://127.0.0.1:8001",
    },
  },
});
