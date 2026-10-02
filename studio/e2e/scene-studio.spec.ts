import { expect, test, type Locator, type Page } from "@playwright/test";

type StudioState = {
  integrity: { source_digest: string; exact_ir_digest: string };
  document: { visual_patches: unknown[]; redo_patches: unknown[] };
  view_state: {
    node_positions: Record<string, { x: number; y: number }>;
    module_expansion: string[];
    pinned_node_ids: string[];
    theme: "paper-light" | "studio-dark";
  };
};

async function studioState(page: Page): Promise<StudioState> {
  return page.evaluate(async () => {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  });
}

async function drag(page: Page, locator: Locator, dx: number, dy: number) {
  const box = await locator.boundingBox();
  if (!box) throw new Error("drag target is not visible");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + dx, box.y + box.height / 2 + dy, { steps: 8 });
  await page.mouse.up();
}

test("source-backed scene uses one canvas across presets and persists visual patches", async ({ page }) => {
  await page.goto("/");
  const canvas = page.locator("svg.lab-canvas");
  await expect(canvas).toBeVisible();
  await expect.poll(() => page.locator(".lab-node").count()).toBeGreaterThan(0);
  await expect.poll(() => page.locator(".lab-edge").count()).toBeGreaterThan(0);
  const baseline = await studioState(page);
  const initialCount = await page.locator(".lab-node").count();

  await page.getByTitle("打开搜索、问题与任务").click();
  const operations = page.getByRole("complementary", { name: "搜索、问题与任务" });
  await operations.getByLabel("搜索语义对象").fill("Transformer");
  await expect.poll(() => operations.locator(".operations-results button").count()).toBeGreaterThan(0);
  await operations.getByRole("tab", { name: /问题/ }).click();
  await operations.getByRole("tab", { name: /任务/ }).click();
  await operations.getByRole("tab", { name: /一致性/ }).click();
  await expect(operations.locator(".conformance-list")).toContainText("source-view");
  await expect(operations.locator(".conformance-list")).toContainText("exact");
  await operations.getByRole("tab", { name: /恢复/ }).click();
  await expect(operations).toContainText(/没有崩溃恢复记录|rolled-back|committed/);
  await operations.getByTitle("关闭搜索、问题与任务").click();

  await page.getByTitle("打开源码工作区").click();
  const sourceWorkspace = page.locator(".source-workspace-drawer");
  await expect(sourceWorkspace).toBeVisible();
  await expect(sourceWorkspace.locator(".cm-editor")).toBeVisible();
  await expect(sourceWorkspace.locator("textarea")).toHaveCount(0);
  await page.screenshot({ path: "/tmp/archcanvas-scene-studio-source-workspace.png", fullPage: true });
  await sourceWorkspace.getByTitle("关闭源码工作区").click();

  const exported = new Map<string, Buffer>();
  page.on("download", async (download) => {
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(Buffer.from(chunk));
    exported.set(download.suggestedFilename().split(".").at(-1) ?? "", Buffer.concat(chunks));
  });
  const rasterResponses: Array<{ format: string; scope: string | null }> = [];
  page.on("response", (response) => {
    if (!response.url().endsWith("/api/scene-export") || response.request().method() !== "POST") return;
    const format = (response.request().postDataJSON() as { format?: string } | null)?.format ?? "";
    rasterResponses.push({ format, scope: response.headers()["x-archcanvas-export-scope"] ?? null });
  });
  await page.getByRole("button", { name: "导出 SVG/PNG/PDF/JSON" }).click();
  await expect.poll(() => exported.size).toBe(4);
  expect([...exported.keys()].sort()).toEqual(["json", "pdf", "png", "svg"]);
  expect(exported.get("png")?.subarray(0, 8)).toEqual(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
  expect(exported.get("pdf")?.subarray(0, 5).toString("ascii")).toBe("%PDF-");
  expect(rasterResponses.sort((left, right) => left.format.localeCompare(right.format))).toEqual([
    { format: "pdf", scope: "scene-studio" },
    { format: "png", scope: "scene-studio" },
  ]);

  await page.getByTitle("全部收起源码层级").click();
  await expect.poll(async () => (await studioState(page)).view_state.module_expansion.length).toBe(0);
  await expect.poll(() => page.locator(".lab-node").count()).toBeLessThanOrEqual(initialCount);
  const collapsedCount = await page.locator(".lab-node").count();
  let node = page.locator(".lab-node[data-node-id*='hierarchy:']").first();
  await expect(node).toBeVisible();
  await node.click();
  await expect(page.locator(".source-binding-summary")).toBeVisible();
  await expect(page.locator(".source-evidence-panel")).toBeVisible();
  await expect.poll(() => page.locator(".source-excerpt pre span").count()).toBeGreaterThan(0);
  const expandResponse = page.waitForResponse((response) => response.url().endsWith("/api/patch-batch") && response.request().method() === "POST");
  await page.getByRole("button", { name: "展开源码层级", exact: true }).click();
  expect((await expandResponse).ok()).toBe(true);
  await expect.poll(() => page.locator(".lab-node").count()).toBeGreaterThan(collapsedCount);
  const ffnGroup = page.locator(".lab-node").filter({ has: page.locator(".node-label", { hasText: /^ffn$/ }) }).first();
  await ffnGroup.click();
  const ffnExpand = page.getByRole("button", { name: "展开源码层级", exact: true });
  if (await ffnExpand.isVisible().catch(() => false)) {
    const ffnResponse = page.waitForResponse((response) => response.url().endsWith("/api/patch-batch") && response.request().method() === "POST");
    await ffnExpand.click();
    expect((await ffnResponse).ok()).toBe(true);
  }
  await page.getByRole("button", { name: "模型", exact: true }).click();
  const projectedNodes = page.locator(".lab-node[data-node-id*='hierarchy:']");
  let parameterPanelFound = false;
  for (let index = 0; index < await projectedNodes.count(); index += 1) {
    await projectedNodes.nth(index).click();
    if (await page.locator(".parameter-transaction-panel").isVisible().catch(() => false)) {
      parameterPanelFound = true;
      break;
    }
  }
  expect(parameterPanelFound).toBe(true);
  const parameterPanel = page.locator(".parameter-transaction-panel");
  await expect(parameterPanel.locator(".parameter-impact")).toBeVisible();
  await expect(parameterPanel.locator(".parameter-impact")).toContainText(/direct|adapter-required|readonly/);
  await expect(parameterPanel).toContainText(/config-key|constructor-literal|module-field|computed-expression/);
  if (await parameterPanel.getByText("编辑作用域").isVisible().catch(() => false)) {
    await expect(parameterPanel.locator("select")).toHaveCount(2);
  }
  const parameterInput = parameterPanel.locator("input").first();
  const currentParameter = Number(await parameterInput.inputValue());
  expect(Number.isFinite(currentParameter)).toBe(true);
  await parameterInput.fill(String(currentParameter + 1));
  const prepareResponse = page.waitForResponse((response) => response.url().endsWith("/api/transaction/prepare") && response.request().method() === "POST");
  await parameterPanel.getByRole("button", { name: "准备并验证" }).click();
  expect((await prepareResponse).ok()).toBe(true);
  const transactionDrawer = page.getByRole("complementary", { name: "源码事务审查" });
  await expect(transactionDrawer).toBeVisible();
  await expect(transactionDrawer).toContainText("提交与状态兼容性");
  await expect(transactionDrawer).toContainText("checkpoint/state");
  await expect(transactionDrawer).toContainText("not-bound");
  expect(await transactionDrawer.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: "/tmp/archcanvas-scene-studio-transaction-compatibility.png", fullPage: true });
  const discardResponse = page.waitForResponse((response) => response.url().endsWith("/api/transaction/discard") && response.request().method() === "POST");
  await transactionDrawer.getByRole("button", { name: "放弃" }).click();
  expect((await discardResponse).ok()).toBe(true);
  await expect(transactionDrawer).toBeHidden();
  await page.getByRole("button", { name: "打开拓扑草稿工作台" }).click();
  await expect(page.getByRole("complementary", { name: "拓扑草稿工作台" })).toBeVisible();
  await expect(page.getByRole("button", { name: "解锁拓扑草稿" })).toBeVisible();
  await page.screenshot({ path: "/tmp/archcanvas-scene-studio-graph-draft.png", fullPage: true });
  await page.getByTitle("收起拓扑草稿工作台").click();
  await page.getByRole("button", { name: "布局", exact: true }).click();
  const layoutNodes = page.locator(".lab-node[data-node-id*='hierarchy:']");
  await expect.poll(() => layoutNodes.count()).toBeGreaterThanOrEqual(3);
  await layoutNodes.nth(0).click();
  await layoutNodes.nth(1).click({ modifiers: ["Shift"] });
  await layoutNodes.nth(2).click({ modifiers: ["Shift"] });
  await expect(page.getByRole("group", { name: "对齐、分布与固定" })).toContainText("3 已选");
  const alignResponse = page.waitForResponse((response) => response.url().endsWith("/api/patch-batch") && response.request().method() === "POST");
  await page.getByTitle("顶端对齐").click();
  expect((await alignResponse).ok()).toBe(true);
  await expect.poll(async () => {
    const values = await Promise.all([0, 1, 2].map((index) => layoutNodes.nth(index).evaluate((element: SVGGElement) => element.getBBox().y)));
    return new Set(values.map((value) => Math.round(value))).size;
  }).toBe(1);

  const pinResponse = page.waitForResponse((response) => response.url().endsWith("/api/patch-batch") && response.request().method() === "POST");
  await page.getByTitle("固定所选节点").click();
  expect((await pinResponse).ok()).toBe(true);
  await expect.poll(async () => (await studioState(page)).view_state.pinned_node_ids.length).toBeGreaterThanOrEqual(3);
  const pinnedX = await layoutNodes.nth(0).evaluate((element: SVGGElement) => element.getBBox().x);
  await drag(page, layoutNodes.nth(0).locator(".node-surface"), 40, 0);
  expect(await layoutNodes.nth(0).evaluate((element: SVGGElement) => element.getBBox().x)).toBe(pinnedX);
  const unpinResponse = page.waitForResponse((response) => response.url().endsWith("/api/patch-batch") && response.request().method() === "POST");
  await page.getByTitle("取消固定所选节点").click();
  expect((await unpinResponse).ok()).toBe(true);

  const darkResponse = page.waitForResponse((response) => response.url().endsWith("/api/patch") && response.request().method() === "POST");
  await page.getByTitle("切换深色主题").click();
  expect((await darkResponse).ok()).toBe(true);
  await expect(page.locator(".scene-studio-root")).toHaveClass(/theme-studio-dark/);
  await page.reload();
  await expect(page.locator(".scene-studio-root")).toHaveClass(/theme-studio-dark/);
  const lightResponse = page.waitForResponse((response) => response.url().endsWith("/api/patch") && response.request().method() === "POST");
  await page.getByTitle("切换浅色主题").click();
  expect((await lightResponse).ok()).toBe(true);
  await expect(page.locator(".scene-studio-root")).toHaveClass(/theme-paper-light/);

  node = page.locator(".lab-node[data-node-id*='hierarchy:']").filter({
    has: page.locator(".node-label", { hasText: /^ffn_in$/ }),
  }).first();
  await expect(node).toBeVisible();
  const sceneNodeId = await node.getAttribute("data-node-id");
  if (!sceneNodeId) throw new Error("source-backed node has no stable scene identity");
  const hierarchyId = await node.getAttribute("data-hierarchy-node-id");
  if (!hierarchyId) throw new Error("source-backed node has no hierarchy binding");
  const before = await node.evaluate((element: SVGGElement) => element.getBBox().x);
  const patchResponse = page.waitForResponse((response) => response.url().endsWith("/api/patch") && response.request().method() === "POST");
  await drag(page, node.locator(".node-surface"), 30, 18);
  const completedPatch = await patchResponse;
  expect(completedPatch.ok()).toBe(true);
  const persistedTarget = (completedPatch.request().postDataJSON() as { target_id?: string }).target_id;
  expect(hierarchyId).toMatch(/^hierarchy:/);
  expect(persistedTarget).toBe(`view:${hierarchyId}`);
  await expect.poll(async () => persistedTarget && (await studioState(page)).view_state.node_positions[persistedTarget]).toBeTruthy();
  const changed = await studioState(page);
  expect(changed.integrity).toEqual(baseline.integrity);

  await page.reload();
  await expect.poll(() => page.locator(".lab-node").count()).toBeGreaterThan(0);
  const reloaded = page.locator(`[data-node-id="${sceneNodeId}"]`);
  await expect(reloaded).toBeVisible();
  expect(await reloaded.evaluate((element: SVGGElement) => element.getBBox().x)).not.toBe(before);

  await page.locator(".preset-control select").selectOption("paper-publication");
  await expect(page.locator(".scene-lab")).toHaveClass(/paper-layout/);
  expect((await studioState(page)).integrity).toEqual(baseline.integrity);
  await page.screenshot({ path: "/tmp/archcanvas-scene-studio-paper.png", fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(canvas).toBeVisible();
  await page.getByTitle("打开搜索、问题与任务").click();
  const mobileOperations = page.getByRole("complementary", { name: "搜索、问题与任务" });
  await mobileOperations.getByRole("tab", { name: /恢复/ }).click();
  await expect(mobileOperations).toContainText(/没有崩溃恢复记录|rolled-back|committed/);
  await mobileOperations.getByRole("tab", { name: /一致性/ }).click();
  await expect(mobileOperations.locator(".conformance-list")).toContainText("source-view");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "/tmp/archcanvas-scene-studio-mobile-e2e.png", fullPage: true });
  await mobileOperations.getByTitle("关闭搜索、问题与任务").click();

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator(".preset-control select").selectOption("engineering-flow");
  const undoResponse = page.waitForResponse((response) => response.url().endsWith("/api/undo") && response.request().method() === "POST");
  await page.getByTitle("撤销").click();
  expect((await undoResponse).ok()).toBe(true);
  expect((await studioState(page)).integrity).toEqual(baseline.integrity);
});
