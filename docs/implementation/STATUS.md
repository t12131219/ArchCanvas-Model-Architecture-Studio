# Implementation Status

## Current State

The repository is in Stage 2 static recovery. It contains strict Pydantic v2 models,
committed v1 schemas, schema drift tests, Source Identity, a Transformer fixture analyzer,
candidate-only LibCST `set_parameter` transform, ArchitectureDiffer, GraphDeltaValidator, and a
fixture-scoped CLI with atomic `--commit`. The current `TFB_py311` suite has passed 56 tests.

The fixture analyzer is intentionally narrow. It is evidence for the source -> identity -> IR
pipeline; it is not a general PyTorch static analyzer.

## In Progress

- Stage 2 static foundation: a conservative AST scanner and strict PyTorch adapter recover the
  Transformer, ResNet residual, and concat fixtures' module topology into Source Identity and
  Architecture IR. Constructor parameters retain literal, argument, constant, config-attribute,
  or unresolved-computed provenance with source anchors; `ModuleList(range(...))` produces a
  repeat record; identity refresh records new, exact, or ambiguous reconciliation outcomes.
- Stage 2 fixture corpus: committed Source Identity and Exact IR goldens cover Transformer and
  ResNet and are checked deterministically by `python tools/generate_static_goldens.py`.
- Stage 2 project discovery: a bounded, read-only project scanner finds `nn.Module` candidates
  without importing user code, skips unsafe/oversized files, and emits machine-readable issues.
  Direct `from torch.nn import Linear, Module` imports are resolved alongside `torch.nn` aliases.
- Stage 2 local symbols: selected entrypoints can resolve direct local imports to discovered
  `nn.Module` classes without executing source. A branch-free direct constructor call becomes one
  local-module node with both a call-site and target-class declaration anchor, and records both
  revisions; it does not flatten the imported implementation. Constructor control flow fails
  closed, and direct-call or literal `OrderedDict` `Sequential` expressions, plus literal
  `ModuleList` expressions, materialize each member in source order. `ModuleList(range(...))`
  remains a conservative repeat record; dynamic members are unresolved.
- Stage 2 transitive evidence: bounded traversal of confirmed direct local calls records nested
  call-site/class declaration anchors and file revisions in metadata, with `expanded`,
  `depth_limit`, `duplicate`, or `cycle` traversal status. It deliberately does not flatten target
  implementations into root IR nodes or edges.
- Stage 2 remaining work: transitive cross-file topology, dynamic/non-literal container members,
  common functional-op records, broader container/branch corpus, and an
  ambiguity-to-transaction policy before this stage can be declared complete.
- T-01 engineering maturity foundation: project routing rules, acceptance taxonomy, interface
  reservations, and an eventual user-facing Skill contract.

## Not Started

- General PyTorch project static recovery and broader compatibility corpus (Stage 2).
- Isolated runtime evidence and shape validation (Stage 3).
- Publication compiler, VisualScene, SVG renderer (Stage 4).
- Engine RPC, cache/history, desktop shell/canvas, parameter UI, structural edits, MCP,
  packaging, and release matrix (Stages 5-10).

## Next Entry Criteria

The next implementation task should extend only an explicitly bounded static subset, beginning
with transitive local-call evidence or additional container forms. It must preserve the current
fail-closed rule: a conditionally constructed local module, including PatchTST's backbone path,
cannot appear as confirmed topology.
