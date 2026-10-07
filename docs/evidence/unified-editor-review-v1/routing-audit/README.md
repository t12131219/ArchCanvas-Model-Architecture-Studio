# Current routing audit — before fix

This directory is a read-only audit of the current formal Studio before the
outside-corridor candidate fix. The observations were produced from fresh
static analyses of `fixtures/mlp`, `fixtures/residual_cnn`, and
`fixtures/transformer`, then rendered with the current `CanvasDocument` scene
and SVG path. No historical router or failed prototype is imported.

`report.json` contains 41 cases: collapsed and expanded frontiers plus the
available four-direction single-node moves. The audit independently checks
orthogonal path crossings, point contacts, collinear overlap, body/header
intrusion, route detour, canonical coverage, source facts, port attachment,
parent/child coarse-arrow ambiguity, and SVG/scene agreement. The report is
AI-generated geometry evidence; it is not human visual or publication review.

The principal reproducible defect is in
`residual_cnn-level2-right.audit.json`: moving the first convolution leaf right
by 24 world units leaves `edge:9` on the same x=74 ancestor lane as `edge:3`
(220.67 units of overlap) and crosses `edge:8` at `(204.7,972)`. It has no
blocked diagnostic. The current candidate search did not retain the required
outside x=426 corridor when the per-route axis list was capped.

`residual_cnn-level2-right-candidate.svg` is a bounded witness of a manually
proposed route that keeps canonical endpoints, removes that overlap/crossing,
and stays outside node bodies. It is diagnostic geometry, not product output.
