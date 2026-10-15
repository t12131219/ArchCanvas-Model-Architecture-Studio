# VAE recursive layout browser comparison — 2026-10-14

The read-only inspection uses disposable Chromium contexts against the actual Studio at `http://127.0.0.1:8891/`. It captures the overview, a mixed frontier with `vae.forward` and `vae.encoder` expanded, full expansion after that mixed frontier, and direct full expansion in a fresh context. The final inspection additionally expands `vae.sampling`, `vae.sample_operands` and `vae.scaled_noise` to capture a deeper mixed frontier. Model Python source is neither imported nor executed. The original `prototype/Summary_Merge` remains unchanged.

## Final scoped browser inspection (frozen v18)

The native screenshots were inspected at full Studio scale and at one CSS pixel per graph unit. All five frontiers pass source/layout/non-draft edge checks with zero recorded contacts and zero unrelated wire overlaps. No browser runtime errors occurred. `final-v18/report.json` records the actual served preview and Studio bundle hashes; its 11-resource audit matches all eight other final v18 browser reports in `../preview-generalization-20261014/final-v18-browser-audit.json`. The separate final CPU comparisons report no worsening against v16 across 1,396 stages and nine metrics. Some bend reductions seen only in intermediate v17, affecting the historical MI-LSTM case and the current TransformerXL case, are not retained by v18's stricter guards; they are not new degradations against v16. This browser report remains scoped to its checked frontiers and commands.

| Stage | Nodes / edges | Total route length | Bends | Unrelated segment crossings |
| --- | ---: | ---: | ---: | ---: |
| Overview | 4 / 3 | 956.61 | 6 | 0 |
| Mixed encoder | 13 / 17 | 6,754.82 | 35 | 12 |
| Mixed scaled noise | 20 / 21 | 14,132.67 | 62 | 13 |
| Full after mixed | 28 / 24 | 18,480.18 | 54 | 11 |
| Full direct | 28 / 24 | 18,480.18 | 54 | 11 |
| Original detailed reference | 28 / 24 | 18,472.84 | 54 | 11 |

The mixed encoder length is **57.2% lower** than baseline. Gaussian helper placement now follows the active right-side source interfaces instead of forcing the compact overview's left-side anchor. The previously shifted posterior, sampling, encoder return, activation and linear siblings share center x=981; forward return, decoder and select-z share center x=983. The source-relative input glyph stays close to that axis (center x=1002). This removes the former 285 px shift caused by collapsing wide containers. V16 narrowed automatic content-axis alignment to cases justified by a collapsed wide container. V17 additionally requires a real producer rather than the frame's own entry proxy; the targeted PatchTST browser check confirms that its prior 2 px placement regression is removed.

The deepest 20-node transition completed in **916.59 ms** bridge round-trip, with no other CPU matrix running. The sequential individual frontier transitions took 203.93, 403.38, 540.45, 600.92 and 916.59 ms. Full expansion after mixed took 678.92 ms; fresh direct full expansion took 557.55 ms. These exclude subsequent fitting, graph snapshot, validation and screenshot work. The separate native 10-family suite measured 40 gestures at 150–884 ms; its individual timings appear in the generalization evidence. Those two groups are the clean latency scope; supplemental functional groups and targeted PatchTST/TimeMixer/LSTM inspections are functional and geometry evidence, not latency benchmarks.

Both full frontiers preserve every original detailed node rectangle exactly and have identical route geometry. All five stages preserve v17 node rectangles and aggregate route metrics; the deep mixed `route-0007-6` moves two intermediate terminal corners from y=976.5 to y=965 without changing length, bends, crossings or near-parallel diagnostics. Full bend count returns to the reference's 54, with only 7.34 units (0.04%) additional total route length. The two outside-root logvar return routes are present in the original reference; their 486 px exterior extent is retained.

The native closeups show separate long rails, clear right-angle turns and visible terminal arrows. The old extended lines separated by only 1 px and repeated tiny stair steps are absent in these checked mixed and full stages. Crossings remain: the deep mixed view has 13 unrelated segment crossings, while both original and final full views have 11. Two short near-parallel pairs remain in the deep mixed view:

- `route-0007-6` / `route-0008-7`: horizontal segments at y=991 / 988.6, separated by 2.4 px over 14 px.
- `route-0020-19` / `route-0024-23`: vertical segments at x=1457.5 / 1459.25, separated by 1.75 px over 30 px, close to recorded right-side container gates.

These short segments are documented rather than hidden by an exact-overlap-only check. No near-parallel pair below the diagnostic 8 px threshold remains in the overview, 13-node mixed or full frontiers. The cropped user image has no identifying labels, and CUA exposed no active browser surfaces to this verification worker, so these fresh-context screenshots cannot prove that the user's prior persisted frontier was the same one.

The final recursive engine hash is `5ae9a734ee521b31a7fb474df77c3c9e263d8dec390ac7c1dba69f0888fc6073`; router `56be06129595998c3d92f0d8bf0725ca3d5a6f62f674b0e89f9b68f440f3904d`; graph engine `5d71d3f68426d57f9b266d4459b367aff26d62335b1fc41b755aeda030524ee4`. The report is authoritative for all served resource hashes. The native Transformer supplemental and broader engine suites separately check source-aligned content axes and generic move/fork behavior.

## Historical frozen v17

`final-v17/` retains the previous scoped browser evidence and recursive hash `61a58bfbbd45246997b5c227428e61b7b575fcca60527e404710ecdb243530ea`. Its VAE geometry metrics and residual near-parallel pairs match v18. Its deepest clean bridge transition was 910.67 ms; the separate 40 native gestures ranged from 139 to 893 ms. V18 delays terminal follow-up until after existing shift/shorten passes and strengthens crowding guards. This removes the LSTM extra-bend regression while giving up some intermediate-v17 bend reductions affecting the historical MI-LSTM and current TransformerXL cases. V17 browser success alone was not final acceptance.

