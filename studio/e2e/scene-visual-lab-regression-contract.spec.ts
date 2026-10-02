import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

const PROTOTYPE_BASE_URL = process.env.ARCHCANVAS_PROTOTYPE_E2E_BASE_URL
  ?? "http://127.0.0.1:4312";

test("canvas gestures, negative coordinates, hierarchy A/B, and export stay coherent", async ({ page }, testInfo) => {
  await page.goto(`${PROTOTYPE_BASE_URL}/?scene=classic-transformer&qa=regression-contract`);
  const viewport = page.locator(".canvas-viewport");
  const canvas = page.locator("svg.lab-canvas");
  await expect(canvas).toBeVisible();
  await expect(canvas.locator(".lab-node")).not.toHaveCount(0);

  const viewportBounds = await viewport.boundingBox();
  expect(viewportBounds).not.toBeNull();
  if (!viewportBounds) return;

  const zoom = page.getByLabel("当前缩放比例");
  const zoomBefore = await zoom.textContent();
  await page.keyboard.down("Control");
  await page.mouse.move(
    viewportBounds.x + viewportBounds.width * 0.42,
    viewportBounds.y + viewportBounds.height * 0.45,
  );
  await page.mouse.wheel(0, -180);
  await page.keyboard.up("Control");
  await expect.poll(() => zoom.textContent()).not.toBe(zoomBefore);
  await page.getByTitle("适合视图").click();

  const sourceNode = canvas.locator('[data-node-id="transformer-src"]');
  const sourceSurface = sourceNode.locator(".node-surface");
  const sourceBounds = await sourceSurface.boundingBox();
  expect(sourceBounds).not.toBeNull();
  if (!sourceBounds) return;
  const xBefore = Number(await sourceSurface.getAttribute("x"));
  const yBefore = Number(await sourceSurface.getAttribute("y"));
  await page.mouse.move(
    sourceBounds.x + sourceBounds.width / 2,
    sourceBounds.y + sourceBounds.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    sourceBounds.x + sourceBounds.width / 2 - 70,
    sourceBounds.y + sourceBounds.height / 2 - 120,
    { steps: 8 },
  );
  await page.mouse.up();
  await expect.poll(async () => Number(await sourceSurface.getAttribute("x"))).toBeLessThan(xBefore);
  await expect.poll(async () => Number(await sourceSurface.getAttribute("y"))).toBeLessThan(yBefore);
  expect(Number(await sourceSurface.getAttribute("x"))).toBeLessThan(0);
  expect(Number(await sourceSurface.getAttribute("y"))).toBeLessThan(0);

  const transformBeforeNodePan = await canvas.getAttribute("style");
  const visiblePanSurface = canvas.locator('[data-node-id="transformer-encoder"] .node-surface');
  const movedNodeBounds = await visiblePanSurface.boundingBox();
  expect(movedNodeBounds).not.toBeNull();
  if (!movedNodeBounds) return;
  await page.mouse.move(
    movedNodeBounds.x + movedNodeBounds.width / 2,
    movedNodeBounds.y + movedNodeBounds.height / 2,
  );
  await page.mouse.down({ button: "middle" });
  await page.mouse.move(
    movedNodeBounds.x + movedNodeBounds.width / 2 + 70,
    movedNodeBounds.y + movedNodeBounds.height / 2 + 55,
    { steps: 6 },
  );
  await page.mouse.up({ button: "middle" });
  await expect.poll(() => canvas.getAttribute("style")).not.toBe(transformBeforeNodePan);

  await page.evaluate(() => {
    (window as Window & { __nativeDragStarts?: number }).__nativeDragStarts = 0;
    document.addEventListener("dragstart", () => {
      const target = window as Window & { __nativeDragStarts?: number };
      target.__nativeDragStarts = (target.__nativeDragStarts ?? 0) + 1;
    });
  });
  const title = canvas.locator(".node-label").first();
  const titleBounds = await title.boundingBox();
  expect(titleBounds).not.toBeNull();
  if (!titleBounds) return;
  await page.mouse.move(titleBounds.x + 2, titleBounds.y + 2);
  await page.mouse.down();
  await page.mouse.move(titleBounds.x + titleBounds.width - 2, titleBounds.y + 2, { steps: 5 });
  await page.mouse.up();
  expect(await page.evaluate(() => window.getSelection()?.toString() ?? "")).toBe("");
  expect(await page.evaluate(() => (window as Window & { __nativeDragStarts?: number }).__nativeDragStarts)).toBe(0);

  const hierarchyMode = page.locator(".variant-toolbar label").filter({ hasText: "层级" }).locator("select");
  await page.getByRole("button", { name: "全部展开" }).click();
  await expect(page.locator(".detail-bulk-actions")).toHaveAttribute("aria-busy", "false", { timeout: 30_000 });
  await expect(page.locator(".nested-inline-detail").first()).toBeVisible();
  const expandedCount = await page.locator(".expanded-node").count();
  await hierarchyMode.selectOption("recursive");
  await expect(hierarchyMode).toHaveValue("recursive");
  await expect(page.locator(".expanded-node")).toHaveCount(expandedCount);
  await hierarchyMode.selectOption("atomic-bottom-up");
  await expect(hierarchyMode).toHaveValue("atomic-bottom-up");

  const exportedDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出方案" }).click();
  const download = await exportedDownload;
  const downloadPath = await download.path();
  expect(downloadPath).not.toBeNull();
  if (!downloadPath) return;
  const exported = JSON.parse(await readFile(downloadPath, "utf-8")) as {
    scene: { nodes: Array<{ scene_node_id: string; bounds: { x: number; y: number } }> };
    svg: string;
    hierarchyRoutingMode: string;
  };
  const exportedSource = exported.scene.nodes.find((node) => node.scene_node_id === "transformer-src");
  expect(exportedSource).toBeDefined();
  expect(exportedSource?.bounds.x).toBe(Number(await sourceSurface.getAttribute("x")));
  expect(exportedSource?.bounds.y).toBe(Number(await sourceSurface.getAttribute("y")));
  expect(exported.hierarchyRoutingMode).toBe("atomic-bottom-up");
  const exportedGeometry = await page.evaluate((svg) => {
    const document = new DOMParser().parseFromString(svg, "image/svg+xml");
    const surface = document.querySelector('[data-node-id="transformer-src"] .node-surface');
    return { x: Number(surface?.getAttribute("x")), y: Number(surface?.getAttribute("y")) };
  }, exported.svg);
  expect(exportedGeometry).toEqual({ x: exportedSource?.bounds.x, y: exportedSource?.bounds.y });

  const screenshot = await viewport.screenshot();
  expect(screenshot.byteLength).toBeGreaterThan(10_000);
  await testInfo.attach("classic-transformer-regression-contract", {
    body: screenshot,
    contentType: "image/png",
  });
});

