import type { ModuleDefinition, ParameterContract, PortContract } from "../module-registry/types";
import type {
  ContractChange,
  ContractDiff,
  ContractReviewReceipt,
  ContractValidation,
  DefinitionDraft,
  DefinitionMigration,
  VersionBump,
} from "./types";

const rank: Record<VersionBump, number> = { none: 0, patch: 1, minor: 2, major: 3 };

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([key]) => key !== "digest")
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonicalize(item)]),
    );
  }
  return value;
}

async function digest(domain: string, value: unknown): Promise<string> {
  const body = new TextEncoder().encode(`${domain}\0${JSON.stringify(canonicalize(value))}`);
  const bytes = await crypto.subtle.digest("SHA-256", body);
  return Array.from(new Uint8Array(bytes), (item) => item.toString(16).padStart(2, "0")).join("");
}

export function candidateDigest(candidate: ModuleDefinition): Promise<string> {
  return digest("archcanvas:module-definition-candidate:v1", candidate);
}

function same(left: unknown, right: unknown): boolean {
  return JSON.stringify(canonicalize(left)) === JSON.stringify(canonicalize(right));
}

function change(
  changes: ContractChange[],
  subject: string,
  kind: ContractChange["kind"],
  compatibility: ContractChange["compatibility"],
  message: string,
): void {
  changes.push({ subject, kind, compatibility, message });
}

function compareParameters(base: ParameterContract[], candidate: ParameterContract[], changes: ContractChange[]): void {
  const before = new Map(base.map((item) => [item.parameter_id, item]));
  const after = new Map(candidate.map((item) => [item.parameter_id, item]));
  for (const [id, prior] of before) {
    const next = after.get(id);
    if (!next) {
      change(changes, id, "parameter", "breaking", `Parameter ${id} was removed or renamed.`);
      continue;
    }
    if (
      prior.value_type !== next.value_type
      || prior.required !== next.required
      || prior.positional_index !== next.positional_index
      || prior.editability !== next.editability
      || !same([...prior.affects].sort(), [...next.affects].sort())
    ) {
      change(changes, id, "parameter", "breaking", `Parameter ${id} changed its type, required state, or positional binding.`);
    } else if (!same(prior.default, next.default)) {
      change(changes, id, "parameter", "breaking", `Parameter ${id} changed its runtime default.`);
    }
  }
  for (const [id, next] of after) {
    if (before.has(id)) continue;
    change(
      changes,
      id,
      "parameter",
      next.required ? "breaking" : "backward-compatible",
      `${next.required ? "Required" : "Optional"} parameter ${id} was added.`,
    );
  }
}

function comparePorts(base: PortContract[], candidate: PortContract[], changes: ContractChange[]): void {
  const before = new Map(base.map((item) => [item.port_id, item]));
  const after = new Map(candidate.map((item) => [item.port_id, item]));
  for (const [id, prior] of before) {
    const next = after.get(id);
    if (!next) {
      change(changes, id, "port", "breaking", `Port ${id} was removed or renamed.`);
      continue;
    }
    if (
      prior.direction !== next.direction
      || prior.required !== next.required
      || prior.min_connections !== next.min_connections
      || prior.max_connections !== next.max_connections
      || prior.ordering !== next.ordering
      || !same([...prior.accepted_relations].sort(), [...next.accepted_relations].sort())
      || !same([...prior.tensor_ranks].sort((left, right) => left - right), [...next.tensor_ranks].sort((left, right) => left - right))
      || !same([...prior.tensor_layouts].sort(), [...next.tensor_layouts].sort())
    ) {
      change(changes, id, "port", "breaking", `Port ${id} changed its direction, cardinality, ordering, or relation contract.`);
    }
  }
  for (const [id, next] of after) {
    if (before.has(id)) continue;
    change(
      changes,
      id,
      "port",
      next.required || next.min_connections > 0 ? "breaking" : "backward-compatible",
      `${next.required ? "Required" : "Optional"} port ${id} was added.`,
    );
  }
}

export function diffDefinitions(base: ModuleDefinition, candidate: ModuleDefinition): ContractDiff {
  const changes: ContractChange[] = [];
  if (base.definition_id !== candidate.definition_id) {
    change(changes, "definition_id", "semantic", "breaking", "Definition identity cannot change in place.");
  }
  if (base.semantic_kind !== candidate.semantic_kind) {
    change(changes, "semantic_kind", "semantic", "breaking", "Canonical semantic kind changed.");
  }
  if (base.parameter_schema_version !== candidate.parameter_schema_version) {
    change(changes, "parameter_schema_version", "semantic", "breaking", "Parameter schema version changed.");
  }
  compareParameters(base.parameters, candidate.parameters, changes);
  comparePorts(base.ports, candidate.ports, changes);
  const beforeNames = new Set(base.qualified_names);
  const afterNames = new Set(candidate.qualified_names);
  for (const value of beforeNames) {
    if (!afterNames.has(value)) change(changes, value, "matcher", "breaking", `Source matcher ${value} was removed.`);
  }
  for (const value of afterNames) {
    if (!beforeNames.has(value)) change(changes, value, "matcher", "backward-compatible", `Source matcher ${value} was added.`);
  }
  for (const key of ["shape_rule_id", "cost_rule_id", "codegen_rule_id"] as const) {
    if (base[key] !== candidate[key]) change(changes, key, "rule", "breaking", `${key} changed.`);
  }
  for (const key of ["glyph_id", "detail_template_id"] as const) {
    if (base[key] !== candidate[key]) change(changes, key, "visual", "visual-only", `${key} changed.`);
  }
  const compatibility = changes.some((item) => item.compatibility === "breaking")
    ? "breaking"
    : changes.some((item) => item.compatibility === "backward-compatible")
      ? "backward-compatible"
      : changes.length ? "visual-only" : "unchanged";
  const requiredVersionBump: VersionBump = compatibility === "breaking"
    ? "major"
    : compatibility === "backward-compatible"
      ? "minor"
      : compatibility === "visual-only" ? "patch" : "none";
  return { changes, compatibility, requiredVersionBump };
}

