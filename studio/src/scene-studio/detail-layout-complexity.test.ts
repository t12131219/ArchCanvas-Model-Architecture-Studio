import { describe, expect, it } from "vitest";

import { shouldVirtualizeSceneDetails } from "./canvas-viewport";
import {
  buildInlineDetailLayout,
  fullyExpandedDetailTree,
  inlineDetailComplexity,
} from "./detail-layout";

describe("expanded detail complexity", () => {
  it("includes recursive detail nodes and flows in the large-scene policy", () => {
    const bounds = { x: 0, y: 0, width: 1420, height: 540 };
    const collapsed = buildInlineDetailLayout("transformer-decoder", bounds, undefined, {}, "decoder");
    const expanded = buildInlineDetailLayout(
      "transformer-decoder",
      bounds,
      fullyExpandedDetailTree("transformer-decoder"),
      {},
      "decoder",
    );
    const collapsedComplexity = inlineDetailComplexity(collapsed);
    const expandedComplexity = inlineDetailComplexity(expanded);

    expect(expandedComplexity.nodeCount).toBeGreaterThan(collapsedComplexity.nodeCount);
    expect(expandedComplexity.edgeCount).toBeGreaterThan(collapsedComplexity.edgeCount);
    expect(shouldVirtualizeSceneDetails(
      13 + expandedComplexity.nodeCount,
      15 + expandedComplexity.edgeCount,
    )).toBe(true);
  });
});
