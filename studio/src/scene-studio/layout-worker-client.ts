import type { LabPatch, LabScene } from "./types";
import {
  layoutRequestForScene,
  type LayoutWorkerRequest,
  type LayoutWorkerResponse,
  type LayoutWorkerSuccess,
} from "./layout-worker-protocol";

interface LayoutWorkerPort {
  onmessage: ((event: MessageEvent<LayoutWorkerResponse>) => void) | null;
  onerror: ((event: ErrorEvent) => void) | null;
  postMessage(message: LayoutWorkerRequest): void;
  terminate(): void;
}

export interface LayoutTask {
  requestId: string;
  promise: Promise<LayoutWorkerSuccess>;
  cancel(): void;
}

function createLayoutWorker(): LayoutWorkerPort {
  return new Worker(new URL("./layout.worker.ts", import.meta.url), { type: "module" });
}

function abortError(): Error {
  const error = new Error("Layout cancelled");
  error.name = "AbortError";
  return error;
}

export function startElkLayout(
  scene: LabScene,
  workerFactory: () => LayoutWorkerPort = createLayoutWorker,
): LayoutTask {
  const requestId = crypto.randomUUID();
  const worker = workerFactory();
  let settled = false;
  let rejectTask: (reason: unknown) => void = () => undefined;
  const finish = () => {
    if (settled) return false;
    settled = true;
    worker.terminate();
    return true;
  };
  const promise = new Promise<LayoutWorkerSuccess>((resolve, reject) => {
    rejectTask = reject;
    worker.onmessage = (event) => {
      if (event.data.requestId !== requestId || !finish()) return;
      if (event.data.type === "layout-failed") reject(new Error(event.data.message));
      else resolve(event.data);
    };
    worker.onerror = (event) => {
      if (!finish()) return;
      reject(new Error(event.message || "Layout worker failed"));
    };
    worker.postMessage(layoutRequestForScene(scene, requestId));
  });
  return {
    requestId,
    promise,
    cancel() {
      if (!finish()) return;
      rejectTask(abortError());
    },
  };
}

function persistenceTargetForNode(scene: LabScene, nodeId: string): string | undefined {
  const node = scene.nodes.find((item) => item.scene_node_id === nodeId);
  return node?.hierarchy_node_id ? `view:${node.hierarchy_node_id}` : undefined;
}

export function layoutPatchesFromResult(
  scene: LabScene,
  positions: readonly { id: string; x: number; y: number }[],
  pinnedNodeIds: ReadonlySet<string>,
): LabPatch[] {
  const resultById = new Map(positions.map((position) => [position.id, position]));
  const positionedNodes = scene.nodes.filter((node) => resultById.has(node.scene_node_id));
  if (!positionedNodes.length) return [];

  const anchor = [...scene.nodes]
    .sort((left, right) => left.scene_node_id.localeCompare(right.scene_node_id))
    .find((node) => pinnedNodeIds.has(node.scene_node_id) && resultById.has(node.scene_node_id));
  const offset = anchor
    ? {
      x: anchor.bounds.x - resultById.get(anchor.scene_node_id)!.x,
      y: anchor.bounds.y - resultById.get(anchor.scene_node_id)!.y,
    }
    : {
      x: Math.min(...positionedNodes.map((node) => node.bounds.x))
        - Math.min(...positionedNodes.map((node) => resultById.get(node.scene_node_id)!.x)),
      y: Math.min(...positionedNodes.map((node) => node.bounds.y))
        - Math.min(...positionedNodes.map((node) => resultById.get(node.scene_node_id)!.y)),
    };

  return positionedNodes.flatMap((node) => {
    if (pinnedNodeIds.has(node.scene_node_id)) return [];
    const position = resultById.get(node.scene_node_id)!;
    const x = position.x + offset.x;
    const y = position.y + offset.y;
    if (!Number.isFinite(x) || !Number.isFinite(y)
      || (x === node.bounds.x && y === node.bounds.y)) return [];
    return [{
      operation: "update-node" as const,
      nodeId: node.scene_node_id,
      changes: { bounds: { ...node.bounds, x, y } },
      persistenceTargetId: persistenceTargetForNode(scene, node.scene_node_id),
    }];
  });
}
