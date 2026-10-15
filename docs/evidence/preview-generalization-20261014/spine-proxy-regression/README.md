# Container-input proxy spine regression

The v16 predicate accepted a shared fan-out whose producer was the container
itself. These source-recorded proxy arrows restated the container's input and
started at its predefined centered boundary. Using that endpoint to authorize
a new content axis was circular: the container's own chosen interface became
the evidence for moving the same container against its surrounding source
column.

The isolated patch additionally requires a distinct recorded producer
(`e.source !== n.id`). It retains the existing shared-value, central terminal,
and common content-axis requirements. It names no model, node ID or depth.
A genuine external producer crossing one child boundary remains sufficient;
the new positive control verifies that explicitly under all four x/y
reflection combinations.

In the first changed PatchTST frontier, the residual frame and its Attention
and Add children shifted 2 px. Its frame center changed from 985 to 987 while
the content center changed from 983 to 985. The adjacent source-normalization
column stayed fixed. Its only shared input group originated from the residual
frame itself, then branched to centered Attention and the Add's side port.
The other centered input/output interfaces were single edges and supplied no
shared-producer authorization. `input-geometry-difference.json` preserves the
node/gate differences and complete recorded fan-out/endpoint trace.

Disabling only the content spine reproduced all nine v14 quality metrics;
disabling only the optional contact guard did not. The narrowed producer rule
then removed all 22 stages' extra 2/4 px length while leaving the other eight
metrics unchanged. PatchTST's 35 stages reproduce all nine v14 metrics.
Transformer compact's 16 stages retain all nine v14 and v16 metrics. All
51 routed stages pass the complete routing/source/layout/edge/junction/label
checks and preserve their source authority. The detailed report is
`isolation-mixed-report.json`; `51-stage-quality-summary.json` pairs every
stage with identical source input hashes and records all nine metrics.

The full Transformer proof opens Encoder and Decoder self-attention. Both K
inputs remain 2-point straight lines through both registered frame gates
(x = 382 / 1244), with exact source bindings, contracts, recorded ports and
authority bytes. See `transformer-k-proof.json` and its runnable script.

The new proxy negative control fails against the actual frozen v16 engine:
frame center 516 differs from the recorded sibling column's center 500.
Its captured output and all eight loaded runtime hashes are in
`baseline-proxy-failure.log` and its receipt. The narrowed predicate passes
all 9 spine and 8 contact tests (17 total). Test bytes, logs and hashes are
preserved here. The one-line runtime patch and test patch record the exact
adaptation; the formal product was not edited by this isolation task.

`runtime/recursive-graph.js` is the isolated predicate variant, SHA-256
`de8a27425e9d7d00bbee89c1b204f3efcc345a29376ece39ec7ee11ceb834c59`.
The other unchanged engine bytes are referenced individually from existing
frozen receipts in `runtime-receipt.json`, avoiding another complete runtime
copy. The runner verifies every byte before use. This isolation precedes the
combined v17 implementation; it does not attest later product bytes.

From this directory:

```bash
node run-regression.cjs
node run-regression.cjs --baseline  # Expected failure: source-proxy outline assertion.
node transformer-k-proof.cjs
node run-regression.cjs --matrix --output /tmp/archcanvas-spine-proxy-matrix
```

The geometry-only replays are explicitly diagnostic and do not certify
unrouted graphs. Routing certification comes from the 51-stage actual matrix.
No Python model source was imported or executed.
