# ArchCanvas

ArchCanvas is a source-grounded model architecture studio. The current rewrite baseline provides the protocol boundary, a short agent skill, deterministic Python source discovery, an Exact Architecture IR, and structured validation receipts.

This repository is intentionally rebuilding from the source-truth boundary outward. The Studio
keeps visual patches separate from source truth and provides an explicit prepare, verify, review,
and commit flow for exact parameter edits and a small registry of bounded structural transforms.

## Quick start

```bash
python -m pip install -c .github/constraints-py311.txt -e .[dev,cross-framework,runtime-pytorch]
archcanvas doctor --json
archcanvas analyze \
  --project fixtures/tier_a/transformer \
  --entry model:Transformer \
  --framework pytorch \
  --task inference \
  --mode eval \
  --out build/transformer \
  --json
archcanvas validate build/transformer/architecture.json --json
archcanvas trace build/transformer/architecture.json \
  --input-spec fixtures/tier_a/transformer/runtime-input.json \
  --out build/transformer \
  --json
archcanvas render build/transformer/architecture.json \
  --view all \
  --out build/transformer/publication \
  --json
archcanvas studio build/transformer/architecture.json \
  --workspace build/transformer/.archcanvas \
  --serve \
  --json
```

For a hash-locked Linux CPython 3.11 core development environment, install
`pylock.dev-linux-py311.toml`, then add the separately constrained PyTorch runtime:

```bash
python -m pip install -r pylock.dev-linux-py311.toml
python -m pip install -c .github/constraints-py311.txt "torch>=2.2"
python -m pip check
```

The PEP 751 lock is intentionally platform-specific because binary wheels for LibCST, ONNX,
NumPy, and Cairo differ by platform. macOS and Windows development use the cross-platform direct
constraints above; CI resolves and tests the full dependency graph on all three operating systems.

Cross-framework static analysis and opt-in runtime tracing use the same pipeline:

```bash
archcanvas analyze --framework keras --project my-project --entry model:MyModel ...
archcanvas analyze --framework jax --project my-project --entry model:my_function ...
archcanvas analyze --framework onnx --project my-project --entry model.onnx ...
```

Keras and JAX adapters parse source without importing those frameworks. ONNX uses the optional
official parser declared by `.[cross-framework]`; no adapter executes the target during analysis.
Install only the runtime adapters you need with `.[runtime-keras]`, `.[runtime-jax]`,
`.[runtime-onnx]`, or use `.[runtime-all]` for CPU development. `trace` dispatches through the
framework registry and records framework/backend versions, device or provider, parameter/state
digests, observation mechanism, and two-run replay evidence.

Prepare and verify a semantic parameter transaction from a versioned request:

```bash
archcanvas patch prepare request.json --workspace build/transformer/.archcanvas --json
archcanvas patch verify build/transformer/.archcanvas/transactions/<transaction-id> --json
archcanvas patch commit build/transformer/.archcanvas/transactions/<transaction-id> --json
```

The same commands accept `SemanticStructuralPatch` requests for the registered
`replace_activation` and `insert_layer_norm` transforms. Unsupported structural intent is routed
to an `AgentProposal` instead of a source transaction:

```bash
archcanvas propose proposed-connection.json \
  --out build/transformer/agent-proposal.json \
  --json
```

`prepare` writes only to an isolated transaction copy. `verify` reparses, statically resolves local
imports, reanalyzes Exact IR, requires an exact Expected/Observed Graph Delta match, checks
shape/type invariants, runs the built-in compile check plus requested targeted tests, and recompiles
the arbitrary-depth containment hierarchy plus collapsed and fully expanded projections. Only a `review-ready` transaction can replace the exact source/config artifact or
managed ONNX artifact set under the rollback contract; stale revisions and concurrent changes to
any member are rejected without fuzzy merging.

`analyze` never imports the target project. It reads Python source, records file digests and source spans, and emits unresolved facts whenever the static subset cannot prove a claim.

`trace` is a separate, explicit opt-in boundary. It imports and executes the frozen entrypoint only
inside an isolated subprocess with a temporary working directory, timeout, CPU/memory limits,
network denial, and sandbox-only Python file writes. A seeded input spec is executed twice; only a
matching structural replay digest can pass the runtime replay gate. CPU is the default. Request
`"device": "cuda"` only when `doctor` and the runtime capability report confirm CUDA is available.
Use `selected_target` for an ONNX Execution Provider or an explicit JAX platform.

