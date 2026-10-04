# Formal local Alpha runtime

The formal project now contains an independently written visual Alpha. The Skill distribution still contains instructions only: copying this Skill does not copy or install the runtime. Resolve the actual checkout or installation before using these commands.

From the formal project root:

```bash
PYTHONPATH=src python -m archcanvas_cli capabilities
PYTHONPATH=src python -m archcanvas_cli --help
PYTHONPATH=src python -m archcanvas_cli analyze --root fixtures/transformer --entry model:Transformer --output /tmp/archcanvas-transformer.json
```

`analyze --root PATH --entry module:Class` produces Architecture JSON. `analyze --source FILE --entry Class` handles an explicit single file. The stdlib AST frontend never imports or executes model code. Unsupported dynamic structures remain opaque. This Alpha has no shape inference, runtime observation, semantic transaction or source commit API.

For a configured local checkout, build its own Studio and start its own loopback service:

```bash
cd studio
npm ci
npm run build
cd ..
PYTHONPATH=src python -m archcanvas_cli serve --host 127.0.0.1 --port 8765
```

Check the actual JSON startup receipt for the URL and package provenance. Do not assume port 8765 identifies ArchCanvas. Retain the background process/session; opening a browser does not keep a terminated service running.

Studio opens bundled source examples, accepts single-file source text, and loads a validated Architecture JSON via the import dialog. For a multi-file project, analyze its explicit root with the CLI and select the resulting JSON in Studio. Producing JSON alone does not open the interactive document.

Visual operations include aliases, registered glyphs, node/edge colors, moves, pins, in-place hierarchy expansion, legend text/symbol/order, annotations and paper/monochrome page profiles. Direct manipulation and the limited local text commands use the same typed operation history. Text commands target a selected node and support named colors, `命名为…`, expand/collapse and pin. They are not a general language parser.

Explicit Save persists the CanvasDocument through a storage version guard. Refresh reopens a matching saved source snapshot. Undo/redo history belongs to the active browser session; the persistent canvas retains the visual result and revision. Current SVG export consumes that same edited scene and excludes editor controls. PDF/PNG and cross-harness end-to-end certification remain absent.

Browser downloads depend on the host. A local checkout can export a saved document using `node scripts/export_canvas.mjs --document PATH --output FIGURE.svg` (Node 24+). This imports the same formal TypeScript scene/renderer as Studio, emits the current edited SVG and a digest receipt, and does not re-analyze model source.

For implementation evidence and limits, consult the configured formal checkout's `README.md`, `docs/capability-matrix.md` and `docs/acceptance.md`. The independent release check is `python scripts/check_independence.py --build`; its receipt records actual package paths and a standalone copy.
