# Generalized preview final verification — 2026-10-14

The final acceptance uses frozen presentation version 18. The original Summary_Merge source remains read-only; every test runs the formal vendored engine. Model Python code is not imported or executed. Studio panels, source authority, reviewed authoring contracts, visual drafts and browser history remain distinct and connected through the existing bridge.

## Final checks

- Frontend targeted regression: **131 passed, 0 failed** (`frontend-targeted.log`). One Chromium DOM test was skipped by the sandbox, then the publication file passed **3 / 3** outside it (`frontend-publication-dom.log`), covering all **132 declared unique checks** without double-counting the two repeated tests. Source corpus identities, authoring projection, race/transaction guards, recursive routing, source wires, labels, manual knots, source spine and provisional move reservations are covered.
- Original prototype engine tests against only formal runtime: **67 / 67 actual TAP tests** (`engine-regression.json`). Source definitions contain 70 declarations, including inactive definitions; the count is not substituted for executed tests.
- Backend archive budget/inventory regression: **4 / 4** (`bundle-budget.log`).
- Build and integrity: 16 integration resources match the manifest, public tree, built dist and actual 8891 response. Main page assets match too (`build-integrity.json`).
- Native browser: 10 / 10 model families, 40 real expand/fold gestures. Every family covers nested reopen geometry, container movement, Apply layout and undo/redo. Portable state/load/recovery checks: 6 / 6; Transformer atomic transactions: 7; no-Worker fallback: 3. The additional standard/compact shared-trunk native gesture suite is recorded in `final-v18-shared-trunks/report.json`.
- The unified `final-v18-browser-audit.json` binds all nine browser groups to the same 11 actually served resource hashes, with zero browser errors. Targeted PatchTST placement/gates, TimeMixer terminal lanes and LayerNorm LSTM initial/fold return geometry are included; these supplemental checks are not latency measurements.
- Parent implementation and CPU projection evidence remain bound to their unchanged 13 implementation hashes (`parent-verification.json`); those CPU measurements do not stand in for browser latency.

## Clean native timing

All matrix and other CPU tests were held during `final-v18-cases` and the five-stage VAE inspection. Forty native gestures took **150–884 ms**. These include the action, settled snapshots and diagnostics; they are not isolated router CPU costs.

| Model | Native expand / nested / fold / reopen (ms) |
| --- | --- |
| UNet | 433, 463, 444, 459 |
| DenseNet | 635, 322, 310, 319 |
| Autoformer | 775, 884, 603, 612 |
| VAE | 749, 416, 263, 276 |
| Flow Sequential | 150, 339, 168, 176 |
| Graph Attention | 735, 878, 279, 290 |
| ResNet | 505, 499, 437, 429 |
| TCN Block | 481, 196, 153, 164 |
| MobileNetV3 | 539, 596, 579, 587 |
| WaveNet Block | 557, 329, 250, 282 |

VAE final native closeups and five-stage measurements are documented in `../preview-vae-layout-20261014/README.md`. They include equal-depth comparison, exact source node positions, full-direct versus mixed-first stability, and residual crossings/near-parallel approaches.

## Full catalog and mixed frontiers

The final standard matrix covers **229 cases / 916 stages**, including historical snapshots. All **114 / 114 current cases with registered graphs** pass. One current SVG-only case has no registered graph and is listed explicitly in the report. Historical cases pass **99 / 115**; the remaining 16 fail source/geometry constraints and remain rejected.

The mixed matrix covers **26 cases / 480 stages**, all passing. Nested targets are selected by hierarchy depth/branching rather than model names. Both matrices check source authority, node containment, every edge, headings, frame clearance, fold/reopen geometry and retained route identity. Their timings ran concurrently with functional validation and must not be presented as clean latency measurements.

`final/failure-classification.json` preserves all failing stage categories and violations. `historical-fixed-interface-conflicts.json` proves 10 historical cases / 26 independent fixed-terminal pairs from saved failure graphs; each pair requires a shared positive terminal ray under its original policies. Other historical cases contain invalid source/containment and sometimes separate wire overlaps. No evidence was rewritten to make these snapshots pass.

## Nonregression and provenance

