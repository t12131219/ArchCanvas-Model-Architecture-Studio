import { expect, test, type Locator, type Page } from "@playwright/test";

type StudioState = {
  session_nonce: string;
  architecture: {
    architecture_id: string;
    nodes: Array<{
      node_id: string;
      input_ports: Array<{ port_id: string }>;
      output_ports: Array<{ port_id: string }>;
    }>;
    edges: Array<{
      producer_id: string;
      producer_port: string;
      consumer_id: string;
      consumer_port: string;
    }>;
  };
  hierarchy: {
    root_node_id: string;
    nodes: Array<{ hierarchy_node_id: string; parent_hierarchy_node_id: string | null }>;
  };
  document: { source_digest: string; visual_patches: unknown[]; redo_patches: unknown[] };
  integrity: { source_digest: string; exact_ir_digest: string };
  view_state: {
    node_positions: Record<string, { x: number; y: number }>;
    node_sizes: Record<string, { width: number; height: number }>;
    detail_offsets: Record<string, { x: number; y: number }>;
    module_expansion: string[];
    route_style?: string;
    node_style?: string;
    label_style?: string;
    cameras: Record<string, { x: number; y: number; width?: number; height?: number }>;
  };
  draft: { nodes: Array<{ node_id: string }> };
  proposal?: { status: string; permissions: Record<string, boolean> } | null;
};

async function state(page: Page): Promise<StudioState> {
  return page.evaluate(async () => {
    const response = await fetch("/api/state");
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  });
}

async function closeOpenDialog(page: Page) {
  const dialog = page.getByRole("dialog", { name: "Open model" });
  try {
    await dialog.waitFor({ state: "visible", timeout: 5_000 });
    await dialog.getByRole("button", { name: "Close" }).click();
    await expect(dialog).toBeHidden();
  } catch {
    // The dialog is optional after the first project activation.
  }
}

async function waitForPatchBatch(page: Page, action: () => Promise<void>) {
  const response = page.waitForResponse((candidate) => (
    candidate.url().endsWith("/api/patch-batch") && candidate.request().method() === "POST"
  ));
  await action();
  expect((await response).ok()).toBe(true);
}

async function drag(page: Page, locator: Locator, dx: number, dy: number) {
  const box = await locator.boundingBox();
  if (!box) throw new Error("drag target is not visible");
  const start = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x + dx, start.y + dy, { steps: 8 });
  await page.mouse.up();
}

