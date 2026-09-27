import { describe, expect, it } from "vitest";

import { buildTemplateDetail, templateDetailSize } from "./template-details";
import type { Bounds, KernelTemplateBinding, RenderDetailPrimitive } from "./types";

const slots = [
  "q_projection", "k_projection", "v_projection", "q_split", "k_split", "v_split",
  "key_transpose", "score_matmul", "softmax", "value_matmul", "concat", "output_projection",
];

function binding(fidelity: KernelTemplateBinding["fidelity"] = "exact"): KernelTemplateBinding {
  return {
    bindingId: "binding:attention:test",
    templateId: "attention.qkv-v1",
    templateVersion: "1.0.0",
    fidelity,
    rootCanonicalNodeIds: ["node:attention"],
    canonicalNodeIds: slots.map((slot) => `node:${slot}`),
    nodeSlots: Object.fromEntries(slots.map((slot) => [slot, [`node:${slot}`]])),
    edgeSlots: {},
    portSlots: {},
    tensorSlots: {},
    evidenceIds: ["evidence:attention"],
    predicateIds: ["predicate:attention"],
    bindingDigest: "sha256:attention-binding",
  };
}

function primitivePoints(primitive: RenderDetailPrimitive): Array<{ x: number; y: number }> {
  if (primitive.kind === "flow") return primitive.points;
  if (primitive.kind === "operator") return [
    { x: primitive.cx - primitive.radius, y: primitive.cy - primitive.radius },
    { x: primitive.cx + primitive.radius, y: primitive.cy + primitive.radius },
  ];
  if (primitive.kind === "text") return [{ x: primitive.x, y: primitive.y }];
  return [
    { x: primitive.x, y: primitive.y },
    { x: primitive.x + primitive.width, y: primitive.y + primitive.height },
  ];
}

describe("formal template details", () => {
  it("matches the complete Lab attention primitive inventory without escaping its bounds", () => {
    const bounds: Bounds = { x: 72, y: 48, width: 900, height: 380 };
    const detail = buildTemplateDetail("view:attention", binding(), bounds)!;

    expect(detail.primitives).toHaveLength(46);
    expect(detail.primitives.filter((primitive) => primitive.kind === "flow")).toHaveLength(23);
    expect(detail.primitives.filter((primitive) => primitive.kind === "matrix")).toHaveLength(10);
    expect(detail.primitives.filter((primitive) => primitive.kind === "operator")).toHaveLength(2);
    expect(detail.primitives.filter((primitive) => primitive.kind === "box")).toHaveLength(8);
    expect(detail.primitives.filter((primitive) => primitive.kind === "text")).toHaveLength(3);
    expect(detail.primitives.flatMap(primitivePoints).every((point) => (
      point.x >= bounds.x && point.x <= bounds.x + bounds.width
      && point.y >= bounds.y && point.y <= bounds.y + bounds.height
    ))).toBe(true);
  });

  it("keeps auxiliary glyphs visual-only while preserving one primitive per formal node slot", () => {
    const detail = buildTemplateDetail("view:attention", binding(), { x: 0, y: 0, width: 900, height: 380 })!;
    const formalPrimitives = detail.primitives.filter((primitive) => slots.includes(primitive.slotId));
    const visualPrimitives = detail.primitives.filter((primitive) => primitive.slotId.startsWith("visual:"));

    expect(formalPrimitives.map((primitive) => primitive.slotId).sort()).toEqual([...slots].sort());
    expect(formalPrimitives.every((primitive) => primitive.canonicalIds.length === 1)).toBe(true);
    expect(visualPrimitives.map((primitive) => primitive.slotId).sort()).toEqual([
      "visual:attention-weights", "visual:context", "visual:k-input", "visual:output",
      "visual:q-input", "visual:scale", "visual:v-input",
    ]);
    expect(visualPrimitives.every((primitive) => primitive.canonicalIds.length === 0)).toBe(true);
  });

  it("does not size or build exact internals for opaque bindings", () => {
    expect(templateDetailSize(binding("opaque"))).toBeUndefined();
    expect(buildTemplateDetail("view:attention", binding("opaque"), { x: 0, y: 0, width: 900, height: 380 })).toBeUndefined();
  });

  it("moves an exact slot within its frame and keeps adjacent flows attached", () => {
    const bounds = { x: 0, y: 0, width: 900, height: 380 };
    const original = buildTemplateDetail("view:attention", binding(), bounds)!;
    const moved = buildTemplateDetail("view:attention", binding(), bounds, {
      "binding:attention:test:q_projection": { x: 24, y: 18 },
    })!;
    const originalProjection = original.primitives.find((primitive) => primitive.primitiveId === "binding:attention:test:q_projection")!;
    const movedProjection = moved.primitives.find((primitive) => primitive.primitiveId === "binding:attention:test:q_projection")!;
    expect(originalProjection.kind).toBe("box");
    expect(movedProjection).toMatchObject({ kind: "box", x: 134, y: 103 });

    const incoming = moved.primitives.find((primitive) => primitive.primitiveId === "binding:attention:test:flow:q:input-projection")!;
    const outgoing = moved.primitives.find((primitive) => primitive.primitiveId === "binding:attention:test:flow:q:projection-split")!;
    expect(incoming.kind === "flow" ? incoming.points.at(-1) : null).toEqual({ x: 134, y: 123 });
    expect(outgoing.kind === "flow" ? outgoing.points[0] : null).toEqual({ x: 188, y: 123 });
  });
});
