# Frozen v14 contact diagnostic replay

This directory adds contact and T-touch measurements to the archived v14 routing baseline. The original archived reports and runtime remain unchanged. `wire-contact-metric.js` copies the production geometry helper into the separate `ArchCanvasContactMetric` namespace; it does not replace the baseline router or any routing predicate. Its origin and SHA are recorded in `metric-helper-origin.json`.

Run from `studio/`:

```bash
node scripts/check-preview-frontiers.cjs --phase standard --include-historical --concurrency 1 --timeout-ms 90000 --runtime-dir ../docs/evidence/preview-generalization-20261014/pre-v15-v14-final/frozen-runtime --contact-metric-helper ../docs/evidence/preview-generalization-20261014/baseline-v14-contact-audit/wire-contact-metric.js --output ../docs/evidence/preview-generalization-20261014/baseline-v14-contact-audit
node scripts/check-preview-frontiers.cjs --phase mixed --selection ../docs/evidence/preview-generalization-20261014/final-mixed-selection.json --single-limit 2 --concurrency 1 --timeout-ms 90000 --runtime-dir ../docs/evidence/preview-generalization-20261014/pre-v15-v14-final/frozen-runtime --contact-metric-helper ../docs/evidence/preview-generalization-20261014/baseline-v14-contact-audit/wire-contact-metric.js --output ../docs/evidence/preview-generalization-20261014/baseline-v14-contact-audit
node scripts/verify-preview-baseline-replay.cjs
node scripts/compare-preview-frontier-quality.cjs --baseline ../docs/evidence/preview-generalization-20261014/baseline-v14-contact-audit
```

The standard run returns nonzero for existing historical failures. A completed report, every unchanged runtime/helper hash and the replay integrity receipt establish whether the replay itself succeeded. `routing-replay-integrity.json` compares all seven original quality metrics, every legality result, source and input hash, and layout restoration receipt against the original v14 archive. Timings are excluded.

Each contact/touch comparison is measured on both versions. Missing baseline metrics are explicitly unavailable, never treated as zero. Contacts exclude coincident actual terminal pairs, equal source-value wire identities, and licensed shared presentation. These diagnostics add evidence for review; they do not replace the source/layout/port/overlap validators.
