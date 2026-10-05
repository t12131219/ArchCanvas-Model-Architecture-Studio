# Independent four-direction public SVG audit

This AI QA role checks the user-requested four-direction manipulation task from actual browser artifacts captured by the root agent. It does not operate a browser, execute a model, import product/render/history code, alter product source/build or modify older evidence/seals. It does not count as a human participant or publication reviewer.

`predeclared-protocol.json` establishes the same visible MLP canonical Linear target, right/left/up/down movements, full interactive SVG undo/redo comparison, bound port endpoints and unchanged model facts. Camera pan has a separate three-phase contract: before/panned/reversed. The product keeps camera navigation outside CanvasDocument undo history, so node undo/redo cannot be presented as pan undo/redo.

`check_directional.py` consumes a journal with schema `archcanvas-ai-directional-journal/1`; each case references complete captured JSON SVG (`svgMarkup`, `svg` or `markup`) or actual `.svg` output. It parses XML independently, verifies the complete source/IR/node/binding metadata against DOM objects, finds the visible canonical port for every rendered binding and checks both explicit path endpoints within 0.051 canvas px (path rounding is 0.1px and port rounding 0.01px). Unsupported path commands fail explicitly. Full undo/redo comparisons alter only root `data-revision` and metadata `revision` values. Native input endpoints plus public camera scale permit an independently computed 4px grid terminal delta.

The captured node operation must be one revision and each undo/redo one revision. The same Linear body keeps its dimensions and moves on the intended signed axis; all other visible leaf bodies stay fixed. Enclosing container body changes are reported separately, since the product may grow a parent to contain a moved child. SourceFacts, canonical bindings and node identities must remain exact. Public expanded/pinned membership is checked when captured; absence is reported as missing evidence, not invented from hidden state.

Actual export comparison checks metadata, page geometry, nodes, ports, path/style records and the complete publication appearance tree. Only documented interaction presentation differences are normalized: node `role/tabindex`, expand/collapse controls, port hit circles and drag-instruction titles, and the 30px expanded-repeat badge shift when the control is absent. An export path without its actual transport receipt establishes byte comparison only; no browser download claim is invented.

The geometry summary separately reports leaf rectangle overlaps, leaf bodies invading the visible horizontal header band of an expanded container, axis-aligned paths through unrelated leaf bodies, proper nonshared path crossings and bodies outside viewBox. It excludes ordinary container containment, collinear overlap, shared-owner intersections, actual glyph text, strokes and arrowhead size. Zero narrow findings is not an aesthetic pass, complete no-crossings proof or publication certification. Actual screenshot review remains separate.

`test_directional.py` contains 20 independently authored counterexamples for wrong direction, incomplete phases, unrelated leaf motion, stale source, detached endpoint, unsupported curve, snapped endpoint mismatch, undo/redo drift, excessive revision change, camera reversal, header intrusion findings and stale/styled exports. These are checker tests, not added Studio product tests. Current logs are in `checker-tests.txt`.

The partial reports bind only artifacts available when generated. Later final journal/report paths must be explicit; a partial report must not be described as four-direction completion. Run:

```bash
python -m unittest discover -s docs/evidence/m4-ai-usability-next/gesture -p test_directional.py -v
python docs/evidence/m4-ai-usability-next/gesture/check_directional.py JOURNAL --output REPORT
```
