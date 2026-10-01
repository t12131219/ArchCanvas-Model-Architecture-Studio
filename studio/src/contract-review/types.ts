import type { ModuleDefinition } from "../module-registry/types";

export type ContractCompatibility = "breaking" | "backward-compatible" | "visual-only" | "unchanged";
export type VersionBump = "major" | "minor" | "patch" | "none";

export interface ContractChange {
  subject: string;
  kind: "parameter" | "port" | "rule" | "matcher" | "semantic" | "visual";
  compatibility: Exclude<ContractCompatibility, "unchanged">;
  message: string;
}

export interface ContractDiff {
  changes: ContractChange[];
  compatibility: ContractCompatibility;
  requiredVersionBump: VersionBump;
}

export interface DefinitionMigration {
  migrationId: string;
  fromVersion: string;
  toVersion: string;
  parameterMap: Record<string, string | null>;
  portMap: Record<string, string | null>;
  fixtureIds: string[];
}

export interface DefinitionDraft {
  draftId: string;
  base: { definitionId: string; version: string; digest: string };
  candidate: ModuleDefinition;
  candidateDigest: string;
  author: string;
  createdAt: string;
  migration?: DefinitionMigration;
}

export interface ContractValidation {
  status: "passed" | "failed";
  candidateDigest: string;
  diff: ContractDiff;
  diagnostics: Array<{ code: string; message: string }>;
}

export interface ContractReviewReceipt {
  receiptId: string;
  draftId: string;
  candidateDigest: string;
  validationDigest: string;
  reviewer: string;
  decision: "approved" | "rejected";
  decidedAt: string;
}

