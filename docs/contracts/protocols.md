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
   and optional targeted tests/runtime replay. `SemanticStructuralPatch` is restricted to a named,
   versioned transform in the trusted registry.
8. `ProposedConnection` describes authored source/target ports without changing source.
   `AgentProposal` carries the unsupported intent, compatibility finding, and handoff context while
   requiring shell, network, and source-write permissions to remain false.
9. `GraphDelta` records exact node, edge, parameter, port, tensor, shape, fanout, repeat,
   configuration-predicate, sharing, evidence, and unresolved changes without using renderer
   geometry as semantic evidence.
10. `SourceTransaction` persists the original revision and hashes, exact anchor fingerprint, isolated
   project copy, unified diff, expected/observed deltas, gates, diagnostics, and state.
11. `PatternPackManifest` defines ordered structural, dataflow, shape, sharing/control-flow, and
   weak-name predicates. A pack reads Exact IR and emits only `SemanticAnnotationOverlay`.
   `PatternPackReceipt` records every loaded pack, match or rejection reason, selection, and the
   Exact IR digest before and after. `PatternCandidateReview` is preview-only and grants no shell,
   network, or source-write permission.
12. `CommandReceipt` and `TransactionReceipt` report command status, artifacts, gates, structured
   diagnostics, and whether a source write occurred.

Canonical identifiers derive from source symbol, callsite, logical path, repeat/branch identity, and sharing identity. Renderer coordinates and list ordering are never identity inputs.

## CLI behavior

With `--json`, stdout contains one compact JSON object. Diagnostics go to stderr. `ok` exits 0, invalid input exits 2, unavailable capabilities exit 3, and internal failures exit 1.

`analyze` is always static and never imports the target project. `trace` requires an existing
architecture/source snapshot pair plus an explicit input spec, runs in a separate process, and
publishes `runtime-trace.json`, `runtime-evidence-ledger.json`, a node-evidence overlay, capability
report, and receipt. Runtime failure leaves the static bundle usable and emits failed/skipped gates
without claiming runtime-confirmed evidence.

## Pattern Pack behavior

Matching order is fixed: structural hard constraints, dataflow/ports, shape/axes,
sharing/control-flow, then weak names. A failed hard constraint sets the score to zero; weak names
cannot rescue it. Equal unresolved winners or conflicting builtin/workspace annotations produce
`ambiguous_pattern` and a generic overlay. Packs cannot create, delete, reconnect, or rewrite any
canonical execution fact.

Builtin manifests ship as package data. Workspace manifests are loaded only from an explicitly
named path with an exact digest lock; when a builtin also matches, a workspace manifest must have
more required hard predicates and must not conflict. A session candidate participates in review
only and never enters selection. Declarative JSON is the only third-party format accepted in this
stage; a colocated executable `matcher.py` is rejected.

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

## Structural registry and proposal boundary

The Stage 7 registry contains two deliberately narrow transforms:

- `replace_activation` replaces a zero-argument, directly registered `nn.GELU`, `nn.ReLU`, or
  `nn.SiLU` constructor without changing topology.
- `insert_layer_norm` inserts one directly registered `nn.LayerNorm` after a module output that has
  exactly one authored downstream consumer, then rewires only that consumer.

Every prepare and verify phase runs the transform-specific semantic oracle in addition to requiring
model-equal Expected and Observed Graph Delta. The delta includes canonical fact digests so a
different activation, extra edge, changed tensor, or other same-category mutation cannot pass by
matching only aggregate changed IDs.

Arbitrary connections, new branches, cross-attention, skip/loss paths, tensor-rank changes, merge
changes, complex control flow, and unknown multi-factory refactors are not transactions. Use
`archcanvas propose REQUEST --out agent-proposal.json --json`; the output is context for Agent
review and grants no execution or write authority.
