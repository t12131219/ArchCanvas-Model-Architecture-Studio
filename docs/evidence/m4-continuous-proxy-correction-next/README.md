# Continuous DOM proxy correction: bounded design

Design only, 2026-10-06. Product, observer, validator, tests, builds and all historical raw/reports remain unchanged. No model execution or browser input is added. This proposes a narrow engineering-observation correction after the current stage is sealed; it does not close an M4 performance or human gate.

## Actual defect and regression target

`scripts/validate_input_observation.mjs:229–230` initializes `signature(t.before)` from every object in a full boundary and compares it with each partial frame. The responsive observer records all 304 body objects at boundaries, but only the union of declared targets, anchors and pins at frames. The first unchanged partial frame therefore appears changed because its object set is smaller. The existing nonresponsive observer often has equal sets, and the old hand-authored tests have two bodies at both boundary and frame, so they do not expose this case.

The frozen seven-attempt raw has 60 trusted retained inputs, no dropped or failed received inputs, and 33 continuous raw events: 17 assigned to requested trials and 16 unassigned. Trial 2 is still `no-input` (the attempted drag actually used the hand tool), not a successful drag. The old independent audit remains **26/29**, with its three discrepancy groups retained as failures.

| Requested trial | Frame object set | First proxy, old → independent | Independent p95 | Eligible/measured |
| --- | --- | --- | --- | --- |
| 1: pan | anchor + pin, 2 IDs | 960 → 965.4 ms | 994.9 ms | 8/8 |
| 5: drag | target + anchor + pin, 3 IDs | 772.9 → 1015.4 ms | 1716.1 ms | 8/8 |
| 7: wheel zoom | anchor + pin, 2 IDs | 39.5 → 45.2 ms | 45.2 ms | 1/1 |

Read-only reconstruction using the existing signature fields (`revision`, camera matrix, canvas rectangle, screen rectangle and label), projected to the same sorted declared IDs at every sample, reproduces all 17 independent per-input values exactly. It also leaves trials 3/4/6 with zero continuous rows. That reconstruction is design evidence, not an implemented-validator test result.

## Proposed narrow implementation

1. Keep the existing full `visualSignature` and its uses for whole-boundary shape/undo/redo checks. Do not project those checks to the smaller frame set.
2. Add a separate continuous signature helper accepting a stable ID list: sorted unique `targetIds ∪ anchorIds ∪ pinnedIds`. Initialize it from `t.before`; use the identical IDs and fields for each frame. Exclude observation clocks, object enumeration order, CSS transform text, full SVG, frontier arrays, selection markup and other boundary-only fields from this signature. Keep numerical camera matrix and revision. Include each ID, canvas rectangle, screen rectangle and label in a fixed field order rather than serializing the entire object.
3. Validate identity/coverage before comparing signatures. A required ID absent as an own property is a contract error; do not replace absence with `null` or omit it. A non-null object's canonical ID must agree with the same ID's before binding; otherwise reject the trial binding. A drag's requested target must have measured before/after geometry. Existing null pin evidence must remain explicitly unmeasured, never zero movement.
4. A declared object recorded as `null` in before or any compared frame is unavailable geometry. Conservatively mark that trial's continuous coverage incomplete and its eligible proxy rows `null` with `required-object-unavailable`; do not treat disappearance/reappearance as a known geometrical first change or compare across the gap. A structurally valid toggle can still have its independently established frontier result; continuous coverage is a separate result. An empty declared set can provide only a camera/revision proxy, with that scope explicit, and cannot establish object coverage.
5. Preserve document ID validation for every frame, source/IR equality at full before/after boundaries, revision deltas and the existing camera/terminal comparisons. Frames do **not** contain source/IR digests; do not infer per-frame digests from before. If optional digest fields are present in an independent fixture or future frame, reject disagreement; otherwise report source/IR scope as boundaries only. A source mutation that changes and reverts between full boundaries remains unobservable under this contract.
6. Retain first changed observation at/after `capturedAt`, and duration `observedAt - eventAt`, for compatibility with this bounded regression. This is the first observed DOM state change after capture, not the input's causally identified response. Inputs may share one changed frame. Keep `presentedPaintCertified=false` and `causalInputIdentified=false`.
7. Keep revision in the signature but report whether a matched change was revision-only, camera, or declared object geometry/label. A revision-only match is a DOM revision observation, not proof that body geometry or pixels changed. Preserve all original operation-trigger, cancellation and terminal checks; proxy coverage or a low value must never turn `no-input`, wrong target, wrong tool, or missing pointer-up into successful operation evidence.
8. Report the declared continuous ID set and eligible/measured/unmeasured counts, plus null reasons. Any p95 uses finite measured values only and is labelled a measured subset; no missing values become zero. Keep all received/assigned/unassigned denominators distinct. On dropped event/frame buffers, observer errors, or responsive-ledger failed/dropped inputs, preserve diagnostics but mark continuous completeness false and suppress first-change certification (null with explicit incomplete-capture reason). The responsive ledger wrapper must check its `failed` count as well as the base buffer `dropped` count; base v1/v2 alone does not have that ledger.

Suggested derived-report discriminator: `continuousProxyDefinition: same-declared-ids-dom-state/1`, plus `continuousObjectIds`, `continuousCoverageComplete` and an explicit observation scope. Do not change the old raw schema or overwrite its original reports. The exact report API can remain small; no observer or product change is needed to correct the known three groups.

## Independent counterexample fixtures

