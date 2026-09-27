import { getStudioJson, postStudioJson } from "../api/studio-client";
import type { CanonicalDeleteImpact, StudioState } from "./studio-types";

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
  parent_entrypoint: string | null;
  parent_entrypoints: string[];
  root_entrypoint: string;
  depth: number;
  contains: string[];
  child_count: number;
  top_level: boolean;
  analysis_root: string;
  analysis_entrypoint: string;
  config_paths: string[];
  category: "model" | "encoder" | "decoder" | "backbone" | "attention" | "head" | "block" | "layer" | "component";
}

export interface PendingProject {
  project: { project_id: string; generation: number; framework: string };
  discovery: {
    entrypoints: ProjectEntrypoint[];
    configs: Array<{ path: string }>;
    scanned_files: number;
    environment?: CondaEnvironment | null;
  };
}

export interface DirectoryBrowserState {
  path: string;
  parent: string | null;
  breadcrumbs: Array<{ name: string; path: string }>;
  directories: Array<{ name: string; path: string }>;
  truncated: boolean;
}

export async function loadCondaEnvironments(signal?: AbortSignal) {
  return getStudioJson<{ environments: CondaEnvironment[]; selected: string | null }>(
    "/api/environments/conda",
    { signal },
  );
}

export function loadStudioState() {
  return getStudioJson<StudioState>("/api/state");
}

export function searchStudio(query: string, signal?: AbortSignal) {
  return getStudioJson<{ results: Array<{
    id: string;
    kind: string;
    title: string;
    aliases: string[];
    canonical_ids: string[];
    view_bindings: Array<{ projection_id: string; scene_id: string; scene_node_id: string }>;
    facets: Record<string, string>;
  }> }>(`/api/search?q=${encodeURIComponent(query)}`, { signal });
}

export function previewCanonicalDelete(nodeId: string, nonce?: string | null) {
  return postStudioJson<{ impact: CanonicalDeleteImpact }>(
    "/api/proposal/delete-node/preview",
    { node_id: nodeId },
    { nonce: nonce ?? undefined },
  );
}

export function startValidation(profile: string, nonce?: string | null) {
  return postStudioJson<{ job_id: string }>(
    "/api/validation-runs",
    { profile, runtime_execution_authorized: false },
    { nonce: nonce ?? undefined },
  );
}

export function openProject(root: string, environmentPath: string | null, nonce?: string | null) {
  return postStudioJson<PendingProject>(
    "/api/projects/open",
    { root, environment_path: environmentPath },
    { nonce: nonce ?? undefined },
  );
}

export function browseDirectories(path: string) {
  return getStudioJson<DirectoryBrowserState>(`/api/directories?path=${encodeURIComponent(path)}`);
}

export interface AnalysisRequest {
  project_id: string;
  project_generation: number;
  entrypoint: string;
  framework: string;
  task: "inference";
  config_path: string | null;
  execution_mode: "static";
  pattern_packs_enabled: boolean;
  request_id: string;
}

export function startAnalysis(request: AnalysisRequest, nonce?: string | null) {
  return postStudioJson<{ job_id: string }>("/api/analyses", request, { nonce: nonce ?? undefined });
}