test("Phase 6 persists kernel state and keeps structural edits behind formal APIs", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("archcanvas.locale", "en"));
  await page.goto("/");
  await closeOpenDialog(page);
  const baseline = await state(page);
  const integrity = baseline.integrity;
  const node = page.locator(".kernel-node").filter({ hasText: /^encoder/ }).first();
  await expect(node).toBeVisible();
  const nodeId = await node.getAttribute("data-kernel-node-id");
  if (!nodeId) throw new Error("encoder has no stable kernel identity");

  const routeSelect = page.locator(".kernel-control-strip select").nth(0);
  const nodeSelect = page.locator(".kernel-control-strip select").nth(1);
  const labelSelect = page.locator(".kernel-control-strip select").nth(2);
  await waitForPatchBatch(page, () => routeSelect.selectOption("channel"));
  await waitForPatchBatch(page, () => nodeSelect.selectOption("technical"));
  await waitForPatchBatch(page, () => labelSelect.selectOption("endpoint"));
  await waitForPatchBatch(page, () => page.getByRole("button", { name: "Fit scene" }).click());

  await node.click();
  await expect(node).toHaveClass(/selected/);
  const beforeMove = await node.evaluate((element: SVGGElement) => element.getBBox().x);
  await drag(page, node.locator(".kernel-node-body"), 36, 20);
  await expect.poll(() => node.evaluate((element: SVGGElement) => element.getBBox().x)).not.toBe(beforeMove);
  await expect.poll(async () => (await state(page)).view_state.detail_offsets[nodeId]).toBeTruthy();
  let changed = await state(page);
  expect(changed.view_state.detail_offsets[nodeId]).toBeTruthy();
  expect(changed.integrity).toEqual(integrity);

  await node.click();
  const resize = page.locator(`[data-resize-node-id="${nodeId}"]`);
  await expect(resize).toBeVisible();
  const priorSize = (await state(page)).view_state.node_sizes[nodeId];
  await waitForPatchBatch(page, () => drag(page, resize, 36, 24));
  changed = await state(page);
  expect(changed.view_state.node_sizes[nodeId]).toBeTruthy();
  const resized = changed.view_state.node_sizes[nodeId];

  const undoResponse = page.waitForResponse((candidate) => candidate.url().endsWith("/api/undo"));
  await page.getByRole("button", { name: "Undo" }).click();
  expect((await undoResponse).ok()).toBe(true);
  expect((await state(page)).view_state.node_sizes[nodeId]).toEqual(priorSize);
  const redoResponse = page.waitForResponse((candidate) => candidate.url().endsWith("/api/redo"));
  await page.getByRole("button", { name: "Redo" }).click();
  expect((await redoResponse).ok()).toBe(true);
  expect((await state(page)).view_state.node_sizes[nodeId]).toEqual(resized);

  const expansionToggle = page.locator(".kernel-module-toggle.collapsed").first();
  if (await expansionToggle.count()) {
    const owner = expansionToggle.locator("xpath=ancestor::*[@data-hierarchy-node-id][1]");
    const hierarchyId = await owner.getAttribute("data-hierarchy-node-id");
    if (!hierarchyId) throw new Error("expandable module has no hierarchy identity");
    await waitForPatchBatch(page, () => expansionToggle.click());
    expect((await state(page)).view_state.module_expansion).toContain(hierarchyId);
  }

  await waitForPatchBatch(page, () => page.getByRole("button", { name: "Zoom in" }).click());
  changed = await state(page);
  const kernelSceneId = `kernel:${changed.architecture.architecture_id}:${changed.document.source_digest.slice(0, 12)}`;
  const camera = changed.view_state.cameras[kernelSceneId];
  expect(camera?.width).toBeGreaterThan(0);
  expect(changed.integrity).toEqual(integrity);

  await page.reload();
  await closeOpenDialog(page);
  await expect(routeSelect).toHaveValue("channel");
  await expect(nodeSelect).toHaveValue("technical");
  await expect(labelSelect).toHaveValue("endpoint");
  const reloadedNode = page.locator(`[data-kernel-node-id="${nodeId}"]`).first();
  await expect(reloadedNode).toBeVisible();
  expect(await reloadedNode.evaluate((element: SVGGElement) => element.getBBox().x)).not.toBe(beforeMove);
  expect(await page.locator("svg.kernel-scene").getAttribute("viewBox")).toBe([
    camera.x, camera.y, camera.width, camera.height,
  ].join(" "));

  const edge = changed.architecture.edges[0];
  const proposal = await page.evaluate(async ({ payload, nonce }) => {
    const response = await fetch("/api/proposal/connection", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-ArchCanvas-Nonce": nonce },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }, {
    nonce: baseline.session_nonce,
    payload: {
      proposal_id: "proposal:phase6-boundary",
      source_node_id: edge.producer_id,
      source_port_id: edge.producer_port,
      target_node_id: edge.consumer_id,
      target_port_id: edge.consumer_port,
    },
  }) as StudioState;
  expect(proposal.proposal?.status).toBe("handoff-required");
  expect(Object.values(proposal.proposal?.permissions ?? {})).not.toContain(true);
  expect(proposal.integrity).toEqual(integrity);

  const draftNodeId = "draft:phase6-node-boundary";
  const drafted = await page.evaluate(async ({ draftNodeId, nonce }) => {
    const response = await fetch("/api/proposal/node", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-ArchCanvas-Nonce": nonce },
      body: JSON.stringify({ node: {
        node_id: draftNodeId,
        semantic_name: "Phase 6 Draft",
        framework: "pytorch",
        node_type: "Linear",
        parameters: {},
        ports: [
          { port_id: `${draftNodeId}.input`, name: "input", direction: "input", role: "main" },
          { port_id: `${draftNodeId}.output`, name: "output", direction: "output", role: "main" },
        ],
      } }),
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }, { draftNodeId, nonce: baseline.session_nonce }) as StudioState;
  expect(drafted.draft.nodes.some((item) => item.node_id === draftNodeId)).toBe(true);
  expect(drafted.integrity).toEqual(integrity);

  const deleted = await page.evaluate(async ({ draftNodeId, nonce }) => {
    const response = await fetch("/api/draft/node/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-ArchCanvas-Nonce": nonce },
      body: JSON.stringify({ node_id: draftNodeId }),
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }, { draftNodeId, nonce: baseline.session_nonce }) as StudioState;
  expect(deleted.draft.nodes.some((item) => item.node_id === draftNodeId)).toBe(false);
  expect(deleted.integrity).toEqual(integrity);
});
