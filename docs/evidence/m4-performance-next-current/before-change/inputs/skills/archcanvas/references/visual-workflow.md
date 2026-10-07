# Visual workflow

## Current formal checkout: three AI roles and usability fixes (2026-10-06)

Final assets are `index-B_XHk-wz.js` / `index--unhoRTb.css`. Studio passes **347/347 with zero skipped**; strict TypeScript/Vite exits 0, with 100 source/test/config and 3 build bindings exact. See the [current stage](../../../docs/m4-ai-simulated-current.md) and [current gate audit](../../../docs/evidence/m4-current-gate-audit.json). Fixes preserve the viewport center during toolbar zoom, apply initial generated display aliases before layout, fold long unary chains by viewport, and give new presets stable role labels.

Three authorized AI roles actually exercised blank authoring, four-direction camera/node movement, history/save/reopen, and catalog/routing on DuFX. CC91 follow-ups and seven final B_XH states remain version-qualified. Final CNN fit is 2 columns / 4 rows / 84% in a 637×619.5 viewport; pool 2×2 requires Linear 32, correctly diagnosed, corrected and reopened. Independent review personally inspected all seven final images with bounded matching; 42 draft state routes have exact endpoints and no unrelated card interior hits. Historical failures and stale images remain. The draggable palette has 17 base kinds and 3 transparent starts; there is no all-kind generation, execution or global aesthetics claim.

M4 remains partial, M5 not_started, humans 0. A [fresh B_XH research package](../../../docs/evidence/m4-ai-simulated-current/research-final-preparation/report.json) is prepared/verified with 273/273 independent readiness checks; five pristine seats register ports 43451–43455, without serving, assignment or collection. DuFX/CC91 packages are now stale and preserved. Two earlier DuFX small-scene diagnostic pairs each match p95 40 ms / about 60 Hz rAF, but do not establish host-visibility A/B or presented FPS. The old D60 1008 ms failure remains; final B_XH performance is unmeasured. AI is not a human participant. Real users, physical publication review and presented performance remain open. The formal runtime is independent of the failed prototype; no reuse candidate is certified. Earlier “current/final” statements below apply only to their named frozen version.

Use this reference for figure creation, visual refinement, expansion, and export. These are acceptance contracts for a compatible Studio, not assertions that every installed runtime supports them. Check operations before invoking them.

## First view and visual grammar

Create a composed overview that can be understood without opening a property panel. Choose an overview/detail scope, flow direction, page profile, and visual preset. Use a restrained palette, consistent typography, generous container padding, aligned stages, and enough whitespace for labels and bypass routes.

For a Transformer, a suitable starting grammar has encoder/decoder lanes, repeated-layer frames, compact Attention/FFN stages, external residual corridors, and explicit memory connections. Pre-/Post-LN order, mask roles, positional encoding, output Softmax, and repetition must follow the analyzed implementation. An interpretive mathematical view of fused attention is labeled schematic and retains its source reference.

Use shapes as well as color: framed containers for modules, compact boxes for operators, tensor strips/grids for values, `+` for addition, a named concat glyph, a junction for fan-out, and a distinct opaque frame. A fan-out junction must not imply a learned Split layer. Do not fabricate activation values when only structure is available.

Publication defaults may start at 85 mm or 180 mm width, 7–9 pt final labels, and 0.5–1 pt main strokes. Adapt to the intended venue and actual amount of information; export details separately when a full expansion is too dense.

## Editing targets and operations

Maintain stable canonical references and independent presentation identities. A visual document should preserve the following objects when its runtime supports them:

| Target | Presentation changes | Preserve |
|---|---|---|
| Node/container | Display alias, subtitle, fill/stroke, typography, padding, corner radius, title placement, registered glyph | Canonical operator/module identity and source name |
| Edge | Stroke, dash, arrow, routing bends/corridor, displayed label and position | Canonical tensor/port binding |
| Legend | Add/remove/reorder items, edit text and symbol sample, place, horizontal/vertical arrangement | Clear correspondence with the displayed visual language |
| Annotation | Text/formula, callout, position, style | Separate identity from executable model structure |
| Page | Background, margin, width, orientation, monochrome/color preset | Model facts and current document revision |

Style precedence: global tokens → semantic category → per-object override. Reset removes the local override. “Apply to similar objects” specifies its scope and becomes one undoable operation. A display alias is not a symbol rename.

Treat legend entries as objects, not only a computed footer. Automatic entries may derive from visible categories; manual entries retain user text and order. Distinguish decorative explanatory lines from actual tensor edges. Renaming a legend cannot relabel an Add operation as Concat.

Use the runtime's typed visual patch interface when available. Retrieve the base document revision, resolve selection/identity, apply one atomic batch, inspect the resulting receipt, and refresh the same scene. Do not invent an `apply-visual` command or submit a guessed JSON schema.

The current formal local Studio exposes an explicit position-recovery preview for a selected visible object. Free dragging retains the chosen position and reports body/header/outside-parent/blocked-route conflicts. Inspect the proposed position, apply or cancel it, and verify undo and save/reopen. Pins and infeasible candidates are refused. Recovery protects unrelated geometry according to its recorded conflict metrics; route severity is total reported intrusion length, not a guarantee for each obstacle or every crossing. This local capability does not imply globally optimal or publication-ready routing. Verify the actual runtime before claiming it in another installation.

## Interaction and history

Direct manipulation and language edits share selection, revisions, and command history. A completed drag, text edit, multi-object alignment, or accepted layout forms one undo command, rather than one per pointer event. Reversible visual edits preview immediately and save without invoking source review.

Expected interaction: pointer-centered zoom; pan; fit/reset/focus selection; click, Shift multi-select and box select; move/resize; align/distribute; guide snapping; pin/unpin; double-click label editing with Enter/Esc; undo/redo. Keep inline editing from triggering global keyboard shortcuts.

For in-place expansion, keep the selected container's screen anchor, move only the necessary neighborhood, and preserve unrelated pins. Restore that level's prior layout on collapse/re-expansion. A short animation may help continuity but respect reduced-motion and do not delay interaction to disguise slow computation.

After a source refresh, retain camera, selection, styles, and arrangement only for unique identity matches. Report unmatched objects for reconciliation; never attach a previous override to an arbitrary node with the same displayed name.

## Check and export

Inspect the actual rendered view with available browser/screenshot tools, not only serialized fields. Check one collapsed overview, one expanded detail, and final physical export size. Look for clipped glyph/text, detached endpoints, illegal node crossings, congested residual/memory routes, unreadable small labels, inconsistent legend symbols, and excessive empty space.

Export the current CanvasDocument/Scene revision through the shared renderer. SVG is the vector authority; PDF/PNG are derived. Exclude handles, selection boxes, toolbars, and editor grid unless the user explicitly asks for them. Preserve fonts/page dimensions and source/document digests in the export receipt when supported.

Verify save/reopen and undo/redo for substantive edits. A fresh static render of the original architecture does not prove it exported user overrides. If the renderer cannot consume the edited document, report the export gap and do not claim screen/export equivalence.
