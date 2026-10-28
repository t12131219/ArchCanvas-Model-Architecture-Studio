// Formal-core regression with retired preview test support; not evidence of current Summary gesture performance.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import type { PointerEvent } from 'react';
import { cameraViewportSize, resizeCameraViewport } from '../src/cameraViewport.ts';
import type { CameraViewport } from '../src/cameraViewport.ts';
import { beginCameraPan, cameraAtPanInput } from '../src/cameraGesture.ts';
import type { CameraPan, CameraState } from '../src/cameraGesture.ts';
import { fitCameraToBounds, viewportToWorld } from '../src/cameraProjection.ts';
import { canApplyCameraViewTicket, readCameraView, sameCameraViewDocument, writeCameraView } from '../src/cameraViewState.ts';
import type { CameraViewIdentity, CameraViewStorage } from '../src/cameraViewState.ts';
import type { CameraViewTicket } from '../src/cameraViewState.ts';
import { buildScene, createDocument, createHistory, reduceHistory } from '../src/core/index.ts';
import { prepareMovePreview } from './retired-preview/movePreview.ts';
import type { CanvasDocument, HistoryState, VisualOperation } from '../src/core/types.ts';

const small = { width: 672, height: 711 }, large = { width: 883, height: 786 };
const baseline = { x: -14, y: -49.5, zoom: 1 };
function center(view: CameraState, size: CameraViewport) {
  // Independent equation: no product projection/resize helper supplies oracle.
  return { x: (size.width / 2 - view.x) / view.zoom, y: (size.height / 2 - view.y) / view.zoom };
}
function close(actual: number, expected: number) { assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} != ${expected}`); }

test('the observed large-to-small live resize keeps world centre 350,405 in its first coordinated result', () => {
  const next = resizeCameraViewport({ x: 91.5, y: -12, zoom: 1 }, large, small)!;
  assert.deepEqual(next, baseline);
  assert.deepEqual(center(next, small), { x: 350, y: 405 });
  assert.deepEqual(resizeCameraViewport(next, small, large), { x: 91.5, y: -12, zoom: 1 });
});

test('fractional, negative and small-fit cameras preserve centre and zoom across anisotropic size chains', () => {
  for (const view of [baseline, { x: -1204.25, y: 380.75, zoom: .017 }, { x: .125, y: -.375, zoom: 3 }]) {
    const sizes = [small, { width: 4096.5, height: 160.25 }, { width: 80, height: 70 }, large, small];
    const expected = center(view, small);
    let current = view;
    for (let index = 1; index < sizes.length; index++) {
      current = resizeCameraViewport(current, sizes[index - 1], sizes[index])!;
      const observed = center(current, sizes[index]);
      close(observed.x, expected.x); close(observed.y, expected.y);
      assert.equal(current.zoom, view.zoom);
    }
    close(current.x, view.x); close(current.y, view.y);
  }
});

test('same-size deliveries are no-ops and invalid or hidden dimensions cannot establish a frame', () => {
  assert.equal(resizeCameraViewport(baseline, small, { ...small }), baseline);
  for (const size of [null, undefined, { width: 0, height: 711 }, { width: 672, height: -1 },
    { width: NaN, height: 711 }, { width: 672, height: Infinity }, { width: 100001, height: 711 }]) {
    assert.equal(cameraViewportSize(size), null);
    if (size) {
      assert.equal(resizeCameraViewport(baseline, small, size), null);
      assert.equal(resizeCameraViewport(baseline, size, small), null);
    }
  }
  for (const view of [{ ...baseline, x: Infinity }, { ...baseline, y: NaN }, { ...baseline, zoom: 0 },
    { ...baseline, zoom: -1 }, { ...baseline, zoom: Infinity }]) assert.equal(resizeCameraViewport(view, small, large), null);
  const before = JSON.stringify({ baseline, small, large });
  resizeCameraViewport(baseline, small, large);
  assert.equal(JSON.stringify({ baseline, small, large }), before);
});

// Retired host callback matrices are preserved in docs/evidence/summary-preview-retirement-20261028/before.
// The live Summary camera/gesture owner is covered by the real browser retirement matrix.