Three quality comparisons pair identical source/catalog bytes and stage names across **1396 stages and nine measured metrics**. Against v16, v18 has **zero stages with any measured worsening**, with shorter paths in 24 stages and less close parallel length in 19. Against the earlier v14, **6 stages have a measured increase**, all reviewed: three ASPP stages add 87 px while removing four bends and two strict crossings; three TimeMixer stages add one strict crossing while independent contacts fall from 14 to 12 and T touches fall from three to zero. No new intersecting pair or increased crowding is introduced in those TimeMixer stages. Against v17, a historical MI-LSTM case and a current Transformer-XL case lose incidental early-pass improvements in four stages, and two active MI-LSTM stages have 28 px more close length but two fewer bends. All six remain no worse than v16. The complete per-stage figures are in `final/quality-comparison.json`, `final/v16-to-v18-quality-comparison.json` and `final/v17-to-v18-quality-comparison.json`.

There are **0 previously legal stages becoming invalid**. This legality result is separate from the visual cost comparisons; it does not establish universal visual optimality. Earlier v13–v17 matrices and failures remain in version-labelled archives. Final results never use older engine bytes as current proof.

The early v14 original-engine run exposed two real regressions despite successful browser and catalog checks: asymmetric frame padding displaced an aligned shared input, and provisional invalid peer routes blocked a norm move. Version 15 fixed those two regressions, but the expanded quality comparison then exposed overly broad content-axis alignment in other pipelines. Version 16 restricts the content axis to explicit shared-value boundary fanout with a source-aligned central terminal, and retains complete move transaction validation. The rule uses source evidence rather than model names or case IDs. New synthetic tests and native standard/compact Transformer gestures retain these failure modes as ongoing checks. A separate real optional-cleanup counterexample showed one new internal corner contact without changing strict crossing count; deduplicated geometric contacts now participate in the nonregression guard, while source-authorized sharing stays licensed. `t-contact-regression/` preserves the counterexample and its runtime bytes. Version 17 additionally excludes a container’s own input proxy from shared-axis authority, removing the PatchTST length-only regression without disabling genuine single-boundary fanout. A bounded terminal-band follow-up reuses neighboring fixed value slots and shares the same cleanup budgets. It accepts only less crowding with no increased contacts, strict crossings, length or bends and preserves ordered manual knots and exact gates. `spine-proxy-regression/` and `terminal-band-regression/` retain old failing examples, isolated runtime receipts and reflection/rotation tests. The complete v17 matrix exposed a cleanup-order regression in layer-normalized LSTM and a bend tradeoff in MI-LSTM. Version 18 finishes all existing lane shifting and shortening before the terminal follow-up. The follow-up additionally guards near-parallel run count, total length and minimum gap, and cannot consume the normal simplification budget before it finishes. Whole-pipeline failing and passing receipts are preserved under `terminal-band-regression/post-loop/`.

## Reproduction

Run these commands from the full source checkout, which supplies `studio/public/preview`, the test fixtures and development dependencies. The distributable bundle retains the reviewed reports and bounded historical isolation materials as evidence; it does not include the complete development checkout. In particular, the historical post-loop runner requires the checkout's public fixture tree and is not a standalone bundle command.

```bash
node studio/scripts/check-preview-frontiers.cjs --phase standard --include-historical --output docs/evidence/preview-generalization-20261014/recheck-standard
node studio/scripts/check-preview-frontiers.cjs --phase mixed --selection docs/evidence/preview-generalization-20261014/final-mixed-selection.json --output docs/evidence/preview-generalization-20261014/recheck-mixed
node studio/scripts/test-preview-generalization.mjs --phase final --cases "UNet,DenseNet,Autoformer,VAE,Flow Sequential,Graph Attention,ResNet,TCN Block,MobileNetV3,WaveNet Block" --output-dir docs/evidence/preview-generalization-20261014/recheck-browser
node studio/scripts/test-preview-expansion.mjs --phase final --shared-trunks-only --output-dir docs/evidence/preview-generalization-20261014/recheck-shared-trunks
python3 studio/scripts/test-preview-engine-regression.py --output-directory docs/evidence/preview-generalization-20261014/recheck-engine
```

`summary.json` records final report paths and hashes. Large graph/SVG artifacts are compressed deterministically; reports and screenshots remain directly readable.
