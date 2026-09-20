# ArchCanvas Product Truth

## Users

ArchCanvas serves researchers and ML engineers who need to understand, communicate, and make
safe changes to neural-network architecture implemented in a supported source project. They may
use code, a desktop canvas, or an agent workflow, but the result must be explainable in terms of
their source code and observed runtime evidence.

## Product Purpose

ArchCanvas recovers an Exact Architecture view from source, compiles a separate Publication view
for communication, and supports controlled visual or semantic edits. It makes a source change
only through a candidate diff, validation gates, explicit confirmation, atomic commit, and
re-analysis.

## Product Invariants

- User source is the semantic source of truth.
- Exact Architecture IR, Publication IR, and CanvasDocument have distinct ownership and are not
  serialized into one graph.
- Visual layout, annotation, and styling edits never modify user source.
- Runtime traces add evidence and shape information; they never replace source anchors.
- Unsupported, unresolved, or ambiguous code is reported as such. ArchCanvas does not fabricate
  a confirmed graph or a safe rewrite.
- The desktop, CLI, MCP, and Skill use the same engine policy for analysis, validation, history,
  and commit behavior.

## Supported Boundary

The first complete product target is PyTorch source recovery with documented static and runtime
capabilities, publication SVG export, persisted visual canvas edits, and registered safe model
parameter/structural edits. Keras and ONNX remain import-only future work. Arbitrary Python
metaprogramming, unrestricted dynamic control flow, training-pipeline visualization, and
automatic synthesis of arbitrary model code are outside the supported boundary unless a later
capability record explicitly adds them.
