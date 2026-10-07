# Next routing step: three concrete cases, two bounded experiments

This is a read-only proposal, not a product change or visual acceptance. The formal BGj2ZBSY L3 projection was recomputed from the exact sealed `transformer-level3-paper-180/canvas.json` (SHA256 `c600fedbdebad397dd73d77cb0863c9106da08aec8cc748be4b80a46b95f2675`). Its complete scene equals the independent Repeat-after scene. An independent path parser, strict intersection calculation and merged-overlap calculation reproduce the ChS advisory's **19 different-tensor overlap pairs / 20 strict crossing pairs** (23 crossing points, 4314.21 total pair-overlap units). These are candidate geometry counts, not a defect classification.

## Cases with a measurable local improvement

| Case | Frozen geometry | Hypothetical improvement | What must remain visible |
| --- | --- | --- | --- |
| `edge:44` memory / `edge:45` target mask | Common horizontal y397 span x684.4–833; overlap length 148.6 | Bring memory from the encoder/decoder middle corridor into its x621.6 port; remove that overlap completely | Both canonical tensor bindings, separate memory/mask styles, port `(621.6,410)` and mask port `(684.4,410)` |
| `edge:44` memory / `edge:46` memory mask | Common horizontal y397 span x747.2–844; overlap length 96.8 | The same memory corridor change removes this overlap completely | Memory and memory-mask are different tensors despite related names; retain separate ports `(621.6,410)` and `(747.2,410)` |
| `edge:58` residual / `edge:57` memory mask and `edge:59` cross-attention result | Residual currently wraps around x754, crossing the mask and final data approach | A left corridor x520 removes both selected different-tensor crossings; it adds one crossing with memory `edge:55`, yielding net strict pairs 20→19 | Residual endpoint `(655.3,734)→(590.7,872)`, both source consumers and every data/memory/mask binding |

The first two cases are one memory experiment. Move the existing long memory lane while keeping its source lead and target gate, rather than rebuilding its full path. The pointwise candidate is:

`edge:44: M 237 2772 V 2785 H 462 V 397 H 621.6 V 410`

The full-scene counts become overlap pairs **19→17**, overlap length **4314.21→4068.81**, strict pairs remain **20**, strict points remain **23**, disjoint strict pairs **17→16**. Memory route length falls **3265.4→2798.6**, and independent nominal-body/header penetration is zero. This removes three old crossing pairs and adds three other pairs (`43/44`, `44/47`, `44/51`): the aggregate benefit must not conceal that exchange. The path is an experiment, not a pairwise-monotone guarantee.

Changing only `edge:44` also adds a same-tensor crossing against `edge:55`, despite preserving their 6-unit common source stub. Prefer a bounded **shared-source memory-family** candidate when canonical source, role and style all agree:

`edge:44: M 237 2772 V 2778 H 467 V 397 H 621.6 V 410`

`edge:55: M 237 2772 V 2778 H 467 V 766 H 623 V 772`

Both use the exact `encoder.1.feedforward_norm` canonical output, declared tensor, memory role and appearance. This retains every edge/port and provides a common 2248-unit trunk without the added same-tensor crossing. Its different-tensor counts match the single-memory experiment, the combined memory length falls by 480.8 units, and nominal penetrations remain zero. The longer visible shared trunk requires an actual publication-pixel review before choosing it. No renderer junction semantics are implemented by this proposal.

The third case uses:

`edge:58: M 655.3 734 V 747 H 520 V 859 H 590.7 V 872`

Residual length falls **400→344**, with no body/header penetration and fixed endpoints. The different-tensor count improves, but a same-tensor crossing against data `edge:54` appears at its fanout. Their roles/styles differ. This candidate is **conditional**, not a recommended automatic acceptance: a broad same-tensor exemption must not hide the readability cost at the split. Combining it with the single-memory experiment yields 17 overlap / 19 strict crossing pairs, but still carries both fanout qualifications. Begin with the memory-family experiment; keep the residual option as a separately reviewed follow-up.

## Small implementation scope

Keep the existing clear-path/body checks, endpoint-normal validation, global monotone crossing/overlap counts and fixed work caps. Extend candidate generation with a bounded replacement of one long interior vertical lane while retaining its original source/target gate vertices. Derive alternate lanes from the endpoint ancestors' adjacent regions and their reserved outline rectangles; evaluate one or two relevant side corridors before the nearest-coordinate generic list. Do not hardcode Transformer edge IDs or these page coordinates.

Current candidate generation explains why these alternatives are missed: in a geometry-only reconstruction, memory `edge:44` ranks 9th and residual `edge:58` 15th by pressure, beyond the cap of 8 refined routes. The current usable ancestor-side lane x468 ranks 79th for memory; residual's x520 ranks 37th. Both fall outside the nearest 24 axis coordinates. These are reconstructed rankings, not runtime instrumentation or a timing claim. Reserve at most two prioritized, body-clear corridor proposals per selected route/family under the existing overall candidate budget; avoid simply raising every cap.

The common-source family variant is an additional small, typed grouping option. Group only exact canonical source node/port + exact tensor + same role and effective appearance; preserve every original edge and destination. Different display sides, different roles, different styles and unresolved proxy bindings must not be merged. Source/target stubs and final circles must remain matched. Do not auto-merge residual/data routes merely because their tensor IDs agree.

Naive mask lane separation is an explicit negative result: moving source-mask `edge:7` or `edge:11` to x58 and staggered gates eliminates five overlap pairs but raises strict pairs to 25 or 24. Moving `edge:29`'s arrival gate removes one overlap but raises strict pairs to 21. The current protected-count acceptance must reject all three. A bounded ±24-unit single-lane search found no strict-count improvement; this is a limit of that search, not a proof that the diagram has no better routing.

## Independent oracle and acceptance expectations

Use a separate parser/intersection/interval-union oracle and SVG parsing, not router functions, for expected results. Check the two named overlap spans disappear, full-scene protected counts do not rise, the exact crossing-pair exchanges are reported, and total length/bends/reversals do not degrade. Compare same-tensor and differing-role/style fanout separately; canonical output equality alone cannot justify a new invisible junction.

Negative controls should hide/delete a branch, retarget one canonical binding, coherently move the public circle and route endpoint together, move through a backplate/header, split intervals to distort overlap length, or exchange an overlap for more crossings. They must be rejected even if one headline count improves. Positive controls retain same-source/style shared trunks and mere point contact. Verify every canonical edge/tensor/role/style, all port coverage, source/IR digests, Canvas input bytes, manual/pinned anchors, expand/re-expand local geometry, move preview/commit/undo/redo, whole/detail SVG agreement and deterministic repeated projection.

Validate all nine frontiers and relevant detail exports before a browser comparison. Inspect the complete figure plus the exact local fanout/crossing regions at 85/180 mm, in paper/monochrome output. These read-only coordinate experiments cannot certify aesthetics, physical readability, participant/native provenance, human acceptance or performance.

## Work evidence

`candidate-experiments-final.json` is the final sorted experiment report. The v1/v2 reports preserve rejected options; the v3 staging report was recomputed while importing the exploratory module for the ranking reconstruction, changing only unordered pair-report presentation, not metric values. The final report records this staging regeneration and does not claim the earlier v3 byte hash remains current. Product, dist, old matrix evidence and all selected source inputs are bound in the final readback receipt.
