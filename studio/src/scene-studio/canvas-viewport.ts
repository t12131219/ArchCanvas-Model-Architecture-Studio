import type { Point } from "./types";

export interface CanvasCamera extends Point {
  zoom: number;
}

export const MIN_CANVAS_ZOOM = 0.08;
export const MAX_CANVAS_ZOOM = 4;
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
