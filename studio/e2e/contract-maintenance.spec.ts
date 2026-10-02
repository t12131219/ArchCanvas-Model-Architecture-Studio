import { expect, test, type Page } from "@playwright/test";

type ContractState = {
  session_nonce: string;
  edit_session: {
    mode: string;
    current_document_digest?: string;
    capability?: { capability_id: string };
  };
  contract_maintenance: {
    session: null | { capability: { capability_id: string } };
    draft: null | {
      candidate: Record<string, unknown>;
      candidate_digest: string;
      state: string;
    };
    validation: null | {
      status: "passed" | "failed";
      diagnostics: Array<{ code: string }>;
    };
    review_receipt: null | { decision: string };
    published: Array<{ candidate_digest: string }>;
  };
};

async function studioState(page: Page): Promise<ContractState> {
  return page.evaluate(async () => {
    const response = await fetch("/api/state");
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  });
}

async function openContractDialog(page: Page, definitionId: string) {
  await page.getByRole("button", { name: "Module contract maintenance" }).click();
  const dialog = page.getByRole("dialog", { name: "Module contract maintenance" });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Approved base definition").selectOption(definitionId);
  await dialog.getByRole("button", { name: "Create contract draft" }).click();
  await expect(dialog.getByLabel("Candidate definition")).toBeVisible();
  return dialog;
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("archcanvas.locale", "en"));
  await page.goto("/");
  const openDialog = page.getByRole("dialog", { name: "Open model" });
  if (await openDialog.isVisible().catch(() => false)) {
    await openDialog.getByRole("button", { name: "Close" }).click();
  }
  const state = await studioState(page);
  const capabilityId = state.contract_maintenance.session?.capability.capability_id;
  if (capabilityId) {
    const discarded = await page.request.post("/api/contracts/session/discard", {
      headers: { "X-ArchCanvas-Nonce": state.session_nonce },
      data: { capability_id: capabilityId },
    });
    expect(discarded.ok()).toBe(true);
    await page.reload();
  }
});

test("contract candidate is validated, approved, and published through the Studio UI", async ({ page }) => {
  const baseline = await studioState(page);
  const baseDocumentDigest = baseline.edit_session.current_document_digest!;
  const dialog = await openContractDialog(page, "pytorch.nn.relu");
  const active = await studioState(page);

  expect(active.edit_session.mode).toBe("contract-maintenance");
  const locked = await page.request.post("/api/draft/session/begin", {
    headers: { "X-ArchCanvas-Nonce": active.session_nonce },
    data: { base_document_digest: baseDocumentDigest },
  });
  expect(locked.status()).toBe(422);
  expect(await locked.text()).toContain("contract-maintenance mode must be closed");

  const candidateEditor = dialog.getByLabel("Candidate definition");
  const candidate = JSON.parse(await candidateEditor.inputValue()) as Record<string, unknown>;
  candidate.version = "1.0.1";
  candidate.glyph_id = "relu-reviewed";
  await candidateEditor.fill(JSON.stringify(candidate, null, 2));
  await dialog.getByRole("button", { name: "Validate" }).click();
  await expect.poll(async () => (await studioState(page)).contract_maintenance.validation?.status)
    .toBe("passed");

  await dialog.getByRole("button", { name: "Approve" }).click();
  await expect.poll(async () => (await studioState(page)).contract_maintenance.review_receipt?.decision)
    .toBe("approved");
  const approvedDigest = (await studioState(page)).contract_maintenance.draft!.candidate_digest;

  await dialog.getByRole("button", { name: "Publish" }).click();
  await expect(dialog).toBeHidden();
  await expect.poll(async () => (await studioState(page)).edit_session.mode).toBe("visual");
  expect((await studioState(page)).contract_maintenance.published)
    .toEqual(expect.arrayContaining([expect.objectContaining({ candidate_digest: approvedDigest })]));
});

test("breaking contract requires a fixture-tested migration before review", async ({ page }) => {
  const dialog = await openContractDialog(page, "pytorch.nn.multiheadattention");
  const candidateEditor = dialog.getByLabel("Candidate definition");
  const candidate = JSON.parse(await candidateEditor.inputValue()) as {
    version: string;
    ports: Array<{ port_id: string }>;
  };
  candidate.version = "2.0.0";
  candidate.ports = candidate.ports.filter((port) => port.port_id !== "attention_mask");
  await candidateEditor.fill(JSON.stringify(candidate, null, 2));
  await dialog.getByRole("button", { name: "Validate" }).click();

  await expect.poll(async () => (await studioState(page)).contract_maintenance.validation?.status)
    .toBe("failed");
  expect((await studioState(page)).contract_maintenance.validation?.diagnostics.map((item) => item.code))
    .toContain("CONTRACT_MIGRATION_REQUIRED");
  await expect(dialog.getByRole("button", { name: "Publish" })).toBeDisabled();

  await dialog.getByLabel("Migration (required for breaking changes)").fill(JSON.stringify({
    migration_id: "migration:mha-v2-e2e",
    from_version: "1.0.0",
    to_version: "2.0.0",
    parameter_map: {},
    port_map: { attention_mask: null },
    fixture_results: [{
      fixture_id: "fixture:mha-mask-e2e",
      status: "passed",
      message: "Existing masked attention graph migrated deterministically.",
    }],
  }, null, 2));
  await dialog.getByRole("button", { name: "Validate" }).click();
  await expect.poll(async () => (await studioState(page)).contract_maintenance.validation?.status)
    .toBe("passed");
  await dialog.getByRole("button", { name: "Discard" }).click();
  await expect(dialog).toBeHidden();
});
