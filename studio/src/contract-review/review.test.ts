import { describe, expect, it } from "vitest";

import { resolveDefinitionId } from "../module-registry/registry";
import type { ModuleDefinition } from "../module-registry/types";
import {
  createDefinitionDraft,
  diffDefinitions,
  reviewDefinitionDraft,
  validateDefinitionDraft,
} from "./review";

function candidate(base: ModuleDefinition, patch: Partial<ModuleDefinition>): ModuleDefinition {
  return { ...structuredClone(base), ...patch, digest: "0".repeat(64) };
}

const time = "2026-10-01T00:00:00Z";

describe("module contract review", () => {
  it("keeps approved registry definitions immutable", () => {
    const definition = resolveDefinitionId("pytorch.nn.conv2d")!;
    expect(Object.isFrozen(definition)).toBe(true);
    expect(() => { definition.glyph_id = "other"; }).toThrow();
  });

  it("classifies optional additions as minor and visual-only changes as patch", () => {
    const base = resolveDefinitionId("pytorch.nn.conv2d")!;
    const optional = candidate(base, {
      version: "1.1.0",
      ports: [...base.ports, {
        port_id: "residual",
        direction: "input",
        required: false,
        min_connections: 0,
        max_connections: 1,
        ordering: "ordered",
        accepted_relations: ["residual"],
        tensor_ranks: [],
        tensor_layouts: [],
      }],
    });
    expect(diffDefinitions(base, optional).requiredVersionBump).toBe("minor");
    expect(diffDefinitions(base, candidate(base, { version: "1.0.1", glyph_id: "conv2d-v2" })))
      .toMatchObject({ compatibility: "visual-only", requiredVersionBump: "patch" });
  });

  it("rejects breaking changes without a fixture-tested migration", async () => {
    const base = resolveDefinitionId("pytorch.nn.multiheadattention")!;
    const changed = candidate(base, {
      version: "2.0.0",
      ports: base.ports.filter((port) => port.port_id !== "attention_mask"),
    });
    const draft = await createDefinitionDraft(base, changed, {
      draftId: "contract-draft:mha-v2",
      author: "author:test",
      createdAt: time,
    });
    const validation = await validateDefinitionDraft(base, draft);

    expect(validation.status).toBe("failed");
    expect(validation.diagnostics.map((item) => item.code)).toContain("CONTRACT_MIGRATION_REQUIRED");
    await expect(reviewDefinitionDraft(draft, validation, {
      receiptId: "receipt:mha-v2",
      reviewer: "reviewer:test",
      decision: "approved",
      decidedAt: time,
    })).rejects.toThrow("cannot be approved");
  });

  it("approves a digest-bound breaking candidate only with migration coverage", async () => {
    const base = resolveDefinitionId("pytorch.nn.multiheadattention")!;
    const changed = candidate(base, {
      version: "2.0.0",
      ports: base.ports.filter((port) => port.port_id !== "attention_mask"),
    });
    const draft = await createDefinitionDraft(base, changed, {
      draftId: "contract-draft:mha-v2",
      author: "author:test",
      createdAt: time,
      migration: {
        migrationId: "migration:mha-v2",
        fromVersion: "1.0.0",
        toVersion: "2.0.0",
        parameterMap: {},
        portMap: { attention_mask: null },
        fixtureIds: ["fixture:mha-mask"],
      },
    });
    const validation = await validateDefinitionDraft(base, draft);
    const receipt = await reviewDefinitionDraft(draft, validation, {
      receiptId: "receipt:mha-v2",
      reviewer: "reviewer:test",
      decision: "approved",
      decidedAt: time,
    });

    expect(validation.status).toBe("passed");
    expect(receipt.candidateDigest).toBe(draft.candidateDigest);
    expect(receipt.decision).toBe("approved");
  });

  it("invalidates validation and receipts after candidate mutation", async () => {
    const base = resolveDefinitionId("pytorch.nn.relu")!;
    const changed = candidate(base, { version: "1.0.1", glyph_id: "relu-v2" });
    const draft = await createDefinitionDraft(base, changed, {
      draftId: "contract-draft:relu",
      author: "author:test",
      createdAt: time,
    });
    const validation = await validateDefinitionDraft(base, draft);
    draft.candidate.glyph_id = "relu-v3";

    expect((await validateDefinitionDraft(base, draft)).diagnostics.map((item) => item.code))
      .toContain("CONTRACT_CANDIDATE_MUTATED");
    await expect(reviewDefinitionDraft(draft, validation, {
      receiptId: "receipt:relu",
      reviewer: "reviewer:test",
      decision: "approved",
      decidedAt: time,
    })).rejects.toThrow("stale or mutated");
  });

  it("treats parameter impact and tensor constraints as reviewed runtime contracts", () => {
    const base = resolveDefinitionId("pytorch.nn.conv2d")!;
    const impactChanged = candidate(base, {
      version: "2.0.0",
      parameters: base.parameters.map((parameter) => (
        parameter.parameter_id === "out_channels"
          ? { ...parameter, affects: ["visual"] }
          : parameter
      )),
    });
    const rankChanged = candidate(base, {
      version: "2.0.0",
      ports: base.ports.map((port) => (
        port.port_id === "input" ? { ...port, tensor_ranks: [3, 4] } : port
      )),
    });

    expect(diffDefinitions(base, impactChanged)).toMatchObject({
      compatibility: "breaking",
      requiredVersionBump: "major",
    });
    expect(diffDefinitions(base, rankChanged)).toMatchObject({
      compatibility: "breaking",
      requiredVersionBump: "major",
    });
  });
});
