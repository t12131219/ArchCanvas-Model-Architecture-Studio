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

Keras and JAX static analysis does not require or import their framework packages. Runtime adapters
are optional extras. Dynamic framework control flow and unproven parameter sharing remain
unresolved. ONNX external-data mutation is rejected until multi-file atomic commit is verified.

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
