# PatchTST entry-proxy regression: frozen v18 browser check

This is the detailed-only case `28c0565ef37d1aff`, not the separate PatchTST overview preset `04d820631d2261bc`. A disposable Chromium context expands `patch_encoder`, `patch_layer1` and `patch_layer1_attn_res` through the actual same-origin bridge. Model Python is not imported or executed. These supplemental runs are functional and geometry evidence, not clean latency measurements.

Both stages pass source/layout/non-draft edge validation, have zero recorded routing contacts and exact unrelated overlaps, and retain the same recursive source-authority hash. No browser runtime errors occurred. All 11 served resource hashes match the other frozen v18 browser reports; see `../final-v18-browser-audit.json`.

The actual three changed node rectangles now exactly match the earlier v14 projection captured in `../spine-proxy-regression/input-geometry-difference.json`:

| Node | x | y | w | h | Center x |
| --- | ---: | ---: | ---: | ---: | ---: |
| `patch_layer1_attn_res` | 344 | 1298 | 1282 | 310.12 | 985 |
| `patch_layer1_attention` | 818 | 1498.12 | 330 | 84 | 983 |
| `patch_layer1_attnadd` | 967 | 1396.5 | 32 | 32 | 983 |

All six affected route gate sets retain v14 frame, side, fraction, order and direction; the derived gate coordinates also match v14. The erroneous v16 +2 x shift is removed. This does not imply that every nested frame shares one center: the parent layer center is 987, residual frame center is 985, and its source content center is 983, as in the correct reference projection.

The final stage has 20 nodes, 26 edges, length 5,973.29, 28 bends and one unrelated segment crossing. The full Studio screenshot and native boundary closeups were inspected. The check confirms restored placement and valid source gates, not universal absence of crossings or equivalence to a fully expanded source graph.

```bash
node studio/scripts/inspect-preview-vae-layout.mjs --case 28c0565ef37d1aff --steps patch_encoder,patch_layer1,patch_layer1_attn_res --closeups patch_layer1,patch_layer1_attn_res --output-dir docs/evidence/preview-generalization-20261014/recheck-patch
```
