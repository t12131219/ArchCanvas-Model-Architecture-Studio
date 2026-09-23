# V3 Stages 1-8 Local Audit

This record separates locally verified implementation from V3 acceptance. It is not a
stage validation report and does not authorize a formal exit from Stages 4, 6, 7 or 8.

| Stage | Local evidence and current limit |
| --- | --- |
| 1 Protocol | Schema drift, literal candidate/commit and negative-path tests pass. No V3 change to the source-write contract. |
| 2 Static | Bounded PyTorch recovery and fixture goldens pass. Dynamic or ambiguous topology stays unresolved. |
| 3 Runtime | Isolated trace and shape-gate tests pass; runtime cannot replace source anchors. |
| 4 Publication | Strict VisualSpec v1, schema, ports, relative constraints and fixture goldens exist. The separate read-only Tier A samples now select five archived configurations and generate source-hash/line checked module, partial tensor, edge, evidence and discrepancy ledgers. Autoformer query/key/value projections are separate source-backed canonical nodes instead of one ambiguous Q/K/V box. Their topology is not yet compiled from Exact/Publication IR into the shared VisualSpec/VisualScene, and the sample still lacks separate canonical tensor/operator objects and complete axes/dtype/runtime proof. The generic compiler therefore still correctly rejects unsupported full-detail claims. Reviewed five-model goldens remain absent. |
| 5 Engine | Approved-root lifecycle, cache and typed RPC tests pass. VisualSpec is cached alongside the scene; rollback restores the prior cache snapshot. |
| 6 Desktop | Native Tauri E2E checks existing Engine workflows. A read-only Tier A source-map view offers inline L1-L4 disclosure and direct-full/export from the same sample graph, with browser coverage for all five models and Transformer identity/port invariants. The sample renderer now distinguishes tensor matrices, projection operator-to-tensor units, merge circles, condition diamonds, repeat stacks, axis transforms, patch windows, scale pyramids and evidence-supported decomposition forks. Q/K/V use same-rank layouts and named paths; residual Add/Norm and cross-attention K/V memory routes remain attached to canonical ports. Export freezes `rect`, `circle`, `path` and text styling from the same SVG scene, while browser checks cover glyph identity, non-serial Q/K/V, label overflow and merge-label collision. Local disclosure is keyed by archive hash in browser storage and survives reload, but is not persisted as a CanvasDocument or backed by the generic Engine VisualScene. Approved configs, 147 human reviews and hosted Ubuntu CI remain outstanding. |
| 7 Parameter edit | Tauri now keeps one Engine session across RPCs and never replays a failed request. Restart still discards candidate/confirmation. The default sidecar registers no project-specific patch analyzer or runtime profile, so a real project remains read-only until explicitly approved and configured. Formal exit depends on Stage 6 acceptance. |
| 8 Structural | Restricted LayerNorm insert/remove plans require unique source-proven data edges, exclusive inverse splice and exact declared 1-to-2/2-to-1 graph deltas. Runtime/shape gating and fixture round trips pass. Generic module removal, arbitrary rewire and residual editing remain unsupported; formal entry/exit depend on Stage 7. |

## Unresolved Decisions And External Evidence

The user confirmed Autoformer-main, iTransformer, PatchTST, TimeMixer-main and Transformer
as the five model instances for this acceptance scope on 2026-09-22. The confirmation
is recorded with archive hashes in `fixtures/tier_a_v1/acceptance-scope.json`; it does
not approve a task branch, entrypoint or numeric configuration.

- Review the implementation-selected config snapshots in `fixtures/tier_a_v1/` and
  explicitly approve or replace their parameter, task and branch selections. Archive/file
  SHA-256 and source spans are reproducible; those selections remain pending review.
  T2T remains a second reference, not a mapped Transformer execution profile.
- Review image/source discrepancies and 147 Publication checklists with a named
  reviewer. Machine-generated evidence cannot substitute for those decisions.
- Run the first hosted Ubuntu CI and attach its run reference. Local native results
  are implementation evidence only.
- Promote the reviewed sample topology into the generic Exact/Publication IR ->
  VisualSpec -> VisualScene chain; add separate canonical tensor and operator ledgers,
  complete dtype/axes and runtime shape checks, and prove conditional/parameter-share
  and per-edge execution relationships. E3 route-inferred edges remain identified in
  evidence metadata but are no longer given a misleading dotted "non-data" appearance.
- Add persistent/undoable per-module expansion in CanvasDocument, generic direct-full
  Engine RPC and deterministic scene/SVG goldens from the shared renderer.

## Local Verification

`pytest`, `ruff`, `compileall`, schema drift, static/publication golden verification,
`cargo test`, `cargo fmt --check`, desktop build/lint/tokens, Playwright visual tests
and native WebKitDriver E2E are the applicable local commands. Their exact results
must be rerun on the final worktree before using this record as an implementation
checkpoint; none establishes a hosted or human acceptance gate.

The new source-map tests compare generated JSON byte-for-byte against archive-backed
reconstruction, verify every source span and source/reference image hash, keep canonical
IDs stable across L1/direct-full, and verify SVG export/port identity. The focused Tier A
Python test and twelve browser tests pass locally after the V7 glyph change. The remaining
full verification matrix must still be rerun on the final worktree; local success does not
resolve the external gates above.
