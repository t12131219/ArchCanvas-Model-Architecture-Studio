import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const owner = 'docs/evidence/m4-memory-continuity-current';
const attempt = process.argv[2];
if (!/^production-matrix-attempt-[1-9][0-9]*$/.test(attempt ?? '')) throw Error('append-only attempt required');
const out = path.join(root, owner, attempt);
if (existsSync(out)) throw Error('Do not replace existing evidence');
mkdirSync(out);
const hash = value => createHash('sha256').update(value).digest('hex');
const bind = relative => { const bytes = readFileSync(path.join(root, relative)); return { path: relative, bytes: bytes.length, sha256: hash(bytes) }; };
const current = readdirSync(path.join(root, 'studio/src/core')).filter(p => p.endsWith('.ts')).sort().map(p => `studio/src/core/${p}`);
const previous = readdirSync(path.join(root, owner, 'before-change/inputs/studio/src/core')).filter(p => p.endsWith('.ts')).sort().map(p => `${owner}/before-change/inputs/studio/src/core/${p}`);
const sourcePath = 'docs/evidence/m4-caption-stability-current/independent-review/source-envelope.json';
const adapterPath = 'studio/tests/historical-memory-continuity-compat.ts';
const inputs = [...current, ...previous, sourcePath, adapterPath, `${owner}/capture_production_matrix.mjs`].map(bind);
writeFileSync(path.join(out, 'inputs-before.json'), JSON.stringify(inputs, null, 2) + '\n');
const { applyVisualBatch, createHistory, reduceHistory } = await import(path.join(root, 'studio/src/core/document.ts'));
const { buildExportScene } = await import(path.join(root, 'studio/src/core/exportScene.ts'));
const { buildExportScene: priorScene } = await import(path.join(root, owner, 'before-change/inputs/studio/src/core/exportScene.ts'));
const { normalizeMemoryContinuityGeometry } = await import(path.join(root, adapterPath));
const source = JSON.parse(readFileSync(path.join(root, sourcePath), 'utf8')).document;
const originalSource = JSON.stringify(source), encoder = 'repeat:instance:model.Transformer.encoder', decoder = 'call:instance:model.Transformer.decoder';
const rows = [], checks = [], transitions = [];
const json = value => JSON.stringify(value);
const check = (rowId, name, actual, expected = true) => {
  const passed = json(actual) === json(expected);
  checks.push({ rowId, name, passed, ...(passed ? {} : { actual, expected }) });
};
function points(value) {
  const t = value.match(/[MHV]|[-+]?(?:\d*\.\d+|\d+\.?\d*)/g), p = [];
  for (let i = 0; i < t.length;) { const c = t[i++]; p.push(c === 'M' ? [+t[i++], +t[i++]] : c === 'H' ? [+t[i++], p.at(-1)[1]] : [p.at(-1)[0], +t[i++]]); }
  return p;
}
const length = p => p.slice(1).reduce((sum, b, i) => sum + Math.abs(b[0] - p[i][0]) + Math.abs(b[1] - p[i][1]), 0);
const fixedEdge = ({ path: _p, labelX: _x, labelY: _y, ...rest }) => rest;
function inspect(id, base, operations, options, metadata) {
  const document = applyVisualBatch(base, operations), bytes = json(document);
  const before = priorScene(document, options), scene = buildExportScene(document, options);
  check(id, 'input-immutable', json(document), bytes);
  check(id, 'source-and-ir-facts', [scene.sourceDigest, scene.irDigest, scene.sourceFacts], [before.sourceDigest, before.irDigest, before.sourceFacts]);
  check(id, 'complete-edge-inventory-and-facts', scene.edges.map(fixedEdge), before.edges.map(fixedEdge));
  check(id, 'nonmemory-paths-exact', scene.edges.filter(e => e.role !== 'memory').map(e => [e.id, e.path]), before.edges.filter(e => e.role !== 'memory').map(e => [e.id, e.path]));
  for (const key of ['documentId', 'revision', 'title', 'pageSpec', 'exportScope', 'hiddenEdges', 'legend', 'annotations']) check(id, `protected-${key}`, scene[key], before[key]);
  let adapted = false, adapterError;
  try { normalizeMemoryContinuityGeometry(document, scene); adapted = true; } catch (error) { adapterError = String(error); }
  check(id, 'independent-side-midpoint-and-consumer-version-adapter', adapted);
  check(id, 'detached-rebuild-deterministic', buildExportScene(structuredClone(document), options), scene);
  const memory = scene.edges.filter(e => e.role === 'memory').map(e => {
    const old = before.edges.find(o => o.id === e.id), p = points(e.path), q = points(old.path);
    check(id, `memory-${e.id}-label-preserved`, e.label, old.label);
    check(id, `memory-${e.id}-finite-orthogonal`, p.every((a, i) => a.every(Number.isFinite) && (!i || a[0] === p[i - 1][0] || a[1] === p[i - 1][1])));
    if (e.path !== old.path) check(id, `memory-${e.id}-length-does-not-increase`, length(p) <= length(q) + 1e-6);
    if (metadata.kind === 'horizontal-gap' && metadata.dx > 23) check(id, `memory-${e.id}-narrow-gap-closes`, e.path, old.path);
    return { id: e.id, canonicalEdgeIds: e.canonicalEdgeIds, sourceId: e.sourceId, targetId: e.targetId, label: e.label,
      beforePath: old.path, path: e.path, beforeLength: length(q), length: length(p), beforeEndpoints: [q[0], q.at(-1)], endpoints: [p[0], p.at(-1)], changed: e.path !== old.path,
      ports: scene.nodes.filter(n => [e.sourceId, e.targetId].includes(n.id)).map(n => ({ id: n.id, ports: n.ports.filter(p => p.canonicalEdgeIds.some(id => e.canonicalEdgeIds.includes(id))) })) };
  });
  const row = { id, ...metadata, operations, options, documentSha256: hash(bytes), beforeSceneSha256: hash(json(before)), sceneSha256: hash(json(scene)), memory,
    nonmemoryPathSha256: hash(json(scene.edges.filter(e => e.role !== 'memory').map(e => [e.id, e.path]))), ...(adapterError ? { adapterError } : {}) };
  rows.push(row); return row;
}
const yValues = [-24, -16, -15.001, -15, -14.999, -14, 0, 14, 14.999, 15, 15.001, 16, 24];
const xValues = [22.99, 23, 23.01, 34.99, 35, 35.01, 41.99, 42, 42.01];
for (const mode of ['default', 'empty', 'custom']) for (const preset of ['paper', 'monochrome']) for (const widthMm of [85, 180]) for (const scope of ['whole', 'detail']) {
  const base = structuredClone(source);
  if (mode !== 'default') for (const e of base.architecture.edges.filter(e => e.role === 'memory')) e.label = mode === 'empty' ? '' : 'memory context';
  const options = { widthMm, ...(scope === 'detail' ? { nodeId: base.expandedIds[0] } : {}) };
  for (const endpoint of [encoder, decoder]) {
    const observed = new Map();
    for (const dy of yValues) {
      const id = `${endpoint === encoder ? 'source' : 'target'}-${mode}-${preset}-${widthMm}-${scope}-dy${dy}`;
      observed.set(dy, inspect(id, base, [{ type: 'page', page: { preset, widthMm } }, { type: 'move', ids: [endpoint], dx: 0, dy }], options,
        { kind: 'threshold-y', endpoint, mode, preset, widthMm, scope, dy }));
    }
    for (const [a, b] of [[14, 15], [-14, -15]]) {
      const old = observed.get(a).memory.find(e => e.id === 'edge:44'), now = observed.get(b).memory.find(e => e.id === 'edge:44');
      const id = `${endpoint === encoder ? 'source' : 'target'}-${mode}-${preset}-${widthMm}-${scope}-${a}-to-${b}`;
      const moving = endpoint === encoder ? 0 : 1, fixed = 1 - moving;
      check(id, 'new-length-continuity-one-world-unit', Math.abs(now.length - old.length - 1) < 1e-6);
      check(id, 'fixed-endpoint-exact', now.endpoints[fixed], old.endpoints[fixed]);
      check(id, 'moving-endpoint-x-exact', now.endpoints[moving][0], old.endpoints[moving][0]);
      check(id, 'moving-endpoint-y-one-world-unit', Math.abs(Math.abs(now.endpoints[moving][1] - old.endpoints[moving][1]) - 1) < 1e-6);
      transitions.push({ id, fromRow: observed.get(a).id, toRow: observed.get(b).id, beforeLengths: [old.beforeLength, now.beforeLength], lengths: [old.length, now.length],
        oldEndpointJumps: old.beforeEndpoints.map((p, i) => Math.hypot(p[0] - now.beforeEndpoints[i][0], p[1] - now.beforeEndpoints[i][1])), endpointJumps: old.endpoints.map((p, i) => Math.hypot(p[0] - now.endpoints[i][0], p[1] - now.endpoints[i][1])) });
    }
  }
  for (const dx of xValues) inspect(`gap-${mode}-${preset}-${widthMm}-${scope}-dx${dx}`, base,
    [{ type: 'page', page: { preset, widthMm } }, { type: 'move', ids: [encoder], dx, dy: 15 }], options, { kind: 'horizontal-gap', mode, preset, widthMm, scope, dx, dy: 15 });
}
const initial = createHistory(source), historyBytes = json(initial);
const moved = reduceHistory(initial, { type: 'apply', operations: [{ type: 'move', ids: [encoder], dx: 0, dy: 24 }] });
const undone = reduceHistory(moved, { type: 'undo' }), redone = reduceHistory(undone, { type: 'redo' });
check('history', 'input-history-immutable', json(initial), historyBytes);
check('history', 'single-typed-command', moved.past.length, 1);
check('history', 'undo-document-exact-except-revision', { ...undone.document, revision: source.revision }, source);
// Undo/redo revisions intentionally differ; compare geometry separately.
const redoScene = buildExportScene(redone.document), movedScene = buildExportScene(moved.document);
check('history', 'redo-geometry-exact', { ...redoScene, revision: movedScene.revision }, movedScene);
check('history', 'JSON-persist-reopen-scene-exact', buildExportScene(JSON.parse(json(redone.document))), redoScene);
check('source', 'source-envelope-document-immutable', json(source), originalSource);
const after = inputs.map(i => bind(i.path));
check('inputs', 'pre-post-source-hashes-exact', after, inputs);
writeFileSync(path.join(out, 'inputs-after.json'), JSON.stringify(after, null, 2) + '\n');
writeFileSync(path.join(out, 'rows.json'), JSON.stringify(rows, null, 2) + '\n');
writeFileSync(path.join(out, 'transitions.json'), JSON.stringify(transitions, null, 2) + '\n');
const failures = checks.filter(c => !c.passed);
const report = { schema: 'archcanvas-current-production-memory-matrix/1', createdUtc: new Date().toISOString(), rows: rows.length, yRows: rows.filter(r => r.kind === 'threshold-y').length,
  horizontalGapRows: rows.filter(r => r.kind === 'horizontal-gap').length, memoryOccurrences: rows.reduce((s, r) => s + r.memory.length, 0), adoptedOccurrences: rows.reduce((s, r) => s + r.memory.filter(e => e.changed).length, 0),
  transitionPairs: transitions.length, relations: checks.length, passed: checks.length - failures.length, failures, inputBindings: inputs.length, inputsUnchanged: json(inputs) === json(after), checks,
  scope: 'Production renderer and hash-frozen immediately prior formal core from the same document. The narrow historical adapter independently derives side/midpoint paths and complete consumers; it does not prove obstacle/peer safety. Dedicated independent guard reports provide that finite evidence. Scene geometry, document history and serialization only; no browser pixels, served asset hash, actual publication artifacts, resolved fonts/arrowheads, global aesthetics, performance or human participation.' };
writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ attempt, rows: report.rows, relations: report.relations, passed: report.passed, failures: failures.length, adoptedOccurrences: report.adoptedOccurrences, inputsUnchanged: report.inputsUnchanged }));
process.exitCode = failures.length ? 1 : 0;
