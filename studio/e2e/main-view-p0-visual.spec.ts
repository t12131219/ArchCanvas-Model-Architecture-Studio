import { resolve } from "node:path";

import { expect, test } from "@playwright/test";

const ACCEPTANCE = resolve(process.cwd(), "../docs/acceptance/main-view-p0/production");
const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 1024, height: 768 },
  { width: 390, height: 844 },
] as const;

test("P0 visual acceptance covers fixed viewports and dark theme", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("archcanvas.locale", "en"));
  await page.goto("/");
  await page.getByRole("dialog", { name: "Open model" }).getByRole("button", { name: "Close" }).click();

  const scene = page.locator("svg.kernel-scene");
  await expect(scene).toBeVisible();
  expect(await page.locator(".kernel-node, .kernel-expanded-module").count()).toBeGreaterThan(0);
  expect(await page.locator(".kernel-edge").count()).toBeGreaterThan(0);
  expect(await page.locator(".kernel-relation-legend").count()).toBe(1);

  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport);
    await expect(scene).toBeVisible();
    const box = await scene.boundingBox();
    expect(box?.width).toBeGreaterThan(250);
    expect(box?.height).toBeGreaterThan(250);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({
      path: resolve(ACCEPTANCE, `runtime-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    });
  }

  await page.getByRole("button", { name: "Open inspector" }).click();
  await expect(page.locator(".right-panel.mobile-open")).toBeVisible();
  await page.getByRole("button", { name: "Close inspector" }).click();

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator(".kernel-node").first().focus();
  await page.keyboard.press("Enter");
  const pinResponse = page.waitForResponse((response) =>
    response.url().endsWith("/api/patch") && response.request().method() === "POST",
  );
  await page.getByTitle("Pin").click();
  expect((await pinResponse).status()).toBe(200);
  await expect(page.getByTitle("Unpin")).toBeVisible();

  const themeResponse = page.waitForResponse((response) =>
    response.url().endsWith("/api/patch") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Toggle theme" }).click();
  expect((await themeResponse).status()).toBe(200);
  await expect(page.locator(".studio")).toHaveClass(/dark/);
  await expect.poll(async () => page.locator(".kernel-paper").evaluate((element) => getComputedStyle(element).fill))
    .toBe("rgb(23, 33, 38)");
  await page.screenshot({ path: resolve(ACCEPTANCE, "runtime-dark-1440x900.png"), fullPage: true });

  await page.reload();
  await page.getByRole("dialog", { name: "Open model" }).getByRole("button", { name: "Close" }).click();
  await expect(page.locator(".studio")).toHaveClass(/dark/);
  await page.locator(".kernel-node").first().focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTitle("Unpin")).toBeVisible();

  const unpinResponse = page.waitForResponse((response) =>
    response.url().endsWith("/api/patch") && response.request().method() === "POST",
  );
  await page.getByTitle("Unpin").click();
  expect((await unpinResponse).status()).toBe(200);
  const lightThemeResponse = page.waitForResponse((response) =>
    response.url().endsWith("/api/patch") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Toggle theme" }).click();
  expect((await lightThemeResponse).status()).toBe(200);
  await expect(page.locator(".studio")).not.toHaveClass(/dark/);
});
