# Camera reload/resize and performance next-step review

This is a read-only technical review. It adds only this evidence directory, snapshots 23 inputs, imports no product helper or model, and operates no browser/service. Current entry documents and product files are untouched. [report.json](report.json) records independent frozen-body arithmetic, source locations and recommendations; [review.py](review.py) reproduces the review against its exact inputs.

## Actual camera gap

`App.tsx` starts with `{x:35,y:35,zoom:.9}`. Architecture opening schedules `fit(document)` in rAF at line210; saved active-document reload schedules `fit(doc)` at line241; generated-model opening schedules another fit at611. There is no camera storage, `ResizeObserver`, or resize listener. The prior actual browser reload changed camera from100% to68.1141% while Scene/document/facts matched. This matches the source implementation; it is not Canvas corruption. The 100% button is a separate operation: zoom to1 around the viewport-centre world point, not fit-to-bounds.

The scheduled callback captures a document but does not recheck load generation, current document/source/IR or intervening camera intent. Delayed old-load fit overriding a newer view is a source-level risk, not a newly reproduced browser failure. Semantic commit currently retains the numeric camera through reconciliation; that does not authorize loading saved camera state under a different source/IR.

## Minimal separate view-state option

Store a versioned view preference outside CanvasDocument and its undo history. Bind exact documentId/sourceBindingDigest/irDigest, finite zoom, world centre and positive viewport dimensions. Include view mode `manual|fit` and the saved visual revision used for the observation. Session storage is the smallest reload-preservation scope and avoids other tabs overwriting transient camera ownership. Persistence across closed tabs needs an explicit origin/service namespace and cross-tab preference policy; it is a separate scope choice.

On restore, derive `x = newWidth/2 − worldCenter.x×zoom`, `y = newHeight/2 − worldCenter.y×zoom`. Manual resize keeps world centre and zoom; fit mode can recompute fit against committed current bounds. A different viewport should not blindly reuse old pixel translations. Invalid/tiny measurements defer restoration; malformed storage falls back without a source/history write.

Explicit fit/reset/focus/pan/zoom must win over delayed initial restore. An intent generation and document/source/IR/load-generation check should guard any scheduled callback. Do not first write a prior document's camera to the next document key. Save only committed view state after pan release/zoom/fit/focus; active pan previews or cancelled gestures must not become the saved view. Storage errors should leave the usable current camera intact.

The proposal is **not implemented**. Necessary proof includes exact same-viewport restore, different-viewport same-centre intent, manual versus fit resize, new-source rejection, stale asynchronous load callbacks, explicit fit precedence, cancelled-pan persistence, actual native pan/zoom/reload and unchanged Canvas/source/history/export. Root chooses whether to add this as a separate stage. It is useful, but does not need to be bundled into the current memory-label threshold repair.

## Why 304 DOM bodies are only six viewport intersections

The frozen BTw sample has300 ordinary Linear/ReLU layers in one Sequential vertical chain, plus4other bodies. The recorded canvas is672×641CSSpx, but all bodies' union extent is303.973×29376.969CSSpx. A normal layer is187.805×60.020CSSpx, and neighbouring layers are about96.807px apart vertically. Independent recomputation confirms6body intersections/4fully contained; the300layer bodies themselves contribute only3intersections/3contained. The fixed performance panel also geometrically covers five of the intersecting bodies, including those three layers. DOM presence is not readable viewport presence.

Fitting only that body's union with the existing fit margins would need a relative scale0.018688 and shrink a layer to3.510×1.122px. This is arithmetic, not an actual fit/browser sample, and would not prove a useful300-object experience. A hypothetical12×25grid of194×62world cards with32×24gaps atzoom.15 fits402×318.9px, but its13-unit titles become1.95px. A20×15grid atzoom.85 occupies3814.8×1076.1px with11.05px titles, requiring a much larger actual canvas. These are sizing hypotheses, not implemented layouts or a certified workload.

A genuine next workload needs300distinct source-backed bodies in the actual uncovered viewport, non-overlap, actual text/object pixel sizes and unchanged timed camera. Normal typed layout/new isolated document can prepare it. Offscreen bodies, collapsed canonical IDs, overlapping cards,1px objects or objects under controls cannot substitute for a readable300-object claim. This is feasible preparation work, but routing/readability and the real host viewport must be demonstrated.

## Performance work still available

The formal targets remain300visible objects input-to-paint p95≤50ms and actual presented≥50fps, medium incremental processing p95<500ms, screen anchor≤8px and unrelated pinned canvas displacement0, in a fixed browser/hardware/font/DPR/power environment with prescribed repeated conditions. Trusted discrete EventTiming toggles, rAF cadence, longtasks, public geometry and the2rAF geometry boundary provide engineering evidence; they do not fill the continuous-input/full-denominator or actual surface presentation feedback gaps.

The retained [presentation capability audit](../../m4-presented-performance-capability-audit/report.json) already found no documented tracing/CDP provider; native app control is disabled. The installed native Start/Stop Performance Trace menu is an operator path, with no guarantee that a future trace contains the right surface feedback. This review performs no unsupported API retry or private IPC/DevTools workaround. Reuse that evidence and only reconsider if actual available capability changes.

Safe independent next work is a real300-visibility/readability setup, observer overhead measurements around `readScene`, full input logging and explicit warmup/capture/settle/drain, fresh same-build trusted engineering samples and actual environment/font-file bindings. More rAF/DOM observations cannot certify presentedFPS. Existing BTw/DuFX/D60 results remain version-qualified; this review provides no new timing sample, no human participant or publication acceptance. M4 remains partial.
