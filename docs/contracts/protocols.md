# Protocol Contracts

All persisted documents use a `schema_version` with major/minor semantics. A reader must reject unknown major versions and may accept additive minor changes.

## Truth layers

1. `SourceSnapshot` freezes project root, entrypoint, task, execution mode, adapter version, configuration digest, and source file digests.
2. `EvidenceRecord` binds a claim to a source span or an explicitly identified non-source provenance kind.
3. `ArchitectureIR` stores canonical nodes, tensors, typed port-to-tensor edges, repeats, and unresolved facts.
4. `CanvasDocument` stores only visual patches and selection-independent view state.
5. `CommandReceipt` reports command status, output artifacts, gates, and structured diagnostics.

Canonical identifiers derive from source symbol, callsite, logical path, repeat/branch identity, and sharing identity. Renderer coordinates and list ordering are never identity inputs.

## CLI behavior

With `--json`, stdout contains one compact JSON object. Diagnostics go to stderr. `ok` exits 0, invalid input exits 2, unavailable capabilities exit 3, and internal failures exit 1.

