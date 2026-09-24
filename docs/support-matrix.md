# Release Support Matrix

This matrix describes verified behavior, not intended future coverage. `archcanvas doctor --json`
emits the machine-readable version with installed dependency versions.

## Frameworks

| Framework | Static Exact IR | Runtime evidence | Transactions | Status |
| --- | --- | --- | --- | --- |
| PyTorch | Module `forward`, generic recovery, five Tier A profiles | Verified opt-in hooks | Parameter plus registered structural transforms | Verified |
| Keras | Subclassed `call`, Functional builder dataflow | Experimental layer-call replay on the selected backend | Config, registered/inline layer parameters, activation replacement, subclass normalization insertion | Partial |
| JAX/Flax | Flax-style `__call__`, pure function dataflow, Module fields | Experimental JAXPR/eval-shape replay with params/state digest | Config, Module field, bounded Flax activation replacement | Partial |
| ONNX | ModelProto graph, initializer, attribute, symbolic shape and fan-out | Experimental ONNX Runtime replay per provider | Initializer, attribute and bounded node ModelProto transactions | Partial |

### Framework forms

| Form | Static | Runtime | Parameter | Structural | Commit |
| --- | --- | --- | --- | --- | --- |
| PyTorch `nn.Module.forward` | Verified | Verified on probed targets | Verified | Verified registered lowerings | Verified |
| Keras subclassed `Model.call` | Partial | Experimental | Partial | Partial | Verified |
| Keras Functional builder | Partial | Experimental | Partial | Partial | Verified |
| Keras custom/backend-specific Layer | Partial | Experimental | Unavailable | Unavailable | Unavailable |
| JAX pure function | Partial | Experimental | Partial | Unavailable | Verified |
| Flax Module | Partial | Experimental | Partial | Partial | Verified |
| JAX `jit/vmap/scan` or stateful form | Partial | Experimental | Unavailable | Unavailable | Unavailable |
| ONNX standard-domain graph | Verified | Experimental | Partial | Partial | Verified |
| ONNX external-data initializer | Verified | Experimental | Partial | Unavailable | Verified |
| ONNX custom-domain operator | Partial | Unavailable without provider | Unavailable | Unavailable | Unavailable |

Keras and JAX static analysis does not require or import their framework packages. Runtime adapters
are optional extras. Dynamic framework control flow and unproven parameter sharing remain
unresolved. PyTorch targets come from an isolated environment probe: installing a CUDA build does
not advertise `cuda` unless `torch.cuda.is_available()` succeeds. ONNX external-data initializer
updates freeze the complete artifact set, reject unconfined paths, replay from an isolated copy,
and restore all replaced members after a failed post-commit gate. This is service-contract
atomicity with rollback, not a claim of one filesystem-level multi-file rename.

Runtime receipts now preserve form-specific context: Keras backend/form/training mode, JAX PRNG,
static-argument and pytree fingerprints, and ONNX provider, opset, custom-domain, instrumentation,
and complete ArtifactSet identity. These fields are evidence for future promotion; they do not by
themselves change a partial or experimental status to verified.

## Studio expansion

| Capability | Status |
| --- | --- |
| Project picker and static discovery | Available; Python is parsed without import or execution |
| Generation-bound background analysis jobs | Available; current canvas swaps only after success |
| Ordered multi-select and batch movement | Available; one gesture is one undo/redo action |
| Alignment, distribution, deterministic constrained layout | Available for current scene nodes; pinned nodes are protected |
| Node/Tensor/Port/Edge/Evidence search | Available with facet queries and cross-view bindings |
| Validation profiles | Fast and publication available; full reports transaction gates; runtime remains explicit |
| Draft intent and proof overlay | Connection and arbitrary-node handoffs persist as blocked typed intents with reason codes |
| Arbitrary draft node lowering | Authoring/proposal available; writeback blocked until a framework adapter proves a lowering |
| Staged multi-file source editor | Unavailable; current snapshots do not yet inventory transitive source files |
| ONNX external-data commit | Available for same-size initializer updates; complete ArtifactSet freshness and rollback verified |

## Hosts

| Host | Status | Install target |
| --- | --- | --- |
| Codex local | Verified in the current local workflow | `.agents/skills/archcanvas` |
| Claude Code local | Filesystem installer and identical skill package tested | `.claude/skills/archcanvas` |
| Claude API | Unsupported; no verified self-contained dependency image | None |
| claude.ai | Unsupported; local skill installation does not synchronize | None |

## Platforms

Linux is verified locally. Ubuntu, macOS, and Windows are configured as the CI matrix for Python
3.11, cross-framework tests, schema freshness, compile checks, and the Studio production build.
macOS and Windows remain `ci-configured` until those jobs have produced successful release evidence.

All supported local workflows are offline by default. Copy-mode skill installation bundles the
ArchCanvas runtime and schemas but requires declared Python dependencies to be preinstalled.