function parseVersion(value: string): [number, number, number] | null {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(value);
  return match ? [Number(match[1]), Number(match[2]), Number(match[3])] : null;
}

export function actualVersionBump(base: string, candidate: string): VersionBump | "invalid" {
  const before = parseVersion(base);
  const after = parseVersion(candidate);
  if (!before || !after) return "invalid";
  if (after[0] > before[0]) return after[1] === 0 && after[2] === 0 ? "major" : "invalid";
  if (after[0] !== before[0]) return "invalid";
  if (after[1] > before[1]) return after[2] === 0 ? "minor" : "invalid";
  if (after[1] !== before[1]) return "invalid";
  if (after[2] > before[2]) return "patch";
  return after[2] === before[2] ? "none" : "invalid";
}

function migrationCovers(diff: ContractDiff, migration: DefinitionMigration | undefined): boolean {
  if (diff.compatibility !== "breaking") return true;
  if (!migration || !migration.fixtureIds.length) return false;
  return diff.changes.filter((item) => item.compatibility === "breaking").every((item) => {
    if (item.kind === "port") return Object.hasOwn(migration.portMap, item.subject);
    if (item.kind === "parameter") return Object.hasOwn(migration.parameterMap, item.subject);
    return true;
  });
}

export async function createDefinitionDraft(
  base: ModuleDefinition,
  candidate: ModuleDefinition,
  options: { draftId: string; author: string; createdAt: string; migration?: DefinitionMigration },
): Promise<DefinitionDraft> {
  return {
    draftId: options.draftId,
    base: { definitionId: base.definition_id, version: base.version, digest: base.digest },
    candidate: structuredClone(candidate),
    candidateDigest: await candidateDigest(candidate),
    author: options.author,
    createdAt: options.createdAt,
    migration: options.migration,
  };
}

export async function validateDefinitionDraft(base: ModuleDefinition, draft: DefinitionDraft): Promise<ContractValidation> {
  const currentDigest = await candidateDigest(draft.candidate);
  const diff = diffDefinitions(base, draft.candidate);
  const diagnostics: ContractValidation["diagnostics"] = [];
  if (base.definition_id !== draft.base.definitionId || base.version !== draft.base.version || base.digest !== draft.base.digest) {
    diagnostics.push({ code: "CONTRACT_BASE_STALE", message: "The approved base definition no longer matches the draft." });
  }
  if (currentDigest !== draft.candidateDigest) {
    diagnostics.push({ code: "CONTRACT_CANDIDATE_MUTATED", message: "Candidate content changed after the draft digest was bound." });
  }
  const actual = actualVersionBump(base.version, draft.candidate.version);
  if (actual === "invalid" || rank[actual] < rank[diff.requiredVersionBump]) {
    diagnostics.push({ code: "CONTRACT_VERSION_INSUFFICIENT", message: `The contract requires a ${diff.requiredVersionBump} version bump.` });
  }
  if (!migrationCovers(diff, draft.migration)) {
    diagnostics.push({ code: "CONTRACT_MIGRATION_REQUIRED", message: "Breaking contract changes require a fixture-tested migration." });
  }
  return {
    status: diagnostics.length ? "failed" : "passed",
    candidateDigest: currentDigest,
    diff,
    diagnostics,
  };
}

export async function reviewDefinitionDraft(
  draft: DefinitionDraft,
  validation: ContractValidation,
  options: { receiptId: string; reviewer: string; decision: "approved" | "rejected"; decidedAt: string },
): Promise<ContractReviewReceipt> {
  const currentDigest = await candidateDigest(draft.candidate);
  if (currentDigest !== draft.candidateDigest || validation.candidateDigest !== draft.candidateDigest) {
    throw new Error("review receipt cannot bind a stale or mutated candidate");
  }
  if (options.decision === "approved" && validation.status !== "passed") {
    throw new Error("failed contract validation cannot be approved");
  }
  return {
    receiptId: options.receiptId,
    draftId: draft.draftId,
    candidateDigest: draft.candidateDigest,
    validationDigest: await digest("archcanvas:contract-validation:v1", validation),
    reviewer: options.reviewer,
    decision: options.decision,
    decidedAt: options.decidedAt,
  };
}
