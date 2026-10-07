# Current routing verification (v3)

This snapshot uses the current formal Studio. `routing-before` remains unchanged;
no prototype or historical router supplies the result.

Readable routing now samples the existing orthogonal route with interior lane
offsets of ±2 world units. Endpoints and outward normals stay fixed. A candidate
is accepted only when body/header clearance, self geometry, every route pair and
canonical port attachment remain valid. In a real Transformer overview, the
six-unit target-mask lane moved to an eight-unit lane around the intervening
input card. Translation and horizontal mirror checks exercise the same case.

The 41 cases retain complete canonical coverage, exact source facts, canonical
attached ports, source/IR digests, and scene/SVG agreement. Exact pair geometry
comparison against `routing-before` reports 19 changed pair observations and
zero new crossing, contact, or overlap violations. The aggregate border-near
observations drop from 547 to 483 in the current matrix; this is a bounded
engineering improvement, not a global routing optimum.

The remaining constrained cases are recorded rather than hidden. Upward
Attention placement overlaps an ancestor header and keeps its explicit blocked
route diagnostic. Dense Transformer frontiers retain distinct-tensor crossings,
same-source shared trunks and some narrow lanes where no safe local replacement
exists. Manual node anchors remain unchanged.

Validation is bound in `receipt.json`: current routing tests 3/3 and full Studio suite 525/525 pass. The
TypeScript/Vite production build passes with the existing >500 kB chunk-size
warning. This evidence does not certify M4 human
usability, publication review, model execution, numerical equivalence or global
minimum crossings/bends.
