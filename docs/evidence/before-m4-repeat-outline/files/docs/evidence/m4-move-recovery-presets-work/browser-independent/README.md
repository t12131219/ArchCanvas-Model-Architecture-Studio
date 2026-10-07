# Independent audit of actual browser-authored preset models

The four saved browser drafts and their displayed generated Python passed an independent static audit. The cases are the session-2 MLP with the actual Input edit to `[2,16]`, the session-2 original CNN, the session-2 residual MLP, and the final `ChS0wIgb` compact CNN. The final CNN retains the complete default semantic network and appears in two forward rows in its actual saved/public SVG coordinates.

The audit ran with the formal `.venv` and source package paths, without importing `torch` or a model, executing generated source, installing dependencies, changing product files, rebuilding, or operating the browser. Root supplied the actual saved draft-store envelopes, visible source text and UI captures; this agent audited their saved bytes. It is an AI static evidence audit, not a human acceptance record.

| Check | Actual denominator | Result |
| --- | --- | --- |
| Saved frontend graph | 4 drafts, 27 nodes and 24 connections | Complete handwritten types, exact parameters, ordered ports and producer graph matched |
| Declared tensors | All 27 node declarations | Formal `validate_draft` agrees with independent hand-calculated shapes and float32 dtype |
| Visible generated Python | Every constructor, parameter, dtype, forward producer, ordered residual operand and named returned result in 4 sources | Full stdlib AST checks passed |
| AST sensitivity controls | 29 altered sources | All rejected as required |
| Actual source-derived IR | All 4 sources analyzed statically by the formal frontend | Exact observed nodes, port names/directions/ordinals/roles, all edges and fan-out tensor identities passed independent source/output-derived reconciliation |
| Source visibility chain | 3 original generated modal AX captures, 1 final public generated-source modal dialog | Exact source content matches after AX whitespace normalization; final source is an exact substring of the sole dialog text |
| Compact CNN saved/public geometry | 8 node identities/types/labels/positions, 7 edges and 14 canonical endpoints | Exact draft/public SVG agreement; relative coordinates are four columns of 224 units and two rows 180 units apart |
| Earlier oracle evidence | Original 106-file preset audit package | All original bytes and original manifest preserved and verified |

The edited MLP Input declares `[2,16]`; its downstream declarations are `[2,32]`, `[2,32]`, `[2,4]` and `[2,4]`. The generated `forward` receives one argument and preserves the exact 16→32→4 module widths. The Python source does not encode the Input batch-size declaration in a function signature; batch 2 is proved by the actual saved declaration and static shape deduction, not by a numerical forward call.

The compact CNN independently matches Input `[1,3,32,32]` → Conv2d `[1,8,32,32]` → ReLU → MaxPool2d `[1,8,16,16]` → AdaptiveAvgPool2d `[1,8,1,1]` → Flatten `[1,8]` → Linear `[1,4]` → Output `[1,4]`. Its coordinate change does not substitute a shorter or disconnected graph. The residual MLP's ordered Add left producer is the final main-path projection and right producer is the original Input.

## Relationship to the earlier root audit

`../browser-source-audit/check.py` validly checks three actual saved drafts against the previously handwritten graph/parameter contracts and complete AST oracle, with 22 negative controls. Its emitted shapes are independent hand calculations; that script did not compare them with a fresh backend validation receipt or analyze the actual source IR endpoints. This new audit adds those checks, the source visibility chain, input bytes locked before/after, and the fourth final compact CNN. The old three-case report remains a three-case report.

The observed IR node identities come from independently checked source expressions, Input symbols and named output paths. No generation-receipt `nodeBindings`, `portBindings` or verifier result supplies the oracle's expected mapping. Every constructor and forward statement is parsed; operation counts alone do not establish success. Negative-control outputs remain in each case audit.

## Evidence

- `attempt-1/audit-summary.json`: totals, exact scope, shape and source limitations, root check scope review and all input SHA256 bindings.
- `attempt-1/*-audit.json`: complete per-case handwritten tensor specs, AST/IR mapping, visibility checks and actual negative-control source text.
- `attempt-1/*-validation.json`: fresh formal static validation of the actual saved frontend graph.
- `attempt-1/*-actual-source-ir.json`: fresh static analysis of the exact browser-visible Python text.
- `attempt-1/input-snapshots/`: copies of every byte-bound input, including the original source-oracle files and UI evidence.
- `attempt-1/command-receipt.json` and `process-output.txt`: actual command, exit 0 and tool observation.
- `evidence-manifest.json`: binds this new audit package independently; it does not overwrite or rebind the earlier 106-file manifest.

The actual command, from the formal project root, was:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/evidence/m4-move-recovery-presets-work/browser-independent/check.py --output docs/evidence/m4-move-recovery-presets-work/browser-independent/attempt-1
```

Use a fresh output directory when reproducing. Files are written exclusively; no failed or earlier evidence is overwritten. This first new browser-independent attempt completed with exit 0 and had no failed graph/source checks.

This evidence does not certify model numerical results, memory allocation, training/evaluation, torch-version execution, native event latency, live browser/frame synchronization, pixel beauty, physical publication readability, research-user task completion, or M4 completion. The final public capture observes `/assets/index-ChS0wIgb.js`; bundle/source bindings belong to the root final-build evidence.
