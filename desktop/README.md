# ArchCanvas Desktop

Stage 6 provides an independent ArchCanvas world/SVG/HTML canvas and a minimal Tauri 2 shell.
The canvas uses the shared warm-white/near-black/blue design tokens, pointer-anchored zoom,
middle-mouse or Space pan, selection, marquee selection, preview-only node dragging and visual-only
snapping. The browser experience starts in an explicitly labelled read-only Transformer fixture
mode, where visual state is stored only in browser storage and the fixture source is never read or
written.

The Tauri client calls the `engine_rpc` command with typed Engine envelopes. One JSONL
`archcanvas_engine.stdio` sidecar remains alive for the window session, so validated in-memory
patch confirmations survive separate RPC calls but not a desktop/Engine restart. A broken session
fails its current request without replaying it; the next request starts a fresh Engine. The bridge
does not read source paths or emulate source access. `CanvasDocument` is visual-only.

For a native development session, configure a Python environment where ArchCanvas is installed and
an Engine-owned cache directory. These values are host configuration, never UI-controlled paths.

```bash
ARCHCANVAS_ENGINE_PYTHON=/path/to/TFB_py311/bin/python \
ARCHCANVAS_ENGINE_CACHE_ROOT=/absolute/path/to/archcanvas-cache \
npm run tauri dev
```

The Open Project dialog only sends user-provided project approval data to `open_project`; Engine
validates the root and entrypoint before it reads source. Source jumps resolve to a relative path
and line via Engine evidence and never return source bytes to the desktop bridge.

```bash
npm install
npm run dev
npm run build
npm run lint
```

Native Linux E2E requires a `WebKitWebDriver` binary (provided by `webkit2gtk-driver` on Ubuntu) in
addition to Tauri's SDK dependencies. It drives the compiled app through `tauri-driver`, opens the
Transformer fixture through Engine, moves and saves a visual node, restarts, then verifies canvas
coordinate restoration, source-backed Exact view selection, and byte-identical source. WebKitGTK
uses classic WebDriver, not WebDriver BiDi.

```bash
ARCHCANVAS_ENGINE_PYTHON=/path/to/TFB_py311/bin/python \
ARCHCANVAS_ENGINE_CACHE_ROOT=/absolute/path/to/archcanvas-cache \
ARCHCANVAS_WEBKIT_DRIVER=/path/to/WebKitWebDriver \
npm run test:e2e:tauri
```

## Tier A source-map samples

The read-only bundled models can be opened from the Tier A list in Tauri or at
`/?tierA=transformer` in a browser preview (also `autoformer`, `itransformer`,
`patchtst`, `timemixer`). L1-L4, a selected module's inline disclosure and
`Open full` all use the same sample graph; the toolbar exports the visible SVG.
Regenerate the checked source spans, archive hashes and ledgers with
`conda run -n TFB_py311 python tools/build_tier_a.py` from the repository root.
The samples are implementation-selected and pending human approval. They do not
authorize source edits or imply V3 Stage 4/6 acceptance.
