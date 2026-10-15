/** CPU-only parent projection across recorded model families and bounded
 * import-style graphs. This excludes native UI events and Worker routing. */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { performance } from 'node:perf_hooks';
import { createHash } from 'node:crypto';
import { projectPreviewHistory } from '../src/previewPanelDocument.ts';
import { validateDocument } from '../src/core/validate.ts';
import { registeredProjectionFixture, syntheticProjectionFixture } from '../tests/previewGeneralizationFixtures.ts';
const project = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const args = process.argv.slice(2), option = (name: string, fallback: string) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const output = resolve(option('--output', project + '/docs/evidence/preview-generalization-20261014/parent-projection.json'));
const samples = Number(option('--samples', '10'));
if (!Number.isInteger(samples) || samples < 1 || samples > 100) throw Error('Invalid sample budget');
const cases = ['e40ad1504991acea', '2ae45b28d78ba027', '654be40c8d6a5cc2', '0342f4170c15ba8e', '9a9263f9a6014d8a', 'dab3eabe196047ba', '39ca17212a8004c5', 'b4e7f02ce4dce8d4', 'routing-lab'];
const fixtureFactories = [...cases.map(id => () => registeredProjectionFixture(id)), ...[12, 480].flatMap(size => [true, false].map(recursive => () => ({ ...syntheticProjectionFixture(size, recursive), title: `import-${size}-${recursive ? 'recursive' : 'plain'}` })))];
const measured = fixtureFactories.map(create => {
  const start = performance.now(), fixture = create(), setupMs = performance.now() - start;
  const source = 'source' in fixture ? fixture.source : undefined, initial = fixture.initial, architecture = JSON.stringify(initial.document.architecture);
  const runs = Array.from({ length: samples }, () => {
    const started = performance.now(), full = projectPreviewHistory(initial, fixture.expanded, source), projectionMs = performance.now() - started;
    const copy = structuredClone(fixture.expanded), noOpStart = performance.now(), unchanged = projectPreviewHistory(full, copy, source), unchangedMs = performance.now() - noOpStart;
    if (unchanged !== full || full.document.architecture !== initial.document.architecture || JSON.stringify(full.document.architecture) !== architecture) throw Error('Source/history identity changed');
    validateDocument(full.document);
    const positions = new Map(copy.nodes.map(node => [node.id, node]));
    for (const node of copy.nodes) {
      const parent = node.parent ? positions.get(node.parent) : undefined;
      if (node.parent && !parent) continue;
      const actual = full.document.layout[node.id];
      if (actual.x !== node.x - (parent?.x ?? 0) || actual.y !== node.y - (parent?.y ?? 0)) throw Error(`Coordinate mismatch ${node.id}`);
    }
    return { projectionMs, unchangedMs };
  });
  return { id: fixture.id, title: fixture.title, nodes: fixture.detail.nodes.length, edges: fixture.detail.edges.length, sourceFiles: initial.document.architecture.sources.length,
    detailSha256: createHash('sha256').update(JSON.stringify(fixture.detail)).digest('hex'),
    sourceCorpusSha256: createHash('sha256').update(JSON.stringify(initial.document.architecture.sources.map(file => [file.path, file.content]))).digest('hex'),
    setupMs, sourceIdentityPreserved: true, exactLocalCoordinates: true, unchangedHistoryStable: true, runs };
});
const files = ['studio/src/App.tsx', 'studio/src/previewPanelDocument.ts', 'studio/src/previewPresentation.ts', 'studio/src/previewInterop.ts', 'studio/tests/previewGeneralizationFixtures.ts', 'studio/tests/previewGeneralization.test.ts', 'studio/scripts/benchmark-preview-generalization.ts', 'studio/public/preview/data/catalog-sources.json'];
const report = { schema: 'archcanvas-preview-general-parent-projection/1', measuredAt: new Date().toISOString(), node: process.version,
  scope: 'CPU-only parent projection of recorded snapshots and synthetic multifile/shared-call/tuple cases; excludes native UI events, React paint, iframe and Worker',
  cases: measured.length, samplesPerCase: samples, implementation: Object.fromEntries(files.map(path => [path, createHash('sha256').update(readFileSync(project + '/' + path)).digest('hex')])), measured };
mkdirSync(dirname(output), { recursive: true }); writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ output, cases: report.cases, measured: measured.map(item => ({ id: item.id, title: item.title, nodes: item.nodes, edges: item.edges, minMs: Math.min(...item.runs.map(run => run.projectionMs)), maxMs: Math.max(...item.runs.map(run => run.projectionMs)) })) }));
