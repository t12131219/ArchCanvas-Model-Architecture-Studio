import { expect, test, type Locator, type Page } from "@playwright/test";

const WRITEBACK_BASE_URL = "http://127.0.0.1:4313";

type Port = { port_id: string; direction: "input" | "output" };
type DraftNode = { node_id: string; node_type: string; ports: Port[] };
type TopologyState = {
  edit_session: { mode: string; current_document_digest: string };
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
  draft: {
    nodes: DraftNode[];
    edges: Array<{ edge_id: string }>;
    writeback_summary: { eligibility: string };
    reconciliation_receipts: Array<{ status: string; canonical_subject_ids: string[] }>;
  };
  generated_projects?: {
    active: {
      state: string;
      files: Array<{ path: string; sha256: string }>;
      conformance_report?: { semantic_isomorphism: string } | null;
    } | null;
  };
  round_trip_reports?: Array<{ path: string; semantic_isomorphism: string }>;
  transaction?: { state: string; source_diff: string } | null;
  jobs?: Array<{ job_id: string; state: string }>;
};

async function studioState(page: Page): Promise<TopologyState> {
  return page.evaluate(async () => {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  });
}

async function createFromRegistry(
  page: Page,
  workspace: Locator,
  search: string,
  semanticName: string,
  parameters: Record<string, string> = {},
): Promise<DraftNode> {
  const before = (await studioState(page)).draft.nodes.length;
  await workspace.getByLabel("搜索模块").fill(search);
  await workspace.getByRole("option", { name: new RegExp(search, "i") }).first().click();
  await workspace.getByLabel("语义名称").fill(semanticName);
  for (const [name, value] of Object.entries(parameters)) {
    await workspace.getByLabel(name, { exact: true }).fill(value);
  }
  await workspace.getByRole("button", { name: "创建草稿节点", exact: true }).click();
  await expect.poll(async () => (await studioState(page)).draft.nodes.length).toBe(before + 1);
  const created = (await studioState(page)).draft.nodes.find((node) => node.node_id && node.node_type.toLowerCase().includes(search.toLowerCase().replace("tensor input", "input.tensor")));
  return created ?? (await studioState(page)).draft.nodes.at(-1)!;
}

async function connect(
  page: Page,
  workspace: Locator,
  sourcePortId: string,
  targetPortId: string,
  policy: "fanout" | "replace-input" = "fanout",
) {
  const before = (await studioState(page)).draft.edges.length;
  await workspace.getByLabel("输出端口").selectOption(sourcePortId);
  await workspace.getByLabel("输入端口").selectOption(targetPortId);
  await workspace.getByLabel("连接策略").selectOption(policy);
  await workspace.getByRole("button", { name: "连接严格端口" }).click();
  await expect.poll(async () => (await studioState(page)).draft.edges.length).toBe(before + 1);
}

async function openTopologyWorkspace(page: Page) {
  await page.goto(WRITEBACK_BASE_URL);
  await expect(page.locator("svg.lab-canvas")).toBeVisible();
  await page.getByRole("button", { name: "模型", exact: true }).click();
  await page.getByRole("button", { name: "打开拓扑草稿工作台" }).click();
  const workspace = page.getByRole("complementary", { name: "拓扑草稿工作台" });
  await workspace.getByRole("button", { name: "解锁拓扑草稿" }).click();
  await expect.poll(async () => (await studioState(page)).edit_session.mode).toBe("topology-draft");
  return workspace;
}

