# Native Transformer fork and content-axis checks

`report.json` records **12 passing checks** on frozen v16 with no browser runtime errors. Tests use actual pointer drags and native `+` controls in a disposable Studio context. Model Python code is not executed.

Both standard and compact Transformer presets commit an actual 10 graph-unit horizontal move of the overview `enc.norm1` and expanded `enc.norm1.layernorm`. Each move retains exact source bindings and immutable recursive authority, a connected source fork with at least three rays, and valid source/layout/edge constraints. Undo and redo restore exact graph geometry. A rejected/no-op move would fail these tests.

Standard native encoder self-attention expansion has one source-aligned shared Q/K/V trunk: Q and V have four route points, while center K has two. Both source-recorded ancestor gates align to the producer. This verifies the straight-path regression exposed by the broader engine suite.

The compact preset's source reference uses a left-side perimeter corridor with six points per Q/K/V route, so it is not subject to the standard center-straight assertion. Its final mixed frontier has 6 / 8 / 7 points for Q / K / V. The native screenshot was inspected: K retains an extra local elbow around the preceding glyph/caption before entering from below, and V enters the permitted left perimeter. These legal terminal/obstacle detours are a remaining visual difference from the full reference, not exact route equivalence. Source bindings, gate frame/side/direction/order, single producer-wire identity and connected three-ray source fork all remain intact.

`../final-v15-shared-trunks-attempt-1/` preserves the earlier v15 harness attempt. It incorrectly required compact K to be a two-point path, despite the original compact reference being a six-point corridor. The corrected test scopes straightness to the source-aligned standard preset and records the compact point-count difference explicitly. V15 product bytes did not change between its two attempts. The corrected native suite was repeated against frozen v16 and retains the same compact point-count difference.

```bash
node studio/scripts/test-preview-expansion.mjs --phase final --shared-trunks-only --output-dir docs/evidence/preview-generalization-20261014/recheck-shared-trunks
```

The served-resource audit is included in the report. Timings were measured after other CPU verification was released; they are functional evidence and do not replace the uncontended 10-family and VAE latency measurements.
