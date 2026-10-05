import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { cpus, platform, arch, loadavg, totalmem, freemem } from 'node:os';

const directory = dirname(fileURLToPath(import.meta.url));
const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) args.set(process.argv[index], process.argv[index + 1]);
const label = args.get('--label');
const coreDirectory = resolve(args.get('--core'));
const output = resolve(args.get('--output'));
const samples = 30, warmup = 5;
assert.ok(label);
const hash = value => createHash('sha256').update(value).digest('hex');
const hashes = () => Object.fromEntries(readdirSync(coreDirectory).filter(name => name.endsWith('.ts')).sort().map(name => [name, hash(readFileSync(join(coreDirectory, name)))]));
const coreHashes = hashes();
const startedAtUtc = new Date().toISOString();
const environment = { node: process.version, executable: process.execPath, pid: process.pid, platform: platform(), arch: arch(),
  cpu: cpus()[0]?.model, cpuCount: cpus().length, initialLoadAverage: loadavg(), totalMemoryBytes: totalmem(), initialFreeMemoryBytes: freemem() };
const core = await import(pathToFileURL(join(coreDirectory, 'index.ts')).href);
const preview = await import(pathToFileURL(join(coreDirectory, 'movePreview.ts')).href);
const inputRecords = [JSON.parse(readFileSync(join(directory, 'baseline-manifest.json'))).inputFiles,
  JSON.parse(readFileSync(join(directory, 'density-inputs.json'))).inputFiles].flat();
