import { expect, test, type Locator, type Page } from "@playwright/test";

type StudioState = {
  integrity: { source_digest: string; exact_ir_digest: string };
  document: { visual_patches: unknown[]; redo_patches: unknown[] };
  view_state: {
    node_positions: Record<string, { x: number; y: number }>;
    module_expansion: string[];
    source_expansion: string[];
    navigation_view: "module" | "source";
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

async function firstUnobstructedNode(page: Page, nodes: Locator): Promise<Locator> {
  for (let index = 0; index < await nodes.count(); index += 1) {
    const node = nodes.nth(index);
    const id = await node.getAttribute("data-node-id");
    const box = await node.locator(".node-surface").boundingBox();
    if (!id || !box) continue;
    const hitsItself = await page.evaluate(({ x, y, expectedId }) => (
      document.elementFromPoint(x, y)?.closest("[data-node-id]")?.getAttribute("data-node-id") === expectedId
    ), { x: box.x + box.width / 2, y: box.y + box.height / 2, expectedId: id });
    if (hitsItself) return page.locator(`[data-node-id="${id}"]`);
  }
  throw new Error("no unobstructed source-backed node is available for pointer verification");
}

test("source-backed scene uses one canvas across presets and persists visual patches", async ({ page }) => {
  const routingWorkerResponses: string[] = [];
  const pythonSyntaxResponses: string[] = [];
  page.on("response", (response) => {
    if (response.url().includes("routing.worker-")) routingWorkerResponses.push(response.url());
    if (response.url().includes("python-syntax.worker-") || response.url().includes("tree-sitter") && response.url().endsWith(".wasm")) {
      pythonSyntaxResponses.push(response.url());
    }
  });
  await page.goto("/");
  const canvas = page.locator("svg.lab-canvas");
  await expect(canvas).toBeVisible();
  await expect.poll(() => page.locator(".lab-node").count()).toBeGreaterThan(0);
  await expect.poll(() => page.locator(".lab-edge").count()).toBeGreaterThan(0);
  const baseline = await studioState(page);
  const initialCount = await page.locator(".lab-node").count();

  const navigationTabs = page.locator(".navigation-tabs");
  const inspectorTabs = page.locator(".inspector-tabs");
  await expect(navigationTabs.getByRole("tab", { name: "模块" })).toHaveAttribute("aria-selected", "true");
  const sourceNavigationResponse = page.waitForResponse((response) => response.url().endsWith("/api/navigation") && response.request().method() === "POST");
  await navigationTabs.getByRole("tab", { name: "源码" }).click();
  expect((await sourceNavigationResponse).ok()).toBe(true);
  await expect.poll(async () => (await studioState(page)).view_state.navigation_view).toBe("source");
  const expandSourceResponse = page.waitForResponse((response) => response.url().endsWith("/api/navigation") && response.request().method() === "POST");
  await page.getByTitle("全部展开源码树").click();
  expect((await expandSourceResponse).ok()).toBe(true);
  await expect.poll(async () => (await studioState(page)).view_state.source_expansion.length).toBeGreaterThan(0);
  await page.reload();
  await expect(navigationTabs.getByRole("tab", { name: "源码" })).toHaveAttribute("aria-selected", "true");
  const moduleNavigationResponse = page.waitForResponse((response) => response.url().endsWith("/api/navigation") && response.request().method() === "POST");
  await navigationTabs.getByRole("tab", { name: "模块" }).click();
  expect((await moduleNavigationResponse).ok()).toBe(true);
  const expandModuleNavigationResponse = page.waitForResponse((response) => response.url().endsWith("/api/navigation") && response.request().method() === "POST");
  await page.getByTitle("全部展开源码层级").click();
  expect((await expandModuleNavigationResponse).ok()).toBe(true);
  await expect.poll(async () => (await studioState(page)).view_state.module_expansion.length).toBeGreaterThan(0);
  const navigationSearch = page.getByLabel("搜索导航");
  await navigationSearch.fill("transformer");
  await expect.poll(() => page.locator(".navigation-tree .navigation-row").count()).toBeGreaterThan(0);
  await navigationSearch.fill("");
  const navigationRows = page.locator(".navigation-tree .tree-label");
  for (let index = 0; index < Math.min(await navigationRows.count(), 12); index += 1) {
    await navigationRows.nth(index).click();
    if (await page.locator(".lab-node.selected").count()) break;
  }
  await expect(page.locator(".lab-node.selected")).toHaveCount(1);
  await page.getByTitle("收起左侧导航").click();
  await expect(page.locator(".lab-workspace")).toHaveClass(/left-panel-collapsed/);
  await page.getByTitle("展开左侧导航").click();
  await expect(page.locator(".lab-workspace")).not.toHaveClass(/left-panel-collapsed/);
  await page.getByTitle("收起右侧检查器").click();
  await expect(page.locator(".lab-workspace")).toHaveClass(/right-panel-collapsed/);
  await page.getByTitle("展开右侧检查器").click();
  await expect(page.locator(".lab-workspace")).not.toHaveClass(/right-panel-collapsed/);
  await expect(page.getByRole("button", { name: "重新布局" })).toHaveCount(0);
  await expect(page.getByRole("group", { name: "对齐、分布与固定" })).toHaveCount(0);
  await expect(page.getByTitle("重置视觉布局")).toHaveCount(0);

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

  await page.locator(".lab-node[data-hierarchy-node-id]").first().click();
  await inspectorTabs.getByRole("tab", { name: "源码", exact: true }).click();
  await page.getByRole("button", { name: "打开源码工作区" }).click();
  const sourceWorkspace = page.locator(".source-workspace-drawer");
  await expect(sourceWorkspace).toBeVisible();
  await expect(sourceWorkspace.locator(".cm-editor")).toBeVisible();
  await expect(sourceWorkspace.locator("textarea")).toHaveCount(0);
  const syntaxBar = sourceWorkspace.locator(".codemirror-syntax-bar");
  await expect(syntaxBar).toHaveAttribute("data-syntax-source", "editor-local");
  await expect(syntaxBar).toHaveAttribute("data-syntax-status", "ready");
  await expect(syntaxBar).toContainText("0 errors");
  await sourceWorkspace.locator(".cm-content").click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText("\ndef broken(:\n");
  await expect(syntaxBar).toContainText(/[1-9]\d* errors/);
  await expect(syntaxBar).toHaveAttribute("data-syntax-parse-mode", "incremental");
  await page.keyboard.press("Control+z");
  await expect(syntaxBar).toContainText("0 errors");
  await expect(syntaxBar).toHaveAttribute("data-syntax-parse-mode", "incremental");
  expect(pythonSyntaxResponses.some((url) => url.includes("python-syntax.worker-"))).toBe(true);
  expect(pythonSyntaxResponses.filter((url) => url.endsWith(".wasm")).length).toBeGreaterThanOrEqual(2);
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

  const collapseModuleNavigation = page.getByTitle("全部收起源码层级");
  if (await collapseModuleNavigation.isEnabled()) {
    const collapseNavigationResponse = page.waitForResponse((response) => response.url().endsWith("/api/navigation") && response.request().method() === "POST");
    await collapseModuleNavigation.click();
    expect((await collapseNavigationResponse).ok()).toBe(true);
  }
  await expect.poll(async () => (await studioState(page)).view_state.module_expansion.length).toBe(0);
  await expect.poll(() => page.locator(".lab-node").count()).toBeLessThanOrEqual(initialCount);
  let node = page.locator(".lab-node[data-hierarchy-node-id]").first();
  await expect(node).toBeVisible();
  await node.click();
  await inspectorTabs.getByRole("tab", { name: "概览", exact: true }).click();
  await expect(page.locator(".overview-section")).toBeVisible();
  await expect(page.locator(".canonical-list, .schematic-notice")).toBeVisible();
  await inspectorTabs.getByRole("tab", { name: "源码", exact: true }).click();
  await expect(page.locator(".source-only-panel")).toBeVisible();
  await expect.poll(() => page.locator(".source-excerpt pre span").count()).toBeGreaterThan(0);
  await inspectorTabs.getByRole("tab", { name: "证据", exact: true }).click();
  await expect(page.locator(".source-evidence-panel")).toBeVisible();
  await inspectorTabs.getByRole("tab", { name: "视觉", exact: true }).click();
  await expect(page.getByRole("button", { name: /固定节点位置|取消固定节点/ })).toBeVisible();
  const expandDetail = page.getByRole("button", { name: /展开.+内部数据流/ }).first();
  await expect(expandDetail).toBeVisible();
  await expandDetail.click();
  await expect.poll(() => page.locator(".detail-interactive-node").count()).toBeGreaterThan(0);
  await page.locator(".mode-switch").getByRole("button", { name: "模型", exact: true }).click();
  await inspectorTabs.getByRole("tab", { name: "模型", exact: true }).click();
  const projectedNodes = page.locator(".lab-node[data-hierarchy-node-id]");
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
  const collapseDetails = page.getByRole("button", { name: "全部收起", exact: true });
  if (await collapseDetails.isEnabled()) await collapseDetails.click();
  await expect(page.locator(".detail-interactive-node")).toHaveCount(0);
  await page.locator(".mode-switch").getByRole("button", { name: "布局", exact: true }).click();
  await expect(page.getByRole("button", { name: "重新布局" })).toBeVisible();
  const layoutNodes = page.locator(".lab-node[data-hierarchy-node-id]");
  await expect.poll(() => layoutNodes.count()).toBeGreaterThanOrEqual(3);
  const candidateSceneNodeIds = new Set((await layoutNodes.evaluateAll((elements) => (
    elements.slice(0, 3).map((element) => element.getAttribute("data-node-id")).filter((id): id is string => Boolean(id))
  ))));
  if (candidateSceneNodeIds.size !== 3) throw new Error("layout tools need three stable source-backed scene identities");
  const selectedLayoutNodes = [...candidateSceneNodeIds].map((id) => page.locator(`[data-node-id="${id}"]`));
  await selectedLayoutNodes[0].click();
  await selectedLayoutNodes[1].click({ modifiers: ["Shift"] });
  await selectedLayoutNodes[2].click({ modifiers: ["Shift"] });
  const selectedSceneNodeIds = new Set(await page.locator(".lab-node.selected").evaluateAll((elements) => (
    elements.map((element) => element.getAttribute("data-node-id")).filter((id): id is string => Boolean(id))
  )));
  expect([...selectedSceneNodeIds].sort()).toEqual([...candidateSceneNodeIds].sort());
  const hierarchyBindingsBeforePin = Object.fromEntries(await Promise.all([...selectedSceneNodeIds].map(async (id) => [
    id,
    await page.locator(`[data-node-id="${id}"]`).getAttribute("data-hierarchy-node-id"),
  ])));
  await expect(page.getByRole("group", { name: "对齐、分布与固定" })).toContainText("3 已选");
  const alignResponse = page.waitForResponse((response) => response.url().endsWith("/api/patch-batch") && response.request().method() === "POST");
  await page.getByTitle("顶端对齐").click();
  expect((await alignResponse).ok()).toBe(true);
  await expect.poll(async () => {
    const values = await Promise.all(selectedLayoutNodes.map((selectedLayoutNode) => selectedLayoutNode.evaluate((element: SVGGElement) => element.getBBox().y)));
    return new Set(values.map((value) => Math.round(value))).size;
  }).toBe(1);

  const pinResponse = page.waitForResponse((response) => response.url().endsWith("/api/patch-batch") && response.request().method() === "POST");
  await page.getByTitle("固定所选节点").click();
  const completedPinResponse = await pinResponse;
  expect(completedPinResponse.ok()).toBe(true);
  const pinRequest = completedPinResponse.request().postDataJSON() as { patches?: Array<{ target_id?: string }> };
  expect((pinRequest.patches ?? []).map((patch) => patch.target_id).sort()).toEqual(
    Object.values(hierarchyBindingsBeforePin).map((id) => `view:${id}`).sort(),
  );
  await expect.poll(async () => (await studioState(page)).view_state.pinned_node_ids.length).toBeGreaterThanOrEqual(3);
  await expect(page.getByTitle("取消固定所选节点")).toBeVisible();
  const hierarchyBindingsAfterPin = Object.fromEntries(await Promise.all([...selectedSceneNodeIds].map(async (id) => [
    id,
    await page.locator(`[data-node-id="${id}"]`).getAttribute("data-hierarchy-node-id"),
  ])));
  expect(hierarchyBindingsAfterPin).toEqual(hierarchyBindingsBeforePin);
  let pinnedSceneNodeId: string | undefined;
  for (const id of selectedSceneNodeIds) {
    const surface = page.locator(`[data-node-id="${id}"] .node-surface`);
    const box = await surface.boundingBox();
    if (!box) continue;
    const hitsItself = await page.evaluate(({ x, y, expectedId }) => (
      document.elementFromPoint(x, y)?.closest("[data-node-id]")?.getAttribute("data-node-id") === expectedId
    ), { x: box.x + box.width / 2, y: box.y + box.height / 2, expectedId: id });
    if (hitsItself) {
      pinnedSceneNodeId = id;
      break;
    }
  }
  if (!pinnedSceneNodeId) throw new Error("no unobstructed pinned node is available for drag verification");
  const pinnedNode = page.locator(`[data-node-id="${pinnedSceneNodeId}"]`);
  const pinnedX = await pinnedNode.evaluate((element: SVGGElement) => element.getBBox().x);
  await drag(page, pinnedNode.locator(".node-surface"), 40, 0);
  expect(await pinnedNode.evaluate((element: SVGGElement) => element.getBBox().x)).toBe(pinnedX);

  await expect.poll(() => layoutNodes.count()).toBeGreaterThan(3);
  const pinnedStateBeforeLayout = await studioState(page);
  const pinnedTargetIds = new Set(pinnedStateBeforeLayout.view_state.pinned_node_ids);
  const pinnedPositionsBeforeLayout = Object.fromEntries([...pinnedTargetIds].map((targetId) => [
    targetId,
    pinnedStateBeforeLayout.view_state.node_positions[targetId] ?? null,
  ]));
  const movableSceneNodeId = (await layoutNodes.evaluateAll((elements) => (
    elements.map((element) => element.getAttribute("data-node-id"))
  ))).find((id) => id && !selectedSceneNodeIds.has(id));
  if (!movableSceneNodeId) throw new Error("ELK browser check needs one unpinned node");
  const movableNode = page.locator(`[data-node-id="${movableSceneNodeId}"]`);
  const movableBeforeLayout = await movableNode.evaluate((element: SVGGElement) => {
    const bounds = element.getBBox();
    return { x: bounds.x, y: bounds.y };
  });
  const layoutResponse = page.waitForResponse((response) => {
    if (!response.url().endsWith("/api/patch-batch") || response.request().method() !== "POST") return false;
    return (response.request().postDataJSON() as { description?: string } | null)?.description === "Explicit ELK layered relayout";
  });
  await page.getByRole("button", { name: "重新布局" }).click();
  const completedLayoutResponse = await layoutResponse;
  expect(completedLayoutResponse.ok()).toBe(true);
  const layoutRequest = completedLayoutResponse.request().postDataJSON() as {
    patches?: Array<{ target_id?: string }>;
  };
  expect((layoutRequest.patches ?? []).every((patch) => !patch.target_id || !pinnedTargetIds.has(patch.target_id))).toBe(true);
  await expect(page.getByRole("button", { name: "重新布局" })).toBeEnabled();
  await expect.poll(async () => {
    const current = await studioState(page);
    return Object.fromEntries([...pinnedTargetIds].map((targetId) => [
      targetId,
      current.view_state.node_positions[targetId] ?? null,
    ]));
  }).toEqual(pinnedPositionsBeforeLayout);
  await expect.poll(async () => movableNode.evaluate((element: SVGGElement, before) => {
    const bounds = element.getBBox();
    return bounds.x !== before.x || bounds.y !== before.y;
  }, movableBeforeLayout)).toBe(true);
  await page.screenshot({ path: "/tmp/archcanvas-scene-studio-elk-relayout.png", fullPage: true });

  const undoLayoutResponse = page.waitForResponse((response) => response.url().endsWith("/api/undo") && response.request().method() === "POST");
  await page.getByTitle("撤销").click();
  expect((await undoLayoutResponse).ok()).toBe(true);
  await expect.poll(async () => movableNode.evaluate((element: SVGGElement) => {
    const bounds = element.getBBox();
    return { x: bounds.x, y: bounds.y };
  })).toEqual(movableBeforeLayout);

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

  node = await firstUnobstructedNode(page, page.locator(".lab-node[data-hierarchy-node-id]"));
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

  await page.getByRole("button", { name: "全部展开", exact: true }).click();
  await expect(canvas).toHaveAttribute("data-viewport-detail-mode", "virtualized");
  await expect(canvas).toHaveAttribute("data-routing-mode", "worker-ready", { timeout: 20_000 });
  expect(routingWorkerResponses.length).toBeGreaterThan(0);
  await expect(page.locator(".lab-node")).toHaveCount(initialCount);
  await expect.poll(() => page.locator(".detail-interactive-node").count()).toBeGreaterThan(0);
  expect(await page.locator(".lab-node > .node-surface").count()).toBe(await page.locator(".lab-node").count());
  expect(await page.locator(".edge-hit").count()).toBe(await page.locator(".lab-edge").count());
  expect(await page.locator(".edge-path").count()).toBe(await page.locator(".lab-edge").count());

  for (let index = 0; index < 6; index += 1) await page.getByTitle("放大").click();
  await expect.poll(() => page.locator('.lab-node[data-detail-rendering="surface"]').count()).toBeGreaterThan(0);
  await expect.poll(() => page.locator('.lab-edge[data-label-rendering="deferred"]').count()).toBeGreaterThan(0);
  const visibleBeforePan = await page.locator('.lab-node[data-detail-rendering="full"]').evaluateAll((elements) => (
    elements.map((element) => element.getAttribute("data-node-id")).sort()
  ));
  const viewportBox = await page.locator(".canvas-viewport").boundingBox();
  if (!viewportBox) throw new Error("large-scene viewport is not visible");
  const panStart = {
    x: viewportBox.x + viewportBox.width * 0.25,
    y: viewportBox.y + viewportBox.height * 0.5,
  };
  const panDistance = viewportBox.width * 0.5;
  for (let index = 0; index < 4; index += 1) {
    await page.mouse.move(panStart.x, panStart.y);
    await page.mouse.down({ button: "middle" });
    await page.mouse.move(panStart.x + panDistance, panStart.y, { steps: 8 });
    await page.mouse.up({ button: "middle" });
  }
  await expect.poll(async () => page.locator('.lab-node[data-detail-rendering="full"]').evaluateAll((elements) => (
    elements.map((element) => element.getAttribute("data-node-id")).sort()
  ))).not.toEqual(visibleBeforePan);
  await page.screenshot({ path: "/tmp/archcanvas-scene-studio-viewport-virtualization.png", fullPage: true });
});
