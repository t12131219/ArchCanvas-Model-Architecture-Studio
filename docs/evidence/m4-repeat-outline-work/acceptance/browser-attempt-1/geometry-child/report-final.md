# Independent nominal SVG geometry review — completed hierarchy projection

No endpoint/ray-union/stack/backplate geometry violations in this bounded sample. One explicit blocked up-move edge retains 3 non-stack card intersections; no full-matrix or human acceptance claim.

21 SVG artifacts; 229 route observations; 458/458 endpoints verified. 36 input hashes unchanged.

| Input | Routes | Endpoints | Endpoint violations | Stack / backplate hits | Card hits | Header hits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| transformer-l0/browser-scene.svg | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| transformer-l0/figure.svg | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| cnn-l0/browser-scene.svg | 7 | 14 | 0 | 0 / 0 | 0 | 0 |
| cnn-l0/figure.svg | 7 | 14 | 0 | 0 / 0 | 0 | 0 |
| mlp-l0/browser-scene.svg | 2 | 4 | 0 | 0 / 0 | 0 | 0 |
| mlp-l0/figure.svg | 2 | 4 | 0 | 0 / 0 | 0 | 0 |
| transformer-encoder-detail/browser-scene.svg | 15 | 30 | 0 | 0 / 0 | 0 | 0 |
| transformer-encoder-detail/figure.svg | 14 | 28 | 0 | 0 / 0 | 0 | 0 |
| transformer-encoder-detail/preview.svg | 14 | 28 | 0 | 0 / 0 | 0 | 0 |
| transformer-moves/before.json | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| transformer-moves/right.json | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| transformer-moves/left.json | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| transformer-moves/up.json | 12 | 24 | 0 | 0 / 0 | 3 | 0 |
| transformer-moves/down.json | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| transformer-moves/right-undo.json | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| transformer-moves/left-undo.json | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| transformer-moves/up-undo.json | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| transformer-moves/down-undo.json | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| transformer-moves/down-redo.json | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| transformer-moves/saved.json | 12 | 24 | 0 | 0 / 0 | 0 | 0 |
| transformer-moves/reopened.json | 12 | 24 | 0 | 0 / 0 | 0 | 0 |

The exact-ID first pass remains intact. Ten target observations (five in preview and five in detail export) use the independently checked nearest visible collapsed ancestor: query/key/value become EncoderLayer x; attn_mask becomes EncoderLayer mask. Canonical hidden endpoint IDs remain in SVG metadata.

Up edge:7 is explicitly blocked in the DOM. Its horizontal segment crosses source embedding by 97 units and target embedding by 194 units; its terminal segment crosses source embedding by 3 units. These are 3 segment/rectangle hits across 2 card bodies, zero Repeat or backplate interiors. Other four-direction movement states, undo states, redo/save/reopen states have no nominal card/header/stack intersections.

SVG public node geometry, public port identities/owners/centers, and route point arrays match exactly for three whole-scene interactive/static pairs, detail preview/export, and down versus redo/save/reopen.

Nominal unrounded rectangle interiors and route centerlines only: stroke, glyph, arrowhead, rounded-corner, raster and screenshot visibility claims are outside scope. This is four representative cases, not a full matrix or human acceptance.
