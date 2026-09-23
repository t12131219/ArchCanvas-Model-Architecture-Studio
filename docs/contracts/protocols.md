# Protocol Contracts

All persisted documents use a `schema_version` with major/minor semantics. A reader must reject unknown major versions and may accept additive minor changes.

## Truth layers

1. `SourceSnapshot` freezes project root, entrypoint, task, execution mode, adapter version, configuration digest, and source file digests.
2. `EvidenceRecord` binds a claim to a source span or an explicitly identified non-source provenance kind.
3. `ArchitectureIR` stores canonical nodes, tensors, typed port-to-tensor edges, repeats, and unresolved facts.
4. `RuntimeInputSpec` freezes generated inputs, seed, device, and resource limits for an explicit
   opt-in execution.
5. `RuntimeTrace` stores module-boundary shape/dtype observations, environment provenance,
   isolation policy, blocked boundary attempts, and a deterministic replay digest. It is a sidecar
   and never overwrites static Evidence or Exact IR.
6. `CanvasDocument` stores only visual patches and selection-independent view state.
7. `SemanticParameterPatch` identifies one canonical node parameter, target value, artifact binding,
   and optional targeted tests/runtime replay.
8. `GraphDelta` records exact node, edge, parameter, port, tensor, shape, repeat, sharing, evidence,
   and unresolved changes without using renderer geometry as semantic evidence.
9. `SourceTransaction` persists the original revision and hashes, exact anchor fingerprint, isolated
   project copy, unified diff, expected/observed deltas, gates, diagnostics, and state.
10. `CommandReceipt` and `TransactionReceipt` report command status, artifacts, gates, structured
   diagnostics, and whether a source write occurred.

Canonical identifiers derive from source symbol, callsite, logical path, repeat/branch identity, and sharing identity. Renderer coordinates and list ordering are never identity inputs.

## CLI behavior

With `--json`, stdout contains one compact JSON object. Diagnostics go to stderr. `ok` exits 0, invalid input exits 2, unavailable capabilities exit 3, and internal failures exit 1.

`analyze` is always static and never imports the target project. `trace` requires an existing
architecture/source snapshot pair plus an explicit input spec, runs in a separate process, and
publishes `runtime-trace.json`, `runtime-evidence-ledger.json`, a node-evidence overlay, capability
report, and receipt. Runtime failure leaves the static bundle usable and emits failed/skipped gates
without claiming runtime-confirmed evidence.

## Source transaction behavior

`archcanvas patch prepare REQUEST --workspace WORKSPACE --json` validates the frozen source and
config hashes, resolves an exact parameter anchor, creates a filtered private project copy, applies
the structured JSON or LibCST transform there, and records a unified diff plus Expected Graph Delta.
The original project is not written.

`patch verify TRANSACTION --json` executes the gates in order: parse/syntax, static relative-import
resolution, Exact IR reanalysis, exact Graph Delta comparison, shape/type invariants, built-in and
requested targeted tests, optional isolated runtime replay, and L1-L4 publication/geometry
recompilation. A failed gate transitions to `failed`; unexecuted gates are never labeled passed.

`patch commit TRANSACTION --json` accepts only `review-ready`, rechecks every frozen source hash and
the target file hash, rejects concurrent changes without fuzzy merge, uses same-directory atomic
replacement, and reruns analysis. Any commit failure restores original bytes. `patch discard`
removes the private project copy while retaining the audit manifest.
