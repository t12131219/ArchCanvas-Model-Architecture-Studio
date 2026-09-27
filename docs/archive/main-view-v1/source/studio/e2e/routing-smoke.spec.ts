import { expect, test, type Page } from "@playwright/test";

interface Point {
  x: number;
  y: number;
}

interface SceneNode {
  scene_node_id: string;
  bounds: Point & { width: number; height: number };
}

interface SceneEdge {
  scene_edge_id: string;
  source_scene_node_id: string;
  target_scene_node_id: string;
  points: Point[];
  source_port_id: string | null;
  target_port_id: string | null;
  route_digest: string | null;
}

interface StudioState {
  active_projection_id: string;
  scenes: Record<string, { nodes: SceneNode[]; edges: SceneEdge[] }>;
  document: { visual_patches: unknown[]; redo_patches: unknown[] };
  routing: {
    mode: string;
    visible_engine: string;
    reports: Record<string, {
      status: string;
      receipt: { route_digest: string; metrics: {
        invalid_endpoint_count: number;
        obstacle_intersection_count: number;
      } };
    }>;
  };
}

function parsePoints(value: string | null): Point[] {
  if (!value) return [];
  return value.trim().split(/\s+/).map((pair) => {
    const [x, y] = pair.split(",").map(Number);
    return { x, y };
  });
}

function departure(points: Point[], source: boolean): string {
  const ordered = source ? points : [...points].reverse();
  for (let index = 1; index < ordered.length; index += 1) {
    const dx = ordered[index].x - ordered[index - 1].x;
    const dy = ordered[index].y - ordered[index - 1].y;
    if (Math.abs(dx) > 0.01) return dx > 0 ? "right" : "left";
    if (Math.abs(dy) > 0.01) return dy > 0 ? "bottom" : "top";
  }
  return "stationary";
}

function expectOrthogonal(points: Point[]) {
  expect(points.length).toBeGreaterThanOrEqual(2);
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    expect(
      Math.abs(previous.x - current.x) < 0.01
      || Math.abs(previous.y - current.y) < 0.01,
    ).toBeTruthy();
  }
}

async function state(page: Page): Promise<StudioState> {
  return page.evaluate(async () => {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  });
}

function activeScene(value: StudioState) {
  return value.scenes[value.active_projection_id];
}

function nodeBounds(value: StudioState, nodeId: string) {
  const node = activeScene(value).nodes.find((item) => item.scene_node_id === nodeId);
  if (!node) throw new Error(`missing node ${nodeId}`);
  return node.bounds;
}

