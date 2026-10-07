import test from 'node:test';
import assert from 'node:assert/strict';
import { canvasDotGrid, clampCanvasZoom, viewportToWorld, worldToViewport, zoomCameraAtPoint } from '../src/cameraProjection.ts';
import { beginCameraPan, cameraAtPanInput } from '../src/cameraGesture.ts';
import { buildScene, createDocument, renderSvg } from '../src/core/index.ts';
import type { Architecture } from '../src/core/types.ts';

test('dot lattice follows the world origin through all pan quadrants and zoom levels', () => {
  for (const zoom of [.04, .09, .25, .7, 1, 2.8, 6]) {
    for (const position of [{ x: -93017, y: -813.5 }, { x: -47, y: 123 }, { x: 571.25, y: -32 }, { x: 71384, y: 39421 }]) {
      const camera = { ...position, zoom }, grid = canvasDotGrid(camera);
      assert.ok(grid.spacing >= 14 && grid.spacing <= 42);
      for (const multiple of [-12, -1, 0, 1, 17]) {
        const projected = worldToViewport(camera, { x: grid.worldSpacing * multiple, y: grid.worldSpacing * (multiple + 1) });
        const col = (projected.x - grid.x) / grid.spacing, row = (projected.y - grid.y) / grid.spacing;
        assert.ok(Math.abs(col - Math.round(col)) < 1e-8);
        assert.ok(Math.abs(row - Math.round(row)) < 1e-8);
      }
    }
  }
});

test('navigation is unbounded in position and zoom retains the pointer world point', () => {
  const start = { x: -81000, y: 94000, zoom: .3 };
  const pan = beginCameraPan(start, { pointerId: 3, clientX: 500, clientY: 450, viewportX: 200, viewportY: 100 });
  const camera = cameraAtPanInput(pan, { pointerId: 3, clientX: 950500, clientY: -80450, viewportX: 200, viewportY: 100 })!;
  assert.deepEqual(camera, { x: 869000, y: 13100, zoom: .3 });
  const pointer = { x: 322, y: 174 }, world = viewportToWorld(camera, pointer);
  for (const requested of [.001, .04, .42, 6, 200]) {
    const next = zoomCameraAtPoint(camera, clampCanvasZoom(requested), pointer);
    const observed = viewportToWorld(next, pointer);
    assert.ok(Math.abs(world.x - observed.x) < 1e-8 && Math.abs(world.y - observed.y) < 1e-8);
    assert.ok(next.zoom >= .04 && next.zoom <= 6);
  }
  assert.throws(() => canvasDotGrid({ x: Infinity, y: 0, zoom: 1 }));
  assert.throws(() => canvasDotGrid({ x: 0, y: 0, zoom: Number.MIN_VALUE }));
  assert.throws(() => clampCanvasZoom(NaN));
});

test('transparent editor surface retains exact figure geometry and publication background', () => {
  const architecture: Architecture = {
    schemaVersion: 1, id: 'infinite-test', label: '无限视图', sourceDigest: 'infinite-source', irDigest: 'infinite-ir',
    entry: 'model:Model', diagnostics: [], sources: [],
    nodes: [{ id: 'linear', label: 'Projection', kind: 'Linear', category: 'linear', children: [], parameters: {}, evidence: 'source', ports: [] }], edges: [],
  };
  const document = createDocument(architecture), before = JSON.stringify(document), scene = buildScene(document);
  const published = renderSvg(scene), editor = renderSvg(scene, { background: false });
  const background = published.match(/<\/defs>(<rect [^>]*\/>)/)![1];
  assert.equal(editor, published.replace(background, ''));
  assert.equal(renderSvg(scene), published);
  assert.equal(JSON.stringify(document), before);
  assert.match(editor, /data-node-id="linear"/);
  assert.doesNotMatch(published, /draft-grid|with-grid|infinite-scene/);
});
