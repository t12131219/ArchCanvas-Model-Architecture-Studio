const { defineConfig } = require('@playwright/test')
const { chromium } = require('@playwright/test')

module.exports = defineConfig({
  testDir: './tests',
  testMatch: 'visual-regression.spec.cjs',
  outputDir: 'visual-regression/results',
  snapshotPathTemplate: 'visual-regression/baselines/{arg}{ext}',
  use: {
    baseURL: 'http://127.0.0.1:1419',
    colorScheme: 'light',
    deviceScaleFactor: 1,
    launchOptions: { executablePath: process.env.ARCHCANVAS_PLAYWRIGHT_CHROMIUM ?? chromium.executablePath() },
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 1419',
    url: 'http://127.0.0.1:1419',
    reuseExistingServer: false,
    timeout: 30_000,
  },
})
