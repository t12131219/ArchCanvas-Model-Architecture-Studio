import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import crypto from 'node:crypto';
import { blankDraft, changeDraft, draftHistory, travelDraft } from '../../../../studio/src/authoring.ts';
import { draftPresets, insertDraftPreset } from '../../../../studio/src/authoringPresets.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../../..');
const inputPath = process.argv[2], outputPath = process.argv[3];
if (!inputPath || !outputPath) throw new Error('Usage: node --experimental-strip-types sample-frontends.mjs catalog.json drafts.json');
const catalog = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
const samples = [], checks = [], records = [];
const hash = filename => crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
const productFiles = ['studio/src/authoring.ts', 'studio/src/authoringPresets.ts'];
const productBindingsBefore = Object.fromEntries(productFiles.map(filename => [filename, hash(path.join(root, filename))]));
const makeFactory = label => {
  const counts = { n: 0, e: 0 };
  return prefix => `${prefix}_${label}_${counts[prefix]++}`;
};
const invariantHeader = draft => ({ id: draft.id, title: draft.title, revision: draft.revision, schemaVersion: draft.schemaVersion, mode: draft.mode });
const same = (left, right) => assert.deepEqual(left, right);

function inserted(draft, preset, factory) {
  const old = structuredClone(draft);
  const receipt = insertDraftPreset(draft, catalog, preset, { x: 50, y: 70 }, factory);
  same(invariantHeader(draft), invariantHeader(old));
  same(draft.nodes.slice(0, old.nodes.length), old.nodes);
  same(draft.edges.slice(0, old.edges.length), old.edges);
  assert.equal(new Set([...draft.nodes.map(n => n.id), ...draft.edges.map(e => e.id)]).size, draft.nodes.length + draft.edges.length);
  assert.deepEqual(receipt.nodeIds, draft.nodes.slice(old.nodes.length).map(n => n.id));
  assert.deepEqual(receipt.edgeIds, draft.edges.slice(old.edges.length).map(e => e.id));
  const newIds = new Set(receipt.nodeIds);
  for (const edge of draft.edges.slice(old.edges.length)) {
    assert.ok(newIds.has(edge.source.nodeId) && newIds.has(edge.target.nodeId), 'New network must not bind into existing subgraphs');
  }
  for (const node of draft.nodes.slice(old.nodes.length)) {
    assert.ok(Number.isFinite(node.position.x) && Number.isFinite(node.position.y));
    for (const previous of old.nodes) {
      assert.ok(Math.abs(node.position.x - previous.position.x) >= 196 || Math.abs(node.position.y - previous.position.y) >= 120, 'Existing card overlap');
    }
  }
  records.push({ draftId: draft.id, preset, old, after: structuredClone(draft), receipt });
  return receipt;
}

function sample(caseId, presets, draft) {
  samples.push({ caseId, presets, draft: structuredClone(draft) });
}

function existing(identity, prefix) {
  return { schemaVersion: 1, mode: 'authored-draft', id: identity, title: '手写既有网络', revision: 17,
    nodes: [
      { id: `${prefix}_feature`, kind: 'Input', label: '原输入', parameters: { shape: [2, 7], dtype: 'float32' }, position: { x: 50, y: 70 } },
      { id: `${prefix}_identity`, kind: 'Identity', label: '原恒等', parameters: {}, position: { x: 298, y: 70 } },
      { id: `${prefix}_output`, kind: 'Output', label: '原输出', parameters: {}, position: { x: 546, y: 70 } },
    ], edges: [
      { id: `${prefix}_edge1`, source: { nodeId: `${prefix}_feature`, portId: 'output' }, target: { nodeId: `${prefix}_identity`, portId: 'input' } },
      { id: `${prefix}_edge2`, source: { nodeId: `${prefix}_identity`, portId: 'output' }, target: { nodeId: `${prefix}_output`, portId: 'input' } },
    ] };
}

