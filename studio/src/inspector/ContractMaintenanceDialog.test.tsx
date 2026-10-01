import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ContractMaintenanceCapability, StudioState } from "../app/studio-types";
import { MODULE_REGISTRY } from "../module-registry/registry";
import { ContractMaintenanceDialog } from "./ContractMaintenanceDialog";

const tx = (english: string) => english;
const base = MODULE_REGISTRY.definitions[0];

function state(active: boolean): StudioState {
  const capability: ContractMaintenanceCapability = {
    capability_id: "capability:contract.test",
    subject: "session:test",
    draft_id: "contract-draft:test",
    base: {
      definition_id: base.definition_id,
      version: base.version,
      digest: base.digest,
    },
    allowed_commands: ["UpdateCandidate", "Validate", "Review", "Publish", "Discard"],
    issued_at: "2026-10-01T00:00:00Z",
    expires_at: "2026-10-01T00:30:00Z",
  };
  return {
    edit_session: active
      ? { mode: "contract-maintenance", candidate_digest: "1".repeat(64), capability }
      : { mode: "visual", document_id: "draft:test", current_document_digest: "2".repeat(64) },
    transaction: null,
    contract_maintenance: {
      session: active ? { mode: "contract-maintenance", candidate_digest: "1".repeat(64), capability } : null,
      draft: active ? {
        draft_id: "contract-draft:test",
        base: capability.base,
        candidate: base,
        candidate_digest: "1".repeat(64),
        author: "session:test",
        created_at: "2026-10-01T00:00:00Z",
        revision: 0,
        state: "draft",
        migration: null,
      } : null,
      validation: null,
      review_receipt: null,
      published: [],
    },
  } as unknown as StudioState;
}

describe("contract maintenance dialog", () => {
  it("starts only from an exact approved definition", () => {
    const html = renderToStaticMarkup(<ContractMaintenanceDialog
      open state={state(false)} tx={tx} onClose={() => undefined}
      onState={() => undefined} onActivity={() => undefined}
    />);

    expect(html).toContain("Approved base definition");
    expect(html).toContain(base.version);
    expect(html).toContain("Create contract draft");
  });

  it("exposes candidate, migration, validation, review, and publish controls", () => {
    const html = renderToStaticMarkup(<ContractMaintenanceDialog
      open state={state(true)} tx={tx} onClose={() => undefined}
      onState={() => undefined} onActivity={() => undefined}
    />);

    expect(html).toContain("Candidate definition");
    expect(html).toContain("Migration (required for breaking changes)");
    expect(html).toContain("Validate");
    expect(html).toContain("Approve");
    expect(html).toContain("Publish");
  });
});
