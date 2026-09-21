# Canvas Rules

- Canvas code owns only world/viewport math, selection, interaction previews and visual commits.
  It must not import Engine transport or read source paths.
- A pointer gesture may update local preview state on move. Only an explicit pointer-up commit may
  emit a position or viewport update; `pointercancel`, blur and renderer refresh roll preview back.
- Keep client, viewport and world coordinates explicit. Preserve pointer-anchored zoom, stable
  screen-pixel snapping and the `CanvasDocument` visual-only boundary.
- Canvas colors, spacing, typography, radii and motion come from `../styles/tokens.css`; no second
  visual token system belongs in this directory.
