# Collapsed Repeat outline — read-only implementation plan

This plan is based on the current formal Studio sources and the sealed-matrix acceptance advisory. No product code, old evidence, status document, build, browser, model import, dependency installation or prototype directory was changed during analysis. Product edits wait for the parent task's explicit matrix-sealed release.

## Observed inconsistency

- `svg.ts` renders a collapsed Repeat with front, +3.5 and +7 nominal rectangles, with rounded corners, but owns its offset literals independently.
- `scene.ts` places ordinary output ports on the front bottom, and the horizontal memory special case on the front right. Matching SVG circles and route requests therefore begin inside their own backplates. CNN `(177,416)` and Transformer `(274,444.1)` cannot escape those plates by changing later bends only.
- `orthogonalRouter.ts` treats only the front rectangle as the body. Its ordinary search and batch acceptance can therefore certify a segment crossing a backplate as clear.
- `exportScene.ts` translates existing ports but produces fallback detail ports on the front. Its final right bound adds a local literal 7 while bottom/obstacle calculations remain front-only.

## Smallest coherent change

Introduce a geometry-only helper taking front `Bounds`, `repeat` and `expanded`. It derives nominal owned rectangles (front, +3.5, +7 for collapsed Repeat only), the total bounding envelope and projection along an explicitly selected outward side. Keep every offset in this helper. SVG obtains backplate bounds from it; front content continues to use the existing node coordinates.

Project bottom output and right memory display ports outward along their existing normal. Incoming top and nonrepeat/expanded positions remain unchanged. The advisory examples become CNN `(177,423)` and Transformer `(281,444.1)`. Canonical IDs/bindings/digests remain source data; no CanvasDocument geometry/schema/operation changes are needed.

The helper's nominal silhouette is the union of the displayed card rectangles, not a new shape or a general polygon router. Projection uses the rectangle cross-section on that ray. A port less than 3.5 units from a front side must not be moved 7 units into a blank corner by a naive envelope projection. The existing conservative treatment of rounded-card corners as rectangular obstacles stays explicit.

The router indexes all owned rectangles for collision/endpoint/body checks and retains owner IDs in diagnostics. Node-level overlap reporting groups those same rectangles by owner; duplicate plate pairs must not duplicate diagnostics or report self-overlap. Leads must follow the exposed silhouette side, rather than guessing from the whole-envelope corner. Existing route budgets, tensor crossing/overlap scoring and candidate logic remain unchanged.

Detail export recomputes derived geometry after translation (avoid cached absolute outline fields), applies the same projection for generated inside ports, and uses the same full outline for content and final bounds. Ordinary scene containment/legend/bounds also account for the shared outline without moving manual anchors.

## Meaningful independent validation

Write an independent nominal-rectangle oracle that does not import the product outline or router parser/intersection helpers. Include corrupt front-attached endpoint and backplate-only intrusion controls so it demonstrably rejects the prior defect. Confirm the exact CNN/Transformer source examples and every role in fresh current-source frontier/detail renders.

Hand-authored cases cover bottom/right projection, near-corner +0/+3.5/+7 ray hits, top/left invariance, nonrepeat/expanded invariance, backplate-only unrelated obstacles, own-body reentry, overlapping endpoint honest diagnostics, between-repeat contact/owner deduplication and detail translation/fallback ports. Confirm final SVG circles match every rendered edge endpoint, not just intermediate request coordinates. SVG rectangles and reserved geometry must agree.

Compare canonical/source/IR/tensor/port coverage and input bytes before/after. Check expansion/re-expansion local layout and unrelated pin continuity plus move preview/commit/undo/redo equality. Existing historical endpoint-preserving routing tests may compare to front-attached snapshots; identify incompatibilities rather than rewrite old evidence or silently relax assertions. Build only after parent authorization. Browser/publication pixels remain a separate independent check; static geometry cannot certify human acceptance or physical readability.
