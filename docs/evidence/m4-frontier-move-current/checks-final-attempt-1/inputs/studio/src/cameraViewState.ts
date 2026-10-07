import type { CameraState } from './cameraGesture.ts';
import { viewportToWorld } from './cameraProjection.ts';

export type CameraViewIdentity = Readonly<{
  documentId: string;
  sourceBindingDigest: string;
  irDigest: string;
  visualRevision: number;
}>;
export type CameraViewViewport = Readonly<{ width: number; height: number }>;
export type CameraViewState = Readonly<{
  schemaVersion: 1;
  identity: CameraViewIdentity;
  zoom: number;
  worldCenter: Readonly<{ x: number; y: number }>;
  capturedViewport: CameraViewViewport;
}>;
export type CameraViewStorage = Pick<Storage, 'getItem' | 'setItem'>;
export type CameraViewTicket = Readonly<{
  identity: CameraViewIdentity;
  loadSequence: number;
  intentSequence: number;
}>;

const PREFIX = 'archcanvas.camera-view.v1:';
const MAX_COORDINATE = 1e9;
const MAX_VIEWPORT = 100_000;
const MAX_SERIALIZED = 16_384;

function finiteWithin(value: unknown, limit: number): value is number {
  return typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= limit;
}
function validIdentity(value: unknown): value is CameraViewIdentity {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<CameraViewIdentity>;
  return typeof candidate.documentId === 'string' && candidate.documentId.length > 0 && candidate.documentId.length <= 1024 &&
    typeof candidate.sourceBindingDigest === 'string' && /^[a-f0-9]{64}$/.test(candidate.sourceBindingDigest) &&
    typeof candidate.irDigest === 'string' && /^[a-f0-9]{64}$/.test(candidate.irDigest) &&
    typeof candidate.visualRevision === 'number' && Number.isSafeInteger(candidate.visualRevision) && candidate.visualRevision >= 0;
}
function validViewport(value: unknown): value is CameraViewViewport {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<CameraViewViewport>;
  // A viewport smaller than fit's fixed margins cannot establish an initial view.
  return finiteWithin(candidate.width, MAX_VIEWPORT) && finiteWithin(candidate.height, MAX_VIEWPORT) &&
    candidate.width > 96 && candidate.height > 92;
}
function validZoom(value: unknown): value is number {
  // Fit intentionally supports scales below the toolbar's manual .15 minimum.
  return finiteWithin(value, 3) && value >= 1e-6;
}

export function sameCameraViewDocument(a: CameraViewIdentity | null, b: CameraViewIdentity): boolean {
  return !!a && validIdentity(a) && validIdentity(b) && a.documentId === b.documentId &&
    a.sourceBindingDigest === b.sourceBindingDigest && a.irDigest === b.irDigest;
}

export function cameraViewStorageKey(identity: CameraViewIdentity): string | null {
  if (!validIdentity(identity)) return null;
  return PREFIX + JSON.stringify([identity.documentId, identity.sourceBindingDigest, identity.irDigest]);
}

export function captureCameraView(identity: CameraViewIdentity, camera: CameraState, viewport: CameraViewViewport): CameraViewState | null {
  if (!validIdentity(identity) || !validViewport(viewport) || !validZoom(camera.zoom) ||
      !finiteWithin(camera.x, MAX_COORDINATE) || !finiteWithin(camera.y, MAX_COORDINATE)) return null;
  const center = viewportToWorld(camera, { x: viewport.width / 2, y: viewport.height / 2 });
  if (!finiteWithin(center.x, MAX_COORDINATE) || !finiteWithin(center.y, MAX_COORDINATE)) return null;
  return { schemaVersion: 1, identity: { ...identity }, zoom: camera.zoom,
    worldCenter: center, capturedViewport: { ...viewport } };
}

export function restoreCameraView(value: unknown, identity: CameraViewIdentity, viewport: CameraViewViewport): CameraState | null {
  if (!value || typeof value !== 'object' || !validIdentity(identity) || !validViewport(viewport)) return null;
  const candidate = value as Partial<CameraViewState>;
  if (candidate.schemaVersion !== 1 || !validIdentity(candidate.identity) ||
      !sameCameraViewDocument(candidate.identity, identity) || candidate.identity.visualRevision !== identity.visualRevision ||
      !validZoom(candidate.zoom) || !validViewport(candidate.capturedViewport) || !candidate.worldCenter ||
      !finiteWithin(candidate.worldCenter.x, MAX_COORDINATE) || !finiteWithin(candidate.worldCenter.y, MAX_COORDINATE)) return null;
  const camera = { x: viewport.width / 2 - candidate.worldCenter.x * candidate.zoom,
    y: viewport.height / 2 - candidate.worldCenter.y * candidate.zoom, zoom: candidate.zoom };
  return finiteWithin(camera.x, MAX_COORDINATE) && finiteWithin(camera.y, MAX_COORDINATE) ? camera : null;
}

export function readCameraView(storage: CameraViewStorage | null, identity: CameraViewIdentity, viewport: CameraViewViewport): CameraState | null {
  const key = cameraViewStorageKey(identity);
  if (!key || !storage) return null;
  try {
    const raw = storage.getItem(key);
    if (!raw || raw.length > MAX_SERIALIZED) return null;
    return restoreCameraView(JSON.parse(raw), identity, viewport);
  } catch { return null; }
}

export function writeCameraView(storage: CameraViewStorage | null, identity: CameraViewIdentity, camera: CameraState, viewport: CameraViewViewport): boolean {
  const key = cameraViewStorageKey(identity), state = captureCameraView(identity, camera, viewport);
  if (!key || !state || !storage) return false;
  try { storage.setItem(key, JSON.stringify(state)); return true; }
  catch { return false; }
}

export function canApplyCameraViewTicket(ticket: CameraViewTicket, current: CameraViewIdentity | null,
  loadSequence: number, intentSequence: number): boolean {
  return !!current && sameCameraViewDocument(ticket.identity, current) &&
    ticket.identity.visualRevision === current.visualRevision &&
    ticket.loadSequence === loadSequence && ticket.intentSequence === intentSequence;
}
