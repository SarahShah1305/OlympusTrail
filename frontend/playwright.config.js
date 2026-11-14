import { defineConfig } from "@playwright/test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const baseURL = process.env.BASE_URL || "http://127.0.0.1:5175";
const preview = new URL(baseURL);
const port = preview.port || "5175";
const startsLocalVite = ["127.0.0.1", "localhost"].includes(preview.hostname);
const frontendDirectory = dirname(fileURLToPath(import.meta.url));
const viteEntry = resolve(frontendDirectory, "node_modules/vite/bin/vite.js");

export default defineConfig({
  testDir: "./tests",
  use: { baseURL },
  webServer: startsLocalVite
    ? {
        command: `"${process.execPath}" "${viteEntry}" --host ${preview.hostname} --port ${port}`,
        cwd: frontendDirectory,
        url: baseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 30_000,
      }
    : undefined,
});