const phases = {};
const receipts = {};
const progress = [];
const percentile = (values, probability) => [...values].sort((a, b) => a - b)[Math.ceil(values.length * probability) - 1];
const measure = (id, phase, record, operation) => {
  const start = process.hrtime.bigint();
  const result = operation();
  const ms = Number(process.hrtime.bigint() - start) / 1e6;
  if (record) ((phases[id] ??= {})[phase] ??= []).push(ms);
  return result;
};
try {
  for (let inputIndex = 0; inputIndex < inputRecords.length; inputIndex++) {
    const input = inputRecords[inputIndex];
    const bytes = readFileSync(join(directory, input.path));
    assert.equal(hash(bytes), input.sha256, `frozen input ${input.id}`);
    const document = JSON.parse(bytes);
    core.validateDocument(document);
    const originalBytes = JSON.stringify(document), initial = core.buildScene(document);
    const history = core.createHistory(document), historyBytes = JSON.stringify(history);
    const leaf = initial.nodes.find(node => !node.expandable && !node.pinned && !node.boundary);
    assert.ok(leaf, `visible movable object ${input.id}`);
    const detail = [...initial.nodes].reverse().find(node => node.expanded && node.expandable);
    assert.ok(detail, `visible expanded detail object ${input.id}`);
    let finalReceipt;
    for (let round = 0; round < warmup + samples; round++) {
      const record = round >= warmup;
      // Repeat fixed +/- x/y motion in the same sequence for every core/process.
      const [dx, dy] = [[16, 0], [-16, 0], [0, 16], [0, -16]][round % 4];
      const operation = { type: 'move', ids: [leaf.id], dx, dy };
      const scene = measure(input.id, 'buildScene', record, () => core.buildScene(document));
      const svg = measure(input.id, 'serializeInteractiveSvg', record, () => core.renderSvg(scene, { interactive: true }));
      const combined = measure(input.id, 'buildSceneAndSerialize', record, () => {
        const scene = core.buildScene(document); return { scene, svg: core.renderSvg(scene, { interactive: true }) };
      });
      const session = measure(input.id, 'prepareMoveOnce', record, () => preview.prepareMovePreview(document, operation.ids));
      const previewResult = measure(input.id, 'previewSceneAndSerialize', record, () => {
        const scene = preview.previewMoveScene(session, dx, dy); return { scene, svg: core.renderSvg(scene, { interactive: true }) };
      });
      const committed = measure(input.id, 'guardedCommitSceneAndSerialize', record, () => {
        const next = core.reduceHistory(history, { type: 'apply', operations: [operation], baseRevision: session.baseRevision });
        const scene = core.buildScene(next.document); return { history: next, scene, svg: core.renderSvg(scene, { interactive: true }) };
      });
      const exported = measure(input.id, 'detailExportSceneAndSerialize', record, () => {
        const scene = core.buildExportScene(document, { nodeId: detail.id }); return { scene, svg: core.renderSvg(scene) };
      });
      assert.deepEqual(scene, combined.scene, 'combined entire scene equals single scene');
      assert.equal(svg, combined.svg, 'combined entire interactive SVG equals single serialization');
      assert.deepEqual(previewResult.scene, committed.scene, 'prepared preview matches guarded commit entire scene');
      assert.equal(previewResult.svg, committed.svg, 'prepared preview matches guarded commit SVG bytes');
      assert.deepEqual(committed.history.document.architecture, document.architecture, 'source semantics untouched');
      assert.equal(JSON.stringify(document), originalBytes, 'input document untouched');
      assert.equal(JSON.stringify(history), historyBytes, 'input history untouched');
      const undone = core.reduceHistory(committed.history, { type: 'undo' });
      const redone = core.reduceHistory(undone, { type: 'redo' });
      assert.deepEqual(undone.document.layout, document.layout, 'undo restores layout');
      assert.deepEqual(redone.document.layout, committed.history.document.layout, 'redo restores moved layout');
      finalReceipt = { nodeCount: scene.nodes.length, edgeCount: scene.edges.length,
        canonicalEdgeCount: new Set(scene.edges.flatMap(edge => edge.canonicalEdgeIds)).size,
        detailNodeCount: exported.scene.nodes.length, detailEdgeCount: exported.scene.edges.length,
        movableId: leaf.id, detailId: detail.id, inputDocumentSha256: hash(originalBytes),
        sceneSha256: hash(JSON.stringify(scene)), interactiveSvgSha256: hash(svg), detailSceneSha256: hash(JSON.stringify(exported.scene)),
        detailSvgSha256: hash(exported.svg), lastPreviewSceneSha256: hash(JSON.stringify(previewResult.scene)) };
    }
    receipts[input.id] = finalReceipt;
    progress.push({ id: input.id, rounds: samples + warmup });
    console.log(JSON.stringify({ label, input: input.id, nodeCount: finalReceipt.nodeCount, edges: finalReceipt.edgeCount,
      buildSceneAndSerializeP95Ms: percentile(phases[input.id].buildSceneAndSerialize, .95),
      previewP95Ms: percentile(phases[input.id].previewSceneAndSerialize, .95),
      commitP95Ms: percentile(phases[input.id].guardedCommitSceneAndSerialize, .95) }));
  }
  assert.deepEqual(hashes(), coreHashes, 'frozen measured core remained unchanged');
  const summarized = Object.fromEntries(Object.entries(phases).map(([id, names]) => [id,
    Object.fromEntries(Object.entries(names).map(([name, values]) => [name, { samples: values, p50Ms: percentile(values, .5),
      p95Ms: percentile(values, .95), maxMs: Math.max(...values) }]))]));
  writeFileSync(output, JSON.stringify({ schemaVersion: 1, status: 'completed-cpu-measurement', label, startedAtUtc,
    endedAtUtc: new Date().toISOString(), timer: 'process.hrtime.bigint, monotonic nanoseconds', samples, warmup, environment,
    coreDirectory, coreFiles: coreHashes, scriptSha256: hash(readFileSync(fileURLToPath(import.meta.url))),
    inputFiles: inputRecords, semanticChecks: { completeSceneAndSvgPreviewCommitEqualityEveryRound: true,
      unchangedInputHistoryAndArchitectureEveryRound: true, undoRedoLayoutEveryRound: true },
    receipts, phases: summarized, finalLoadAverage: loadavg(), finalMemoryUsage: process.memoryUsage(),
    limitations: ['CPU-only synchronous public-core paths; no browser event, DOM, layout, paint, presented frame, INP or human readability certification.',
      'Artificial density inputs are geometry stress cases and are not recovered model evidence.',
      'No gc forced; fresh process samples may include GC, JIT and concurrent host noise.',
      'Completed measurements are not a claim that CPU performance met a chosen performance gate.'] }, null, 2) + '\n');
} catch (error) {
  writeFileSync(output, JSON.stringify({ schemaVersion: 1, status: 'failed', label, startedAtUtc, endedAtUtc: new Date().toISOString(),
    environment, coreDirectory, coreFiles: coreHashes, scriptSha256: hash(readFileSync(fileURLToPath(import.meta.url))),
    error: String(error.stack ?? error), completedInputs: progress, partialTimingSamples: phases, receipts }, null, 2) + '\n');
  throw error;
}