Use `--no-pattern-packs` to force source-only generic recovery. Unsupported control flow is
preserved as an `opaque_composite` with explicit boundary ports and unresolved status instead of
being filled with model-specific assumptions.

Pattern Packs run only after Exact IR is complete. Builtin packs are declarative manifests;
workspace packs require both an explicit `--pattern-workspace PATH` and
`--pattern-lock PACK_ID=SHA256`. Use `--pattern-candidate PATH` to produce a preview-only candidate
review. Candidates are never installed or activated, executable workspace matchers are rejected,
and every receipt records the unchanged Exact IR digest before and after matching. The semantic
overlay is consumed by publication and Studio as optional metadata without changing canonical
nodes, tensors, edges, or ports.

Install the same offline-capable skill package into either supported local host:

```bash
archcanvas install-skill --host codex --project /path/to/project --json
archcanvas install-skill --host claude-code --project /path/to/project --json
```

Copy mode includes the ArchCanvas runtime and schemas. It performs no dependency downloads; Python
3.11 and the dependencies reported by `doctor` must already exist. Create and verify a portable,
path-redacted review bundle with:

```bash
archcanvas bundle create build/model/architecture.json --out build/model.archcanvas --json
archcanvas bundle verify build/model.archcanvas --json
```

## Current support

| Capability | Status |
| --- | --- |
| Doctor and environment receipt | Available |
| Python entrypoint discovery | Available |
| Static module/call recovery | Generic fallback plus all five Tier A source profiles |
| Evidence ledger and Exact IR | Available |
| Semantic validation | Available |
| Arbitrary-depth publication hierarchy | Available; stable frontier projections follow tree expansion |
| Family and generic DAG layout | Available |
| Canonical SVG, PNG, PDF and self-contained HTML | Available; binary formats derive from the same SVG scene |
| Publication and geometry validation | Available |
| Interactive visual-only Studio | Available |
| Two navigation projections | Module/source trees share canonical selection; stable expansion directly derives the current frontier scene |
| CanvasDocument persistence and history | Available |
| Studio project discovery and analysis jobs | Static, generation-bound, cancellable |
| PatchBatch multi-select/alignment/layout history | Available; atomic validation and one-step undo/redo |
| Unified semantic search | Node, Tensor, Port, Edge, Evidence, Diagnostic |
| Active validation profiles | Fast static, publication, full; runtime requires explicit authorization |
| Draft intent proof status | Connection handoffs surface unproven/invalid blockers before writeback |
| Arbitrary draft nodes | Authored as blocked, zero-permission proposals until an adapter lowering is proven |
| Staged multi-file source editor | Unavailable until snapshots inventory transitive source files |
| ONNX external-data atomic commit | Same-size initializer updates with whole-set freshness and service-level rollback |
| Runtime tracing | PyTorch verified; Keras/JAX/ONNX adapters available with per-form status |
| Runtime shape/dtype evidence and replay | PyTorch hooks, Keras layer calls, JAXPR/eval-shape, ONNX graph outputs |
| Form-level capability matrix | Explicit Keras subclass/Functional/custom, JAX pure/Flax/transformed, ONNX standard/external/custom rows |
| Safe parameter transactions | Python config/literal/Functional/Flax field and ONNX initializer/attribute anchors |
| Structural transactions | PyTorch transforms; bounded Keras/JAX activation and Keras normalization; bounded ONNX node replacement |
| Proposed Connection and AgentProposal | Available; handoff grants no shell, network, or source-write permission |
| Declarative Pattern Packs | Builtin registry, digest-locked workspace packs, preview-only candidates |
| Holdout generalization | Seven source-only families pass semantic/publication/geometry gates without dedicated packs |
| Keras adapter | Partial: Functional/subclass static + runtime; parameter and two bounded structural lowerings |
| JAX adapter | Partial: pure function/Flax static + JAXPR runtime; config/field and bounded activation transactions |
| ONNX adapter | Partial: ModelProto static/runtime; initializer, attribute and bounded node transactions |
| Local skill installers | Codex verified; Claude Code filesystem installer tested |
| Offline review bundle | Redacted hierarchy plus collapsed/full JSON/SVG/PNG/PDF/HTML with digest verification |

See [PRODUCT.md](PRODUCT.md), [DESIGN.md](DESIGN.md),
[docs/contracts/protocols.md](docs/contracts/protocols.md), and
[docs/support-matrix.md](docs/support-matrix.md).
