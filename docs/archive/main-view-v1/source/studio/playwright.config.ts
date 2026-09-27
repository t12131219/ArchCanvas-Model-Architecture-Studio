import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

const workspacePython = process.platform === "win32"
  ? "../.venv/Scripts/python.exe"
  : "../.venv/bin/python";
const python = process.env.ARCHCANVAS_PYTHON
  ?? (existsSync(workspacePython) ? workspacePython : "python");

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results/playwright",
  fullyParallel: false,
  timeout: 90_000,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [["line"], ["html", { open: "never" }]] : "line",
  use: {
    baseURL: "http://127.0.0.1:4311",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } },
    },
  ],
  webServer: {
    command: `${python} ../tools/serve_routing_smoke.py --port 4311`,
    url: "http://127.0.0.1:4311/api/state",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