Use hand-authored browser facts with explicit expected coordinates/times and fixed matrices; import only the public validator under test. Do not import its signature helper or observer serializer to build expected values. The following are meaningful contract cases, not a requirement to create one test per table row.

| Counterexample | Required result |
| --- | --- |
| Full before has A/P/U; frames have A/P; all geometry/revision/camera equal | No changed frame or finite proxy. The smaller object set alone is not a change. |
| First partial frame unchanged at 25 ms; A moves at 45 ms; input at 20 ms/captured at 20.05 ms | First proxy is the hand-specified 25 ms, not the 5 ms unchanged frame; camera/pin stay exact. |
| Before/frame object keys inserted in different order | Same signature and same proxy; ID ordering cannot create change. |
| Declared target, anchor or pin omitted as an object property | Reject coverage binding. Do not silently project it away. |
| Required object present as null, or one frame has a null gap and later reappears | Continuous coverage incomplete; rows null with reason; pin movement remains unmeasured. No false zero or recovery proxy. |
| Frame's document ID or canonical ID is wrong | Reject, even when rectangles and times are plausible. |
| Full after source or IR digest differs; optional frame digest disagrees | Reject using the available digest evidence. No claim of digest availability when a frame omits it. |
| Valid buffer truncation, frame drop, observer error or ledger failed input | Preserve incomplete diagnosis; no complete first-change or whole-input performance claim. |
| Wheel changes numerical camera scale with unchanged world bodies/revision | Camera proxy is measured; world continuity retained. No Event Timing wheel entry fabricated. |
| Revision alone changes with fixed camera/bodies | Revision-only DOM state match labelled as such; it is not body movement or paint evidence. |
| Only unrelated U changes between full boundaries, with A/P unchanged and stable revision/camera | No A/P continuous proxy. Full-boundary shape/continuity evidence must still see U. If U changes and reverts between boundaries, partial frames cannot detect it. |
| Actual successful A drag also changes unrelated U | Preserve whole-boundary mutation diagnostics; same-ID proxy does not certify that all unrelated bodies stayed fixed. Existing drag success alone is not a whole-layout invariant. |
| No-input/wrong tool attempt has outside pointermoves and camera change | `operationSucceeded=false`; zero assigned proxy rows; outside input remains in the outside denominator. |
| Two assigned continuous inputs and one outside input share a changed frame; another assigned input has no later changed frame | Shared observation is allowed with causality false; null remains null; p95 uses finite assigned rows only and reports full eligible/missing/outside counts. |

For the unrelated-body fixtures, keep full before/after boundary checks separately from the projected continuous signature. The known raw already independently checks all 304 bodies: pan/wheel world coordinates unchanged; successful drag changes one body; undo restores it. Do not replace that broader audit with the proposed projection.

## Implementation and verification boundary

After the parent releases the current stage seal, implement the helper/guards in `scripts/validate_input_observation.mjs` and add focused independent tests in `tests/m4_input_observation.test.mjs`. A new responsive wrapper can use the corrected current validator; never edit the sealed `continuous-observer-work/validate.mjs` or its frozen `inputs/06-validate_input_observation.mjs`. Existing matching/terminal tests remain required. No new product/build/full-runtime tests are justified by a validator-only change.

Write corrected derived reports into a new attempt directory and compare all 17 input IDs/values with the frozen independent audit, while preserving its old 26/29 outcome and old values. Recheck that no-input trial 2 stays failed, native discrete matches/cadence/denominators stay unchanged, and whole-boundary document/source/IR/pin/camera evidence is retained. A corrected replay can resolve only the three proxy disagreements, not revise the original execution or convert performance gates to pass.

`presentedFps`, true continuous input-to-paint, fixed environment A/B×3, publication review, model execution and human participants remain unproved/null/zero as appropriate. The 45.2 ms single wheel observation is not a 300-readable-object ≤50 ms gate. Pan/drag proxy p95 remains much greater than 50 ms.

## Finite inputs read for this design

Paths are relative to the formal project. These seven bindings delimit this design; they are not a transitive runtime manifest. The frozen audit/its existing seal remains the authority for its broader historical input bindings.

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `scripts/validate_input_observation.mjs` | 25888 | `21426de5e08ab0fd7bbf20008ff4f050ba63983209cf1bb00c9aef5565d6d414` |
| `scripts/m4_input_observer.mjs` | 17697 | `b7b8b11da1d267caf5fe18050545bd70a798ea395a492a470349a81041a981b0` |
| `tests/m4_input_observation.test.mjs` | 21784 | `eb61a82f3d2f9624a5f882a2fda23dac8770c226b35ef07e7acb04214e0f75f1` |
| `docs/evidence/m4-readable-grid-browser-next/continuous-observer-work/observer.mjs` | 21319 | `4ab2afb968edaf1ec1f3828de03a1619a6afc71b5f16fa93a4d3046b0a9a7f39` |
| `docs/evidence/m4-readable-grid-browser-next/continuous-observer-work/validate.mjs` | 5273 | `cf422e4c538afae43eb2c7615d1a304150e227c0650fd6a7e536d857d589ab41` |
| `docs/evidence/m4-readable-grid-browser-next/continuous-browser/01-seven-attempts-full.raw.json` | 18831519 | `f9ef101e68590b3bab113f57494042ea09e2107694a591237b7f283b59226889` |
| `docs/evidence/m4-readable-grid-browser-next/continuous-browser/independent-readback-attempt-2/report.json` | 15421 | `fdff557f6b0929c22eabc84606d03d76e360e996b3702e69b76ce3f15fde5c37` |
