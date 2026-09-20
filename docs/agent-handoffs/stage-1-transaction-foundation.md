# Stage 1 Transaction Foundation

## Scope Completed

- Added a candidate-first transaction service for the existing Transformer fixture analyzer.
- Validated the before documents, source/IR semantics, transform preconditions, one textual
  diff hunk, candidate LibCST syntax, after-analysis semantics, and expected Graph Delta.
- Added an atomic `--commit` implementation with a final source revision check, sibling
  temporary file, file fsync, replace, and best-effort parent-directory fsync.
- Exposed the fixture-only workflow as `archcanvas-fixture-transaction`.

## Evidence

```bash
conda run -n TFB_py311 python -m pytest
conda run -n TFB_py311 python -m compileall -q src tools tests
conda run -n TFB_py311 python tools/export_schemas.py
```

Result: 23 tests passed. The installed console script was exercised against a temporary copy of
the Transformer fixture: default execution returned a non-blocking candidate and left bytes
unchanged; `--commit` changed only `nhead=8` to `nhead=16`.

## Protocols Consumed And Produced

- Consumed: `source-identity:1.0`, `architecture-ir:1.0`, `patch-protocol:1.0`.
- Produced: candidate diff, refreshed Source Identity and Architecture IR, observed Graph Delta,
  and `graph_delta_v1` validation report.

## Known Limitations

- The CLI is intentionally limited to `transformer_set_parameter_v1`; it must not be presented
  as a general PyTorch code editor.
- A general PyTorch analyzer has not been implemented; the explicit registry rejects every
  project that has not registered an adapter.

## Next Entry Criteria

The next task may begin Stage 2 PyTorch static recovery. It must preserve the candidate-first
transaction and use `TFB_py311` for validation.
