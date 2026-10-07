import test from 'node:test';
import assert from 'node:assert/strict';
import { beginCameraPan, cameraAtPanInput } from '../src/cameraGesture.ts';

const sample = (clientX: number, clientY: number, viewportX = 230, viewportY = 115, pointerId = 7) =>
  ({ clientX, clientY, viewportX, viewportY, pointerId });

test('pointerup endpoint is available without an intervening move or RAF', () => {
  const pan = beginCameraPan({ x: 104.5, y: -764, zoom: 1 }, sample(650, 311));
  // Simulates a released pointer before the scheduled preview frame executes.
  // The adapter must use this terminal sample rather than its old camera.
  assert.deepEqual(cameraAtPanInput(pan, sample(682, 331)), { x: 136.5, y: -744, zoom: 1 });
});

test('terminal endpoint includes movement beyond the last sampled preview', () => {
  const pan = beginCameraPan({ x: 25, y: 35, zoom: .25 }, sample(500, 300));
  assert.deepEqual(cameraAtPanInput(pan, sample(508, 304)), { x: 33, y: 39, zoom: .25 });
  assert.deepEqual(cameraAtPanInput(pan, sample(532, 320)), { x: 57, y: 55, zoom: .25 });
});

test('pan displacement is measured in CSS pixels and never divided by zoom', () => {
  for (const zoom of [.15, .291711, 1, 3]) {
    const pan = beginCameraPan({ x: -20, y: 46, zoom }, sample(700, 450));
    assert.deepEqual(cameraAtPanInput(pan, sample(660, 474)), { x: -60, y: 70, zoom });
  }
});

test('returning to start restores exact initial camera without cumulative drift', () => {
  for (const camera of [{ x: 211.731, y: 46, zoom: .291711 }, { x: .1, y: .2, zoom: .8 }]) {
    const pan = beginCameraPan(camera, sample(500, 300));
    for (let i = 1; i <= 50; i++) cameraAtPanInput(pan, sample(500 + i * .5, 300 - i * .25));
    assert.deepEqual(cameraAtPanInput(pan, sample(500, 300)), camera);
  }
});

test('viewport-origin shift alone does not masquerade as a pointer delta', () => {
  const pan = beginCameraPan({ x: 104.5, y: -764, zoom: 1 }, sample(650, 311));
  // The full-task capture's viewport moved x230 -> x200. The same local point
  // therefore has clientX620, not650; that host shift is not user navigation.
  assert.deepEqual(cameraAtPanInput(pan, sample(620, 311, 200)), { x: 104.5, y: -764, zoom: 1 });
  assert.deepEqual(cameraAtPanInput(pan, sample(652, 331, 200)), { x: 136.5, y: -744, zoom: 1 });
});

test('a second pointer cannot update or finish the original pan', () => {
  const pan = beginCameraPan({ x: 0, y: 0, zoom: 1 }, sample(500, 300));
  assert.equal(cameraAtPanInput(pan, sample(600, 400, 230, 115, 8)), null);
  assert.deepEqual(cameraAtPanInput(pan, sample(532, 320)), { x: 32, y: 20, zoom: 1 });
});

test('initial camera snapshot and caller input remain untouched', () => {
  const camera = { x: 25, y: 35, zoom: .8 };
  const input = sample(500, 300);
  const beforeInput = { ...input };
  const pan = beginCameraPan(camera, input);
  camera.x = 900;
  const output = cameraAtPanInput(pan, sample(532, 320))!;
  assert.deepEqual(output, { x: 57, y: 55, zoom: .8 });
  assert.deepEqual(input, beforeInput);
  assert.deepEqual(pan.camera, { x: 25, y: 35, zoom: .8 });
  assert.notEqual(output, pan.camera);
});

test('invalid start coordinates, zoom and pointer identity are rejected', () => {
  for (const zoom of [0, -1, NaN, Infinity]) assert.throws(() => beginCameraPan({ x: 0, y: 0, zoom }, sample(500, 300)));
  assert.throws(() => beginCameraPan({ x: Infinity, y: 0, zoom: 1 }, sample(500, 300)));
  assert.throws(() => beginCameraPan({ x: 0, y: 0, zoom: 1 }, sample(NaN, 300)));
  assert.throws(() => beginCameraPan({ x: 0, y: 0, zoom: 1 }, sample(500, 300, 230, 115, 1.5)));
  const pan = beginCameraPan({ x: 0, y: 0, zoom: 1 }, sample(500, 300));
  assert.throws(() => cameraAtPanInput(pan, sample(500, Infinity)));
});
