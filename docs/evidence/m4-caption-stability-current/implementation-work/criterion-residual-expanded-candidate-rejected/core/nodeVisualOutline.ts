import type { Bounds, SceneNode } from './types.ts';

type VisualNode = Bounds & Pick<SceneNode, 'repeat' | 'expanded'>;
type Point = { x: number; y: number };
export type VisualSide = 'bottom' | 'top' | 'right' | 'left';

/** Nominal card rectangles are conservative at the renderer's rounded corners.
 * Derived only: front-card anchors and persisted Canvas geometry never change. */
export function nodeVisualOutline(node: VisualNode) {
  const front: Bounds = { x: node.x, y: node.y, width: node.width, height: node.height };
  // Renderer order is farthest plate first, then the nearer plate.
  const backplates = node.repeat && !node.expanded
    ? [7, 3.5].map(offset => ({ ...front, x: front.x + offset, y: front.y + offset })) : [];
  const rectangles = [front, ...backplates];
  const right = Math.max(...rectangles.map(rectangle => rectangle.x + rectangle.width));
  const bottom = Math.max(...rectangles.map(rectangle => rectangle.y + rectangle.height));
  return { front, backplates, rectangles, bounds: { ...front, width: right - front.x, height: bottom - front.y } };
}

function boundary(rectangles: Bounds[], point: Point, side: VisualSide): number | undefined {
  const vertical = side === 'top' || side === 'bottom';
  const intersecting = rectangles.filter(rectangle => vertical
    ? point.x >= rectangle.x && point.x <= rectangle.x + rectangle.width
    : point.y >= rectangle.y && point.y <= rectangle.y + rectangle.height);
  if (!intersecting.length) return undefined;
  const values = intersecting.map(rectangle => side === 'bottom' ? rectangle.y + rectangle.height
    : side === 'top' ? rectangle.y : side === 'right' ? rectangle.x + rectangle.width : rectangle.x);
  return side === 'bottom' || side === 'right' ? Math.max(...values) : Math.min(...values);
}

/** Project a front-card anchor along its outward normal onto the card union.
 * Near a corner the ray may meet only the front or the nearer backplate. */
export function projectVisualPort(node: VisualNode, point: Point, side: VisualSide): Point {
  const coordinate = boundary(nodeVisualOutline(node).rectangles, point, side);
  if (coordinate === undefined) return { ...point };
  return side === 'top' || side === 'bottom' ? { x: point.x, y: coordinate } : { x: coordinate, y: point.y };
}

/** The nearest exposed nominal side supplies a routing lead, including the
 * stepped outline where a whole bounding box would guess the wrong normal. */
export function visualPortSide(node: VisualNode, point: Point): VisualSide {
  const rectangles = nodeVisualOutline(node).rectangles;
  const sides: VisualSide[] = ['bottom', 'top', 'right', 'left'];
  const candidates = sides.flatMap(side => {
    const coordinate = boundary(rectangles, point, side);
    return coordinate === undefined ? [] : [{ side, distance: Math.abs((side === 'top' || side === 'bottom' ? point.y : point.x) - coordinate) }];
  });
  return candidates.sort((a, b) => a.distance - b.distance)[0]?.side ?? 'bottom';
}