test("Graph Draft UI validates the greenfield Input Conv2d ReLU slice and blocks unsupported writeback", async ({ page }) => {
  const workspace = await openTopologyWorkspace(page);
  const input = await createFromRegistry(page, workspace, "Tensor Input", "image", {
    shape: "[1, 3, 224, 224]",
  });
  const conv = await createFromRegistry(page, workspace, "Conv2d", "stem", {
    in_channels: "3",
    out_channels: "16",
    kernel_size: "3",
  });
  const relu = await createFromRegistry(page, workspace, "ReLU", "activation");
  await connect(page, workspace, input.ports.find((port) => port.direction === "output")!.port_id, conv.ports.find((port) => port.direction === "input")!.port_id);
  await connect(page, workspace, conv.ports.find((port) => port.direction === "output")!.port_id, relu.ports.find((port) => port.direction === "input")!.port_id);

  await expect(workspace.getByText("端口、Shape 与基数检查通过")).toBeVisible();
  await expect(page.locator(".lab-node[data-node-id*=':node:draft:']")).toHaveCount(3);
  await workspace.getByTitle("生成代码预览").click();
  await expect(workspace.locator(".draft-codegen pre")).toContainText("nn.Conv2d");
  await expect(workspace.locator(".draft-codegen pre")).toContainText("nn.ReLU");
  await expect(workspace.getByRole("button", { name: "提交评审" })).toBeDisabled();
  await expect(workspace.getByText(/源码写回被阻断/)).toBeVisible();

  await workspace.getByRole("button", { name: "准备源码工程" }).click();
  await expect.poll(async () => (await studioState(page)).generated_projects?.active?.state).toBe("generated-source-draft");
  expect((await studioState(page)).generated_projects?.active?.files.map((file) => file.path)).toEqual([
    "archcanvas-generation.json",
    "archcanvas-project.json",
    "model.py",
    "pyproject.toml",
  ]);
  await workspace.getByRole("button", { name: "静态验证与重分析" }).click();
  await expect.poll(async () => (await studioState(page)).generated_projects?.active?.state).toBe("review-ready");
  expect((await studioState(page)).generated_projects?.active?.conformance_report?.semantic_isomorphism).toBe("exact");
  expect((await studioState(page)).round_trip_reports).toEqual(expect.arrayContaining([
    expect.objectContaining({ path: "draft-source", semantic_isomorphism: "exact" }),
  ]));
  await expect(workspace.getByRole("button", { name: "物化并打开" })).toBeDisabled();
  await workspace.getByRole("button", { name: "放弃候选" }).click();
  await expect.poll(async () => (await studioState(page)).generated_projects?.active?.state).toBe("discarded");

  await workspace.getByRole("button", { name: "放弃", exact: true }).click();
  await expect.poll(async () => (await studioState(page)).draft.nodes.length).toBe(0);
  await expect.poll(async () => (await studioState(page)).edit_session.mode).toBe("visual");
});

test("Graph Draft UI commits and reconciles a supported existing-source insertion", async ({ page }) => {
  const workspace = await openTopologyWorkspace(page);
  const baseline = await studioState(page);
  const canonicalConv = baseline.architecture.nodes.find((node) => node.attributes.definition_id === "pytorch.nn.conv2d");
  const canonicalRelu = baseline.architecture.nodes.find((node) => node.attributes.definition_id === "pytorch.nn.relu");
  if (!canonicalConv || !canonicalRelu) throw new Error("frontend-v2 fixture is missing Conv2d/ReLU");
  const original = baseline.architecture.edges.find((edge) => edge.producer_id === canonicalConv.node_id && edge.consumer_id === canonicalRelu.node_id);
  if (!original) throw new Error("frontend-v2 fixture is missing the Conv2d -> ReLU boundary");

  const gelu = await createFromRegistry(page, workspace, "GELU", "after_conv");
  await connect(page, workspace, original.producer_port, gelu.ports.find((port) => port.direction === "input")!.port_id);
  await connect(page, workspace, gelu.ports.find((port) => port.direction === "output")!.port_id, original.consumer_port, "replace-input");
  await expect(workspace.getByText("端口、Shape 与基数检查通过")).toBeVisible();
  await workspace.getByTitle("生成代码预览").click();
  await expect(workspace.locator(".draft-codegen pre")).toContainText("self.after_conv = nn.GELU");
  await expect(workspace.getByRole("button", { name: "提交评审" })).toBeEnabled();
  await workspace.getByRole("button", { name: "提交评审" }).click();

  const transaction = page.getByRole("complementary", { name: "源码事务审查" });
  await expect(transaction).toBeVisible();
  await expect(transaction).toContainText("self.after_conv = nn.GELU");
  await transaction.getByRole("button", { name: "提交到源码" }).click();
  await expect.poll(async () => (await studioState(page)).jobs?.at(-1)?.state, { timeout: 60_000 }).toBe("succeeded");
  const reconciled = await studioState(page);
  expect(reconciled.draft.nodes).toHaveLength(0);
  expect(reconciled.draft.reconciliation_receipts.at(-1)?.status).toBe("realized");
  expect(reconciled.architecture.nodes.some((node) => node.attributes.definition_id === "pytorch.nn.gelu")).toBe(true);
});
