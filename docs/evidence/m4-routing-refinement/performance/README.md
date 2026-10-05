# Independent CPU and refinement-budget audit

This directory measures the formal public TypeScript core, not browser or human performance. Product source, tests and `studio/dist` were read only. No dependency was installed, no user model was imported or executed, and no whole suite or production build was run by this audit.

The final measured router is SHA256 `4b73eaadb7331759c67478b29659f86c7211499f9ea1536ca787522571f55a3c`. All 13 measured core source files are retained in `candidate-final-core` and bound by `candidate-final-manifest.json`. The original 13-file baseline, intermediate v1/v2 copies, raw timing logs and reports remain separate.

## Complete paths and fixed inputs

`baseline-manifest.json` freezes nine existing paper/180-mm CanvasDocuments: MLP levels 0–1, Residual CNN levels 0–2, Transformer levels 0–3, plus the source-backed stored DenseStress300 CanvasDocument. `density-inputs.json` adds artificial 16/64/256/1024-edge geometries. Each artificial source connects to every artificial target through a deliberately crowded lane; these are geometry stress cases, not model accuracy evidence. `wide-inputs.json` retains 64 crowded edges while adding 300/1000 unconnected, nonblocking nodes (317/1017 visible objects).

`benchmark.mjs` measures seven complete public paths per input: `buildScene`; interactive SVG serialization; scene plus SVG; once-per-gesture validation/snapshot preparation; prepared move preview plus SVG; guarded history commit plus scene/SVG; and detail export scene plus SVG. Native DOM, React, layout, paint and input timing are outside these CPU scopes. Every round checks the **entire** preview and committed Scene/SVG, input/history/source invariance and undo/redo layout. Moving offsets cycle through right/left/down/up, ±16 units. This is not a native browser gesture test.

The main baseline and final variant each have three fresh, sequential Node v24.19.0 processes on the same i5-13400F host. Each process uses five warm-ups and thirty recorded samples per input and phase; all samples, PID, start/end UTC, memory and initial/final load averages are retained. The table below is the median of three separately reported process p95 values, **not** a pooled percentile or an isolated-machine speedup. Processes were not paired/alternated, GC was not forced and host load was nonzero. Root deferred production builds/full suites during final timing; the local service remained available.

| Input | Scene + SVG before → final, ms | Prepared preview + SVG, ms | Guarded commit + Scene/SVG, ms |
| --- | ---: | ---: | ---: |
| Transformer L2 | 4.246 → 5.582 | 7.004 → 7.860 | 11.948 → 13.638 |
| Transformer L3 | 5.974 → 6.611 | 9.760 → 10.206 | 15.596 → 16.767 |
| DenseStress300 | 17.187 → 16.631 | 16.493 → 15.986 | 34.573 → 38.189 |
| Artificial 64 edges | 1.032 → 2.428 | 1.411 → 3.354 | 2.618 → 5.274 |
| Artificial 256 edges | 3.729 → 5.707 | 3.064 → 5.943 | 6.796 → 12.096 |
| Artificial 1024 edges | 12.812 → 13.850 | 15.738 → 14.860 | 33.197 → 29.315 |

The new refinement costs CPU. It adds about 0.4–1.2 ms on these Transformer L3 paths; crowded small graphs have larger relative costs, and stress commit remains expensive. Differences also include process/GC/host noise. `comparison.json` exposes every phase and each process p50/p95, and flags descriptive added costs above both 2 ms and 25%, including Transformer L0 commit and dense geometry paths. These flags are not silently turned into a performance pass. The initial v1 had L3 scene/SVG 9.895 ms and 64-edge scene/SVG 7.862 ms; feedback led to tighter budgets and an early reject for candidates already worse than the original protected counts. Those old results remain raw evidence.

The wide cases have **one** fresh process per variant and weaker timing scope: 317-node preview 7.057 → 10.124 ms and commit 14.249 → 18.567 ms; 1017-node preview 17.041 → 21.022 ms and commit 39.309 → 50.653 ms. They demonstrate finite additional work with a large coordinate inventory; they do not establish acceptable latency or inherit the main three-process scope.

## Independent counters and adversarial exits

`audit-budget-final.mjs` creates a separate trace copy. It only records references to the existing local budget object; traced **whole** Scene/batch results must equal the unmodified measured copy. Instrumentation is never included in timing. The final audit covers 180 named public paths: sixteen inputs × eleven scene/preparation/four-direction-preview/four-direction-commit/detail paths, plus four direct artificial API cases.

Added refinement gates are 1024 visible nodes, 512 routes and 4096 total route points. Work caps are 32768 broad-phase pairs, 150000 segment comparisons, 60000 obstacle checks, 384 global candidates, 80 candidates per processed route, eight processed routes and two passes. Recorded broad-phase, segment, obstacle, global candidate and processed-route counters stayed strictly at or below their caps. The per-route attempt and two-pass limits were checked directly in the frozen source; this trace does not separately count them. The four adversarial cases prove that 513 routes, 1025 nodes and more than 4096 points return ordinary obstacle routes before refinement, while a dense 512-route batch saturates the explicit broad-phase cap. Node/point gates also bound coordinate inventory and sorting; candidates are finite corridor alternatives, with no combinatorial path enumeration.

These are caps on **added batch refinement**. The ordinary obstacle router, document validation, hierarchy layout, SVG serialization and browser rendering still have their own costs. A capped or gated batch preserves ordinary routes and can retain crossings/overlaps; bounded work is not a promise to solve every layout or meet a frame target.

## Reproduce and inspect

Use the already configured Node runtime with `--experimental-strip-types` and pass `--core`, `--label`, `--output` to `benchmark.mjs`; run a new output filename for each fresh process. `benchmark-wide.mjs` uses the same seven paths against the separate two-input inventory. `audit-budget-final.mjs` requires `--core`, a fresh `--trace-core`, and `--output`; it refuses to overwrite the trace directory. `summarize.mjs` verifies frozen input/source/script bindings and generates `comparison.json` from the retained exact reports.

The final budget report is `candidate-final-budget-audit.json`. Timing reports are `baseline-process-{1,2,3}.json`, `candidate-final-process-{1,2,3}.json` and the separate wide reports. Their logs preserve literal command output. The final measured 13-file source copy matched live product core at the recorded `live-core-verification.json` point; a later product edit requires a new binding check or remeasurement.

**No browser performance, sustained presented FPS, native input-to-paint, INP, publication aesthetics or researcher task gate is certified here. M4 remains partial.**
