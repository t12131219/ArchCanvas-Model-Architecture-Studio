# Independent nominal SVG geometry review

21 literal SVG artifacts; 33 input hashes unchanged. No product geometry/router imports.

| Input | Routes | Endpoints | Endpoint violations | Stack hits | Body hits | Header hits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| transformer-l0/browser-scene.svg | 12 | 24 | 0 | 0 | 0 | 0 |
| transformer-l0/figure.svg | 12 | 24 | 0 | 0 | 0 | 0 |
| cnn-l0/browser-scene.svg | 7 | 14 | 0 | 0 | 0 | 0 |
| cnn-l0/figure.svg | 7 | 14 | 0 | 0 | 0 | 0 |
| mlp-l0/browser-scene.svg | 2 | 4 | 0 | 0 | 0 | 0 |
| mlp-l0/figure.svg | 2 | 4 | 0 | 0 | 0 | 0 |
| transformer-encoder-detail/browser-scene.svg | 15 | 30 | 0 | 0 | 0 | 0 |
| transformer-encoder-detail/figure.svg | 14 | 23 | 5 | 0 | 0 | 0 |
| transformer-encoder-detail/preview.svg | 14 | 23 | 5 | 0 | 0 | 0 |
| transformer-moves/before.json | 12 | 24 | 0 | 0 | 0 | 0 |
| transformer-moves/right.json | 12 | 24 | 0 | 0 | 0 | 0 |
| transformer-moves/left.json | 12 | 24 | 0 | 0 | 0 | 0 |
| transformer-moves/up.json | 12 | 24 | 0 | 0 | 3 | 0 |
| transformer-moves/down.json | 12 | 24 | 0 | 0 | 0 | 0 |
| transformer-moves/right-undo.json | 12 | 24 | 0 | 0 | 0 | 0 |
| transformer-moves/left-undo.json | 12 | 24 | 0 | 0 | 0 | 0 |
| transformer-moves/up-undo.json | 12 | 24 | 0 | 0 | 0 | 0 |
| transformer-moves/down-undo.json | 12 | 24 | 0 | 0 | 0 | 0 |
| transformer-moves/down-redo.json | 12 | 24 | 0 | 0 | 0 | 0 |
| transformer-moves/saved.json | 12 | 24 | 0 | 0 | 0 | 0 |
| transformer-moves/reopened.json | 12 | 24 | 0 | 0 | 0 | 0 |

All intersections remain in report.json. Reported warning text never excuses a geometric hit.

This review covers unrounded nominal rectangles and route centerlines only. It does not establish stroke, arrowhead, glyph or raster clearance; four representative cases are not a full matrix or human acceptance.