## Historical frozen v16

`final-v16/` retains five scoped browser frontiers with the same VAE geometry metrics and residual short near-parallel pairs as v17. Its recursive hash is `5439a0df9cd22f18ffe48cdc27a49f1eb814fad799d6bc08ff616bc0636f02dd`. Its deepest clean bridge transition was 917.32 ms and its separate 40 native gestures ranged from 146 to 909 ms. Broader model comparisons subsequently identified a PatchTST entry-proxy alignment regression and a TimeMixer fixed-slot crowding regression; v17 fixes those separately. Do not attribute v16 latency or hashes to v17.

## Historical frozen v15

`final-v15/` retains its scoped browser evidence and distinct product hashes. It measured mixed encoder length 6,713.82 / 31 bends and deep mixed length 14,115.92 / 60 bends. Broader quality comparisons found overly broad content-axis movement on other models, so v16 restricts that rule. The small additional VAE route length and bends are retained to protect generic placement and source-safe corridors. V15's browser pass alone was not final acceptance of its layout behavior.

## Historical frozen v14

`final-v14/` retains the earlier frozen run and its distinct engine hash. It passed the scoped browser checks, with mixed encoder length 6,754.82 / 35 bends and deep mixed length 14,132.67 / 62 bends. Full geometry and the two short near-parallel diagnostics match v18. This evidence is historical; its timing and product hashes belong to v14. V15 subsequently removed two additional deep bends, but broader placement regressions required the v16 and v17 restrictions above.

## Baseline (frozen v13)

`baseline/report.json` and the corresponding PNG, SVG and graph artifacts describe the actual served baseline. Runtime source, layout and non-draft edge validation passes at all four stages, with zero recorded node/container clearance contacts. Those legality checks do not imply that the routes are visually economical.

| Stage | Nodes / edges | Total route length | Bends | Unrelated segment crossings |
| --- | ---: | ---: | ---: | ---: |
| Overview | 4 / 3 | 956.61 | 6 | 0 |
| Mixed encoder | 13 / 17 | 15,770.54 | 37 | 16 |
| Full after mixed | 28 / 24 | 18,474.18 | 60 | 11 |
| Full direct | 28 / 24 | 18,474.18 | 60 | 11 |
| Original detailed reference | 28 / 24 | 18,472.84 | 54 | 11 |

The two full baseline frontiers preserve every original detailed node rectangle exactly and are independent of expansion order. The three additional two-bend detours are on `route-0006-5`, `route-0007-6` and `route-0024-23`. Other full external return routes already exist in the original reference.

The visibly poor mixed frontier has a different cause. A collapsed 900 px-wide child keeps its old left anchor when becoming 330 px wide, shifting its flow center by 285 px. Meanwhile the expanded encoder widens to 968 px, while surrounding siblings retain the compact view's left alignment. The Gaussian helper retains its overview position on the left, but detailed source interfaces require right-side gates. Two routes then wrap the main root, totaling 7,346.74 px (about 47% of the entire mixed frontier route length). The mixed screenshot and edge metrics capture this diagnosis.

The Gaussian helper's side differs across the original reference snapshots, so its left position alone is not a migration error:

| Original view | Main root x / y / w / h | Gaussian x / y / w / h | Gaussian side |
| --- | --- | --- | --- |
| Overview | 504 / 98 / 394 / 353 | 25 / 305.5 / 330 / 105 | Left |
| Modules | 504 / 98 / 458 / 783 | 25 / 709.5 / 330 / 105 | Left |
| Detailed | 504 / 98 / 1092 / 2659 | 1745 / 1635.5 / 330 / 105 | Right |

`outsideRootEdges` in the report measures routes whose endpoints share the same top-level owner. Cross-root Gaussian routes are intentionally excluded from that ownership-based metric; their bounds and excess lengths remain available in `edgeMetrics`. Segment-crossing counts exclude matching source-wire identities, and can include more than one crossing between the same edge pair. They are diagnostic, not a claim of universal crossing-free routing.

## Historical instrumented CPU diagnostic

`ccvae-encoder-search-profile-memo.json` is an instrumented CPU diagnostic from the v14 investigation, not final browser evidence. It records a legal 24-edge frontier in 5.00 seconds, compared with an earlier 19.08-second diagnostic whose load-time hashes were not captured. Use it to identify repeated gate search work; do not treat it as native browser latency or a fully provenance-bound before/after benchmark.

## Reproduction

```bash
node studio/scripts/inspect-preview-vae-layout.mjs --output-dir docs/evidence/preview-vae-layout-20261014/recheck
```

PNG files show the complete Studio with its preserved panels. JSON and SVG artifacts larger than 1 MiB are stored as deterministic gzip. Each run records hashes of the reference and actual served preview resources. Compare frontiers of equal expansion depth; the detailed reference does not directly represent the mixed frontier.

The final inspector records each expansion's same-origin bridge command round-trip separately from the native 10-family gesture timings. These command measurements exclude later fit, snapshot, validation and screenshot work, and should not be compared as the same latency metric.

Final stages also capture the actual native SVG scene at one CSS pixel per graph unit along the right boundaries of expanded encoder, posterior and sampling containers. The inspector temporarily adjusts only the SVG display `viewBox` within its disposable context, then restores it before further commands. It does not change the graph, native camera state, selection or history. These closeups allow visual assessment of dense rails even when exact geometric overlap is zero. The `nearParallelPairs` metric records unrelated orthogonal segments less than 8 graph units apart over a common span exceeding 10 units; it is diagnostic and does not automatically classify legitimate adjacent ports as defects.
