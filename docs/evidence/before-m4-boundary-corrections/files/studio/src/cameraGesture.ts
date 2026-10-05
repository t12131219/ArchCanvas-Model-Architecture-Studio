/** Transient view navigation only: no CanvasDocument, history, or renderer. */
export type CameraState = Readonly<{ x: number; y: number; zoom: number }>;
export type PanInput = Readonly<{
  pointerId: number;
  clientX: number;
  clientY: number;
  viewportX: number;
  viewportY: number;
}>;
export type CameraPan = Readonly<{
  pointerId: number;
  camera: CameraState;
  start: Readonly<{ x: number; y: number }>;
}>;

function finite(values: number[]) {
  if (!values.every(Number.isFinite)) throw new Error('Camera pan requires finite coordinates');
}
function local(input: PanInput) {
  finite([input.clientX, input.clientY, input.viewportX, input.viewportY]);
  return { x: input.clientX - input.viewportX, y: input.clientY - input.viewportY };
}

/** Freeze the initial camera and pointer's viewport-relative CSS coordinates. */
export function beginCameraPan(camera: CameraState, input: PanInput): CameraPan {
  finite([camera.x, camera.y, camera.zoom]);
  if (camera.zoom <= 0 || !Number.isInteger(input.pointerId) || input.pointerId < 0) throw new Error('Invalid camera pan zoom or pointer');
  return { pointerId: input.pointerId, camera: { ...camera }, start: local(input) };
}

/**
 * Use for both preview samples and pointerup's actual final coordinates.
 * A terminal sample must be calculated synchronously after cancelling pending
 * RAF; depending on the last delivered move/frame can drop the final delta.
 *
 * Coordinates stay in CSS pixels at every zoom. Viewport-origin changes are
 * removed from the gesture displacement; viewport size itself does not zoom.
 * Pointer capture/lifecycle, RAF and state updates belong to the UI adapter.
 */
export function cameraAtPanInput(pan: CameraPan, input: PanInput): CameraState | null {
  if (input.pointerId !== pan.pointerId) return null;
  const point = local(input);
  return {
    x: pan.camera.x + (point.x - pan.start.x),
    y: pan.camera.y + (point.y - pan.start.y),
    zoom: pan.camera.zoom,
  };
}
