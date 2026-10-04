# Formal local Alpha runtime, M2 and first M3 fragment

The formal project now contains an independently written visual Alpha. The Skill distribution still contains instructions only: copying this Skill does not copy or install the runtime. Resolve the actual checkout or installation before using these commands.

From the formal project root:

```bash
PYTHONPATH=src python -m archcanvas_cli capabilities
PYTHONPATH=src python -m archcanvas_cli --help
PYTHONPATH=src python -m archcanvas_cli analyze --root fixtures/transformer --entry model:Transformer --output /tmp/archcanvas-transformer.json
```

`analyze --root PATH --entry module:Class` produces Architecture JSON. `analyze --source FILE --entry Class` handles an explicit single file. The stdlib AST frontend never imports or executes model code. Unsupported dynamic structures remain opaque. This Alpha has no concrete shape inference or runtime observation. M2 registers `set_dropout_probability` for an explicitly authored float literal in PyTorch Dropout `p` or MultiheadAttention `dropout`; configuration references, derived values and integer source literals remain unsupported.

The first M3 fragment registers `rebind_input` through HTTP and `TransactionManager.prepare_rebind`. Its source proof requires a directly authored entry-root straight-line forward, uniquely assigned values, one positional `Name` input per pure Identity/Dropout/ReLU/GELU call, and a dominating producer with the same base input. The source-bound sidecar names the exact argument span, current binding and candidates. Compatibility is conditional symbolic shape/dtype preservation if the actual input is accepted by all registered operations; no model execution, numerical equivalence or actual dtype/shape is proven. Inspect `supportedIntents` and `rebindScope`. In-place operations, unknown side effects, import-time monkeypatches, control flow, nested/shared authored scopes, keyword inputs, aliases, reassignment and different input origins are outside this fragment.

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

Explicit Save persists the CanvasDocument through a storage version guard. Refresh reopens a matching saved source snapshot. Undo/redo history belongs to the active browser session; the persistent canvas retains the visual result and revision. Current SVG export consumes that same edited scene and excludes editor controls. PDF/PNG derive from the same SVG through the optional project-local CairoSVG dependency; inspect `publicationExport` before invoking them. Cross-harness end-to-end certification remains absent.

The export dialog generates current-scene files and bound receipts with view/download links; downloads depend on the host. A local checkout can export a saved document using `node scripts/export_canvas.mjs --document PATH --output FIGURE.svg` (Node 24+). Add `--format pdf` or `--format png --dpi 300`, with `--python /absolute/formal/project/.venv/bin/python`, when that explicit interpreter reports a usable converter. This imports the same formal TypeScript scene/renderer as Studio, emits the current edited output and a digest receipt, and does not re-analyze model source. Receipts name the converter module, native Cairo version and interpreter. The shared Scene font prefers Noto Sans CJK SC; PDF/PNG reject detected missing host Cairo glyphs and record coverage. Cross-host shaping, font family fidelity and complete embedding are not certified.

The local service registers imported source corpora as managed working copies. Its parameter prepare action re-analyzes that registered source, verifies both source/IR bindings, prepares an isolated single-file token change, and returns the actual diff and affected calls. Approve binds the exact review digest; commit verifies an unconsumed signed approval, corpus/staging freshness and journal/backup before replacement. HTTP changes affect the managed copy, not the imported original directory. A successful managed-copy commit does not mean a user's original file was written.

The formal CLI implements `patch prepare|review|approve|commit|discard`. Every action requires an explicit `--root`, `--entry` and project-private `--store`; inspect each action's actual `--help`. Prepare requires `--node`, `--parameter`, `--value` and `--base-source-digest`; subsequent actions use `--transaction`. Approve requires the exact `--review-digest` shown to the human; commit requires its unconsumed `--approval-id`. CLI commit writes the explicitly bound source root, so verify that path and the concrete user approval first. The Python `TransactionManager` API shares these guards. Do not treat browser managed-copy completion as approval to write the original user root through CLI.

After commit, use the returned re-analysis to reconcile only uniquely matching visual identities. Visual undo is not source rollback. Review the concrete diff with the human for real model changes; test approvals in `/tmp` acceptance projects do not authorize future model edits.

For implementation evidence and limits, consult the configured formal checkout's `README.md`, `docs/capability-matrix.md`, `docs/acceptance.md`, `docs/stage2-oracle.md` and `docs/stage3-oracle.md`. The independent release check is `python scripts/check_independence.py --build`; M2 adds `python scripts/check_stage2.py --build --python /absolute/formal/project/.venv/bin/python`, and the first M3 fragment adds `python scripts/check_stage3.py --build --python /absolute/formal/project/.venv/bin/python`. Receipts record actual package paths, an isolated source copy, `/tmp` parameter/rebind tests, exact source changes, re-analysis and same-scene output. These checks do not establish three-host discovery, full M3 runtime profiles or complete publication quality.
