# Stage 9 Acceptance: Cross-Framework and Release

## Delivered

- A unidirectional adapter registry and versioned support matrix; core IR does not depend on
  framework packages. The machine-readable matrix now has separate form rows for Keras subclass,
  Functional and custom layers; JAX pure, Flax and transformed/stateful forms; and ONNX standard,
  external-data and custom-domain graphs.
- Keras static recovery for subclassed `Model.call` and Functional builders, experimental
  layer-call runtime replay, config/registered/inline parameter updates, activation replacement,
  and subclass normalization insertion.
- JAX/Flax static recovery for pure functions and Module `__call__`, experimental JAXPR/eval-shape
  replay with params/state digests, config/Module-field updates, and bounded activation replacement.
- ONNX ModelProto recovery, ONNX Runtime provider replay, initializer/attribute updates, bounded
  activation-node replacement, and external-data initializer transactions.
- Canonical SVG plus self-contained HTML, PNG, and PDF. PNG/PDF are converted from the exact SVG
  bytes used by the interactive publication path, so there is no second layout implementation.
- Portable `.archcanvas` bundles containing redacted analysis, hierarchy JSON and collapsed/full publication
  formats, schemas, support matrix, verification receipt, and SHA-256 inventory.
- Codex and Claude Code installers sourced from the same `skill/` tree, plus a Linux/macOS/Windows
  CI configuration.

## Transaction and Runtime Evidence

All declared Keras/JAX/ONNX fixtures pass source identity, semantic closure, hierarchy/frontier publication, and
geometry. Runtime adapters execute two deterministic replays and emit normalized framework,
backend, target/provider, observation mechanism, output, parameter/state, and checkpoint fields.
Keras receipts also record backend/form/training mode, JAX receipts record PRNG/static-argument and
pytree fingerprints, and ONNX receipts bind provider/opset/instrumentation to the full ArtifactSet.
These non-PyTorch capability rows remain `partial`/`experimental` because the full framework-form
matrix required for an ArchCanvas 1.0 claim has not been completed.

Negative runtime gates now include unavailable ONNX providers and custom-domain operators without
a registered provider library. Both return failed receipts while the original ModelProto and static
analysis artifacts remain byte-identical.

Additional runtime fixtures cover Keras Functional multi-input/multi-output graphs with a shared
Layer, JAX `lax.scan`, and a pure JAX PRNGKey plus static argument. The unified input protocol now
accepts unsigned integer key tensors, and receipts preserve key/static-argument fingerprints.

Studio accepts arbitrary draft-node authorship only as a typed, blocked proposal. An unknown node
creates an `unproven` proof and a zero-permission `AgentProposal`; clients cannot promote their own
proof to `proven` or `review-ready`. A general staged multi-file source editor remains unavailable
because current snapshots do not inventory the complete transitive source set, so offering commit
would violate freshness and rollback guarantees.

ONNX external-data analysis inventories the ModelProto and every referenced data file as one
confined `ArtifactSet`. Prepare freezes every digest and works on an isolated copy. Verification
runs checker, shape inference, Exact IR reanalysis, Graph Delta, publication, and optional runtime
replay. Commit rejects a concurrent change to any member and restores all replaced members after a
write or post-commit validation failure. The verified lowering is a same-shape/same-byte-extent
initializer update. This is service-contract atomicity with rollback; it is not a claim that a
filesystem can atomically rename several independent files in one primitive.

PyTorch target reporting is environment-bound. The registry invokes an isolated probe and reports
`cuda` only when `torch.cuda.is_available()` is true; a CUDA-enabled wheel alone is insufficient.

## Host and Release Boundaries

- Codex local: verified in the current workflow.
- Claude Code local: installer-tested only. On 2026-09-24, neither `command -v claude` nor a bounded
  executable search found a Claude Code host, so trigger/non-trigger host execution is not claimed.
- Claude API and claude.ai: unsupported.
- Linux: locally verified. macOS and Windows: CI-configured, not locally verified.

Copy installs contain byte-identical `SKILL.md` files. The installed Codex launcher passes
`doctor` and produces an analysis artifact in an offline subprocess. Routing fixtures contain
balanced trigger and non-trigger cases, but fixture validation is not a substitute for the absent
Claude Code host eval.

## Remaining 1.0 Gap

This stage closes publication binary output, broad holdout coverage, accurate CUDA advertisement,
and ONNX external-data rollback. It does not promote the release beyond `0.1.0-stage9`: Keras,
JAX/Flax, and ONNX still need the complete per-form replay, Graph Delta, conflict, rollback, and
atomic-commit matrix required by the 1.0 definition, and Claude Code still needs a real host eval.
