import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { applyVisualBatch, buildScene, createDocument } from '../src/core/index.ts';
import type { Architecture } from '../src/core/index.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));

test('source-backed 300-layer Sequential expansion exposes 300 canonical layer objects', async () => {
  const local = fileURLToPath(new URL('../../.venv/bin/python', import.meta.url));
  const python = existsSync(local) ? local : 'python3';
  const { stdout } = await promisify(execFile)(python, ['-I', '-S', '-B', '-c',
    'import sys,json; from pathlib import Path; root=Path(sys.argv[1]); sys.path.insert(0,str(root/"src")); from archcanvas_python import analyze_project; print(json.dumps(analyze_project(root/"fixtures/stress_300","model:DenseStress300")))',
    project], { encoding: 'utf8', maxBuffer: 2_000_000 });
  const architecture = JSON.parse(stdout) as Architecture;
  assert.equal(architecture.nodes.length, 304);
  const root = architecture.nodes.find(node => !node.parentId)!;
  const containers = architecture.nodes.filter(node => node.children.length > 0 && node.parentId);
  assert.equal(containers.length, 1);
  const target = containers[0];
  assert.equal(target.label, 'network');
  assert.equal(target.children.length, 300);
  const initial = createDocument(architecture);
  assert.deepEqual(initial.expandedIds, [root.id]);
  const before = buildScene(initial);
  assert.equal(before.nodes.length, 4);
  assert.equal(before.edges.length, 2);
  assert.ok(before.nodes.find(node => node.id === target.id)?.expandable);
  assert.equal(before.nodes.find(node => node.id === target.id)?.expanded, false);
  const expandedDocument = applyVisualBatch(initial, [{ type: 'expand', id: target.id, expanded: true }]);
  const expanded = buildScene(expandedDocument);
  const canonicalIds = new Set(architecture.nodes.map(node => node.id));
  assert.equal(expanded.nodes.length, 304);
  assert.equal(expanded.nodes.filter(node => node.kind === 'Linear' || node.kind === 'ReLU').length, 300);
  assert.ok(expanded.nodes.every(node => canonicalIds.has(node.id)));
  assert.equal(expanded.edges.length, 302);
  const collapsed = buildScene(applyVisualBatch(expandedDocument, [{ type: 'expand', id: target.id, expanded: false }]));
  assert.deepEqual(collapsed.nodes.map(node => node.id), before.nodes.map(node => node.id));
});
