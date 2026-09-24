# Release Support Matrix

This matrix describes verified behavior, not intended future coverage. `archcanvas doctor --json`
emits the machine-readable version with installed dependency versions.

## Frameworks

| Framework | Static Exact IR | Runtime evidence | Source transactions | Status |
| --- | --- | --- | --- | --- |
| PyTorch | Module `forward`, generic recovery, five Tier A profiles | Verified opt-in hooks | Parameter plus registered structural transforms | Supported |
| Keras | Subclassed `call`, Functional builder dataflow | No | No | Partial |
| JAX/Flax | Flax-style `__call__`, pure function dataflow | No | No | Partial |
| ONNX | ModelProto graph, initializer, symbolic shape and fan-out | No | No | Supported when optional `onnx` dependency is installed |

Keras and JAX analysis does not require or import their framework packages. Dynamic framework
control flow and unproven parameter sharing remain unresolved.

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