async function dragNode(
  page: Page,
  nodeId: string,
  edgeId: string,
  delta: Point,
) {
  const node = page.locator(`[data-scene-node-id="${nodeId}"]`);
  const edge = page.locator(
    `[data-scene-edge-id="${edgeId}"][data-edge-layer="base"]`,
  );
  const path = edge.locator(".edge-path");
  const box = await node.boundingBox();
  if (!box) throw new Error(`node ${nodeId} is not visible`);
  const start = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  const beforePoints = parsePoints(await path.getAttribute("points"));
  const sourceDeparture = departure(beforePoints, true);
  const targetDeparture = departure(beforePoints, false);
  await node.evaluate((element) => {
    (window as Window & { __routingSmokeNode?: Element }).__routingSmokeNode = element;
  });

  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x + delta.x / 2, start.y + delta.y / 2, { steps: 4 });
  await expect(node).toHaveAttribute("transform", /translate\(/);
  const middlePoints = parsePoints(await path.getAttribute("points"));
  expect(middlePoints).not.toEqual(beforePoints);
  expectOrthogonal(middlePoints);
  expect(departure(middlePoints, true)).toBe(sourceDeparture);
  expect(departure(middlePoints, false)).toBe(targetDeparture);
  expect(await node.evaluate((element) => (
    (window as Window & { __routingSmokeNode?: Element }).__routingSmokeNode === element
  ))).toBeTruthy();

  await page.mouse.move(start.x + delta.x, start.y + delta.y, { steps: 4 });
  const finalPreview = parsePoints(await path.getAttribute("points"));
  expectOrthogonal(finalPreview);
  expect(departure(finalPreview, true)).toBe(sourceDeparture);
  expect(departure(finalPreview, false)).toBe(targetDeparture);
  const response = page.waitForResponse((candidate) => (
    candidate.url().endsWith("/api/patch-batch")
    && candidate.request().method() === "POST"
  ));
  await page.mouse.up();
  expect((await response).ok()).toBeTruthy();
  await expect(node).not.toHaveAttribute("transform", /translate\(/);
  return { beforePoints, finalPreview };
}

test("atomic routing survives preview, cancellation, history, expansion, and reload", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("archcanvas.locale", "en"));
  await page.goto("/");
  await page.getByRole("dialog", { name: "Open model" })
    .getByRole("button", { name: "Close" })
    .click();
  await expect(page.locator("svg.scene")).toBeVisible();
  await expect(page.locator(".scene-node:not(.root)").first()).toBeVisible();

  const initial = await state(page);
  const projectionId = initial.active_projection_id;
  const initialReport = initial.routing.reports[projectionId];
  expect(initial.routing.mode).toBe("atomic-v1");
  expect(initial.routing.visible_engine).toBe("atomic-v1");
  expect(initialReport.status).toBe("routed");
  expect(initialReport.receipt.metrics.invalid_endpoint_count).toBe(0);
  expect(initialReport.receipt.metrics.obstacle_intersection_count).toBe(0);
  expect(activeScene(initial).edges.length).toBeGreaterThan(0);
  for (const edge of activeScene(initial).edges) {
    expect(edge.source_port_id).toBeTruthy();
    expect(edge.target_port_id).toBeTruthy();
    expect(edge.route_digest).toBe(initialReport.receipt.route_digest);
    expectOrthogonal(edge.points);
  }

  await page.getByRole("button", { name: "Layout", exact: true }).click();
  const firstEdge = activeScene(initial).edges[0];
  const nodeId = firstEdge.source_scene_node_id;
  const edgeId = firstEdge.scene_edge_id;
  const initialBounds = nodeBounds(initial, nodeId);
  await dragNode(page, nodeId, edgeId, { x: 46, y: 28 });
  const afterFirst = await state(page);
  const firstBounds = nodeBounds(afterFirst, nodeId);
  expect(firstBounds.x).not.toBe(initialBounds.x);
  expect(afterFirst.routing.reports[projectionId].receipt.route_digest)
    .not.toBe(initialReport.receipt.route_digest);

  await dragNode(page, nodeId, edgeId, { x: 34, y: -20 });
  const afterSecond = await state(page);
  const secondBounds = nodeBounds(afterSecond, nodeId);
  expect(secondBounds).not.toEqual(firstBounds);

  const patchCountBeforeCancel = afterSecond.document.visual_patches.length;
  const node = page.locator(`[data-scene-node-id="${nodeId}"]`);
  const nodeBox = await node.boundingBox();
  if (!nodeBox) throw new Error("drag cancellation node is not visible");
  await page.mouse.move(nodeBox.x + nodeBox.width / 2, nodeBox.y + nodeBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(nodeBox.x + nodeBox.width / 2 + 38, nodeBox.y + nodeBox.height / 2 + 22);
  await expect(node).toHaveAttribute("transform", /translate\(/);
  await page.locator("svg.scene").dispatchEvent("pointercancel", { pointerId: 1 });
  await expect(node).not.toHaveAttribute("transform", /translate\(/);
  await page.mouse.up();
  expect((await state(page)).document.visual_patches.length).toBe(patchCountBeforeCancel);

  const undoResponse = page.waitForResponse((candidate) => candidate.url().endsWith("/api/undo"));
  await page.getByRole("button", { name: "Undo" }).click();
  expect((await undoResponse).ok()).toBeTruthy();
  await expect.poll(async () => nodeBounds(await state(page), nodeId)).toEqual(firstBounds);
  const redoResponse = page.waitForResponse((candidate) => candidate.url().endsWith("/api/redo"));
  await page.getByRole("button", { name: "Redo" }).click();
  expect((await redoResponse).ok()).toBeTruthy();
  await expect.poll(async () => nodeBounds(await state(page), nodeId)).toEqual(secondBounds);

  const expandButton = page.getByRole("button", { name: /^Expand / }).first();
  const expandLabel = await expandButton.getAttribute("aria-label");
  expect(expandLabel).toBeTruthy();
  const beforeExpansionCount = activeScene(await state(page)).nodes.length;
  const expandResponse = page.waitForResponse((candidate) => candidate.url().endsWith("/api/navigation"));
  await expandButton.click();
  expect((await expandResponse).ok()).toBeTruthy();
  await expect.poll(async () => activeScene(await state(page)).nodes.length)
    .not.toBe(beforeExpansionCount);
  const expanded = await state(page);
  expect(expanded.routing.visible_engine).toBe("atomic-v1");
  expect(expanded.routing.reports[expanded.active_projection_id].status).toBe("routed");

  const collapseName = expandLabel!.replace(/^Expand /, "Collapse ");
  const collapseResponse = page.waitForResponse((candidate) => candidate.url().endsWith("/api/navigation"));
  await page.getByRole("button", { name: collapseName, exact: true }).click();
  expect((await collapseResponse).ok()).toBeTruthy();
  await expect.poll(async () => activeScene(await state(page)).nodes.length)
    .toBe(beforeExpansionCount);

  const beforeReload = await state(page);
  const beforeReloadDigest = beforeReload.routing.reports[projectionId].receipt.route_digest;
  await page.reload();
  await expect(page.locator("svg.scene")).toBeVisible();
  const reloaded = await state(page);
  expect(nodeBounds(reloaded, nodeId)).toEqual(secondBounds);
  expect(reloaded.routing.reports[projectionId].receipt.route_digest).toBe(beforeReloadDigest);
  expect(reloaded.document.redo_patches).toHaveLength(0);

  await page.setViewportSize({ width: 430, height: 900 });
  await expect(page.locator("svg.scene")).toBeVisible();
  const svgBox = await page.locator("svg.scene").boundingBox();
  expect(svgBox?.width).toBeGreaterThan(200);
  expect(svgBox?.height).toBeGreaterThan(200);
  expect(await page.locator(".scene-node:not(.root)").count()).toBeGreaterThan(0);
});
