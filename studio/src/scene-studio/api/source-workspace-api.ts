import { postStudioJson } from "../../api/studio-client";
import type { SourceWorkspaceBuffer, StudioStatePayload } from "../domain/source-backed-scene";

interface BufferResponse {
  buffer: SourceWorkspaceBuffer;
  state: StudioStatePayload;
}

export function openSourceBuffer(state: StudioStatePayload, path: string) {
  return postStudioJson<BufferResponse>("/api/source-workspace/open", { path }, { nonce: state.session_nonce });
}

export function saveSourceBuffer(
  state: StudioStatePayload,
  buffer: SourceWorkspaceBuffer,
  content: string,
) {
  if (!state.source_workspace) throw new Error("源码工作区不可用");
  return postStudioJson<BufferResponse>("/api/source-workspace/save", {
    path: buffer.path,
    content,
    base_sha256: buffer.base_sha256,
    expected_revision: state.source_workspace.revision,
  }, { nonce: state.session_nonce });
}

export function discardSourceBuffer(state: StudioStatePayload, path: string) {
  if (!state.source_workspace) throw new Error("源码工作区不可用");
  return postStudioJson<StudioStatePayload>("/api/source-workspace/buffer/discard", {
    path,
    expected_revision: state.source_workspace.revision,
  }, { nonce: state.session_nonce });
}

export function validateSourceWorkspace(state: StudioStatePayload) {
  return postStudioJson<StudioStatePayload>("/api/source-workspace/validate", {}, { nonce: state.session_nonce });
}

export function discardSourceWorkspace(state: StudioStatePayload) {
  return postStudioJson<StudioStatePayload>("/api/source-workspace/discard", {}, { nonce: state.session_nonce });
}
