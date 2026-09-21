# Stage 2 Exit Validation

## Decision

**Stage 2 is complete for the declared PyTorch static subset.** This decision applies only to
conservative source recovery and its strict fixture contract. It does not start Stage 3, Stage 4,
or any source-writing workflow.

## Delivered Static Subset

- The bounded project scanner, direct import resolver and symbol table discover selected
  `nn.Module` entrypoints without importing or executing inspected code.
- Constructor recovery supports direct module assignment, literal `Sequential` (including literal
  `OrderedDict`) and literal `ModuleList` members, plus bounded `ModuleList(range(...))` repeats.
- Forward recovery supports ordered calls, literal-container iteration, residual addition,
  `torch.cat`/`torch.stack`, and source-anchored functional calls in the declared whitelist:
  `torch.relu`, `torch.sigmoid`, `torch.tanh`, and `torch.nn.functional.relu`, `gelu`, `silu`,
  `dropout`, and `layer_norm`.
- Source Identity records constructor, parameter and forward-functional anchors. Architecture IR
  carries matching identities, confirmed data/residual edges, explicit unresolved facts and the
  machine-readable capability report.
- Direct branch-free local custom-module calls have both call-site and target-class anchors.
  Bounded transitive local-call records are declaration evidence only, not flattened topology.

## Exit Gates

| Gate | Evidence | Result |
| --- | --- | --- |
| Transformer topology and parameter provenance | committed static fixture/golden tests | pass |
| ResNet topology and residual edge | committed static fixture tests | pass |
| Source-backed anchors and blank-line identity reconciliation | adapter semantic-validation tests | pass |
| `Sequential` and `ModuleList` completeness | direct, named and literal-container regression tests | pass |
| Dynamic constructor/forward paths fail closed | conditional constructor/local-call and forward tests | pass |
| Common functional operations | source-anchor, alias, repeated-assignment and unresolved-input tests | pass |
| Project scan/import/symbol evidence | selected-entrypoint and local-call project tests | pass |

## Validation Run

Executed in `TFB_py311` on 2026-09-21:

```bash
conda run -n TFB_py311 python -m pytest -q
conda run -n TFB_py311 python -m ruff check src/archcanvas_pytorch/static tools/validate_pytorch_static_cases.py
conda run -n TFB_py311 python -m compileall -q src tools tests
conda run -n TFB_py311 python tools/generate_static_goldens.py
conda run -n TFB_py311 python tools/export_schemas.py
git diff --check
```

All commands passed; the test suite result was `60 passed`.

## Article A1 Observations

The following reports used byte reads and AST parsing only. No Article source was imported,
executed, installed, or modified.

- `stage-2-article-patchtst-observation.json`: `models/PatchTST.py:Model`, 64 scanned Python
  files and 120 candidate entrypoints. Conditional construction and forward remain unresolved.
- `stage-2-article-itransformer-observation.json`: `model/iTransformer.py:Model`, 27 scanned
  Python files and 28 candidate entrypoints. It records five direct local bindings and its
  unresolved configuration/dynamic facts.
- `stage-2-article-time-series-library-observation.json`: `models/DLinear.py:Model` and
  `models/iTransformer.py:Model`, 85 scanned Python files and 178 candidate entrypoints.

Each is an A1 capability-boundary observation, not an A0 provenance approval or A2 Exact IR
acceptance. The reports remain explicit that Stage 2 does not provide runtime tracing, publication
visualization, canvas editing or source mutation.

## Remaining Boundaries

- Arbitrary Python control flow, dynamic containers, arbitrary functional calls and recursive
  cross-file topology remain unresolved or excluded.
- Runtime shapes/traces, publication visualization and candidate source transactions belong to
  later planned stages and are not implemented by this exit decision.
