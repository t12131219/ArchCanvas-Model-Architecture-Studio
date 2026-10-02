import { getStudioJson, postStudioJson } from "../../api/studio-client";
import type { StudioJob } from "../../jobs";
import type { StudioStatePayload } from "../domain/source-backed-scene";

export interface CondaEnvironment {
  name: string;
  path: string;
  python: string;
  active: boolean;
}

export interface ProjectEntrypoint {
  entrypoint: string;
  path: string;
  framework: string;
  kind: string;
  confidence: string;
  category: string;
  config_paths: string[];
}

export interface PendingProject {
  project: { project_id: string; generation: number; framework: string };
  discovery: {
    entrypoints: ProjectEntrypoint[];
    configs: Array<{ path: string }>;
    scanned_files: number;
    environment?: CondaEnvironment | null;
  };
  framework_forms: Array<{
    framework: string;
    forms: Array<{
      form_id: string;
      form_name: string;
      static_analysis: "verified" | "experimental" | "partial" | "unavailable";
      runtime_evidence: "verified" | "experimental" | "partial" | "unavailable";
      parameter_transaction: "verified" | "experimental" | "partial" | "unavailable";
      structural_transaction: "verified" | "experimental" | "partial" | "unavailable";
      code_generation: "verified" | "experimental" | "partial" | "unavailable";
      artifact_commit: "verified" | "experimental" | "partial" | "unavailable";
    }>;
  }>;
}

export interface DirectoryBrowserState {
  path: string;
  parent: string | null;
  breadcrumbs: Array<{ name: string; path: string }>;
  directories: Array<{ name: string; path: string }>;
  truncated: boolean;
}

export interface AnalysisRequest {
  project_id: string;
  project_generation: number;
  entrypoint: string;
  framework: string;
  form_id: string;
  task: "inference";
  config_path: string | null;
  execution_mode: "static";
  pattern_packs_enabled: boolean;
  entry_invocation: {
    schema_version: "1.0";
    constructor_args: unknown[];
    constructor_kwargs: Record<string, unknown>;
    forward_args: unknown[];
    forward_kwargs: Record<string, unknown>;
    static_args: Record<string, unknown>;
    mode: "eval" | "train";
    input_structure: unknown;
  };
  request_id: string;
}

export function loadStudioState(signal?: AbortSignal): Promise<StudioStatePayload> {
  return getStudioJson<StudioStatePayload>("/api/state", { signal });
}

export function loadCondaEnvironments(signal?: AbortSignal) {
  return getStudioJson<{ environments: CondaEnvironment[]; selected: string | null }>("/api/environments/conda", { signal });
}

export function browseDirectories(path?: string, signal?: AbortSignal) {
  const query = path?.trim() ? `?path=${encodeURIComponent(path.trim())}` : "";
  return getStudioJson<DirectoryBrowserState>(`/api/directories${query}`, { signal });
}

export function openProject(root: string, environmentPath: string | null, nonce?: string) {
  return postStudioJson<PendingProject>("/api/projects/open", {
    root,
    environment_path: environmentPath,
    framework: "auto",
    task: "inference",
  }, { nonce });
}

export function startAnalysis(request: AnalysisRequest, nonce?: string) {
  return postStudioJson<StudioJob>("/api/analyses", request, { nonce });
}

export function loadJob(jobId: string, signal?: AbortSignal) {
  return getStudioJson<StudioJob>(`/api/jobs/${encodeURIComponent(jobId)}`, { signal });
}

export function cancelJob(jobId: string, nonce?: string) {
  return postStudioJson<StudioJob>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, {}, { nonce });
}

export interface StudioSearchResult {
  id: string;
  kind: string;
  title: string;
  aliases: string[];
  canonical_ids: string[];
  source_spans?: Array<{ path: string; start_line: number; end_line: number }>;
  facets: Record<string, string>;
}

export function searchStudio(query: string, signal?: AbortSignal) {
  return getStudioJson<{ input_fingerprint: string; results: StudioSearchResult[] }>(
    `/api/search?q=${encodeURIComponent(query)}`,
    { signal },
  );
}

export function startValidation(profile: "fast-static" | "publication" | "full", nonce?: string) {
  return postStudioJson<StudioJob>("/api/validation-runs", {
    profile,
    runtime_execution_authorized: false,
  }, { nonce });
}

export function setHierarchyExpansion(state: StudioStatePayload, expandedIds: string[]) {
  const desired = new Set(expandedIds);
  const current = new Set(state.view_state?.module_expansion ?? []);
  const changed = [...new Set([...current, ...desired])].filter((id) => current.has(id) !== desired.has(id)).sort();
  if (!changed.length) return Promise.resolve(state);
  const sourceDigest = state.integrity?.source_digest ?? state.document.source_digest;
  const batchId = `batch:hierarchy.${Date.now().toString(36)}.${crypto.randomUUID()}`;
  return postStudioJson<StudioStatePayload>("/api/patch-batch", {
    batch_id: batchId,
    description: "Update source-backed hierarchy expansion",
    patches: changed.map((id, index) => ({
      patch_id: `${batchId.replace("batch:", "patch:")}.${index}`,
      operation: "set-detail-expansion",
      target_id: id,
      value: {
        enabled: desired.has(id),
        kernel_scene_id: `kernel:${state.architecture.architecture_id}:${sourceDigest.slice(0, 12)}`,
        architecture_id: state.architecture.architecture_id,
        source_digest: sourceDigest,
      },
    })),
  }, { nonce: state.session_nonce });
}

export function setNavigationView(
  state: StudioStatePayload,
  projection: "module" | "source",
  expansions: Record<"module" | "source", string[]>,
) {
  return postStudioJson<StudioStatePayload>("/api/navigation", {
    projection,
    expansions,
  }, { nonce: state.session_nonce });
}
