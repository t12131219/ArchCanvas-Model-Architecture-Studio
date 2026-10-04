# ArchCanvas visual grammar v1

The executable token and category registry lives in `studio/src/core/tokens.ts`.
The canonical renderer lives in `studio/src/core/svg.ts`; screen and publication
export both consume `buildScene(CanvasDocument)`. No model source or diagram
facts are embedded in these assets.

- `paper`: restrained category colors, 13 px scene labels and orthogonal routes.
- `monochrome`: white fills and dark borders; glyph shape and edge dashes retain
  category/role distinctions independently of color.
- Page width starts at 180 mm; 85 mm is available. Width is metadata on the same
  SVG scene, not a second export layout. Full expansion may need a larger page or
  detail view; publication legibility still needs human review.

Geometry uses containment-local coordinates. Collapsed hierarchy edges resolve
to proxy ports and preserve canonical edge IDs, tensor identity and roles.
Auxiliary input roles use a compact lane. Fixed positions are protected, and
frontier snapshots restore edited geometry across repeated expansion.

The first automated gates are structural invariants and escaped SVG output.
Pixel/golden and physical-size typography approval remain release gates; these
assets do not claim that those human acceptance checks have already passed.
