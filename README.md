# ArchCanvas

ArchCanvas is a source-grounded model architecture studio. The current rewrite baseline provides the protocol boundary, a short agent skill, deterministic Python source discovery, an Exact Architecture IR, and structured validation receipts.

This repository is intentionally rebuilding from the source-truth boundary outward. The Studio
keeps visual patches separate from source truth and provides an explicit prepare, verify, review,
and commit flow for exact parameter edits and a small registry of bounded structural transforms.

## Quick start

```bash
python -m pip install -e .[dev]
archcanvas doctor --json
archcanvas analyze \
  --project fixtures/tier_a/transformer \
  --entry model:Transformer \
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
L1-L4 scenes. Only a `review-ready` transaction can atomically replace the exact source/config file;
stale revisions and concurrent modifications are rejected without fuzzy merging.

`analyze` never imports the target project. It reads Python source, records file digests and source spans, and emits unresolved facts whenever the static subset cannot prove a claim.

`trace` is a separate, explicit opt-in boundary. It imports and executes the frozen entrypoint only
inside an isolated subprocess with a temporary working directory, timeout, CPU/memory limits,
network denial, and sandbox-only Python file writes. A seeded input spec is executed twice; only a
matching structural replay digest can pass the runtime replay gate. CPU is the default. Request
`"device": "cuda"` only when `doctor` and the runtime capability report confirm CUDA is available.

Use `--no-pattern-packs` to force source-only generic recovery. Unsupported control flow is
preserved as an `opaque_composite` with explicit boundary ports and unresolved status instead of
being filled with model-specific assumptions.

## Current support

| Capability | Status |
| --- | --- |
| Doctor and environment receipt | Available |
| Python entrypoint discovery | Available |
| Static module/call recovery | Generic fallback plus all five Tier A source profiles |
| Evidence ledger and Exact IR | Available |
| Semantic validation | Available |
| L1-L4 publication compiler | Available |
| Family and generic DAG layout | Available |
| Canonical SVG and self-contained HTML | Available |
| Publication and geometry validation | Available |
| Interactive visual-only Studio | Available |
| CanvasDocument persistence and history | Available |
| Runtime tracing | Available for PyTorch, explicit opt-in only |
| Runtime shape/dtype evidence and replay | Available at module boundaries |
| Safe parameter source transactions | Available for exact config and Python literal anchors |
| Structural source transactions | Activation replacement and sequential LayerNorm insertion |
| Proposed Connection and AgentProposal | Available; handoff grants no shell, network, or source-write permission |

See [PRODUCT.md](PRODUCT.md), [DESIGN.md](DESIGN.md), and [docs/contracts/protocols.md](docs/contracts/protocols.md).
