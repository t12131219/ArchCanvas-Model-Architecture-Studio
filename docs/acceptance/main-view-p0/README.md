# Main View P0 Acceptance

This directory records the first-class visual-kernel acceptance inputs for the
direct rebuild. `build/scene-visual-lab` remains the visual oracle; it is not a
runtime dependency. Production output is generated from the decoupled
TypeScript kernel and the formal-state fixtures under
`studio/src/main-view/fixtures`.

## Coverage

- 26 topology fixtures and 45 route/node/label combinations are exercised by
  `studio/src/visual-kernel/production-matrix.test.ts` (1170 cases).
- The production detail library contains all 39 catalog/module kinds listed in
  `NodeDetailKind` and verifies primitive generation for every kind.
- The build oracle contains `semantic-glyph-library`, six catalog families,
  and `parent-child-expansion`; their production counterparts are the migrated
  visual language, detail templates, portals, and recursive layout.
- `differences.json` is a machine-readable inventory of the comparison gates.
- `structural-differences.json` parses both sides using the prototype
  `scene-node/scene-edge/module-detail` vocabulary and records topology,
  detail-surface, primitive-count, primitive-kind/tone vocabulary, semantic
  token, glyph, bounds, routing, and portal deltas.
- `browser-differences.json` records the build/production PNG hashes,
  dimensions, byte sizes, viewport checks, changed-pixel ratio, RGB deltas,
  and changed-region bounds. Static export cases have a pixel-match gate;
  internal-drag and recursive captures are explicitly marked
  `interaction-only` because their prototype canvas contains interactive and
  nested UI state that is not part of a production SVG export.
- Five additional `runtime-*.png` captures cover the real Studio at 1440x900,
  1280x800, 1024x768, 390x844, and dark 1440x900. The Playwright gate also
  verifies nonempty nodes/edges/legend, mobile overflow, successful theme and
  pin patches, and reload persistence.

## Reproduction

```bash
cd studio
npm run acceptance:p0
npm run acceptance:p0:visual
npx playwright test e2e/main-view-p0-visual.spec.ts
```

The build baseline is read from
`build/scene-visual-lab/cases/manifest.json`. Production must never import or
read that directory at runtime.

## Result

All 14 structural records pass their finite-geometry, topology, detail-surface,
edge, routing, and portal gates. The five required parent-child states are
present as `parent-child-collapsed`,
`parent-child-expanded`, `parent-child-continued-expansion`,
`parent-child-internal-drag`, and `parent-child-collapsed-again`. The recursive
formal hierarchy is captured separately. Twelve static browser records pass
the configured pixel gate; the two interaction-only records retain their
measured pixel deltas but are not misreported as export-equivalent. These
artifacts are acceptance evidence, not runtime inputs.
