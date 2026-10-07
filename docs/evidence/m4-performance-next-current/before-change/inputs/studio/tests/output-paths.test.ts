import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { applyVisualBatch, buildScene, createDocument, reconcileDocument, validateArchitecture } from '../src/core/index.ts';
import type { Architecture } from '../src/core/index.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
async function temporal(): Promise<Architecture> {
  const local = fileURLToPath(new URL('../../.venv/bin/python', import.meta.url));
  const python = existsSync(local) ? local : 'python3';
  const { stdout } = await promisify(execFile)(python, ['-I', '-S', '-B', '-c',
    'import sys,json; from pathlib import Path; root=Path(sys.argv[1]); sys.path.insert(0,str(root/"src")); from archcanvas_python import analyze_project; print(json.dumps(analyze_project(root/"fixtures/holdout_families","model:TemporalForecaster")))',
    project], { encoding: 'utf8', maxBuffer: 2_000_000 });
  return JSON.parse(stdout) as Architecture;
}

test('formal LSTM nested output slots retain handwritten key/index evidence in documents', async () => {
  const architecture = await temporal();
  validateArchitecture(architecture);
  const returned = architecture.nodes.filter(node => node.kind === 'Output');
  assert.deepEqual(returned.map(node => node.outputPath), [
    [{ kind: 'key', key: 'forecast' }, { kind: 'index', index: 0 }],
    [{ kind: 'key', key: 'forecast' }, { kind: 'index', index: 1 }],
    [{ kind: 'key', key: 'state' }, { kind: 'key', key: 'hidden' }],
    [{ kind: 'key', key: 'state' }, { kind: 'key', key: 'cell' }],
  ]);
  const d = createDocument(architecture);
  assert.deepEqual(JSON.parse(JSON.stringify(d)).architecture.nodes.filter((node: { kind: string }) => node.kind === 'Output'), returned);
  assert.ok(returned.every(node => buildScene(d).nodes.some(visible => visible.id === node.id)));
});

test('import validation rejects malformed output paths and slots on non-output nodes', async () => {
  const architecture = await temporal();
  const output = architecture.nodes.findIndex(node => node.kind === 'Output');
  for (const value of [null, {}, [{ kind: 'index', index: -1 }], [{ kind: 'index', index: 1.5 }],
    [{ kind: 'index', index: true }], [{ kind: 'index', index: 9007199254740992 }],
    [{ kind: 'key', key: [] }], [{ kind: 'key', key: Infinity }], [{ kind: 'key' }],
    [{ kind: 'index', index: 0, key: 'x' }], [{ kind: 'unknown' }]]) {
    const invalid = structuredClone(architecture);
    invalid.nodes[output].outputPath = value as never;
    assert.throws(() => validateArchitecture(invalid), /outputPath/);
  }
  const invalid = structuredClone(architecture);
  invalid.nodes.find(node => node.kind === 'Input')!.outputPath = [];
  assert.throws(() => validateArchitecture(invalid), /only graph Output/);
});

test('a renamed return slot cannot borrow presentation from the prior ordinal output', async () => {
  const architecture = await temporal();
  const output = architecture.nodes.find(node => node.kind === 'Output')!;
  const old = applyVisualBatch(createDocument(architecture), [{ type: 'alias', id: output.id, label: 'Forecast identity' }]);
  const changed = structuredClone(architecture);
  changed.sourceDigest = 'changed-source'; changed.irDigest = 'changed-ir';
  changed.nodes.find(node => node.id === output.id)!.outputPath = [{ kind: 'key', key: 'unrelated' }];
  const refreshed = reconcileDocument(old, changed);
  assert.equal(refreshed.document.displayAliases[output.id], undefined);
  assert.ok(!refreshed.preservedNodeIds.includes(output.id));
});
