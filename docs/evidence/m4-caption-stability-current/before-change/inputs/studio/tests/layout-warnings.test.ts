import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildScene } from '../src/core/index.ts';
import type { CanvasDocument } from '../src/core/types.ts';
import { layoutWarnings } from '../src/layoutWarnings.ts';

function mlp(): CanvasDocument {
  return JSON.parse(readFileSync(new URL('../../docs/evidence/browser-visual-matrix-boundary-final/captures/mlp-level1-paper-180/canvas.json', import.meta.url), 'utf8'));
}

test('actual upward header conflict produces understandable guidance using display aliases', () => {
  const original = mlp(), id = 'call:instance:model.MLP.network.0';
  const moved = applyVisualBatch(original, [
    { type: 'alias', id, label: '输入投影' },
    { type: 'move', ids: [id], dx: 0, dy: -32 },
  ]);
  const messages = layoutWarnings(buildScene(moved));
  assert.ok(messages.includes('“输入投影”进入了“network”的标题区。向下移动该对象可恢复留白。'));
  assert.ok(messages.every(message => !message.includes('instance:') && !message.includes('edge:')));
  const restored = applyVisualBatch(moved, [{ type: 'move', ids: [id], dx: 0, dy: 32 }]);
  assert.deepEqual(layoutWarnings(buildScene(restored)), []);
});

test('actual overlapping leaves expose both overlap and blocked connection guidance', () => {
  const original = mlp(), id = 'call:instance:model.MLP.network.0';
  const moved = applyVisualBatch(original, [{ type: 'move', ids: [id], dx: 0, dy: 80 }]);
  const messages = layoutWarnings(buildScene(moved));
  assert.ok(messages.some(message => message.includes('“Linear 1”与“GELU 2”重叠')));
  assert.ok(messages.some(message => message.includes('连线缺少畅通路径')));
  assert.ok(messages.every(message => !message.includes('instance:')));
});

test('source-analysis warnings stay in their own panel and missing object references do not leak identifiers', () => {
  const scene = buildScene(mlp());
  scene.diagnostics.push({ level: 'warning', message: 'Unsupported user source expression' });
  assert.deepEqual(layoutWarnings(scene), []);
  scene.diagnostics.push({ level: 'warning', message: 'internal evidence', code: 'layout-header-overlap', objectIds: ['unknown-canonical-id', 'unknown-container-id'] });
  assert.deepEqual(layoutWarnings(scene), ['“对象”进入了“对象”的标题区。向下移动该对象可恢复留白。']);
  assert.deepEqual(layoutWarnings(null), []);
});
