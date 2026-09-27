export interface InteractionBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function normalizedSelectionBox(start: { x: number; y: number }, end: { x: number; y: number }): InteractionBounds {
  return {
    x: Math.min(start.x, end.x),
    y: Math.min(start.y, end.y),
    width: Math.abs(end.x - start.x),
    height: Math.abs(end.y - start.y),
  };
}

export function selectionIntersectsBounds(selection: InteractionBounds, bounds: InteractionBounds) {
  return selection.x <= bounds.x + bounds.width
    && selection.x + selection.width >= bounds.x
    && selection.y <= bounds.y + bounds.height
    && selection.y + selection.height >= bounds.y;
}
