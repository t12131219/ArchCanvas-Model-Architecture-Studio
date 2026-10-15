# TimeMixer fixed collector: frozen v18 browser check

This is the detailed-only case `b4e7f02ce4dce8d4`, not the separate TimeMixer overview preset `39ca17212a8004c5`. A disposable Chromium context reaches exactly `['tm.model', 'tm.pdm', 'tm.pdm1', 'tm.pdm1.mix', 'tm.pdm1.season']` with no folded overrides. Model Python is not imported or executed. These supplemental runs are functional and geometry evidence, not clean latency measurements.

Both captured stages pass source/layout/non-draft edge validation, have zero recorded routing clearance contacts and zero exact unrelated overlaps, and retain the same recursive source-authority hash. No browser runtime errors occurred. All 11 served resource hashes match the other frozen v18 browser reports; see `../final-v18-browser-audit.json`. Runtime clearance contacts and the broader matrix's segment-nearness/crowding diagnostics are different metrics and must not be conflated.

The targeted collector routes have these final native coordinates and metrics:

| Route | Length | Bends | Target y |
| --- | ---: | ---: | ---: |
| `route-0213-212` | 376.5 | 2 | 1503.24 |
| `route-0214-213` | 248.5 | 4 | 1515.24 |

The native 1:1 target screenshots were inspected: the fixed collector arrows are visibly separate, with their target slots 12 graph units apart. The final frontier has 29 nodes, 45 edges, total route length 13,545.46, 43 bends and 12 unrelated segment crossings.

One other long near-parallel pair remains: `route-0200-199` / `route-0201-200`, vertical separation 1 graph unit over a common span of 287.5. This is recorded by the inspector's diagnostic threshold of separation below 8 and span above 10; the targeted pass is not a claim that all TimeMixer near-lines or crossings were eliminated. The broader matrix separately compares the fixed-slot crowding regression with the baseline.

```bash
node studio/scripts/inspect-preview-vae-layout.mjs --case b4e7f02ce4dce8d4 --steps tm.model,tm.pdm,tm.pdm1,tm.pdm1.mix,tm.pdm1.season --closeups tm.pdm1.mix,tm.pdm1.season --edge-closeups route-0213-212,route-0214-213 --output-dir docs/evidence/preview-generalization-20261014/recheck-timemixer
```
