# Stage 2 Acceptance: Tier A Source Recovery

Status: complete.

Stage 2 provides source-hash-locked static adapters for Transformer, Autoformer, iTransformer,
PatchTST, and TimeMixer, plus a pattern-free generic fallback. Analysis never imports or executes a
fixture project.

Automated contracts cover all corrections in specification section 17:

- Transformer L3 attention, mask, cross-memory, Post-LayerNorm residuals, and logits;
- Autoformer correlation, progressive decomposition, active mask semantics, and trend/season flow;
- iTransformer inverted variable tokens, encoder-only path, config predicates, and covariate trim;
- PatchTST patches, channel independence, positional encoding, true flattened head, and dual path;
- TimeMixer scale construction, bidirectional season/trend mixing, per-scale prediction, and merge.

Every profile emits source snapshot, Exact IR, six ledgers, semantic overlay, pattern receipt,
source-correction report, skipped runtime receipt, and analysis receipt. Independent validation
reloads source/evidence bindings. Pattern receipts prove the Exact IR digest is unchanged by semantic
annotation.

`--no-pattern-packs` bypasses every source profile. All five fixtures still pass source identity and
semantic closure through generic operators and explicit `opaque_composite` boundaries, without
running a profile-specific semantic gate.

Destructive mutation tests cover every profile gate. Source member tampering is rejected against
fixture provenance. Publication compilation, reference-image review, and dynamic frontier visual outputs remain
explicitly skipped until Stage 3.
