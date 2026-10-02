import type { Bounds, Point } from "./types";

export interface CanvasCamera extends Point {
  zoom: number;
}

export const MIN_CANVAS_ZOOM = 0.08;
export const MAX_CANVAS_ZOOM = 4;
export const LARGE_SCENE_NODE_THRESHOLD = 48;
export const LARGE_SCENE_EDGE_THRESHOLD = 72;
export const VIEWPORT_DETAIL_OVERSCAN = 180;
const BASE_GRID_SPACING = 28;
const MIN_SCREEN_GRID_SPACING = 18;
const MAX_SCREEN_GRID_SPACING = 36;

export function clampCanvasZoom(zoom: number): number {
  return Math.min(MAX_CANVAS_ZOOM, Math.max(MIN_CANVAS_ZOOM, zoom));
}

export function canvasGridSize(zoom: number): number {
  let size = BASE_GRID_SPACING * zoom;
  while (size < MIN_SCREEN_GRID_SPACING) size *= 2;
  while (size > MAX_SCREEN_GRID_SPACING) size /= 2;
  return size;
}

export function zoomCameraAt(camera: CanvasCamera, requestedZoom: number, anchor: Point): CanvasCamera {
  const zoom = clampCanvasZoom(requestedZoom);
  const ratio = zoom / camera.zoom;
  return {
    x: anchor.x - (anchor.x - camera.x) * ratio,
    y: anchor.y - (anchor.y - camera.y) * ratio,
    zoom,
  };
}

export function wheelZoomFactor(deltaY: number, deltaMode: number): number {
  const deltaScale = deltaMode === 1 ? 16 : deltaMode === 2 ? 120 : 1;
  return Math.exp(-deltaY * deltaScale * 0.002);
}

export function shouldBeginCanvasPan(button: number, isEmptySurface: boolean, edgeMode: boolean): boolean {
  if (edgeMode) return false;
  return button === 1 || (button === 0 && isEmptySurface);
}

export function fitCanvasCamera(
  viewport: Pick<DOMRect, "width" | "height">,
  world: { x?: number; y?: number; width: number; height: number },
  padding = 52,
): CanvasCamera {
  const availableWidth = Math.max(1, viewport.width - padding * 2);
  const availableHeight = Math.max(1, viewport.height - padding * 2);
  const zoom = clampCanvasZoom(Math.min(availableWidth / world.width, availableHeight / world.height, 1));
  return {
    x: (viewport.width - world.width * zoom) / 2 - (world.x ?? 0) * zoom,
    y: (viewport.height - world.height * zoom) / 2 - (world.y ?? 0) * zoom,
    zoom,
  };
}

export function canvasWorldViewport(
  camera: CanvasCamera,
  viewport: Pick<DOMRect, "width" | "height">,
  overscan = VIEWPORT_DETAIL_OVERSCAN,
): Bounds {
  const zoom = clampCanvasZoom(camera.zoom);
  const padding = Math.max(0, overscan);
  return {
    x: (-camera.x - padding) / zoom,
    y: (-camera.y - padding) / zoom,
    width: (Math.max(0, viewport.width) + padding * 2) / zoom,
    height: (Math.max(0, viewport.height) + padding * 2) / zoom,
  };
}

export function boundsIntersect(first: Bounds, second: Bounds): boolean {
  return first.x <= second.x + second.width
    && first.x + first.width >= second.x
    && first.y <= second.y + second.height
    && first.y + first.height >= second.y;
}

export function pointInBounds(point: Point, bounds: Bounds): boolean {
  return point.x >= bounds.x
    && point.x <= bounds.x + bounds.width
    && point.y >= bounds.y
    && point.y <= bounds.y + bounds.height;
}

export function shouldVirtualizeSceneDetails(nodeCount: number, edgeCount: number): boolean {
  return nodeCount >= LARGE_SCENE_NODE_THRESHOLD || edgeCount >= LARGE_SCENE_EDGE_THRESHOLD;
}
