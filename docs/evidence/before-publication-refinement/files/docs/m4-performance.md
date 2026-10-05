# M4 Studio performance probe

Current build scope (2026-10-05 Asia/Shanghai): `index-DWpF-img.js` / `index-DK5lov-h.css` adds the explicit hand tool, synchronous terminal pan camera update and annotation placement controls. Studio68/68, strict TypeScript/build and the [standalone formal-copy check](evidence/m4-pan-annotation-work/independence.txt) pass. Four trusted hand-tool drags in [two v2 sessions](m4-input-observation.md) have exact terminal deltas (+80/+48, +32/+20, +24/+16, +20/+12) and unchanged public SVG/frontier/pins. Their matched discrete subsets have p95 2008/2024 ms; continuous inputs remain DOM proxies. The observer/independent validator have [32/32 detailed counterexample results](evidence/m4-pan-annotation-work/observer-tests-expanded.txt), separate from Studio68 tests. These sessions certify neither sustained presented FPS nor the performance target.

The old zoom-full39 matrix and zoom-final five-slot trial package are historical/stale for this build. Their original bytes are preserved in [before-pan-annotation-build](evidence/before-pan-annotation-build/manifest.json). The [current full matrix](evidence/browser-visual-matrix-pan-annotation-full/manifest.json) has 36/36 baselines plus one edited case per model,39cases/234artifact files (complete artifacts, human review pending/false); its spec and a [fresh five-slot package](evidence/research-trial/pan-annotation-build/preparation-verification.json) have been prepared (ports8881–8885, zero assignments/collections/researchers). Current coverage and human outcomes cannot inherit the old version. Fixed hardware/resolved fonts, continuous presented paint and actual researcher/publication gates remain open. 

The full matrix does not add a performance measurement. Three edited-note chains include text undo/redo and saved/reopened SVG equality, with a changed camera and fresh session history. Later preset/width edits and Save/export produce final revisions54/22/39, not immediate reload snapshots. A stale-export-copy correction uses unique full Canvas/formatSVG matches to actual server files; original screenshots/times/DOM are unchanged and it is not a browser recapture. An [independent field audit](evidence/browser-visual-pixel-observation-pan-annotation-full/field-audit.json) rebuilds all39Canvas/DOM/publication SVG and checks234files. The [AI pixel report](evidence/browser-visual-pixel-observation-pan-annotation-full/pixel-review.md) records visible page headers/full paper/legends, with dense fit text unreadable. TransformerL3 at85mm has minText2.53093pt/nodeLabel3.29021pt; the earlier rev23 representative≈2.896pt is separate. The CNN note splits the English word across lines as “skip p / ath.”, a recorded readability defect. Neither consistency nor AI pixel checks certify publication or resolved fonts.

The older measurements below retain their own build scope.

Studio exposes a local performance sampler only at `?benchmark=1`. The visible
“运行 20 组性能采样” button runs one warm-up pair and 20 measured expansion /
collapse pairs against the first collapsed, visible non-root container, then
fits the canvas. Every trial records the target's canonical ID and before /
after visible node counts. The scenario restores its starting frontier.
It uses ordinary visual operations, so its warm-up and trials increment the
canvas revision and appear in undo history. The source/IR binding is read from
the rendered SVG metadata and remains the same. Use a fixture canvas when
collecting acceptance evidence.

The latency metric is explicitly a **two-animation-frame paint proxy** from
the typed visual-operation handler entry, so it excludes the browser's initial
event queue delay. The scenario's tree clicks are synthetic DOM clicks;
they are not real pointer Event Timing samples. Native browser Event Timing
entries are collected separately (minimum browser threshold 16 ms), together
with support flags, and are never merged into the proxy percentile.

Before warm-up, a separate two-second idle frame baseline and its visibility
trajectory are captured without any canvas operation. Synchronous visual
handler duration is recorded separately from the two-frame proxy; it includes
typed document/history work and scheduling state, but excludes React rendering
after the handler returns and the browser event queue before it starts.

While the frontier toggles, the probe samples frames for two seconds and records
fps, p95/max frame interval and intervals above 50 ms. When implemented by the
browser, PerformanceObserver records long tasks; an unsupported observer
reports `maxLongTaskMs: null`, rather than implying zero long tasks. The probe
buffers are bounded (200 interactions/events/long tasks, 20 frame samples).

