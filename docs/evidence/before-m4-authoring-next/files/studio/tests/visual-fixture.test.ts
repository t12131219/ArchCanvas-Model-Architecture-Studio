import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { applyVisualBatch, buildScene, createDocument } from '../src/core/index.ts';
import type { Architecture } from '../src/core/index.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
async function actualFixture(fixture: string, entry: string): Promise<Architecture> {
  const local = fileURLToPath(new URL('../../.venv/bin/python', import.meta.url));
  const python = existsSync(local) ? local : 'python3';
  const { stdout } = await promisify(execFile)(python, ['-I', '-S', '-B', '-c',
    'import sys,json; from pathlib import Path; root=Path(sys.argv[1]); sys.path.insert(0,str(root/"src")); from archcanvas_python import analyze_project; print(json.dumps(analyze_project(root/"fixtures"/sys.argv[2],sys.argv[3])))',
    project, fixture, entry], { encoding: 'utf8', maxBuffer: 2_000_000 });
  return JSON.parse(stdout) as Architecture;
}

test('real residual CNN nested expansion keeps downstream pool clear and restores base frontier', async () => {
  const a = await actualFixture('residual_cnn', 'model:ResidualCNN');
  let d = createDocument(a);
  const base = buildScene(d);
  for (const label of ['blocks', 'ResidualBlock 1', 'ResidualBlock 2']) {
    const id = a.nodes.find(n => n.label === label)!.id;
    const before = buildScene(d).nodes.find(n => n.id === id)!;
    d = applyVisualBatch(d, [{ type: 'expand', id, expanded: true }]);
    const scene = buildScene(d), current = scene.nodes.find(n => n.id === id)!;
    assert.equal(current.x, before.x); assert.equal(current.y, before.y);
    const repeat = scene.nodes.find(n => n.label === 'blocks')!;
    const pool = scene.nodes.find(n => n.label === 'pool')!;
    assert.ok(pool.y >= repeat.y + repeat.height + 30, `pool must remain below the complete grown repeat after ${label}`);
  }
  for (const label of ['ResidualBlock 2', 'ResidualBlock 1', 'blocks']) {
    d = applyVisualBatch(d, [{ type: 'expand', id: a.nodes.find(n => n.label === label)!.id, expanded: false }]);
  }
  const restored = buildScene(d);
  for (const node of base.nodes) {
    const current = restored.nodes.find(n => n.id === node.id)!;
    assert.deepEqual([current.x, current.y, current.width, current.height], [node.x, node.y, node.width, node.height]);
  }
});

test('real MLP pinned output conflict is explicit while both expansion anchors stay fixed', async () => {
  const a = await actualFixture('mlp', 'model:MLP');
  let d = createDocument(a);
  const initial = buildScene(d), output = initial.nodes.find(n => n.category === 'output')!;
  const network = initial.nodes.find(n => n.label === 'network')!;
  d = applyVisualBatch(d, [{ type: 'pin', ids: [output.id], pinned: true }, { type: 'expand', id: network.id, expanded: true }]);
  const scene = buildScene(d), pinned = scene.nodes.find(n => n.id === output.id)!, expanded = scene.nodes.find(n => n.id === network.id)!;
  assert.deepEqual([pinned.x, pinned.y], [output.x, output.y]);
  assert.deepEqual([expanded.x, expanded.y], [network.x, network.y]);
  assert.ok(scene.diagnostics.some(diagnostic => diagnostic.level === 'warning' && diagnostic.message.includes('Pinned object') && diagnostic.message.includes('overlaps expanded')));
  d = applyVisualBatch(d, [{ type: 'expand', id: network.id, expanded: false }]);
  assert.ok(!buildScene(d).diagnostics.some(diagnostic => diagnostic.message.includes('overlaps expanded')));
});
