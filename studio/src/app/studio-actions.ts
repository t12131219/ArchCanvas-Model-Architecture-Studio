import { postStudioJson } from "../api/studio-client";
import { navigationExpansion, persistNavigation as persistNavigationRequest } from "./navigation-actions";
import type { ArchitectureNodeView, Projection, StudioState } from "./studio-types";
import type { Dispatch, SetStateAction } from "react";

export interface VisualPatch {
  patch_id: string;
  operation: string;
  target_id?: string;
  value: Record<string, unknown>;
}

export function patchId(operation: string): string {
  const random = crypto.getRandomValues(new Uint32Array(2));
  return `patch:${operation}.${Date.now().toString(36)}.${random[0].toString(36)}${random[1].toString(36)}`;
}

interface StudioActionDependencies {
  data: StudioState | null;
  architectureNode?: ArchitectureNodeView;
  tx: (english: string, chinese: string) => string;
  acceptStudioState: (state: StudioState) => boolean;
  restoreNavigationState: (state: StudioState) => void;
  setActivity: Dispatch<SetStateAction<string[]>>;
  setBottomTab: Dispatch<SetStateAction<"problems" | "source" | "diff" | "validation" | "jobs" | "activity">>;
  setData?: Dispatch<SetStateAction<StudioState | null>>;
  navigationTimer?: { current: number | null };
  navigationQueue?: { current: Promise<void> };
  pollJob?: (jobId: string, onSuccess?: () => void) => void;
}

