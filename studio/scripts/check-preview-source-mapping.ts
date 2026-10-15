// Audit reviewed display IDs independently of formal source editing identities.
// Run check-preview-sources.py first to write --architectures-output, then:
// node --experimental-strip-types studio/scripts/check-preview-source-mapping.ts
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { previewMappingCoverage, previewPanelDocument } from '../src/previewPanelDocument.ts';
import type { Architecture } from '../src/core/types.ts';
import type { PreviewSnapshot } from '../src/PreviewStudio.tsx';
import type { PreviewSourceBundle, PreviewVisualNode } from '../src/previewInterop.ts';

const args = process.argv.slice(2);
const option = (key: string, fallback: string) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const project = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const root = resolve(option('--preview-root', project + '/studio/public/preview'));
const output = resolve(option('--output', project + '/docs/evidence/preview-sources-20261014/source-mapping.json'));
const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const catalog = read(root + '/data/catalog.json');
const index = read(root + '/data/catalog-sources.json').cases;
const architectures: Record<string, Architecture> = read(option('--architectures', '/tmp/archcanvas-catalog-formal-architectures.json'));
const results: { id: string; title: string; formal: boolean; sourceAvailable: boolean; coverage?: ReturnType<typeof previewMappingCoverage>; displayPanel?: boolean }[] = [];
const allNodes = (item: { views: { json?: string }[] }) => {
  const nodes = new Map<string, PreviewVisualNode>();
  for (const view of item.views.filter(view => view.json)) {
    for (const node of read(root + '/' + view.json).nodes) if (!nodes.has(node.id)) nodes.set(node.id, node);
  }
  return [...nodes.values()];
};
for (const item of catalog.cases) {
  if (item.historical) continue;
  const descriptor = index[item.id], architecture = architectures[item.id];
  if (!architecture) {
    results.push({ id: item.id, title: item.title, formal: false, sourceAvailable: descriptor.available });
    continue;
  }
  const evidence: PreviewSourceBundle['evidence'] = {};
  const raw = descriptor.evidence ? read(root + '/' + descriptor.evidence) : {};
  for (const [key, value] of Object.entries(raw.symbols ?? raw)) {
    const entry = value as { line?: number; start?: number; endLine?: number; end?: number; file?: string; path?: string; source?: string; expression?: string; snippet?: string; evidence_id?: string };
    if (!entry || typeof entry !== 'object' || !(entry.line ?? entry.start)) continue;
    const path = entry.file ?? entry.path ?? entry.source ?? raw.origin;
    const aliases = (file: { path: string; originalPath?: string }): string[] => [file.path, file.originalPath].filter((value): value is string => Boolean(value));
    const exact = descriptor.files.find((file: { path: string; originalPath?: string }) => aliases(file).includes(path));
    const suffix = descriptor.files.filter((file: { path: string; originalPath?: string }) => aliases(file).some(alias => path?.endsWith('/' + alias)));
    const basename = descriptor.files.filter((file: { path: string; originalPath?: string }) => aliases(file).some(alias => path?.endsWith('/' + alias.split('/').at(-1))));
    const file = exact ?? (suffix.length === 1 ? suffix[0] : null) ?? (basename.length === 1 ? basename[0] : null);
    evidence[entry.evidence_id ?? key] = { file: file?.path ?? path, line: entry.line ?? entry.start!, endLine: entry.endLine ?? entry.end ?? entry.line ?? entry.start!, expression: entry.expression ?? entry.snippet ?? '' };
  }
  const source: PreviewSourceBundle = { schema: 'archcanvas-preview-source/1', caseId: item.id, entry: architecture.entry,
    files: Object.fromEntries(descriptor.files.map((file: { path: string; asset: string }) => [file.path, readFileSync(root + '/' + file.asset, 'utf8')])), evidence };
  const snapshot = { caseId: item.id, graph: { nodes: allNodes(item), edges: [] } } as unknown as PreviewSnapshot;
  const coverage = previewMappingCoverage(snapshot, architecture, source);
  results.push({ id: item.id, title: item.title, formal: true, sourceAvailable: descriptor.available, coverage,
    displayPanel: coverage.unmapped.length + coverage.ambiguous.length + coverage.shared.length > 0 });
}
const projection = [];
for (const item of catalog.cases) {
  const nodes = allNodes(item);
  if (!nodes.length) continue;
  const snapshot = { caseId: item.id, graph: { nodes, edges: [] } } as unknown as PreviewSnapshot;
  projection.push({ id: item.id, ...previewMappingCoverage(snapshot, previewPanelDocument(snapshot).architecture) });
}
const formal = results.filter(item => item.formal);
const sum = (key: 'total' | 'mapped' | 'unmapped' | 'ambiguous' | 'shared') => formal.reduce((count, item) => {
  const value = item.coverage![key]; return count + (typeof value === 'number' ? value : value.length);
}, 0);
const report = { schema: 'archcanvas-preview-source-mapping-audit/1', scope: 'current catalog; union of registered view node IDs; originalPath normalized to canonical Python corpus; no source execution',
  cases: results.length, sourceAvailable: results.filter(item => item.sourceAvailable).length, formalParsed: formal.length,
  fullFormalView: formal.filter(item => !item.displayPanel).length, opaqueDisplayPanel: results.filter(item => !item.formal || item.displayPanel).length,
  displayProjection: { cases: projection.length, nodes: projection.reduce((count, item) => count + item.total, 0),
    mapped: projection.reduce((count, item) => count + item.mapped, 0), incompleteCases: projection.filter(item => item.total !== item.mapped).map(item => item.id) },
  nodeCoverage: { total: sum('total'), mapped: sum('mapped'), unmapped: sum('unmapped'), ambiguous: sum('ambiguous'), shared: sum('shared') }, results };
mkdirSync(dirname(output), { recursive: true }); writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ ...report, results: undefined }));
if (report.displayProjection.incompleteCases.length) process.exitCode = 1;