for (const sceneId of ["paper-classic-transformer", "paper-tensor2tensor-transformer"]) {
  test(`${sceneId} preserves encoder-left decoder-right ordering`, async ({ page }, testInfo) => {
    await page.goto(`${PROTOTYPE_BASE_URL}/?scene=${sceneId}&qa=paper-ordering`);
    const canvas = page.locator("svg.lab-canvas");
    await expect(canvas).toBeVisible();
    const encoderId = sceneId === "paper-classic-transformer"
      ? "paper-classic-encoder"
      : "paper-t2t-encoder";
    const decoderId = sceneId === "paper-classic-transformer"
      ? "paper-classic-decoder"
      : "paper-t2t-decoder";
    const encoder = canvas.locator(`[data-node-id="${encoderId}"] .node-surface`);
    const decoder = canvas.locator(`[data-node-id="${decoderId}"] .node-surface`);
    expect(Number(await encoder.getAttribute("x"))).toBeLessThan(Number(await decoder.getAttribute("x")));

    await page.getByRole("button", { name: "全部展开" }).click();
    await expect(page.locator(".detail-bulk-actions")).toHaveAttribute("aria-busy", "false", { timeout: 30_000 });
    expect(Number(await encoder.getAttribute("x"))).toBeLessThan(Number(await decoder.getAttribute("x")));
    await expect(canvas.locator(".expanded-node")).not.toHaveCount(0);

    const screenshot = await page.locator(".canvas-viewport").screenshot();
    expect(screenshot.byteLength).toBeGreaterThan(10_000);
    await testInfo.attach(`${sceneId}-expanded`, { body: screenshot, contentType: "image/png" });
  });
}
