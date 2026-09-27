import { expect, test, type Page } from "@playwright/test";

async function closeOpenDialog(page: Page) {
  const dialog = page.getByRole("dialog", { name: "Open model" });
  try {
    await dialog.waitFor({ state: "visible", timeout: 5_000 });
    await dialog.getByRole("button", { name: "Close" }).click();
  } catch {
    // The launcher is optional once a project is active.
  }
}

test("Phase 8 serves only formal state and the TypeScript visual kernel", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("archcanvas.locale", "en"));
  await page.goto("/");
  await closeOpenDialog(page);

  const canvas = page.locator("svg.kernel-scene");
  await expect(canvas).toBeVisible();
  await expect(canvas).toHaveAttribute("data-kernel-render-digest", /^kernel-render:/);
  expect(await page.locator("svg.scene").count()).toBe(0);
  expect(await page.locator("[data-kernel-node-id]").count()).toBeGreaterThan(0);

  const state = await page.request.get("/api/state");
  expect(state.ok()).toBe(true);
  const payload = await state.json() as Record<string, unknown>;
  expect(payload).not.toHaveProperty("scenes");
  expect(payload).not.toHaveProperty("specs");
  expect(payload).not.toHaveProperty("routing");
  expect(payload).toHaveProperty("architecture");
  expect(payload).toHaveProperty("hierarchy");
  expect(payload).toHaveProperty("views");
  expect(payload).toHaveProperty("view_state");

  for (const endpoint of [
    "/api/layout-mode",
    "/api/layout-candidates",
    "/api/layout",
    "/api/route",
    "/api/align",
  ]) {
    const response = await page.request.post(endpoint, { data: {} });
    expect(response.status(), endpoint).toBe(404);
  }

  const publication = await page.request.get("/api/publication-export");
  expect(publication.ok()).toBe(true);
  expect(publication.headers()["x-archcanvas-export-scope"]).toBe("publication");
  expect((await publication.text()).startsWith('<?xml version="1.0"')).toBe(true);
});
