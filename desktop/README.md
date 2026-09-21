# ArchCanvas Desktop

Stage 6 provides an independent ArchCanvas world/SVG/HTML canvas and a minimal Tauri 2 shell.
The canvas uses the shared warm-white/near-black/blue design tokens, pointer-anchored zoom,
middle-mouse or Space pan, selection, marquee selection, preview-only node dragging and visual-only
snapping. The browser experience starts in an explicitly labelled read-only Transformer fixture
mode, where visual state is stored only in browser storage and the fixture source is never read or
written.

The Tauri client calls the `engine_rpc` command with typed Engine envelopes. The bridge starts one
JSONL `archcanvas_engine.stdio` sidecar per request and returns its typed response. It does not
read source paths or emulate source access. `CanvasDocument` data is limited to visual state.

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