To reproduce with the formal server running:

1. Open `http://127.0.0.1:8765/?benchmark=1` in the actual target browser.
2. Load a fixture, expand its root, and retain a collapsed child container.
3. Click “运行 20 组性能采样” and wait for the completed state.
4. Read the “性能采样 JSON” readonly textarea or download its JSON receipt.
5. Save it as `docs/evidence/m4-studio-performance.json` and validate it:

```bash
python -m json.tool docs/evidence/m4-studio-performance.json >/dev/null
node scripts/validate_studio_performance.mjs docs/evidence/m4-studio-performance.json
```

The receipt binds viewport, device-pixel ratio, browser user agent, URL, target,
canonical visible nodes and measured trials. The measured phase also binds
`document.visibilityState`, focus at its start/end, and any visibility-change
trajectory; browsers may throttle animation frames when a tab is hidden. Its result is limited to that
model/frontier/browser/device session. The 300-layer workload has a separate
failed performance receipt, not a passing certification. The three-researcher
task gate also remains open. A browser automation run
is engineering evidence, not a human research participant.

The independent probe coverage is in `studio/tests/perf.test.ts`; `npm test`
and `npm run build` must pass before accepting a browser receipt.

## Recorded sessions

The 2026-10-04 Chromium 154 Linux sessions target Residual CNN's canonical
`repeat:instance:model.ResidualCNN.blocks` container. Every pair changes the
visible frontier from 8 to 10 nodes and back to 8. The receipts retain all 40
trial durations; the independent validator recomputes percentiles, checks
source/IR/document binding and checks the restored canonical frontier.

| Session | Viewport / DPR | Expand proxy p95 | Collapse proxy p95 | FPS | Frame p95 | Intervals > 50 ms |
|---|---|---:|---:|---:|---:|---:|
| Full Python suite competing for CPU | 1102 × 835 / 1 | 126.5 ms | 107.1 ms | 28.07 | 83.4 ms | 11 |
| Earlier session without visibility instrumentation | 1102 × 905 / 1 | 992.4 ms | 992.5 ms | 2.49 | 983.4 ms | 2 |
| Earlier measured session, visible and focused | 1102 × 905 / 1 | 990.2 ms | 990.8 ms | 2.50 | 983.3 ms | 2 |
| Earlier 300-layer stress, visible and focused | 1102 × 905 / 1 | 998.2 ms | 1995.5 ms | 1.68 | 983.3 ms | 2 |

The earlier sessions are preserved separately in
[`m4-studio-performance-contended.json`](evidence/m4-studio-performance-contended.json)
and [`m4-studio-performance-background.json`](evidence/m4-studio-performance-background.json).
Those earlier receipts predate the visibility trace field, so their exact
visibility transitions are not instrumented. The final
[`m4-studio-performance-before-diagnostics.json`](evidence/m4-studio-performance-before-diagnostics.json) adds the
visibility trace: start/end are `visible`, both report focus, and there are no
visibility changes. It still measures roughly one-second frame intervals.
The cause in this in-app browser environment has not been established; the
measured delay must not be attributed to a hidden tab merely from the frame
pattern. The earlier small-frontier reports observe zero main-thread long tasks,
which does not establish smooth frames or exclude browser/scheduler delays.

The earlier small-frontier session does **not** meet a 150 ms paint-proxy or
smooth-frame target. These numbers are retained as measured rather than
replaced by the earlier faster run. They remain engineering diagnostics of
this browser session, not native Event Timing/INP certification.

The earlier source-backed 300-layer scenario targets
`call:instance:model.DenseStress300.network`. The independently validated
[`m4-studio-performance-stress-before-diagnostics.json`](evidence/m4-studio-performance-stress-before-diagnostics.json)
records 20 expansion/collapse pairs, with the canonical visible frontier
4→304→4 every time, and binds its own source/IR digests. Visibility stays
`visible` with focus and no visibility changes. Its maximum observed long task
is 97 ms; expansion proxy p95 is 998.2 ms, collapse proxy p95 is 1995.5 ms, and
fps is 1.68. This source-backed scale scenario is implemented and measured, but
the measured browser performance gate fails in this environment. The roughly
one-second frame cadence remains unexplained, and browser timing results must
not be replaced by faster core-only timings or attributed to hidden visibility
contrary to the receipt.

