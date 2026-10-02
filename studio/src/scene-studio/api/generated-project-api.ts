import { postStudioJson } from "../../api/studio-client";
import type { GeneratedProjectRecord, StudioStatePayload } from "../domain/source-backed-scene";

function activeRecord(state: StudioStatePayload): GeneratedProjectRecord {
  const record = state.generated_projects?.active;
  if (!record) throw new Error("当前没有 Generated Source Project");
  return record;
}

export function prepareGeneratedProject(state: StudioStatePayload) {
  const draft = state.draft;
  const graphDigest = state.edit_session?.mode === "visual" || state.edit_session?.mode === "topology-draft"
    ? state.edit_session.current_document_digest
    : undefined;
  const inputNode = draft?.nodes.find((node) => node.definition_ref?.definition_id === "archcanvas.input.tensor");
  const registryDigest = draft?.base_registry_digest;
  const generatorVersion = state.capabilities?.generated_project?.generator_version;
  if (!draft || !graphDigest || !registryDigest || !generatorVersion || !inputNode) {
    throw new Error("Graph Draft 缺少生成工程所需的 digest 或 Input 定义");
  }
  return postStudioJson<StudioStatePayload>("/api/generated-projects/prepare", {
    graph_digest: graphDigest,
    registry_digest: registryDigest,
    generator_version: generatorVersion,
    target_framework: "pytorch",
    form_id: "form:pytorch-module-forward",
    class_name: "GeneratedModel",
    entrypoint: "model:GeneratedModel",
    input_spec: {
      shape: inputNode.parameters.shape,
      dtype: "float32",
      layout: "NCHW",
    },
  }, { nonce: state.session_nonce });
}

export function validateGeneratedProject(state: StudioStatePayload) {
  const record = activeRecord(state);
  return postStudioJson<StudioStatePayload>(
    `/api/generated-projects/${encodeURIComponent(record.project_id)}/validate`,
    {
      graph_digest: record.graph_digest,
      registry_digest: record.registry_digest,
      generator_version: record.generator_version,
    },
    { nonce: state.session_nonce },
  );
}

export function materializeGeneratedProject(state: StudioStatePayload, targetDirectory: string) {
  const record = activeRecord(state);
  return postStudioJson<StudioStatePayload>(
    `/api/generated-projects/${encodeURIComponent(record.project_id)}/materialize`,
    {
      target_directory: targetDirectory,
      graph_digest: record.graph_digest,
      registry_digest: record.registry_digest,
      generator_version: record.generator_version,
      inventory_digest: record.receipt.inventory_digest,
    },
    { nonce: state.session_nonce },
  );
}

export function discardGeneratedProject(state: StudioStatePayload) {
  const record = activeRecord(state);
  return postStudioJson<StudioStatePayload>(
    `/api/generated-projects/${encodeURIComponent(record.project_id)}/discard`,
    {},
    { nonce: state.session_nonce },
  );
}
