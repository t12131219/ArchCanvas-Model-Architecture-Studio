import type { CameraState } from './cameraGesture.ts';

type Point = Readonly<{ x: number; y: number }>;
type Bounds = Readonly<{ x: number; y: number; width: number; height: number }>;
type Viewport = Readonly<{ width: number; height: number }>;

function finite(values: number[]) {
  if (!values.every(Number.isFinite)) throw new Error('Camera projection requires finite coordinates');
}
function checkCamera(camera: CameraState) {
  finite([camera.x, camera.y, camera.zoom]);
  if (camera.zoom <= 0) throw new Error('Camera projection requires a positive zoom');
}

/** Camera translation locates world (0, 0), independently of export bounds. */
export function worldToViewport(camera: CameraState, point: Point): Point {
  checkCamera(camera); finite([point.x, point.y]);
  return { x: camera.x + point.x * camera.zoom, y: camera.y + point.y * camera.zoom };
}

export function viewportToWorld(camera: CameraState, point: Point): Point {
  checkCamera(camera); finite([point.x, point.y]);
  return { x: (point.x - camera.x) / camera.zoom, y: (point.y - camera.y) / camera.zoom };
}

/** SVG and overlays remain paper-local; the paper starts at its world bounds. */
export function paperTranslation(camera: CameraState, bounds: Point): Point {
  return worldToViewport(camera, bounds);
}

export function fitCameraToBounds(bounds: Bounds, viewport: Viewport): CameraState {
  finite([bounds.x, bounds.y, bounds.width, bounds.height, viewport.width, viewport.height]);
  if (bounds.width <= 0 || bounds.height <= 0 || viewport.width <= 0 || viewport.height <= 0) throw new Error('Camera fit requires positive dimensions');
  const usableWidth = viewport.width - 96, usableHeight = viewport.height - 92;
  if (usableWidth <= 0 || usableHeight <= 0) throw new Error('Camera fit viewport is too small');
  const zoom = Math.min(usableWidth / bounds.width, usableHeight / bounds.height, 1.2);
  return {
    x: viewport.width / 2 - (bounds.x + bounds.width / 2) * zoom,
    y: viewport.height / 2 - (bounds.y + bounds.height / 2) * zoom,
    zoom,
  };
}

export function focusCameraOnPoint(camera: CameraState, point: Point, viewport: Viewport): CameraState {
  checkCamera(camera); finite([point.x, point.y, viewport.width, viewport.height]);
  return { x: viewport.width / 2 - point.x * camera.zoom, y: viewport.height / 2 - point.y * camera.zoom, zoom: camera.zoom };
}
