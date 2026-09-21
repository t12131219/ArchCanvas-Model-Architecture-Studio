# Stage 5 Engine Checkpoint

## Delivered

- Strict ProjectManifest, VisualPatch, EngineRequest, EngineResponse and EngineEvent schemas.
- Cache-root-only repository with atomic JSON writes for manifests, source/Exact/publication/scene
  snapshots, SVG artifacts, visual patches and revision history.
- Engine lifecycle: approved-root entrypoint validation, environment/lockfile validation, static
  analysis, Publication SVG compilation, restart loading and typed RPC dispatch.
- Polling source watcher that records an external revision change as stale and prevents a visual
  patch from replaying across that revision.

## Fixture Evidence

The transformer fixture is copied to a temporary approved root for every integration test. The
Engine opens it, analyzes it, persists and reloads the graph bundle, saves a valid repeat-expansion
patch, and leaves source bytes unchanged. A simulated external source edit changes the observed
revision and marks the stored patch orphaned. RPC rejects an analysis request for an unopened
project with `PROJECT_NOT_OPEN`.

## Boundary

Engine has no desktop, MCP or direct source-write endpoint. The existing fixture CLI has not yet
been moved behind Engine; parameter and structural transactions remain later-stage work.

## Validation

```bash
conda run -n TFB_py311 python -m pytest -q
conda run -n TFB_py311 python -m ruff check src tests tools
conda run -n TFB_py311 python -m compileall -q src tools tests
conda run -n TFB_py311 python tools/export_schemas.py
conda run -n TFB_py311 python tools/generate_static_goldens.py
conda run -n TFB_py311 python tools/generate_publication_goldens.py
git diff --check
```

All commands pass in the current `TFB_py311` environment.
