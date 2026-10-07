# Authored browser final readback

This is a read-only review of root's new browser captures and stored formal
working copies. It does not rerun frozen tests/builds, operate the browser,
execute model code, install dependencies or overwrite raw/previous receipts.
The prior browser-source-readback directory remains frozen and unchanged.

The stored Draft envelope is storage revision 1; draft revision 16, ID
draft-859cef62-6bbe-45c6-a166-b5f519d7e600. Its four nodes and three exact edge IDs
form Input → Linear → ReLU → Output. Final arranged positions are (50,70),
(298,70), (546,70), (794,70). The arranged and reopened raw SVG bytes are exact.
Node IDs, labels/kinds, card dimensions, positions, port ownership/circles,
visible/hit routes and each endpoint agree with stored Draft bindings.

The first from-zero-complete raw state contains four nodes and only one edge.
It is incomplete and is not counted as successful connection creation. The
rapid-batch cause remains undetermined. Subsequent snapshots show 4/2 then 4/3;
arranged/saved/reopened captures show the complete 4/3 graph. The immediate
reopened DOM reports a transient checking/disabled state, while its SVG is
already the exact persisted graph; the later generation-review DOM says the
saved Draft was reopened and statically checked. The getAttribute outerHTML null
capture-tool misuse is not treated as a product failure.

Draft input declaration is float32 with shape [1,16]. Linear declaration is
in_features=16, out_features=32, bias=True; ReLU and Output parameters are empty.
[1,32] is a deduction from these declaration rules, not a runtime shape result.
The independent AST review in source-review-subagent.json confirms the generated
constructor parameters, call order and named output. The fresh 655-byte source
under formal managed project d0af06253a654c978020939ad5fe717d matches the saved IR
embedded source bytes and direct SHA256
2859912da710c0b5384cb0d582c520b3d50af102723b9b1f8760e826de71da77.
Source/IR digests independently recompute to the stored values. Model code was
read as text/AST only; no torch/model import or numerical execution occurred.

The actual saved generated Canvas is storage revision 1 / Canvas revision 0,
ID canvas-architecture-model.AuthoredModel-d97a0e89743e-7a326f80. Its complete
canonical IR is five nodes/four edges because it includes the root Module and
Input→root relation. Its computational leaf graph remains four nodes/three
edges; the public figure displays the root plus four leaf nodes and exactly
edge:1/2/3, with edge:0 accounted as hidden. Source/IR digests are
d97a0e89743eb8602c37980bcbff81b7feabe341b23558cafe5c4c6a272e15b9 and
7a326f80a1612aee98f4aff656b4b3e1ec2a5c3b7a0856cf982e6e2d88fc8c47.
Saved Canvas renderer replay matches public generated SVG cards, circles,
paths, styles and metadata. Canonical coverage and initial Draft display labels
are retained, and no strict crossings or overlaps occur in this simple figure.

Input shape is not encoded/inferred in the generated Python signature or static
IR Input parameters. The Linear dtype expression torch.float32 is deliberately
retained as unknown origin in the static IR. This review does not certify
runtime shape, numerical dtype, training behavior or full execution equivalence.

Final public capture still references index-au3IB_0Q.js and index-B6WbMowt.css;
their current bytes match the frozen au/B6 hashes. Both reviewer executions
retain argv/stdout/stderr and exact before/after input bindings. The independent
source subagent binds its six inputs and reports them unchanged. No source,
model, tests, build or raw capture was edited by this review.

This authored Draft's saving, reopening and generated working-copy success is
specific to that path. Its initial generated labels do not establish imported
Canvas alias editing/reopen behavior. This round contains no new complete visual
matrix or human review and does not turn a screenshot into publication clarity
acceptance.
