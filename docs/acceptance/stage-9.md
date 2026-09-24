# Stage 9 Acceptance: Cross-Framework and Release

## Delivered

- A unidirectional adapter package and versioned capability/support-matrix protocols. Core IR does
  not depend on framework packages.
- Static Keras adapters for subclassed `Model.call` and Functional builder dataflow. Tests run with
  no TensorFlow or Keras installation and do not import target source.
- Static JAX adapters for Flax-style `__call__` and pure function dataflow. Tests run with no JAX,
  Flax, or Haiku installation and preserve unproven runtime/sharing facts as limitations.
- An ONNX ModelProto adapter using the official optional parser, checker, and shape inference with
  external tensor loading disabled. The fixture covers input, initializer, operator flow, residual
  fan-out, symbolic shape, and graph output.
- Codex and Claude Code local installers from the same `skill/` source. Copy mode includes runtime
  packages and schemas without downloading dependencies; symlink mode supports repository
  development.
- Portable `.archcanvas` directory bundles containing redacted analysis records, L1-L4
  PublicationView/VisualSpec/VisualScene, SVG/HTML, schemas, support matrix, verification receipt,
  and a SHA-256 inventory bound to Exact IR.
- A three-OS CI matrix for Python 3.11, cross-framework tests, schema/compile checks, and the Vite
  production build.

## Verified Boundaries

All five cross-framework fixtures pass source identity, semantic closure, L1-L4 publication, and
geometry gates. Keras/JAX do not claim runtime support or source transactions. ONNX does not claim
runtime or editing. Non-PyTorch runtime and transaction requests are rejected.

Copy installs for Codex and Claude Code contain byte-identical `SKILL.md` files. The installed Codex
launcher passes `doctor` and produces an analysis artifact in a subprocess with an empty `PATH`,
demonstrating that artifact generation does not invoke network/package installers or repository
entrypoint scripts. Routing eval fixtures contain balanced trigger and non-trigger cases; actual
Claude Code host execution is not claimed because that host is absent from the test environment.

Bundle verification detects content modification and file-inventory changes. Copied JSON does not
contain the repository absolute path. Publication and geometry gates are recorded as passed, while
human visual review remains `not-included`.

## Honest Support Status

- Codex local: verified in the current workflow.
- Claude Code local: installer-tested; host execution unverified.
- Claude API and claude.ai: unsupported.
- Linux: locally verified.
- macOS and Windows: CI-configured, not yet claimed locally verified.
- PyTorch: full current static/runtime/transaction path.
- Keras and JAX: partial static source recovery only.
- ONNX: static graph recovery when the optional dependency is installed.

Final verification collects 123 tests: 120 pass and the same 3 Studio socket tests remain skipped
because the command sandbox denies local socket creation. Ruff, `compileall`, exported-schema
freshness, the Vite production build, and `git diff --check` pass. The real CLI smoke analyzes and
renders the ONNX residual fixture, creates and verifies a 63-file offline bundle, and installs the
same 109-file skill/runtime package into Codex and Claude Code project targets.
