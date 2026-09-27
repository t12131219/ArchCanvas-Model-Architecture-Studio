export interface LaunchEntrypoint {
  entrypoint: string;
  framework: string;
  top_level: boolean;
  depth: number;
  path?: string;
  kind?: string;
  child_count?: number;
}

export interface InitialProjectSelection {
  entrypoint: string;
  framework: string;
  configPath: string;
}

function modelCandidateScore(candidate: LaunchEntrypoint): number {
  const [moduleName, symbolName = ""] = candidate.entrypoint.split(":", 2);
  const normalizedSymbol = symbolName.toLowerCase().replaceAll("_", "");
  const moduleParts = moduleName.toLowerCase().split(".");
  const pathParts = (candidate.path ?? "").toLowerCase().split(/[/.]/);
  const modelLocations = new Set(["model", "models", "network", "networks", "architecture", "architectures"]);
  const modelNamed = normalizedSymbol === "model"
    || normalizedSymbol.endsWith("model")
    || normalizedSymbol.endsWith("network")
    || normalizedSymbol.endsWith("net");
  return Number(candidate.kind === "model-artifact") * 200
    + Number(modelNamed) * 100
    + Number([...moduleParts, ...pathParts].some((part) => modelLocations.has(part))) * 60
    + Number(candidate.framework !== "unknown") * 10
    + Math.min(candidate.child_count ?? 0, 20)
    - candidate.depth;
}

export function initialProjectSelection(
  entrypoints: LaunchEntrypoint[],
): InitialProjectSelection {
  const roots = entrypoints.filter((item) => item.depth === 0);
  const pool = entrypoints.filter((item) => item.top_level);
  const candidates = pool.length ? pool : roots.length ? roots : entrypoints;
  const candidate = [...candidates].sort((left, right) =>
    modelCandidateScore(right) - modelCandidateScore(left)
    || left.entrypoint.localeCompare(right.entrypoint)
  )[0];

  return {
    entrypoint: candidate?.entrypoint ?? "",
    framework: candidate?.framework === "unknown"
      ? "auto"
      : candidate?.framework ?? "auto",
    // Discovery cannot prove that a benchmark-level config belongs to the
    // initially selected model. Configuration is therefore explicit opt-in.
    configPath: "",
  };
}
