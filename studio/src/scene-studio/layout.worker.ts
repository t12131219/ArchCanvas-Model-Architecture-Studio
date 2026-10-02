/// <reference lib="webworker" />

import ELK from "elkjs/lib/elk-api.js";
import type { ElkNode } from "elkjs/lib/elk-api";
import elkWorkerUrl from "elkjs/lib/elk-worker.min.js?url";

import type { LayoutWorkerRequest, LayoutWorkerResponse } from "./layout-worker-protocol";

const elk = new ELK({
  algorithms: ["layered"],
  workerUrl: elkWorkerUrl,
  workerFactory: (url) => new Worker(url ?? elkWorkerUrl),
});

function messageFor(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

self.onmessage = async (event: MessageEvent<LayoutWorkerRequest>) => {
  const request = event.data;
  if (request.type !== "layout") return;
  const startedAt = performance.now();
  const graph: ElkNode = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": request.direction,
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.padding": "[top=24,left=24,bottom=24,right=24]",
      "elk.spacing.nodeNode": "56",
      "elk.layered.spacing.nodeNodeBetweenLayers": "104",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    },
    children: request.nodes.map((node) => ({
      id: node.id,
      width: node.width,
      height: node.height,
    })),
    edges: request.edges.map((edge) => ({
      id: edge.id,
      sources: [edge.sourceId],
      targets: [edge.targetId],
    })),
  };
  try {
    const result = await elk.layout(graph);
    const response: LayoutWorkerResponse = {
      type: "layout-complete",
      requestId: request.requestId,
      durationMs: performance.now() - startedAt,
      positions: (result.children ?? []).flatMap((node) => (
        Number.isFinite(node.x) && Number.isFinite(node.y)
          ? [{ id: node.id, x: node.x!, y: node.y! }]
          : []
      )),
    };
    self.postMessage(response);
  } catch (error) {
    const response: LayoutWorkerResponse = {
      type: "layout-failed",
      requestId: request.requestId,
      message: messageFor(error),
    };
    self.postMessage(response);
  }
};

export {};
