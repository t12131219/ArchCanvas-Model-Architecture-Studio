# Stage 6 Desktop Checkpoint

## Delivered

- `CanvasDocument` v1 is a strict, source-free core model keyed by project, Publication IR and
  source revision. It accepts only viewport, visual node placement/sizing/style/collapse/lock,
  annotations and layout mode.
- Engine validates the current source revision and Publication node set before atomically saving a
  canvas document under the cache root. Restart replay returns matching documents and suppresses
  stale documents as orphaned. The operation is available through typed Engine RPC.
- `desktop/` contains a Tauri 2 + React + TypeScript shell and a React Flow UI. Publication view
  is visually editable; Exact Architecture view is source-backed and read-only. The browser
  transport is prominently labelled `READ-ONLY FIXTURE`, stores only its CanvasDocument locally,
  and cannot access project paths.
- The Tauri command starts one host-configured `archcanvas_engine.stdio` JSONL sidecar per typed
  request. It has no project filesystem, source parser, or source-write code and therefore cannot
  bypass Engine policy. Missing sidecar configuration fails closed.
- The desktop Open Project dialog sends approved root, entrypoint and interpreter values only to
  Engine RPC. `load_analysis` reconstructs both views from Engine cache; source jump resolves an
  evidence-backed relative file and location without returning source bytes.

## Browser Verification

The local Vite app at `http://127.0.0.1:1420/` was inspected through the browser:

1. Transformer Publication canvas rendered its collapsed encoder group.
2. Selecting the group showed its member count and source anchor in the inspector.
3. Expanding the group changed only visual state; reloading restored that state from fixture-local
   CanvasDocument storage.
4. Exact Architecture view rendered the source-backed `node:encodermodel.layers` ModuleList node,
   while Publication view rendered its separate `repeat_group` abstraction. For this IR, the repeat
   count is a `RepeatSpec` fact, not six invented exact nodes.
5. Engine JSONL integration tests restart the sidecar between open, analysis, CanvasDocument save,
   cached analysis reload and CanvasDocument replay. Fixture source bytes remain identical.

## Native E2E Acceptance

The native Linux E2E passed with Tauri's SDK libraries and a configured WebKit driver. It opened
the Transformer fixture through Engine, dragged and saved the Publication repeat group, restarted
the native desktop, replayed the same `CanvasDocument` position, selected the source-backed Exact
ModuleList node, and verified the fixture source SHA-256 stayed byte-identical. The test forces
classic WebDriver because the installed WebKitGTK driver does not expose WebDriver BiDi.

The GitHub Actions `test-desktop-native` job installs `webkit2gtk-driver` and runs the same command
on Ubuntu 24.04. Its first hosted run is still required as remote CI evidence. No Article source or
PDF was opened, executed, or modified during this work.

## Validation Run

```bash
conda run -n TFB_py311 python -m pytest tests/models tests/engine tests/schema -q
conda run -n TFB_py311 python -m ruff check src tests tools
conda run -n TFB_py311 python -m compileall -q src tools tests
conda run -n TFB_py311 python tools/export_schemas.py
npm run build
npm run lint
cargo fmt --check
git diff --check
ARCHCANVAS_ENGINE_PYTHON=/home/fzg/anaconda3/envs/TFB_py311/bin/python \
ARCHCANVAS_ENGINE_CACHE_ROOT=/tmp/archcanvas-tauri-cache \
ARCHCANVAS_WEBKIT_DRIVER=/path/to/WebKitWebDriver \
npm run test:e2e:tauri
```

All listed local commands pass. Hosted CI has been configured but has not yet produced a remote
run record.
