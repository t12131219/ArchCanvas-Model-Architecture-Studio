# CNN default layout candidates

This is a read-only design comparison, not a product edit or browser acceptance. Root observed the actual current Studio at 1280 × 720; its public draft SVG rectangle was 815 × 535.5. The original CNN had eight nodes in a 1912-unit horizontal row, fitting at 39.73%; the 13-unit titles were approximately 5.16 CSS pixels. Root's screenshot is retained at `../../m4-move-recovery-presets-browser/session-2/cnn-preset-observed-later.png`.

`compare-layouts.mjs` obtains the actual formal catalog without executing a model, inserts the actual CNN preset, and changes only its candidate positions. It calls the actual `draftRoutes` implementation, then independently checks public rectangular card bodies and route segments. The fit calculation includes node/route extents, the existing 32-unit margins and 30-pixel viewport allowance. All eight nodes, their parameters and all seven bindings are retained.

| Candidate | Calculated fit | Title CSS pixels | Bends | Body hits | Strict crossings | Positive-length overlaps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Original one row, 248 spacing | 39.73% | 5.16 | 0 | 0 | 0 | 0 |
| Two forward rows, 248 × 180 | 78.82% | 10.25 | 4 | 0 | 0 | 0 |
| Two forward rows, 224 × 180 | 84.96% | 11.04 | 4 | 0 | 0 | 0 |
| Two forward rows, 224 × 154 | 84.96% | 11.04 | 4 | 0 | 0 | 0 |
| Three forward rows, 248 × 154 | 100% | 13 | 8 | 0 | 0 | 0 |
| Three forward rows, 224 × 154 | 100% | 13 | 8 | 0 | 0 | 0 |
| Two snake rows, 224 × 180 | 84.96% | 11.04 | 16 | 0 | 0 | 2 |
| One vertical column, 154 spacing | 40.70% | 5.29 | 28 | 0 | 0 | 0 |

Recommend two forward rows with column spacing 224 and row spacing 180. Input, Conv2d, ReLU and MaxPool2d occupy the first row; AdaptiveAvgPool2d, Flatten, Linear and Output occupy the second. The 48-unit horizontal card gap preserves the existing input-left/output-right ports. Six edges remain straight, and one external return corridor makes four turns to enter the second row from the left. Independent checks found no node overlap, card-body intrusion, strict segment crossing, positive-length segment overlap or U-turn. The 80-unit row gap gives more space than the equally scaled 154-row candidate. Three rows would improve title size to 13 pixels while doubling the return turns; reverse-flow and vertical layouts add much more bending with the existing horizontal ports.

The generated SVG/PNG files are approximate standalone candidate illustrations, not Studio screenshots. The SVG contains actual labels and routes, but CairoSVG's rasterization showed missing Chinese font glyphs. Do not use these PNGs to certify Chinese typography, browser styling or final readability; root must inspect a newly built real Studio if the product coordinates change. Port labels at the recommended fit are approximately 7.65 pixels and remain a readability limit.

`comparison.json` and eight candidate drafts contain the exact coordinates and routed points. `source-snapshot` preserves the sampled formal source bytes. The first command failed before sampling because of an incorrect import depth; `attempt-1-failure.md` records it. The corrected command exited 0. No generic arrangement, router, source generation or model semantics were modified for this comparison.
