import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/sites": "http://127.0.0.1:8000",
      "/route": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/ask": "http://127.0.0.1:8001",
    },
  },
});