try {
  same(draftPresets.map(p => p.id), ['mlp', 'cnn', 'residual-mlp']);
  for (const preset of ['mlp', 'cnn', 'residual-mlp']) {
    const single = blankDraft(`draft-single-${preset}`);
    inserted(single, preset);
    sample(`single-${preset}`, [preset], single);

    const repeated = blankDraft(`draft-repeat-${preset}`);
    inserted(repeated, preset, makeFactory('restart'));
    const firstIds = new Set([...repeated.nodes.map(n => n.id), ...repeated.edges.map(e => e.id)]);
    const receipt = inserted(repeated, preset, makeFactory('restart'));
    assert.ok([...receipt.nodeIds, ...receipt.edgeIds].every(id => !firstIds.has(id)));
    sample(`repeat-${preset}`, [preset, preset], repeated);
    checks.push({ name: `repeat-${preset}-collisions`, status: 'passed', firstObjectCount: firstIds.size, disjointNewObjectCount: receipt.nodeIds.length + receipt.edgeIds.length });

    const resultCopies = [];
    for (const [identity, prefix] of [['draft-existing-a', 'before_a'], ['draft-existing-b', 'before_b']]) {
      const old = existing(identity, prefix);
      const oldSnapshot = structuredClone(old);
      inserted(old, preset, makeFactory('inserted'));
      sample(`existing-${prefix}-${preset}`, ['identity-pass', preset], old);
      same(invariantHeader(old), invariantHeader(oldSnapshot));
      resultCopies.push(old);
      checks.push({ name: `${identity}-${preset}-preserved`, status: 'passed', oldNodes: oldSnapshot.nodes.length, oldEdges: oldSnapshot.edges.length });
    }
    same(resultCopies[0].nodes.slice(3), resultCopies[1].nodes.slice(3));
    same(resultCopies[0].edges.slice(2), resultCopies[1].edges.slice(2));
    checks.push({ name: `different-existing-identity-${preset}`, status: 'passed', basis: 'Same inserted-node/edge values from identical deterministic factories, independent draft IDs and existing object IDs preserved.' });

    const historyStart = existing(`draft-history-${preset}`, `history_${preset}`);
    const history = draftHistory(historyStart);
    const after = changeDraft(history, next => insertDraftPreset(next, catalog, preset, { x: 50, y: 70 }, makeFactory('history')));
    assert.equal(after.past.length, 1); assert.equal(after.draft.revision, 18); assert.equal(after.future.length, 0);
    same(history.draft, historyStart);
    const undo = travelDraft(after, 'undo'), redo = travelDraft(undo, 'redo');
    same({ ...undo.draft, revision: 17 }, historyStart);
    same({ ...redo.draft, revision: 18 }, after.draft);
    checks.push({ name: `one-history-change-${preset}`, status: 'passed', savedHistory: { before: historyStart, after, undo, redo } });
  }

  const mixed = blankDraft('draft-mixed');
  for (const preset of ['mlp', 'cnn', 'residual-mlp']) inserted(mixed, preset);
  sample('mixed-three', ['mlp', 'cnn', 'residual-mlp'], mixed);
  const randomizedRepeated = blankDraft('draft-random-repeats');
  const sequence = ['mlp', 'cnn', 'residual-mlp', 'mlp', 'cnn', 'residual-mlp'];
  for (const preset of sequence) inserted(randomizedRepeated, preset);
  sample('random-id-repeat-mixed-six', sequence, randomizedRepeated);

  for (const [name, factory] of [
    ['always-invalid-identity', () => 'illegal id'],
    ['late-edge-identity-collision', (() => { let n = 0; return prefix => prefix === 'n' ? `n_late_${n++}` : 'before_a_feature'; })()],
    ['reused-existing-edge-as-node', () => 'before_a_edge1'],
  ]) {
    const draft = existing('draft-atomic-failure', 'before_a'), before = structuredClone(draft);
    assert.throws(() => insertDraftPreset(draft, catalog, 'residual-mlp', { x: 50, y: 70 }, factory));
    same(draft, before);
    checks.push({ name, status: 'passed', draftPreserved: true });
  }

  for (const position of [{ x: 999999, y: 50 }, { x: Number.NaN, y: 50 }]) {
    const draft = existing('draft-position-failure', 'position'), before = structuredClone(draft);
    assert.throws(() => insertDraftPreset(draft, catalog, 'cnn', position));
    same(draft, before);
    checks.push({ name: `out-of-contract-position-${String(position.x)}`, status: 'passed', draftPreserved: true });
  }

  for (const preset of draftPresets) {
    const draft = existing(`draft-catalog-failure-${preset.id}`, 'catalog'), before = structuredClone(draft);
    const incompatible = structuredClone(catalog);
    incompatible.modules = incompatible.modules.filter(m => m.kind !== 'Linear');
    assert.throws(() => insertDraftPreset(draft, incompatible, preset.id, { x: 50, y: 70 }));
    same(draft, before);
    checks.push({ name: `missing-module-${preset.id}`, status: 'passed', draftPreserved: true });
  }

  same(productBindingsBefore, Object.fromEntries(productFiles.map(filename => [filename, hash(path.join(root, filename))])));
  const payload = { schemaVersion: 1, scope: 'Actual exported frontend preset function calls with source bindings; independent snapshots, no browser use.', nodeVersion: process.version, catalogBinding: { path: inputPath, sha256: hash(inputPath) }, productBindings: productBindingsBefore, samples, identityChecks: checks, insertionRecords: records };
  fs.writeFileSync(outputPath, JSON.stringify(payload, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ status: 'passed', samples: samples.length, identityChecks: checks.length, output: outputPath }));
} catch (error) {
  fs.writeFileSync(outputPath + '.FAILED.json', JSON.stringify({ message: String(error), samplesCompleted: samples, identityChecksCompleted: checks, insertionRecords: records, productBindingsBefore }, null, 2) + '\n', { flag: 'wx' });
  throw error;
}
