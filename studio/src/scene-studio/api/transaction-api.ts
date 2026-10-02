import { postStudioJson } from "../../api/studio-client";
import type { EditTargetScope, ParameterEditContext, StudioStatePayload } from "../domain/source-backed-scene";

function intentId(kind: string): string {
  return `patch:${kind}.${Date.now().toString(36)}.${crypto.randomUUID()}`;
}

function formId(framework: string): string {
  return ({
    pytorch: "form:pytorch-module-forward",
    keras: "form:keras-subclass-call",
    jax: "form:jax-pure-function",
    onnx: "form:onnx-standard-op",
    python: "form:python-callable",
  } as Record<string, string>)[framework] ?? "form:python-callable";
}

function intentBinding(state: StudioStatePayload) {
  const sourceDigest = state.semantic_intent_binding?.base_source_digest;
  const exactDigest = state.semantic_intent_binding?.base_exact_ir_digest;
  if (!sourceDigest || !exactDigest) throw new Error("当前项目缺少 semantic intent digest binding");
  return {
    project_id: state.project.project_id,
    project_generation: state.project.generation,
    base_source_digest: sourceDigest,
    base_exact_ir_digest: exactDigest,
    framework: state.project.framework,
    form_id: formId(state.project.framework),
  };
}

export function prepareParameterTransaction(
  state: StudioStatePayload,
  nodeId: string,
  parameterName: string,
  newValue: unknown,
  context: ParameterEditContext,
  scope: EditTargetScope,
) {
  const patchId = intentId("set-parameter");
  return postStudioJson<StudioStatePayload>("/api/transaction/prepare", {
    patch_id: patchId,
    target_node_id: nodeId,
    parameter_name: parameterName,
    new_value: newValue,
    value_origin_id: context.value_origin.origin_id,
    edit_target_scope: scope,
    confirmed_affected_ids: context.affected_canonical_ids,
    confirmed_source_anchor_ids: context.value_origin.source_anchor_ids,
    semantic_intent: {
      schema_version: "2.0",
      intent_id: patchId.replace("patch:", "intent:"),
      ...intentBinding(state),
      operation: "set-parameter",
      target_ids: [nodeId],
      payload: { parameter_name: parameterName, new_value: newValue },
      value_origin: context.value_origin,
      edit_target_scope: scope,
      affected_object_review: {
        review_id: `review:${crypto.randomUUID()}`,
        affected_object_ids: context.affected_canonical_ids,
        source_anchor_ids: context.value_origin.source_anchor_ids,
        parameter_sharing_group_ids: [],
        decision: "confirmed",
        reviewed_generation: state.project.generation,
      },
    },
  }, { nonce: state.session_nonce });
}

export function prepareStructuralTransaction(
  state: StudioStatePayload,
  nodeId: string,
  operation: "replace_activation" | "insert_layer_norm",
  parameters: Record<string, unknown>,
) {
  const patchId = intentId(operation.replaceAll("_", "-"));
  return postStudioJson<StudioStatePayload>("/api/transaction/prepare-structural", {
    patch_id: patchId,
    target_node_id: nodeId,
    operation,
    parameters,
    semantic_intent: {
      schema_version: "2.0",
      intent_id: patchId.replace("patch:", "intent:"),
      ...intentBinding(state),
      operation: operation === "replace_activation" ? "replace-operation" : "insert-normalization",
      target_ids: [nodeId],
      payload: parameters,
      affected_object_review: {
        review_id: `review:${crypto.randomUUID()}`,
        affected_object_ids: [nodeId],
        source_anchor_ids: [],
        parameter_sharing_group_ids: [],
        decision: "confirmed",
        reviewed_generation: state.project.generation,
      },
    },
  }, { nonce: state.session_nonce });
}

export function commitSourceTransaction(state: StudioStatePayload) {
  return postStudioJson<StudioStatePayload & { reanalysis_job_id?: string | null }>(
    "/api/transaction/commit",
    {},
    { nonce: state.session_nonce },
  );
}

export function discardSourceTransaction(state: StudioStatePayload) {
  return postStudioJson<StudioStatePayload>("/api/transaction/discard", {}, { nonce: state.session_nonce });
}
