import type { CameraState } from './cameraGesture.ts';

export type CameraViewport = Readonly<{ width: number; height: number }>;

/** A hidden/collapsed element cannot establish a usable camera coordinate frame. */
export function cameraViewportSize(value: CameraViewport | null | undefined): CameraViewport | null {
  if (!value || !Number.isFinite(value.width) || !Number.isFinite(value.height) ||
      value.width <= 0 || value.height <= 0 || value.width > 100_000 || value.height > 100_000) return null;
  return { width: value.width, height: value.height };
}

/** Keep the same world point at the centre; a resize never changes zoom. */
export function resizeCameraViewport(camera: CameraState, previous: CameraViewport, next: CameraViewport): CameraState | null {
  if (!cameraViewportSize(previous) || !cameraViewportSize(next) ||
      !Number.isFinite(camera.x) || !Number.isFinite(camera.y) || !Number.isFinite(camera.zoom) || camera.zoom <= 0) return null;
  if (previous.width === next.width && previous.height === next.height) return camera;
  const view = { x: camera.x + (next.width - previous.width) / 2,
    y: camera.y + (next.height - previous.height) / 2, zoom: camera.zoom };
  return Number.isFinite(view.x) && Number.isFinite(view.y) ? view : null;
}
