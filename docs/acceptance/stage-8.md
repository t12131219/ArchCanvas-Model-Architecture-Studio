# Stage 8 Acceptance: Pattern Packs and Holdout Generalization

## Delivered

- Versioned schemas for Pattern Pack manifests, semantic annotation overlays, match receipts, and
  preview-only candidate reviews.
- A deterministic declarative matcher with fixed structural, dataflow, shape, sharing/control-flow,
  and weak-name stages. Failed hard constraints cannot be rescued by names.
- Five builtin packs covering the existing Transformer, Autoformer, iTransformer, PatchTST, and
  TimeMixer semantic interpretations. Each declares positive, negative, mutation, and digest
  invariance inventory and is exercised by those four automated test categories.
- Explicit digest-locked workspace loading, specificity checks, conflict-to-generic ambiguity,
  duplicate/stale manifest rejection, and refusal to execute third-party `matcher.py` files.
- Session candidate review with match basis, unproven predicates, counterexample risks, preview
  annotations, Exact IR digest invariance, no activation, and denied shell/network/source-write
  permissions.
- Publication and Studio consume a bound overlay as optional semantic metadata while preserving all
  canonical node, tensor, edge, and port sets.
- An unseen `CrossBlendRegressor` holdout with no architecture profile or dedicated pack. Under
  `--no-pattern-packs`, generic static recovery preserves both residual merges and passes source
  identity, semantic closure, L1-L4 publication compilation, and geometry validation.

## Trust and Fallback Evidence

Every analysis writes `semantic-annotation-overlay.json`, `pattern-pack-receipt.json`, and
`pattern-candidate-review.json`. The receipt lists all loaded manifests and structured rejection
reasons. Disabled matching loads no packs into the receipt. Ambiguous matches apply no annotations
and record `ambiguous_pattern`; a candidate match remains preview-only.

Opaque boundaries retain explicit `unresolved_reason`, boundary status, and visual-only capability
metadata. The holdout requires no opaque fallback. Existing unsupported control-flow fixtures are
tested for auditable reasons rather than being filled with familiar architecture assumptions.

## Verification

The Stage 8 suite includes builtin positive/counterexample/predicate-mutation/digest-invariance,
weak-name non-rescue, workspace lock and ambiguity, candidate non-activation, bound publication
metadata, stale-overlay rejection, CLI `--no-pattern-packs`, and holdout semantic/publication/
geometry coverage. Full repository verification also runs pytest, Ruff, `compileall`, exported
schema freshness, the Vite production build, and `git diff --check`.

Final verification collects 107 tests: 104 pass and the same 3 Studio socket tests remain skipped
because the command sandbox denies local socket creation. The real holdout CLI run writes a
disabled Pattern Pack receipt with equal before/after digests, then renders all four generic DAG
views with passed publication and geometry gates.
