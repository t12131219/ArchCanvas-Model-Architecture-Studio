# Independent memory-continuity guard review

This is a preimplementation counterexample specification. It does not certify product adoption or change an existing gate. The reviewer read the formal AGENTS, ArchCanvas Skill, runtime/visual contracts, the current implementation design and the read-only routing research. No product, gold, App/camera or historical evidence is modified.

The literal reference geometry is two collapsed 100 by 100 cards at `(0,0)` and `(160,10)`. The source outward-right anchor is `(100,55)`; target outward-left anchor is `(160,65)`. Its required six-unit leads permit midpoint H-V-H through x130: `M 100 55 H 130 V 65 H 160`. The independently specified baseline is a longer bottom/top path. A success requires this exact route, exact public anchor attachment and unchanged baseline bytes for every other edge. Rejection/unknown requires exact baseline route and endpoint bytes, never an unsafe path plus a warning.

## Required literal negatives

- Joint-only perpendicular contact: peer `M 130 30 V 55 H 145`; the new point `(130,55)` is a candidate and peer joint. Strict segment-interior tests miss it.
- Whole-peer endpoint contact: peer `M 130 55 V 30`. No endpoint exemption is permitted for an unrelated public tensor route.
- Same-tensor contact: repeat both joint/endpoint cases with equal tensor name, canonical source, role and appearance. Labels and identities do not license a new trunk.
- Collinear contact: peer `M 110 55 H 120`. This is a ten-unit shared interval even when the peer has extra forward collinear vertices or retraced segments; occupied span union must be counted rather than raw segment multiplicity.
- Different-new-contact position: a baseline contact at `(130,30)` cannot authorize a proposal contact at `(130,55)`. Aggregate crossing count equality is insufficient.
- Nominal stroke proximity: peer `M 110 56.9 H 120`, both widths2. Centreline distance1.9 is less than combined half widths2; it has no centreline intersection and still must reject. Exact tangency at y57 also rejects. A parallel y57.01 positive control has2.01 separation.
- Invalid candidate/peer width: zero, negative, missing, NaN and infinite widths. Unknown nominal stroke geometry retains the baseline; it cannot evaluate partially as clear. Dashed appearance is not a width exemption.
- Gap body: a collapsed card covering `(126,56)` through `(134,64)` blocks the vertical candidate segment. A Repeat backplate alone entering the gap must also reject.
- Shared ancestor header: an expanded ancestor header covering `(0,50)` through `(300,60)` blocks the candidate at y55. Only non-header ancestor interior may be traversed; unrelated expanded-frame body is protected in full.
- Own body/header: every middle candidate segment remains outside padded front/backplate geometry. Only the correct source first lead and target last lead may leave/meet an actual exposed boundary; suppressing both end segments for both own cards is too broad.
- Repeat-aware gap: source repeat front-right100 and exposed-right107 produce53 gap to target160, midpoint133.5. A target at119 produces12 actual gap despite19 front gap. Target118.99 leaves11.99 and retains. Very short Repeat cards where the .55-height ray meets only the front/near plate need correct projection, not a bounding-box approximation.
- Rounded lead boundary: derive ports and midpoint to two decimals before testing both leads; an unrounded gap just above12 can round into a <6 lead due to unequal rounding. y coincident after rounding uses a straight route, without zero-length/reversal segments.
- Degenerate/unknown input: zero/negative/nonfinite dimensions, missing endpoint, malformed/nonorthogonal/nonfinite path and nonfinite coordinates retain without exceptions or partial clear results. Parent traversal must be bounded for a cycle/missing parent.
- Every relevant budget dimension: node, route, point, pair, segment and obstacle caps tested just below/at/above exhaustion, including exhaustion on the last peer or obstacle. No positive decision follows an incomplete scan.
- Later peer: an early safe proposal must inspect a complete fixed baseline peer list, including a dangerous peer appearing last. Product route.batch is invoked once, before adoption, and never after it.
- Chosen peer: two proposals can each be safe against the other baseline route yet collide after both adoption. Deterministic order adopts the first and retains the second. A near-stroke version also rejects the second.

## Port and canonical matrix

Build a literal architecture with one source binding consumed by three memory projections: accepted side consumer, retained bottom consumer (expanded/ineligible endpoint), and separately styled consumer. The accepted canonical IDs move from old port coverage to the required right/left coverage. The retained port keeps its exact coordinates and nonempty original coverage. A port disappears only when no projected consumer retains it. Architecture-order canonicalBindings must include every actual represented consumer exactly once; equal labels or tensor names must not coalesce distinct binding identities. Split dashed/style paths stay separate edges. Add a data consumer of the same underlying binding and compare its complete public port array and all non-memory routes byte-exact.

For one accepted edge and two retained edges that share one display side, canonical groups must be recomputed from the full chosen edge list, not patched from only the accepted subset. Compare returned nodes, routes, request arrays and detached input documents to hash-bound pre-call values. Multiple calls and reordered unrelated peers must be deterministic and not retain mutation from an earlier scene.

## Planned implementation readback

Once the implementation owner provides frozen source hashes and the callable API, a separate harness will import the product entry only to exercise it. Literal expected paths, rectangles, inclusive intersections, segment distances and canonical coverage will be independently calculated from public output, without importing its parser/outline/router/guard helpers. The resulting reports bind source and harness bytes and retain failures in append-only attempt directories. Full source-backed matrix, browser settled pixels, export fidelity and global M4 gates are separate evidence; these literal guards do not certify them.
