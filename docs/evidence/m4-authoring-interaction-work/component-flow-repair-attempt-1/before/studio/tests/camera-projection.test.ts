import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildScene, createHistory, reduceHistory } from '../src/core/index.ts';
import { beginCameraPan, cameraAtPanInput } from '../src/cameraGesture.ts';
import { fitCameraToBounds, focusCameraOnPoint, paperTranslation, viewportToWorld, worldToViewport } from '../src/cameraProjection.ts';

type Point = { x: number; y: number };
const close = (actual: Point, expected: Point, tolerance = 1e-9) => {
  assert.ok(Math.abs(actual.x - expected.x) <= tolerance, `x ${actual.x} ≠ ${expected.x}`);
  assert.ok(Math.abs(actual.y - expected.y) <= tolerance, `y ${actual.y} ≠ ${expected.y}`);
};

test('world camera keeps the sealed Transformer scene continuous across negative bounds', () => {
  const document = JSON.parse(readFileSync(new URL('../../docs/evidence/browser-visual-matrix-hierarchy-final/captures/transformer-level0-paper-180/canvas.json', import.meta.url), 'utf8'));
  const original = buildScene(document);
  const root = original.nodes.find(node => node.id === 'call:instance:model.Transformer')!;
  const movedDocument = applyVisualBatch(document, [{ type: 'move', ids: [root.id], dx: -220, dy: -140 }]);
  const moved = buildScene(movedDocument);
  assert.ok(moved.bounds.x < 0 && moved.bounds.y < 0, 'fixture must cross both world axes');
  const camera = { x: 173.25, y: 94.5, zoom: 0.73 };
  const target = moved.nodes.find(node => node.id === root.id)!;
  const originalTarget = original.nodes.find(node => node.id === root.id)!;
  const targetCenter = { x: target.x + target.width / 2, y: target.y + target.height / 2 };
  const screen = worldToViewport(camera, targetCenter);
  close(viewportToWorld(camera, screen), targetCenter);
  // The paper-local SVG still starts at bounds, but its wrapper starts at the
  // world camera position plus bounds * zoom. This is the screen-space contract.
  const paperOrigin = paperTranslation(camera, moved.bounds);
  close({ x: paperOrigin.x + (target.x - moved.bounds.x + target.width / 2) * camera.zoom, y: paperOrigin.y + (target.y - moved.bounds.y + target.height / 2) * camera.zoom }, screen);
  const legacy = { x: camera.x + (targetCenter.x - moved.bounds.x) * camera.zoom, y: camera.y + (targetCenter.y - moved.bounds.y) * camera.zoom };
  assert.notDeepEqual(legacy, screen, 'regression guard: old bounds-relative wrapper misplaces a negative scene');
  assert.notEqual(originalTarget.x, target.x);

  let history = createHistory(document);
  history = reduceHistory(history, { type: 'apply', operations: [{ type: 'move', ids: [root.id], dx: -220, dy: -140 }] });
  const undone = reduceHistory(history, { type: 'undo' });
  const redone = reduceHistory(undone, { type: 'redo' });
  assert.deepEqual(redone.document.layout, history.document.layout);
  assert.deepEqual(redone.document.layoutByFrontier, history.document.layoutByFrontier);
  const redoScene = buildScene(redone.document);
  const redoRoot = redoScene.nodes.find(node => node.id === root.id)!;
  close(worldToViewport(camera, { x: redoRoot.x + redoRoot.width / 2, y: redoRoot.y + redoRoot.height / 2 }), screen);
});

test('fit, focus, pointer-centered zoom and pan use world coordinates', () => {
  const bounds = { x: -160, y: -34, width: 755, height: 976 };
  const fit = fitCameraToBounds(bounds, { width: 620, height: 740 });
  close(worldToViewport(fit, { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2 }), { x: 310, y: 370 });
  const focused = focusCameraOnPoint({ x: 3, y: 8, zoom: .75 }, { x: -120, y: 280 }, { width: 620, height: 740 });
  close(worldToViewport(focused, { x: -120, y: 280 }), { x: 310, y: 370 });
  const anchor = { x: 320, y: 240 }, old = { x: 173, y: 94, zoom: .73 }, world = viewportToWorld(old, anchor), zoom = .91;
  const zoomed = { x: anchor.x - (anchor.x - old.x) * zoom / old.zoom, y: anchor.y - (anchor.y - old.y) * zoom / old.zoom, zoom };
  close(worldToViewport(zoomed, world), anchor);
  const pan = beginCameraPan(old, { pointerId: 12, clientX: 500, clientY: 300, viewportX: 200, viewportY: 100 });
  assert.deepEqual(cameraAtPanInput(pan, { pointerId: 12, clientX: 544, clientY: 322, viewportX: 200, viewportY: 100 }), { x: 217, y: 116, zoom: .73 });
});
