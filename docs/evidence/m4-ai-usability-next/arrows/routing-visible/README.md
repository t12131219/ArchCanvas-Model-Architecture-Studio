# Routing-visible build scope

This scope supersedes the historical `index-DgtJrWU9.js` UI build. Root's actual
browser inspection found that the layout hint existed in DOM but was clipped by
the scrollable canvas viewport, so DOM presence did not prove visibility.
The root UI repair moves the hint to a sibling of `canvas-viewport`, inside the
relative `main`, at `top:95px` with a bounded scrollable height. No core source
changed.

The old `../frozen-final/` source/dist, CPU evidence and review artifact hashes
remain preserved. Its name records the earlier freeze, not current UI acceptance.
The 13 archived/current core files match byte-for-byte, so the earlier 39 CPU SVGs
and the separate 39 whole plus 32 detail geometry audit remain valid for this
core. This does not transfer old UI, browser, human, timing or publication
coverage to the new build.

`manifest.json` freezes 47 formal product files after another 102/102 Studio test
run, strict TypeScript exit 0 and production build exit 0. It records actual
browser visibility as pending. Root maintains new browser screenshot/performance
evidence separately; opening/building the product or this receipt cannot certify
that evidence.

| Frozen file | SHA-256 |
| --- | --- |
| `studio/dist/assets/index-C7L6p5cl.js` | `64f2f29556a0c43e5daef58ca2f46656ec8aa1cffa897326dbaf86d5d3c7eee2` |
| `studio/dist/assets/index-DZv0mPTR.css` | `849aaf8ad3ed6ab6f27d6d33a18dc0fe8910de00832647aca09b135e11a29211` |
| `src/archcanvas_python/frontend.py` | `ce7f7f733da28cb31ecff80ca029a53094e88f8451bffc3874f8167f80a07d00` |
| `manifest.json` | `876a299a7dda7502b8745e812bcab5555b55d116585e233018de1d069ba91dd2` |

The historical narrative [m4-arrow-routing-audit.md](../../../../m4-arrow-routing-audit.md)
and its bound review hashes are unchanged. This README supplies the newer UI
scope without rewriting historical results. M4 remains open.