export function createStudioActions(deps: StudioActionDependencies) {
  const { data, architectureNode, tx, acceptStudioState, restoreNavigationState, setActivity, setBottomTab } = deps;

  async function mutate(endpoint: string, payload?: object, activityLabel?: string): Promise<StudioState | null> {
    try {
      const topologyEndpoints = new Set([
        "/api/proposal/node",
        "/api/proposal/draft-edge",
        "/api/proposal/delete-node",
        "/api/draft/node/delete",
        "/api/draft/node/parameters",
        "/api/draft/edge/delete",
        "/api/draft/delete-intent/discard",
        "/api/draft/session/discard",
        "/api/draft/session/submit",
      ]);
      let requestPayload = payload ?? {};
      if (topologyEndpoints.has(endpoint)) {
        if (data?.edit_session.mode !== "topology-draft") {
          throw new Error(tx("Topology draft mode is required.", "需要先解锁拓扑草稿模式。"));
        }
        requestPayload = {
          ...requestPayload,
          capability_id: data.edit_session.capability.capability_id,
          expected_document_digest: data.edit_session.current_document_digest,
        };
      }
      const state = await postStudioJson<StudioState>(endpoint, requestPayload, { nonce: data?.session_nonce });
      acceptStudioState(state);
      if (["/api/patch", "/api/patch-batch", "/api/undo", "/api/redo"].includes(endpoint)) {
        restoreNavigationState(state);
      }
      const visualPatch = payload as VisualPatch | undefined;
      const label = activityLabel ?? (visualPatch?.operation
        ? `${visualPatch.operation} · ${visualPatch.target_id ?? "document"}`
        : endpoint.slice(5));
      setActivity((items) => [label, ...items].slice(0, 20));
      return state;
    } catch (error) {
      setActivity((items) => [`${tx("Request failed", "请求失败")} · ${String(error)}`, ...items].slice(0, 20));
      return null;
    }
  }

  async function submitGlobal(operation: string, targetId: string | undefined, value: Record<string, unknown>) {
    await mutate("/api/patch", { patch_id: patchId(operation), operation, target_id: targetId, value });
  }

  async function submitKernel(operation: string, targetId: string | undefined, value: Record<string, unknown>) {
    if (!data) return;
    const kernelSceneId = `kernel:${data.architecture.architecture_id}:${data.document.source_digest.slice(0, 12)}`;
    await mutate("/api/patch", {
      patch_id: patchId(operation), operation, target_id: targetId,
      value: { ...value, kernel_scene_id: kernelSceneId, architecture_id: data.architecture.architecture_id, source_digest: data.document.source_digest },
    });
  }

  async function submitKernelBatch(description: string, patches: Array<{ operation: string; targetId?: string; value: Record<string, unknown> }>) {
    if (!data) return;
    const batchId = patchId("kernel-batch").replace("patch:", "batch:");
    const kernelSceneId = `kernel:${data.architecture.architecture_id}:${data.document.source_digest.slice(0, 12)}`;
    await mutate("/api/patch-batch", {
      batch_id: batchId,
      description,
      patches: patches.map((patch, index) => ({
        patch_id: `${batchId.replace("batch:", "patch:")}.${index}`,
        operation: patch.operation,
        target_id: patch.targetId,
        value: { ...patch.value, kernel_scene_id: kernelSceneId, architecture_id: data.architecture.architecture_id, source_digest: data.document.source_digest },
      })),
    }, description);
  }

  async function prepareParameter(parameterName: string, newValue: unknown) {
    if (!architectureNode) return;
    await mutate("/api/transaction/prepare", {
      patch_id: patchId("set-parameter"), target_node_id: architectureNode.node_id, parameter_name: parameterName, new_value: newValue,
    }, `${tx("Prepared", "已准备")} ${architectureNode.node_id}.${parameterName}`);
    setBottomTab("diff");
  }

  async function prepareStructural(operation: string, parameters: Record<string, unknown>) {
    if (!architectureNode) return;
    await mutate("/api/transaction/prepare-structural", {
      patch_id: patchId(operation.replaceAll("_", "-")), operation, target_node_id: architectureNode.node_id, parameters,
    }, `${tx("Prepared", "已准备")} ${operation} ${tx("on", "作用于")} ${architectureNode.node_id}`);
    setBottomTab("diff");
  }

  async function proposeConnection(sourcePortId: string, targetNodeId: string, targetPortId: string) {
    if (!architectureNode) return;
    await mutate("/api/proposal/connection", {
      proposal_id: patchId("connection").replace("patch:", "proposal:"),
      source_node_id: architectureNode.node_id, source_port_id: sourcePortId,
      target_node_id: targetNodeId, target_port_id: targetPortId, role: "main",
    }, `${tx("Proposed", "已提议")} ${architectureNode.node_id} → ${targetNodeId}`);
  }

  function persistNavigation(
    nextProjection: Projection,
    nextExpansions: Record<Projection, Set<string>>,
    activityLabel: string,
  ) {
    if (!data || !deps.navigationTimer || !deps.navigationQueue) return;
    if (deps.navigationTimer.current !== null) window.clearTimeout(deps.navigationTimer.current);
    const payload = navigationExpansion(nextProjection, nextExpansions);
    deps.navigationTimer.current = window.setTimeout(() => {
      deps.navigationTimer!.current = null;
      deps.navigationQueue!.current = deps.navigationQueue!.current
        .then(async () => {
          const state = await persistNavigationRequest(payload, data.session_nonce);
          acceptStudioState(state);
          setActivity((items) => [activityLabel, ...items].slice(0, 20));
        })
        .catch((error) => {
          setActivity((items) => [`${tx("Navigation persistence failed", "导航状态保存失败")} · ${String(error)}`, ...items].slice(0, 20));
        });
    }, 160);
  }

  async function commitSourceTransaction() {
    if (!data || !deps.setData) return;
    try {
      const state = await postStudioJson<StudioState & { reanalysis_job_id?: string | null }>(
        "/api/transaction/commit", {}, { nonce: data.session_nonce },
      );
      deps.setData(state);
      setActivity((items) => [tx("Committed source transaction", "已提交源码事务"), ...items].slice(0, 20));
      if (state.reanalysis_job_id && deps.pollJob) {
        setBottomTab("jobs");
        deps.pollJob(state.reanalysis_job_id, () => {
          setActivity((items) => [tx("Reanalysis completed on the committed source", "已基于提交后的源码完成重新分析"), ...items].slice(0, 20));
          setBottomTab("problems");
        });
      }
    } catch (error) {
      setActivity((items) => [`${tx("Source commit failed", "源码提交失败")} · ${String(error)}`, ...items].slice(0, 20));
    }
  }

  return { mutate, submitGlobal, submitKernel, submitKernelBatch, prepareParameter, prepareStructural, proposeConnection, persistNavigation, commitSourceTransaction };
}
