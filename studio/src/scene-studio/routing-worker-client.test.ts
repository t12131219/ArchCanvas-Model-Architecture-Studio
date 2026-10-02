import { describe, expect, it, vi } from "vitest";

import { startWorkerRouting } from "./routing-worker-client";
import type { RoutingWorkerRequest, RoutingWorkerResponse } from "./routing-worker-protocol";
import type { LabScene } from "./types";

const scene: LabScene = {
  scene_id: "worker-route",
  title: "Worker route",
  description: "test",
  paper_width: 800,
  paper_height: 400,
  nodes: [{
    scene_node_id: "a",
    bounds: { x: 40, y: 60, width: 100, height: 60 },
    shape: "operation",
    label: "A",
    secondary_label: "",
  }, {
    scene_node_id: "b",
    bounds: { x: 300, y: 60, width: 100, height: 60 },
    shape: "operation",
    label: "B",
    secondary_label: "",
  }],
  edges: [{
    scene_edge_id: "a-b",
    source_scene_node_id: "a",
    target_scene_node_id: "b",
    relation: "flow",
    label: "flow",
  }],
};

function fakeWorker() {
  return {
    onmessage: null as ((event: MessageEvent<RoutingWorkerResponse>) => void) | null,
    onerror: null as ((event: ErrorEvent) => void) | null,
    postMessage: vi.fn<(message: RoutingWorkerRequest) => void>(),
    terminate: vi.fn(),
  };
}

describe("routing worker client", () => {
  it("sends a cloneable request and resolves the matching result", async () => {
    const worker = fakeWorker();
    const task = startWorkerRouting(scene, "adaptive", undefined, () => worker);
    expect(worker.postMessage).toHaveBeenCalledWith(expect.objectContaining({
      type: "route",
      requestId: task.requestId,
      scene,
      style: "adaptive",
    }));
    worker.onmessage?.(new MessageEvent<RoutingWorkerResponse>("message", { data: {
      type: "route-complete",
      requestId: task.requestId,
      durationMs: 4,
      routes: [],
      metrics: {
        crossings: 0,
        overlaps: 0,
        nodeIntersections: 0,
        labelIntersections: 0,
        clearanceViolations: 0,
        endpointCongestion: 0,
        reverseExits: 0,
        sharedLength: 0,
        bends: 0,
        routeLength: 0,
      },
    } }));
    await expect(task.promise).resolves.toMatchObject({ type: "route-complete", durationMs: 4 });
    expect(worker.terminate).toHaveBeenCalledOnce();
  });

  it("terminates the worker and rejects cancellation as AbortError", async () => {
    const worker = fakeWorker();
    const task = startWorkerRouting(scene, "adaptive", undefined, () => worker);
    task.cancel();
    await expect(task.promise).rejects.toMatchObject({ name: "AbortError" });
    expect(worker.terminate).toHaveBeenCalledOnce();
  });

  it("ignores stale worker responses", async () => {
    const worker = fakeWorker();
    const task = startWorkerRouting(scene, "adaptive", undefined, () => worker);
    worker.onmessage?.(new MessageEvent<RoutingWorkerResponse>("message", { data: {
      type: "route-failed",
      requestId: "stale",
      message: "stale",
    } }));
    expect(worker.terminate).not.toHaveBeenCalled();
    task.cancel();
    await expect(task.promise).rejects.toMatchObject({ name: "AbortError" });
  });
});
