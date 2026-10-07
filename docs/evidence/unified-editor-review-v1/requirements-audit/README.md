# Unified editor requirements audit (superseded v1 snapshot)

This record is historical. Later source-generation, generated-frontier and
browser checks use the [v2 audit](../../unified-editor-review-v2/requirements-audit/README.md).
The v1 routing after outputs were subsequently regenerated; their old receipt
does not bind the latest bytes. Use the separate v2 routing receipt for current
geometry claims. No M4 human or publication gate is promoted by either audit.

Generated 2026-10-07 after the current routing and collapsed-frontier fixes. This is a bounded code/test audit; it does not certify human usability, physical publication, model execution, or global routing optimality.

| Requirement | Result | Evidence |
| --- | --- | --- |
| Source → authoring continuity | **Bounded passed** | 9/9 focused Node tests; source rebase/save-reopen/digest rejection and collapsed-frontier generation covered |
| 74 atoms / 23 starting graphs | **Bounded passed** | Catalog readback 74/74 atomic and 23/23 preset receipts; Studio catalog tests 20/20; Python focused 18/18 |
| Infinite dot-grid canvas | **Bounded passed** | 3/3 focused tests |
| Atomic frontier / routing | **Bounded passed at recorded time** | 13/13 focused tests; recorded receipt has 41 before/41 after cases, 2 changed edge-pair comparisons, 0 new pair violations |

Current validation is tied to the working tree: the full Studio suite passes **523/523**, and `npm run build` passes with the existing Vite chunk-size warning. The focused Python bridge/catalog/group suite passes **18/18**. Catalog receipts are independently hash-verified and the live runtime catalog matches the 74-module, 13-category snapshot. All catalog and collapsed-frontier generation records declare `modelExecution: not_run`; static shapes and AST reanalysis are not numerical execution evidence.

The current UI keeps the execution boundary visible: generation is described as static checking, source-preserved drafts warn that numerical equivalence and execution were not verified, and export preflight reports dimensions and minimum text/line sizes while leaving font, line, and actual readability review open.

Open boundaries: human participants remain 0 and publication review is open by explicit authorization; complex custom source groups remain experimental; Transformer expanded frontiers retain distinct-tensor crossings and long mask/residual lanes in bounded cases; the 24-unit upward Attention move retains an explicit blocked/header-overlap diagnostic. These are reported diagnostics, not silently converted to pass.
