import { postStudioJson } from "../../api/studio-client";
import type { StudioStatePayload } from "../domain/source-backed-scene";
import type { LabPatch, LabScene } from "../types";

export interface VisualPatchRequest {
  patch_id: string;
  operation: string;
  target_id?: string;
  value: Record<string, unknown>;
}

function requestId(kind: string): string {
  return `patch:${kind}.${Date.now().toString(36)}.${crypto.randomUUID()}`;
}

function kernelValue(state: StudioStatePayload): Record<string, unknown> {
  const sourceDigest = state.integrity?.source_digest ?? state.document.source_digest;
  return {
    kernel_scene_id: `kernel:${state.architecture.architecture_id}:${sourceDigest.slice(0, 12)}`,
    architecture_id: state.architecture.architecture_id,
    source_digest: sourceDigest,
  };
}

export function visualRequestsForPatch(
  state: StudioStatePayload,
  patch: LabPatch,
  scene: LabScene,
): VisualPatchRequest[] {
  if (patch.operation !== "update-node" || !patch.changes.bounds) return [];
  const node = scene.nodes.find((item) => item.scene_node_id === patch.nodeId);
  if (!node) return [];
  const targetId = patch.persistenceTargetId
    ?? (node.hierarchy_node_id ? `view:${node.hierarchy_node_id}` : undefined);
  if (!targetId) return [];
  const next = patch.changes.bounds;
  const shared = kernelValue(state);
  const patches: VisualPatchRequest[] = [];
  if (next.x !== node.bounds.x || next.y !== node.bounds.y) {
    patches.push({ patch_id: requestId("position"), operation: "set-position", target_id: targetId, value: { ...shared, x: next.x, y: next.y } });
  }
  if (next.width !== node.bounds.width || next.height !== node.bounds.height) {
    patches.push({ patch_id: requestId("size"), operation: "set-size", target_id: targetId, value: { ...shared, width: next.width, height: next.height } });
  }
  return patches;
}

export async function persistVisualPatch(
  state: StudioStatePayload,
  patch: LabPatch,
  scene: LabScene,
): Promise<StudioStatePayload | null> {
  const patches = visualRequestsForPatch(state, patch, scene);
  if (!patches.length) return null;
  if (patches.length === 1) return postStudioJson<StudioStatePayload>("/api/patch", patches[0], { nonce: state.session_nonce });
  return postStudioJson<StudioStatePayload>("/api/patch-batch", {
    batch_id: requestId("batch").replace("patch:", "batch:"),
    description: "Update source-backed scene geometry",
    patches,
  }, { nonce: state.session_nonce });
}

export function persistVisualPatchBatch(
  state: StudioStatePayload,
  patches: readonly LabPatch[],
  scene: LabScene,
  description: string,
): Promise<StudioStatePayload | null> {
  const requests = patches.flatMap((patch) => visualRequestsForPatch(state, patch, scene));
  if (!requests.length) return Promise.resolve(null);
  return postStudioJson<StudioStatePayload>("/api/patch-batch", {
    batch_id: requestId("batch").replace("patch:", "batch:"),
    description,
    patches: requests,
  }, { nonce: state.session_nonce });
}

export function persistPinnedNodes(
  state: StudioStatePayload,
  scene: LabScene,
  sceneNodeIds: readonly string[],
  enabled: boolean,
): Promise<StudioStatePayload | null> {
  const shared = kernelValue(state);
  const patches = sceneNodeIds.flatMap((sceneNodeId) => {
    const node = scene.nodes.find((item) => item.scene_node_id === sceneNodeId);
    if (!node?.hierarchy_node_id) return [];
    return [{
      patch_id: requestId("pin"),
      operation: "set-pin",
      target_id: `view:${node.hierarchy_node_id}`,
      value: { ...shared, enabled },
    } satisfies VisualPatchRequest];
  });
  if (!patches.length) return Promise.resolve(null);
  return postStudioJson<StudioStatePayload>("/api/patch-batch", {
    batch_id: requestId("batch").replace("patch:", "batch:"),
    description: enabled ? "Pin source-backed scene nodes" : "Unpin source-backed scene nodes",
    patches,
  }, { nonce: state.session_nonce });
}

export function persistTheme(state: StudioStatePayload, theme: "paper-light" | "studio-dark") {
  return postStudioJson<StudioStatePayload>("/api/patch", {
    patch_id: requestId("theme"),
    operation: "set-theme",
    value: { theme },
  }, { nonce: state.session_nonce });
}

export function undoVisualPatch(state: StudioStatePayload) {
  return postStudioJson<StudioStatePayload>("/api/undo", {}, { nonce: state.session_nonce });
}

export function redoVisualPatch(state: StudioStatePayload) {
  return postStudioJson<StudioStatePayload>("/api/redo", {}, { nonce: state.session_nonce });
}