## Final diagnostics with idle baseline

The final receipts add an idle frame baseline and synchronous typed-handler
duration. Both sessions report visible/focused start/end with no visibility
changes, including the idle baseline. Source/IR and canonical frontier checks
pass for every measured pair.

| Final fixture | Frontier | Idle FPS / frame p95 | Interaction FPS | Expand proxy p95 | Collapse proxy p95 | Handler p95 expand / collapse | Max long task |
|---|---|---:|---:|---:|---:|---:|---:|
| Residual CNN blocks | 8→10→8 | 1.01 / 1000 ms | 1.68 | 996.4 ms | 998.6 ms | 1.8 / 1.9 ms | 0 ms |
| Source-backed 300-layer Sequential | 4→304→4 | 1.02 / 1000 ms | 1.33 | 1005.4 ms | 1955.2 ms | 44.1 / 40.0 ms | 101 ms |

The unchanged approximately one-second cadence in the **idle** baseline shows
that the browser/environment contributes a scheduling limitation independent
of the frontier operation. The precise cause in this in-app browser has not
been established. The synchronous handler timing also shows additional work
at 300 layers, but it excludes subsequent React/SVG rendering, so it cannot
establish the total render cost. The performance gate remains failed; neither
the idle result nor the handler timing is used to lower the target.

The original final JSON objects are
[`m4-studio-performance.json`](evidence/m4-studio-performance.json) and
[`m4-studio-performance-stress.json`](evidence/m4-studio-performance-stress.json).
Independent percentile/frontier/binding validation outputs are
[`m4-studio-performance-validation.json`](evidence/m4-studio-performance-validation.json)
and [`m4-studio-performance-stress-validation.json`](evidence/m4-studio-performance-stress-validation.json).
The original receipts have not been rewritten with inferred environment
causes or replacement timings.

Browser collection loaded `index-CoSwliyU.js`. The subsequent final production
build is `index-DhwEfskO.js` (SHA-256
`a464a9e9837a337c9506fabd1cb5fb3a2c6b2366feb636f8cd38065cd4f4fca4`).
The intervening changes hardened export metadata copies and study-receipt
restoration; they did not change the measured benchmark or ordinary SVG scene
rendering. This build distinction is documented separately from the original
browser receipts rather than inserted into their measured data.

Final Studio verification is 26/26 tests with no skips and a passing production
build. The two-frame boundary and independent receipt counterexamples are
included alongside source-derived export and scale tests in
[`m4-studio-tests.txt`](evidence/m4-studio-tests.txt) and
[`m4-studio-build.txt`](evidence/m4-studio-build.txt).

## Scene indexing optimization and native input collection

The next implementation replaces repeated level/predecessor, projected-port,
canonical-edge and parallel-edge scans with indexed queries in `scene.ts`.
The independent [CPU comparison](evidence/m4-core-performance-comparison.json)
freezes nine baseline core files and changes **only `scene.ts`**. Five warm-ups
and 30 trials use the same source, script and Node/CPU; every expanded/collapsed
document, history, scene and interactive SVG is compared against the baseline.
Validation and deep-copy counts stay unchanged. Expand handler/core p95 is
38.78→20.07 ms; expanded scene construction is 10.10→3.77 ms; collapse is
22.99→13.08 ms. These are CPU measurements and do not certify browser paint.
Concurrent output-path contract changes are excluded from this causal comparison.

The same `?benchmark=1` panel now has “开始原生输入采样”. It observes ordinary
tree click or canvas pointerdown controls without dispatching input. Before
sampling, pin an unrelated visible object; toggle one container at a time and
wait for its scene to settle. Finish after at least two frames. Each trial binds
the actual event timestamp, `isTrusted`, target ID, source/IR/document/revision,
expanded IDs, visible objects, and the body rectangle in screen and canvas
coordinates. The target itself must change expansion state at exactly the next
revision; a different-container operation cannot count as that trial.

