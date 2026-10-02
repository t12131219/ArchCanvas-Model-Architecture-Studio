import { postStudioJson } from "../../api/studio-client";
import type { DraftEdge, DraftNode, StudioStatePayload } from "../domain/source-backed-scene";

function topologyPayload(state: StudioStatePayload, payload: Record<string, unknown> = {}) {
  if (state.edit_session?.mode !== "topology-draft") {
    throw new Error("需要先解锁拓扑草稿模式");
  }
  return {
    ...payload,
    capability_id: state.edit_session.capability.capability_id,
    expected_document_digest: state.edit_session.current_document_digest,
  };
}

function postDraft(state: StudioStatePayload, endpoint: string, payload: Record<string, unknown> = {}) {
  return postStudioJson<StudioStatePayload>(endpoint, topologyPayload(state, payload), {
    nonce: state.session_nonce,
  });
}

export function beginTopologyDraft(state: StudioStatePayload) {
  if (!state.edit_session || state.edit_session.mode !== "visual") {
    throw new Error("当前编辑会话不能进入拓扑草稿模式");
  }
  return postStudioJson<StudioStatePayload>("/api/draft/session/begin", {
    base_document_digest: state.edit_session.current_document_digest,
  }, { nonce: state.session_nonce });
}

export function discardTopologyDraft(state: StudioStatePayload) {
  return postDraft(state, "/api/draft/session/discard");
}

export function submitTopologyDraft(state: StudioStatePayload) {
  return postDraft(state, "/api/draft/session/submit");
}

export function createDraftNode(state: StudioStatePayload, node: DraftNode) {
  return postDraft(state, "/api/proposal/node", { node });
}

export function deleteDraftNode(state: StudioStatePayload, nodeId: string) {
  return postDraft(state, "/api/draft/node/delete", { node_id: nodeId });
}

export function updateDraftNodeParameters(
  state: StudioStatePayload,
  nodeId: string,
  parameters: Record<string, unknown>,
) {
  return postDraft(state, "/api/draft/node/parameters", { node_id: nodeId, parameters });
}

export function connectDraftPorts(state: StudioStatePayload, edge: DraftEdge) {
  return postDraft(state, "/api/proposal/draft-edge", { edge });
}

export function disconnectDraftEdge(state: StudioStatePayload, edgeId: string) {
  return postDraft(state, "/api/draft/edge/delete", { edge_id: edgeId });
}
