/** Keep task menus inside the viewport, including short windows and bottom docks. */
export function workspaceMenuPosition(anchor: { left: number; top: number; bottom: number }, size: { width: number; height: number }, viewport: { width: number; height: number }, preferAbove = false) {
  const gap = 8, edge = 8;
  const width = Math.min(size.width, Math.max(0, viewport.width - edge * 2));
  const below = Math.max(0, viewport.height - anchor.bottom - gap - edge);
  const above = Math.max(0, anchor.top - gap - edge);
  const up = preferAbove ? above >= Math.min(size.height, below) : below < size.height && above > below;
  const maxHeight = up ? above : below;
  const height = Math.min(size.height, maxHeight);
  return { left: Math.max(edge, Math.min(anchor.left, viewport.width - width - edge)), top: up ? anchor.top - gap - height : anchor.bottom + gap, width, maxHeight };
}