Latency comes **only from matched native browser Event Timing**, including
the event queue. It matches event name, timestamp, canonical target and positive
interactionId, with no reuse; ambiguous, unavailable or below-threshold entries
remain null. Browser duration is quantized to 8 ms with a 16 ms reporting
threshold. The reported p95 covers the matched subset, whose count is explicit;
it is neither a complete low-latency distribution nor overall page INP.
Two animation frames are used only to read post-operation geometry, never as
native paint evidence. Unrelated pin canvas displacement is distinct from the
expanded object's screen displacement. Hidden/disappeared pins remain unmeasured.

The frame receipt spans the manual sampling window, including pauses between
inputs; it is not sustained dragging/rendering FPS. The observer itself adds
overhead. Viewport/DPR/UA/font-loading state are recorded, but fallback font
bytes and target hardware still require an external fixed-environment manifest.
`isTrusted` browser automation does not establish a human participant.

Save the exact “原生性能 JSON”, then run:

```bash
node scripts/validate_native_performance.mjs path/to/native-performance.json
```

The independent checker recomputes event matching, target state, frontier,
geometry, pin coverage, percentiles and frame summaries. It always retains a
pending certification state. Historical initial smoke is preserved under
`evidence/native-performance-before-target-check/`; it measured 2016/1032 ms
for two stress toggles with zero screen-anchor/pin displacement, but predates
the target-identity/state checks. It is not accepted by the hardened checker
as a current receipt. Neither it nor the faster core results replaces the
earlier failed browser receipts.

The hardened [current smoke](evidence/m4-native-performance-stress-smoke.json)
and [independent validation](evidence/m4-native-performance-stress-smoke-validation.json)
contain two matched native clicks on the actual network target and its state
transition: 4→304→4 visible objects. Expand and collapse each record 2024 ms;
screen-anchor displacement and the pinned output's canvas/screen displacement
are all 0. The full manual window records 2.16 FPS and an 85 ms maximum long
task, visible/focused without changes. The pinned output overlaps the expanded
network, and Studio reports that conflict; zero movement is not a layout pass.
This is an **automated two-input smoke**, not a statistically representative
target-browser benchmark. The final Python suite was competing for CPU during
this sample; that context and the exact loaded build `index-73IkoEeA.js` are
preserved in [build/environment context](evidence/m4-native-performance-build-context.json).
The raw JSON has not been rewritten to remove that contention. Host CPU and
font lookup are observations, not a fixed browser-font certification.


## Historical zoom-build evidence boundary

The later [nine-toggle native receipt](evidence/m4-native-performance-intrusion-current.json) and [independent validator](evidence/m4-native-performance-intrusion-current-validation.json) bind the intrusion build before the zoom-control fix. Nine scene transitions are valid; eight Event Timing matches yield p95 3024 ms and the whole observation window yields 2.01 FPS. The first missing native entry remains null. Anchor displacement and eight unrelated pin canvas measurements are zero. Visible/focused state and a fixed 1280×720 viewport were recorded; the contemporaneous [environment context](evidence/m4-native-current-environment.json) records load average about 0.17 with no regression/build running in parallel. Continued slow scheduling means prior CPU contention alone does not resolve this diagnostic. Font loaded status does not certify resolved fallback font bytes.

The final zoom build `index-oH4Ot2L9.js` has [actual committed gesture observations](evidence/m4-actual-gesture-zoom-current.json): 100% and zoom-out buttons, node move (+32,+20), undo/redo, collapse/re-expansion and saved/reopened position. These observations do not measure intermediate drag FPS or drag input-to-paint. Its pin is outside the viewport at 100%, so that sample does not certify visible pin experience. The [full final visual matrix](evidence/browser-visual-matrix-zoom-full/manifest.json) contains 36 baseline and three edited/save/reopen/export cases, with independent Canvas/DOM/SVG consistency and pending human review; it is not a performance certificate. That build’s core regression was 54/54 with no skips; the subsequent one-line UI event fix passed strict TypeScript, production build and actual button checks. Native performance and human gates remain open.

## Historical zoom-build input diagnostics (2026-10-05 Asia/Shanghai)

