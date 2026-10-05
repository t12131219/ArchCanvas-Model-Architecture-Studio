# Capture-copy helper contract

`scripts/prepare_hierarchy_matrix_capture.py` processes bytes an operator already saved through the actual browser. It never controls the browser, generates a screenshot, makes an export request, replaces a stale URL, or grants human acceptance. It does not alter the product/build or old frozen evidence.

For each case, use the current 8896 Studio to set the declared frontier and page, save the Canvas, export the whole document as SVG, and **read that case's current direct link after export completes**. Save the actual final DOM observation, SVG outerHTML and native screenshot. A direct link from a previous case is not accepted even if one could find a newer matching export on disk.

The raw input format is shown in `helper-observation-template.json`. Obtain each populated field from the actual current browser. `documentBinding` comes from the visible SVG attributes and metadata. `pageSpec` comes from the current page DOM/control values. `expandedIds` comes from the `.publication-scene` attribute. `camera` records `.paper` transform and SVG `getBoundingClientRect()`. `loadedBuildAssets` records actual loaded script/stylesheet paths and URLs. `studioUrl`, export URL, capture time, user agent, viewport and DPR are observations. Browser version, hardware and resolved font bytes remain null/empty when unknown; a system inventory cannot substitute for browser observations.

The helper accepts exactly the artifact ID in `actualExport.observedUrl`. It reads that directory's actual `document.json`, `figure.svg`, `figure.svg.receipt.json` and the actual document store file. The export document must equal the saved envelope's `document` in **every field**. Source, visual revision, width, preset, complete expansion frontier and observed SVG metadata must agree. Each input is read as one frozen byte sequence, bound to SHA256 and rechecked before the output directory is renamed. Failure preserves inputs and does not attempt a fallback.

Example commands (replace the case and raw file paths with the actual saved case):

```bash
.venv/bin/python scripts/prepare_hierarchy_matrix_capture.py case \
  --matrix .archcanvas/browser-visual-matrix-hierarchy-final \
  --store .archcanvas/m4-hierarchy-matrix/documents \
  --raw docs/evidence/m4-hierarchy-matrix-work/raw/<case>/dom-observation.json \
  --browser-scene docs/evidence/m4-hierarchy-matrix-work/raw/<case>/browser-scene.svg \
  --screenshot docs/evidence/m4-hierarchy-matrix-work/raw/<case>/screenshot.jpg \
  --output docs/evidence/m4-hierarchy-matrix-work/cases/<case>
```

This produces copied actual artifacts and an **unstamped** `screen-receipt.json`, plus the original raw input, saved envelope, retained unstamped screen receipt and copy bindings. It supplements observed build URLs with hashes from the verified frozen local build files. That linkage does not claim browser response bytes were downloaded or independently hashed in the browser.

When subsequent case saves will replace the same live store file, the operator can copy the actual known `--store/<documentId>.json` bytes during DOM collection into the case's raw directory and supply `--saved-envelope <snapshot-path>`. The copy must retain the envelope bytes unchanged. The operator also writes `<snapshot-path>.receipt.json` with exactly `{observedSourcePath, snapshotPath, copiedAt, sha256, bytes}` and places the same object in the raw DOM file's `actualStoredEnvelope`. `copiedAt` must include a timezone; source and snapshot paths must resolve respectively to the declared store/document and the exact `--saved-envelope` argument. The SHA256 and byte count must match the frozen snapshot. Absolute and relative paths are accepted (relative paths use the helper command's working directory).

```bash
# Optional addition to the case command above; the raw file and sidecar
# must already contain the actual copy observation and exact byte hashes.
--saved-envelope docs/evidence/m4-hierarchy-matrix-work/raw/<case>/actual-document-store.json
```

This branch compares the snapshot's complete Canvas to the exact linked export, without requiring the live store to retain that earlier case. It retains the snapshot and sidecar bindings and performs no scan or replacement. A snapshot receipt is an **operator declaration of a direct file copy**, not independent certification of native provenance. Omitting this option retains the strict live-store equality check.

The root operator then performs the existing, separate hash step:

```bash
.venv/bin/python scripts/browser_visual_matrix.py stamp-hashes \
  --receipt docs/evidence/m4-hierarchy-matrix-work/cases/<case>/screen-receipt.json \
  --screenshot docs/evidence/m4-hierarchy-matrix-work/cases/<case>/screenshot.jpg \
  --browser-scene docs/evidence/m4-hierarchy-matrix-work/cases/<case>/browser-scene.svg
```

Once actual cases have been copied and stamped, prepare the collector's input list:

```bash
.venv/bin/python scripts/prepare_hierarchy_matrix_capture.py index \
  --matrix .archcanvas/browser-visual-matrix-hierarchy-final \
  --cases docs/evidence/m4-hierarchy-matrix-work/cases \
  --output docs/evidence/m4-hierarchy-matrix-work/captures.json
```

The index refuses changed copied bytes, changed observation fields, unstamped hashes and duplicate case/baseline IDs. It does not execute formal collection; only the existing `browser_visual_matrix.py collect` reconstructs the complete interactive scene and independently checks publication bytes. Neither helper consistency nor formal collection proves native pixel content, aesthetics, physical readability, human participants or sustained presented performance.

The helper implementation self-check uses synthetic local inputs solely to test copy/rejection behavior. It is not a matrix capture or browser provenance receipt.
