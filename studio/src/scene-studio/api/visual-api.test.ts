import { describe, expect, it } from "vitest";

import type { StudioStatePayload } from "../domain/source-backed-scene";
import type { LabScene } from "../types";
import { visualRequestsForPatch } from "./visual-api";

const state = {
  architecture: { architecture_id: "architecture:test" },
  document: { source_digest: "a".repeat(64) },
  integrity: { source_digest: "b".repeat(64) },
} as StudioStatePayload;

const scene: LabScene = {
  scene_id: "source:test:engineering-flow",
  title: "Test",
  description: "",
  paper_width: 800,
  paper_height: 600,
  nodes: [{
    scene_node_id: "engineering-flow:node:canonical.input",
    hierarchy_node_id: "hierarchy:node.current-frontier",
    bounds: { x: 10, y: 20, width: 120, height: 64 },
    shape: "io",
    label: "Input",
    secondary_label: "source-backed",
  }],
  edges: [],
};

describe("visualRequestsForPatch", () => {
  it("uses the event-time persistence target when the scene binding has since changed", () => {
    const requests = visualRequestsForPatch(state, {
      operation: "update-node",
      nodeId: "engineering-flow:node:canonical.input",
      persistenceTargetId: "view:hierarchy:group.event-frontier",
      changes: { bounds: { x: -30, y: 45, width: 120, height: 64 } },
    }, scene);

    expect(requests).toHaveLength(1);
    expect(requests[0]).toMatchObject({
      operation: "set-position",
      target_id: "view:hierarchy:group.event-frontier",
      value: { x: -30, y: 45 },
    });
  });

  it("falls back to the current hierarchy binding for callers without an explicit target", () => {
    const requests = visualRequestsForPatch(state, {
      operation: "update-node",
      nodeId: "engineering-flow:node:canonical.input",
      changes: { bounds: { x: 10, y: 20, width: 180, height: 92 } },
    }, scene);

    expect(requests).toHaveLength(1);
    expect(requests[0]).toMatchObject({
      operation: "set-size",
      target_id: "view:hierarchy:node.current-frontier",
      value: { width: 180, height: 92 },
    });
  });
});
