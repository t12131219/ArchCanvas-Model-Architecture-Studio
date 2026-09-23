const { defineConfig } = require('@playwright/test')
const { chromium } = require('@playwright/test')
const port = Number(process.env.ARCHCANVAS_VISUAL_PORT ?? 1419)

module.exports = defineConfig({
  testDir: './tests',
  testMatch: ['visual-regression.spec.cjs', 'tier-a.spec.cjs'],
  outputDir: 'visual-regression/results',
  snapshotPathTemplate: 'visual-regression/baselines/{arg}{ext}',
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    colorScheme: 'light',
    deviceScaleFactor: 1,
    launchOptions: { executablePath: process.env.ARCHCANVAS_PLAYWRIGHT_CHROMIUM ?? chromium.executablePath() },
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: process.env.ARCHCANVAS_VISUAL_PORT !== undefined,
    timeout: 30_000,
  },
})
