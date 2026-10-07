// New static source-bound workload only. No old artifacts are written.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { applyVisualBatch, buildScene, createHistory, reduceHistory, renderSvg, validateDocument } from '../../../../studio/src/core/index.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const project = path.resolve(here, '../../../..');
const out = path.join(here, 'workload'); fs.mkdirSync(out, { recursive: true });
const sourcePath = path.join(project, 'docs/evidence/m4-readable-grid-next-work/inputs/previous-workload/grid.canvas.json');
const bytes = fs.readFileSync(sourcePath), original = JSON.parse(bytes);
const root = 'call:instance:model.DenseStress300', network = 'call:instance:model.DenseStress300.network';
const output = 'output:model.DenseStress300:0', pin = 'input:model.DenseStress300:features';
const compactKey = 'visible-frontier/1:["call:instance:model.DenseStress300"]';
const deepKey = 'visible-frontier/1:["call:instance:model.DenseStress300","call:instance:model.DenseStress300.network"]';
assert.equal(original.revision, 4); assert.equal(original.architecture.nodes.find(n => n.id === network).children.length, 300);
assert.deepEqual(original.pinnedObjects, []); assert.deepEqual(original.layout[output], { x: 30, y: 30254 });
assert.deepEqual(original.layoutByFrontier[compactKey][output], { x: 30, y: 262 }); validateDocument(original);
const operation = { type: 'move', ids: [output], dx: 0, dy: -28590, scope: 'current-frontier' };
const history = reduceHistory(createHistory(original), { type: 'apply', baseRevision: 4, operations: [operation] });
const candidate = history.document, expected = structuredClone(original);
expected.revision = 5; expected.layout[output] = { x: 30, y: 1664 }; expected.layoutByFrontier[deepKey] = structuredClone(expected.layout);
assert.deepEqual(candidate, expected); assert.equal(history.past.length, 1);
const pinned = applyVisualBatch(candidate, [{ type: 'pin', ids: [pin], pinned: true }]);
const collapsed = applyVisualBatch(pinned, [{ type: 'expand', id: network, expanded: false }]);
const reexpanded = applyVisualBatch(collapsed, [{ type: 'expand', id: network, expanded: true }]);
const documents = { candidate, pinned, collapsed, reexpanded };
const write = (name, content) => fs.writeFileSync(path.join(out, name), content, { flag: 'wx' });
write('unbroken-grid4.canvas.json', bytes); write('typed-current-move.json', JSON.stringify(operation, null, 2) + '\n');
const scenes = {};
for (const [name, document] of Object.entries(documents)) {
  validateDocument(document); assert.deepEqual(document.architecture, original.architecture);
  const scene = buildScene(document); scenes[name] = scene;
  write(`${name}.canvas.json`, JSON.stringify(document, null, 2) + '\n');
  write(`${name}.scene.json`, JSON.stringify(scene, null, 2) + '\n');
  write(`${name}.svg`, renderSvg(scene, { interactive: true }));
}
assert.equal(scenes.candidate.nodes.length, 304); assert.equal(scenes.collapsed.nodes.length, 4);
assert.equal(scenes.collapsed.nodes.find(n => n.id === output).y, 354);
assert.equal(scenes.reexpanded.nodes.find(n => n.id === output).y, 1756);
const hash = raw => crypto.createHash('sha256').update(raw).digest('hex');
const coreDirectory = path.join(project, 'studio/src/core');
const inputs = [sourcePath, ...fs.readdirSync(coreDirectory).filter(n => n.endsWith('.ts')).sort().map(n => path.join(coreDirectory, n))]
  .map(p => { const raw = fs.readFileSync(p); return { path: path.relative(project, p), bytes: raw.length, sha256: hash(raw) }; });
const report = { schema: 'archcanvas-frontier-scoped-workload-preparation/1', inputs, operation,
  documentId: candidate.id, sourceBindingDigest: candidate.sourceBindingDigest, irDigest: candidate.architecture.irDigest,
  inputRevision: 4, initialMoveHistoryEntries: history.past.length,
  preservedCompactCacheExact: JSON.stringify(candidate.layoutByFrontier[compactKey]) === JSON.stringify(original.layoutByFrontier[compactKey]),
  rootId: root, networkId: network, outputId: output, pinId: pin,
  states: Object.entries(documents).map(([name, d]) => { const s = scenes[name]; return { name, revision: d.revision,
    sceneObjects: s.nodes.length, leafObjects: s.nodes.filter(n => candidate.architecture.nodes.find(a => a.id === network).children.includes(n.id)).length,
    renderedEdges: s.edges.length, bounds: s.bounds, pinnedIds: d.pinnedObjects,
    outputWorld: Object.fromEntries(['x', 'y'].map(k => [k, s.nodes.find(n => n.id === output)[k]])),
    outputLocal: d.layout[output], diagnostics: s.diagnostics }; }),
  modelExecuted: false, browserInputsAdded: 0, humanParticipantsAdded: 0, performanceGatePassed: false,
  scope: 'Formal current core, genuine typed current-frontier move from unbroken frozen grid4, then typed pin/collapse/reexpand. Static preparation; no timing, paint, actual font/readability or publication acceptance.' };
write('preparation-report.json', JSON.stringify(report, null, 2) + '\n');
process.stdout.write(JSON.stringify({ documentId: report.documentId, states: report.states.map(({ diagnostics, ...s }) => s), inputBindings: inputs.length }, null, 2) + '\n');
