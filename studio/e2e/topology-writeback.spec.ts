import { expect, test, type Page } from "@playwright/test";

const WRITEBACK_BASE_URL = "http://127.0.0.1:4313";

type Port = { port_id: string; direction: "input" | "output" };
type StudioState = {
  session_nonce: string;
  architecture: {
    nodes: Array<{
      node_id: string;
      attributes: Record<string, unknown>;
      input_ports: Port[];
      output_ports: Port[];
    }>;
    edges: Array<{
      producer_id: string;
      producer_port: string;
      consumer_id: string;
      consumer_port: string;
    }>;
  };
  evidence: Array<{ evidence_id: string }>;
  draft: {
    lowering_status: string;
    nodes: Array<{ node_id: string; ports: Port[] }>;
    reconciliation_receipts: Array<{
      status: string;
      canonical_subject_ids: string[];
    }>;
  };
  edit_session: {
    mode: string;
    current_document_digest: string;
    capability?: { capability_id: string } | null;
  };
  transaction?: {
    state: string;
    source_diff: string;
    realized_subject_ids: string[];
  } | null;
  jobs?: Array<{ job_id: string; state: string }>;
};

async function state(page: Page): Promise<StudioState> {
  return page.evaluate(async () => {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  });
}

async function closeOpenDialog(page: Page) {
  const dialog = page.getByRole("dialog", { name: "Open model" });
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("button", { name: "Close" }).click();
    await expect(dialog).toBeHidden();
  }
}

async function connectDraftEdge(
  page: Page,
  edge: {
    edge_id: string;
    source_port_id: string;
    target_port_id: string;
    policy: "fanout" | "replace-input";
    relation: "main";
  },
): Promise<StudioState> {
  const current = await state(page);
  return page.evaluate(async ({ payload, nonce, capabilityId, digest }) => {
    const response = await fetch("/api/proposal/draft-edge", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-ArchCanvas-Nonce": nonce },
      body: JSON.stringify({
        edge: payload,
        capability_id: capabilityId,
        expected_document_digest: digest,
      }),
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }, {
    payload: edge,
    nonce: current.session_nonce,
    capabilityId: current.edit_session.capability?.capability_id,
    digest: current.edit_session.current_document_digest,
  });
}

test("registered draft is previewed, committed, and reconciled after source reanalysis", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.addInitScript(() => window.localStorage.setItem("archcanvas.locale", "en"));
  await page.goto(WRITEBACK_BASE_URL);
  await closeOpenDialog(page);

  const baseline = await state(page);
  const conv = baseline.architecture.nodes.find(
    (node) => node.attributes.definition_id === "pytorch.nn.conv2d",
  );
  const relu = baseline.architecture.nodes.find(
    (node) => node.attributes.definition_id === "pytorch.nn.relu",
  );
  if (!conv || !relu) throw new Error("frontend-v2 fixture did not recover Conv2d and ReLU");
  const original = baseline.architecture.edges.find(
    (edge) => edge.producer_id === conv.node_id && edge.consumer_id === relu.node_id,
  );
  if (!original) throw new Error("frontend-v2 fixture has no Conv2d -> ReLU edge");

  await page.getByRole("button", { name: "Unlock topology draft" }).click();
  await expect.poll(async () => (await state(page)).edit_session.mode).toBe("topology-draft");
  await page.getByRole("button", { name: "Create draft node" }).click();
  const nodeDialog = page.getByRole("dialog", { name: "Create draft node" });
  await nodeDialog.getByLabel("Search modules").fill("GELU");
  await nodeDialog.getByRole("option", { name: /GELU/ }).click();
  await nodeDialog.getByLabel("Semantic name").fill("after_conv");
  await nodeDialog.getByRole("button", { name: "Create draft" }).click();

  let drafted = await state(page);
  const synthetic = drafted.draft.nodes.find((node) => node.node_id.startsWith("draft:"));
  if (!synthetic) throw new Error("registered draft node was not created");
  const input = synthetic.ports.find((port) => port.direction === "input");
  const output = synthetic.ports.find((port) => port.direction === "output");
  if (!input || !output) throw new Error("GELU draft has no named input/output ports");

  drafted = await connectDraftEdge(page, {
    edge_id: "draft:e2e-conv-after",
    source_port_id: original.producer_port,
    target_port_id: input.port_id,
    policy: "fanout",
    relation: "main",
  });
  expect(drafted.draft.nodes).toHaveLength(1);
  drafted = await connectDraftEdge(page, {
    edge_id: "draft:e2e-after-relu",
    source_port_id: output.port_id,
    target_port_id: original.consumer_port,
    policy: "replace-input",
    relation: "main",
  });
  expect(drafted.edit_session.mode).toBe("topology-draft");
  await page.reload();
  await closeOpenDialog(page);
  await expect(page.getByRole("button", { name: "Submit topology draft" })).toBeEnabled();

  const previewButton = page.getByRole("button", { name: "Generate PyTorch code preview" });
  await expect(previewButton).toBeEnabled();
  await previewButton.click();
  await expect(page.locator(".codegen-preview")).toContainText("nn.GELU");
  await expect(page.locator(".codegen-preview")).toContainText("after_conv");

  const submitResponse = page.waitForResponse((response) => (
    response.url().endsWith("/api/draft/session/submit")
    && response.request().method() === "POST"
  ));
  await page.getByRole("button", { name: "Submit topology draft" }).click();
  expect((await submitResponse).ok()).toBe(true);
  const review = await state(page);
  expect(review.transaction?.state).toBe("review-ready");
  expect(review.draft.lowering_status).toBe("planned");
  expect(review.transaction?.source_diff).toContain("self.after_conv = nn.GELU");
  await expect(page.getByText("Source diff", { exact: true })).toBeVisible();
  await expect(page.locator(".transaction-review")).toContainText("self.after_conv = nn.GELU");
  const realized = review.transaction?.realized_subject_ids ?? [];
  expect(realized.some((subjectId) => subjectId.startsWith("node:"))).toBe(true);
  expect(realized.some((subjectId) => subjectId.startsWith("evidence:"))).toBe(true);

  const commitResponse = page.waitForResponse((response) => (
    response.url().endsWith("/api/transaction/commit")
    && response.request().method() === "POST"
  ));
  await page.getByRole("button", { name: "Commit to source" }).first().click();
  const committedPayload = await (await commitResponse).json() as { reanalysis_job_id?: string | null };
  expect(committedPayload.reanalysis_job_id).toBeTruthy();

  await expect.poll(async () => {
    const current = await state(page);
    return current.jobs?.find((job) => job.job_id === committedPayload.reanalysis_job_id)?.state;
  }, { timeout: 60_000 }).toBe("succeeded");

  const reconciled = await state(page);
  expect(reconciled.draft.nodes).toHaveLength(0);
  expect(reconciled.draft.reconciliation_receipts.at(-1)?.status).toBe("realized");
  expect(reconciled.architecture.nodes.some(
    (node) => node.attributes.definition_id === "pytorch.nn.gelu",
  )).toBe(true);
  const available = new Set([
    ...reconciled.architecture.nodes.flatMap((node) => [
      node.node_id,
      ...node.input_ports.map((port) => port.port_id),
      ...node.output_ports.map((port) => port.port_id),
    ]),
    ...reconciled.evidence.map((record) => record.evidence_id),
  ]);
  expect(realized.every((subjectId) => available.has(subjectId))).toBe(true);
  expect(consoleErrors).toEqual([]);
});
