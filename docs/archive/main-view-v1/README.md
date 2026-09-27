# Studio Main View v1 Archive

This directory freezes the Studio main-view implementation that preceded the
direct Scene Visual Lab based rebuild. It is an audit artifact only. Nothing
under this directory is imported by the application or included in the Studio
bundle.

## Provenance

- Repository commit: `45a887fabebf767965235e8f6996369c2b5555ff`
- Captured on: 2026-09-26 (Asia/Shanghai)
- Fixture: `fixtures/tier_a/transformer`, entrypoint `model:Transformer`
- Routing mode: `atomic-v1`
- Baseline server: `.venv/bin/python tools/serve_routing_smoke.py --port 4311`
- Desktop viewport: 1440 x 900
- Mobile viewport: 390 x 844

The source tree preserves original repository-relative paths below `source/`.
`MANIFEST.json` maps each original path to its archived copy, byte size, and
SHA-256 digest. `SHA256SUMS` can be verified from this directory with:

```bash
sha256sum --check SHA256SUMS
```

## Fixtures

- `fixtures/studio-state.json`: complete initial `/api/state` response.
- `fixtures/canvas-document.json`: visual document extracted from that state.
- `fixtures/architecture.json`: Exact Architecture IR extracted from that state.

These fixtures are intentionally offline snapshots. Temporary project paths in
the state identify the isolated capture process and are not expected to exist
after capture.

## Visual Baselines

- `desktop-light.png`: default light Studio after closing the project launcher.
- `desktop-dark.png`: the same state using the dark theme.
- `mobile.png`: responsive layout at 390 x 844.
- `expanded-module.png`: module navigation and canvas after expanding encoder.
- `selected-edge.png`: selected relation and inspector state.
- `dragging-node.png`: in-progress node drag and route preview.

Run `node docs/archive/main-view-v1/capture-baselines.mjs` while the isolated
fixture server is listening on port 4311 to refresh the state and screenshots.
The script writes only within this archive.

## Frozen Behavior

The archived implementation supported project discovery and analysis, module
and source projections, node and edge selection, box selection, camera pan and
zoom, node dragging with a TypeScript preview route, server-side patch history,
Python layout candidates, relation legend, inspector tabs, source workspace,
validation jobs, draft/proposal flows, and publication export.

Known architectural issues that motivated the rebuild:

- `studio/src/main.tsx` mixed application shell, API access, business state,
  canvas interaction, SVG rendering, and dialogs in one module.
- Python produced authoritative scene geometry while TypeScript independently
  produced gesture preview routes.
- Studio routing exposed legacy, shadow, and atomic modes with runtime fallback.
- Main-view export consumed the Python publication renderer rather than the
  exact browser render scene.
- Visual structure glyphs could be selected from labels rather than exclusively
  from evidence-backed template bindings.

The archive is not a fallback implementation and must not be copied into a new
runtime path.
