# Recovered historical artifacts

These 13 files were recovered byte-for-byte from `/tmp` on 2026-10-07. The [manifest](manifest.json) records each original path, timestamp, SHA256, size and evidence classification. No browser session was operated during recovery.

## Distinct evidence chains

- `blank-continuity/canvas.json`: saved CanvasDocument titled `从零连续模型`, with 4 nodes, 3 edges and storage revision 1.
- `custom-ui/draft.json`: saved draft titled `自定义双路模型`, with 8 nodes, 8 edges, one PairFusion definition and two instances. Its named inputs are `left`/`right`; outputs are `output_1`/`output_2`. The managed project beneath `custom-ui/managed/` contains the generated source for that draft. This chain uses module digest prefix `125ef9d`.
- `backend-fixture/`: earlier static preview/generation fixture. It uses a different source digest and custom identity, prefix `3675543`. Its backend result cannot be substituted for the UI draft's interaction sequence.
- `unbound-crop/transformer-canvas-crop.png`: an 833 × 420 cropped Transformer canvas. It has no browser chrome, URL, asset binding or action context; it is only an unbound visual sample.

## What these files establish

Persisted state and generated source exist. The custom draft contains two repeatable instances and named multi-input/multi-output connections. The source files can be inspected without executing the model. The recovery does not establish which browser actions produced the files, that the current build produced them, or that the complete viewport looked correct.

## Remaining gaps

- Current source snapshot and rebuilt asset SHA binding, browser URL/session and operation journal.
- Four-direction moves, hierarchy collapse/reopen, complete view/edit roundtrips and generation-failure retention.
- Floating legend behavior through pan/zoom/fit, legend edits and export omission.
- A saved CanvasDocument and SVG/PDF/PNG exports for the custom UI model.
- Current complete viewport captures covering overview and detail routing.

M4 real participants remain 0 and publication-size human review remains unconfirmed. These files do not change that status.
