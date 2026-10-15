/** CPU-only parent synchronization probe. Native browser receipts measure the
 * complete interaction separately. No model code is imported or executed. */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import { previewPanelDocument, projectPreviewHistory } from '../src/previewPanelDocument.ts';
import { previewCanvasOperations } from '../src/previewInterop.ts';
import { previewPresentationFields } from '../src/previewPresentation.ts';
import { createHistory, reduceHistory, buildScene, renderSvg, presentEditorScene } from '../src/core/index.ts';
const project = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const args = process.argv.slice(2), option = (name: string, fallback: string) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const output = resolve(option('--output', project + '/docs/evidence/preview-expansion-20261014/parent-projection.json'));
const legacySamples = Number(option('--legacy-samples', '1')), samples = Number(option('--samples', '20'));
if (!Number.isInteger(samples) || samples < 1 || samples > 100 || !Number.isInteger(legacySamples) || legacySamples < 0 || legacySamples > 10) throw new Error('Invalid bounded sample count');
const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const prefix = project + '/studio/public/preview/data/cases/01093cc06a87b35a-';
const overview = read(prefix + 'overview.json'), detail = read(prefix + 'detailed.json');
overview.recursive = { authority: { detail } };
const children = new Set(detail.nodes.map((node: { parent?: string }) => node.parent)), expanded = structuredClone(detail);
for (const node of expanded.nodes) node.expanded = children.has(node.id);
expanded.recursive = { authority: { detail } };
const initial = createHistory(previewPanelDocument({ caseId: '01093cc06a87b35a', graph: overview }));
const time = <T>(operation: () => T): { value: T; ms: number } => { const start = performance.now(); const value = operation(); return { value, ms: performance.now() - start }; };
const legacy = Array.from({ length: legacySamples }, () => {
  const mapped = time(() => previewCanvasOperations(initial.document, expanded));
  const apply = time(() => reduceHistory(initial, { type: 'apply', operations: mapped.value }));
  const fields = time(() => ({ ...apply.value.document, ...previewPresentationFields(apply.value.document, expanded) }));
  const scene = time(() => presentEditorScene(buildScene(fields.value, { presentation: 'editor' })));
  const svg = time(() => renderSvg(scene.value, { interactive: true, background: false, presentation: 'editor' }));
  return { mappingMs: mapped.ms, formalReplayMs: apply.ms, presentationMs: fields.ms, hiddenSceneMs: scene.ms, hiddenSvgMs: svg.ms,
    totalMs: mapped.ms + apply.ms + fields.ms + scene.ms + svg.ms };
});
const projection = Array.from({ length: samples }, () => {
  const projected = time(() => projectPreviewHistory(initial, expanded));
  const copy = structuredClone(expanded), noOp = time(() => projectPreviewHistory(projected.value, copy));
  if (noOp.value !== projected.value || projected.value.document.architecture !== initial.document.architecture) throw new Error('Immutable projection/no-op regression');
  return { projectionMs: projected.ms, unchangedSnapshotMs: noOp.ms };
});
const files = ['studio/src/App.tsx', 'studio/src/previewPanelDocument.ts', 'studio/src/previewPresentation.ts', 'studio/src/previewInterop.ts', 'studio/src/core/document.ts'];
const report = { schema: 'archcanvas-preview-parent-projection-benchmark/1', measuredAt: new Date().toISOString(),
  scope: 'CPU-only recorded Transformer overview to full detail snapshot; excludes iframe transition, Worker, transport, React paint and native event latency',
  caseId: '01093cc06a87b35a', nodes: detail.nodes.length, edges: detail.edges.length, node: process.version,
  implementation: Object.fromEntries(files.map(path => [path, createHash('sha256').update(readFileSync(project + '/' + path)).digest('hex')])), legacy, projection };
mkdirSync(dirname(output), { recursive: true }); writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ output, legacy, projection }));
