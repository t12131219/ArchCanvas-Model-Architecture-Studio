# Superseded v1 routing audit — after outside-corridor fix

These outputs were subsequently regenerated during a new review. The original
v1 receipt no longer binds them. Current exact before/after comparisons and
code hashes are in the [v2 routing audit](../../unified-editor-review-v2/routing-after/README.md).

This directory is the independent after snapshot for the current atomic frontier
projection and readable routing implementation. The product code now keeps
authored top/bottom port order stable, shares the horizontal memory anchor with
late memory continuity, and reserves a small set of expanded-ancestor boundary
axes before nearby axes consume the per-route candidate cap. It uses scene
geometry and ancestor membership only; it has no model, fixture, tensor or
edge-ID special case.

`report.json` repeats the exact 41 fresh current-source cases from the before
audit. `pair-comparison.json` compares every visible edge pair in every matching
scene. It reports zero newly introduced crossing, point contact or overlap;
the residual CNN right-move pair loses one crossing and 220.67 units of
overlap. Canonical coverage, source facts, port identities, SVG/scene agreement
and parent/child ambiguity remain unchanged. `residual_cnn-level2-right.svg`
shows the repaired route; the before snapshot remains at the sibling path.

The new current regression is
`studio/tests/readable-routing-current.test.ts`. It dynamically finds the
residual source, nested convolution and Add target, then checks the actual
fixture after a right move, exact ports/canonical bindings, translation, and
horizontal mirror. It does not import `historical-routing-core.ts`.

Validation:

- `studio/tests/readable-routing-current.test.ts`: 2/2 passed.
- Full Studio `npm test`: 523/523 passed after the two new tests.
- `npm run build`: TypeScript and Vite passed; Vite emitted a chunk-size warning.

The remaining current geometry limits are visible in the report: Transformer
expanded frontiers retain distinct-tensor crossings and long mask/residual
lanes, and the 24-unit upward Attention move retains an explicit blocked route
and header-overlap diagnostic. Those are honest open cases, not silently
converted to pass.
