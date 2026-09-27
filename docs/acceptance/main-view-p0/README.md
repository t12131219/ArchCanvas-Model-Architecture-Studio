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
- `structural-differences.json` records finite geometry, complete edge/detail
  rendering, routing metrics, and boundary-port continuity for all 14 pairs.
- `browser-differences.json` records the build/production PNG hashes,
  dimensions, byte sizes, and fixed viewport checks for the same 14 pairs.
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

All 14 structural records and all 14 browser records pass. The five required
parent-child states are present as `parent-child-collapsed`,
`parent-child-expanded`, `parent-child-continued-expansion`,
`parent-child-internal-drag`, and `parent-child-collapsed-again`. The recursive
formal hierarchy is captured separately. These artifacts are acceptance
evidence, not runtime inputs.