The [separate measurement harness](m4-input-observation.md) leaves production assets unchanged and observes a same-origin 1280×720 iframe through public DOM and browser timing APIs. MLP has six ordinary operations; the authored stress model expands to 304 scene objects and has actual drag/undo/redo, plus a separate trusted wheel trial. Both drag sequences move the selected body +40/+24 canvas pixels, restore its exact selected facts on undo and redo, and preserve the unrelated input pin. Matched discrete interaction subsets each yield p95 2016 ms; missing drag pointerdown entries remain null. Callback cadence between the first and last captured rAF timestamps is about 1.83/1.94 per second and includes operation preparation/waits; the entire start/stop session denominator gives 1.827/1.934. Neither is sustained drag or presented FPS. Eight pointermove proxies per drag and the wheel proxy remain DOM observations, never native continuous input-to-paint.

Two simple-page controls without React, SVG, model or product telemetry also contain approximately one-second rAF gaps and native target durations 1000/2016 ms. One window later accelerates, so its aggregate p95 conceals earlier stalls. Host visibility was unconfirmed in those two windows: the browser capability returned false after a visibility request, despite document visible/focused. Probe costs, iframe focus changes, outer scrolling, hashes, independent raw recomputation and limits are retained in the [diagnostic report](m4-input-observation.md). These observations neither establish a scheduling cause nor clear the failed performance gate. Twenty-four new measurement-tool tests passed; formal Studio/Python historical suite totals remain separate. At that time pan was not covered. The new-build pan evidence above adds terminal DOM checks; resolved font/hardware environment, continuous presented paint and human gates remain open.

## Later host-visible control and full task

The separate [third simple-page window](evidence/m4-visible-host-control/README.md) records 40 rAF callbacks in 20,000.4 ms, with two callbacks in every complete one-second bucket. One matched interaction has duration 1016 ms; its missing pointerdown match remains null. The host visibility capability returned true before the window and again 54.5637 seconds after its end. Those two readings establish their own observed states, not continuous host presentation. The unchanged validator was run without the host observations, so its `unconfirmed` presentation result remains intact. This later control adds evidence without identifying the scheduling cause or changing earlier raw files.

The [same-document Transformer task](evidence/automation-full-task/README.md) additionally exercises alias/fill, legend, annotation, edge style, page width/preset, pin, drag/undo/redo, Save/reload and actual SVG/PDF generation through ordinary Studio UI. The +32/+20 target move, exact history restoration in canvas coordinates, saved fields and export inputs are audited separately from timing. Four ancestor bodies grew by 32 pixels and three other routes changed; strict geometry invariance was not satisfied. Viewport differences prevent treating this chain as fixed-environment screen continuity. No input observer was attached, and its roughly 20.5-minute automation session includes agent waits. It is neither a performance sample nor a researcher completion-rate result.

## Current pan and annotation evidence limits

The [independent UI field report](evidence/m4-pan-annotation-work/ui-field-audit.md) verifies one Transformer pan of +64/+40 at revision18 with identical public SVG and viewport. Annotation move, undo/redo, idempotence, new-note placement and rev23 Save/reopen have exact field and SVG reconstruction checks. The public selection array is empty while status sometimes says one object selected; hidden selection/history is not certified. Reopen changes camera and resets session history. In-progress gesture cancellation has pure helper tests and code evidence, but no native cancelled-drag sample.

The two v2 pan sessions record complete buffers and four same-pointer down/up sequences. One session matches three of six eligible discrete inputs into one interaction (p95 2008ms); the priority session matches two of six into one interaction (p95 2024ms). Missing inputs remain null. Captured-frame-span callback cadence is about 1.88/1.86 per second, using (N−1)/(lastFrame−firstFrame), and includes preparation/waits; the true start/stop session rates are about 1.8715/1.8673 per second; it is not sustained dragging or presented FPS. The apparent low scheduling cadence remains diagnostic, without a proven cause.

The actual current SVG was opened; PDF was generated and its local bytes/receipt checked, without a current PDF view. At85mm the full figure has minimum text≈2.896pt. Body-rectangle annotation conflict elimination excludes routes, markers, headers and font shaping. Neither export reconstruction nor successful save establishes publication readability or human success.
