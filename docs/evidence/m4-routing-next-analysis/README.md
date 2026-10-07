# Read-only routing research, 2026-10-06

Product source is untouched. These are geometric proposals, not an implemented renderer, passing aesthetic gate, or new AI participant. The formal from-scratch policy remains in force; no Temp code or model execution is involved.

## Mechanism and failed candidates

`studio/src/core/scene.ts:176` assigns right/left memory ports when `abs(source.y-target.y)<15`, otherwise bottom/top. The port registry owns the displayed endpoint and preserves its canonical bindings. Moving the source from dy14 to dy15 therefore changes two displayed ports before routing: the source jumps 110.021861 and the target 73.136174 world units. The old route length changes from 49 to 644.3. The accepted caption-stability stage keeps the label, and deliberately leaves this geometry unchanged.

`orthogonalRouter.ts:399` starts batch refinement from `requests.map(route)`. Its monotonic checks compare candidates against that **new initial batch**, not against the old policy's final scene. Changing only the memory preferred geometry can remove pressure that previously shortened other routes. It can therefore reintroduce an old residual/mask overlap without a local refinement violating its own metric. The criterion-only candidate at dy24 changes edge51 from its already short y378 lane to y397, sharing 32.4 units with each of edge45 and edge46. The subsequent global residual preferred-path rescue removed that example but still altered unrelated edge7/edge13 topology. It also widened the change beyond memory.

The unrestricted candidate also applied .55-height ports to expanded frames. At Transformer frontier3 it introduced memory edge44/data edge69 contacts at (473,2744.1) and (490,2298), previously absent. The collapsed/shared-band condition is necessary for the bounded proposal here. It is insufficient alone when installed ahead of the whole batch. At horizontal gap boundaries the former candidate falls back to a long bottom/top route with new unrelated peer overlaps; those failures are not closed by emitting a warning.

Named frozen evidence is in `../m4-caption-stability-current/implementation-work/report.json`, `criterion-only-peer-evidence.json`, `residual-preferred-peer-evidence.json`, `historical-route-actual-differences.json`, and the `independent-review/*routes-audit*/report.json` files. Early audit attempts use different crossing/touch metrics; do not combine their pass totals or interpret diagnostic exceptions as aesthetics.

## Narrow recommended implementation

1. Keep the original complete batch as a per-scene baseline, using the current display-port policy. This is a normal computation in the same scene build, not an old-runtime fallback or persisted cache.
2. Propose a late memory-only display projection when both effective endpoint cards are collapsed, their nominal visual outlines share a vertical band, and actual Repeat-aware right/left ports leave at least two six-unit leads. The deterministic local route is H-V-H through the gap midpoint. A same-y route is straight. Every non-memory route byte remains fixed.
3. Evaluate the proposal against **the final fixed complete batch**. Include all unrelated/same-tensor peers, inclusive crossing/touch geometry, collinear span unions, self contacts/reversals, visible stroke widths, endpoint normal/lead lengths, complete Repeat front/backplates, own bodies, unrelated expanded frames, and ancestor headers. Reject on any unknown budget result or new forbidden geometry. A warning cannot authorize adoption.
4. Commit the chosen edge and its public derived ports atomically. Preserve exact canonical edge IDs, source/target bindings and styles. Port bookkeeping must preserve other consumers that retain bottom or side ports; a shared canonical binding alone does not license a new trunk. Do not restart generic/family/residual optimization after this projection. Recompute label/guide placement from the resulting routes. The CanvasDocument, layout, history, source facts and IR digest remain unchanged.

For dy14 the current H-V path already has one extra correctness issue: it arrives at a left port vertically. H-V-H adds the second necessary bend to preserve the horizontal target normal, while keeping length49. At dy15 it replaces four old bends with two and length50. A cost rule must permit that endpoint-normal repair instead of treating the necessary bend as a regression.

The six-unit clearance boundary is a **remaining horizontal transition**, not continuity proof everywhere. Narrow/overlapping gaps, expanded-memory routes, automatic obstacle detours, global optimality, font and arrowhead geometry remain outside this proposal. A broader transition policy requires separate evidence rather than silently accepting the retained scenes.

## Finite independent readout

`evaluate_frozen_candidates.py` parses final frozen Scene paths and nominal rectangles directly, without importing product routing helpers. It validates every scene against its sealed byte/hash binding before proposing. It does not create a new CanvasDocument or accepted Scene.

`frozen-proposal-attempt-1/report.json` contains 504 scenes from one source-backed Transformer: 360 main captures and two 72-scene horizontal gap groups. It has 312 eligible proposals and 192 retained rows, zero geometry-rejected proposals. Eligibility includes body/header clearance, no new peer centerline contacts/spans, and no peer stroke contact at the combined nominal half widths. The 312 eligible rows are 13 moves × three explicit/default caption modes × paper/mono × 85/180mm × whole/root-detail. Other-route byte invariance is by construction, not an implementation test. The report's three example dy14→dy15 pairs show lengths49→50, source displacement1 and target displacement0. `sealed-readback-attempt-1/report.json` independently enumerates both signed threshold transitions over all presentation combinations.

`evaluate_historical_frontiers.py` reads nine hash-bound historical frontiers of MLP/CNN/Transformer (198 route occurrences). Seven are memory occurrences: one collapsed overview is eligible, six deeper occurrences are retained. These are historical frozen scenes; current production regeneration across all frontiers is still required.

## Required product protection matrix

- All three caption modes × paper/mono × 85/180mm × whole/detail; dy at 0, ±14/15/16/24/48 and adjacent fractional values; both source and target moves, not only Encoder.
- dx sweeps at the actual Repeat-aware gap: current +22.9/23/23.1 tests the new 12-unit policy; +34/35/36 tests exposed-gap +1/0/-1; +41/42/43 tests front-card gap +1/0/-1. Preserve blocked/overlap limitations; never count unchanged broken baseline as good aesthetics.
- All nine current source-backed frontiers, including expanded Decoder/Encoder, Repeat, opaque/shared nodes and multiple memory consumers. Whole/detail routes must be independently checked, not inferred by translation.
- Literal counterexamples for a body or ancestor header in the gap, nonpositive/nonfinite width, different dashed styles, peers touching only at joints, near strokes without centerline contact, shared-tensor crossings, different canonical bindings with equal labels/tensor names, tiny gaps, and work-budget exhaustion.
- Per-scene exact non-memory paths and ports, semantic facts/canonical inventory, detached document/history immutability, deterministic reload, preview/commit/undo/redo, save/reopen and faithful actual SVG/PDF export.
- Native four-way continuous gestures with settled public DOM/pixels; inspect overview and detail, both presets and publication dimensions. Nominal geometry does not certify resolved fonts, arrowheads, physical readability, presented FPS, or human acceptance.

M4 remains partial. This research does not change gate status or advance M5.
