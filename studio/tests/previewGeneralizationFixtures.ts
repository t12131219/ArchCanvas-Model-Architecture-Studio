import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import type { Architecture, ArchitectureNode, CanvasDocument, HistoryState } from '../src/core/types.ts';
import type { PreviewSourceBundle, PreviewVisualGraph, PreviewVisualNode, RawPreviewSource } from '../src/previewInterop.ts';
import { previewPanelDocument, projectPreviewHistory } from '../src/previewPanelDocument.ts';

type Graph = PreviewVisualGraph & { caseId?: string; edges: { id: string; source: string; target: string }[];
  recursive?: { authority: { detail: Graph }; state?: { studioPresentation?: Record<string, unknown> } }; studioPresentation?: Record<string, unknown> };
const root = new URL('../public/preview/', import.meta.url);
type SourceDescriptor = { available?: boolean; title: string; entry: string; evidence?: string; profile?: Record<string, unknown>;
  files: { path: string; originalPath?: string; asset: string; sha256: string }[] };
function registeredSource(id: string): RawPreviewSource | undefined {
  const descriptor = JSON.parse(readFileSync(new URL('data/catalog-sources.json', root), 'utf8')).cases[id] as SourceDescriptor | undefined;
  if (!descriptor?.available) return undefined;
  const files = Object.fromEntries(descriptor.files.map(file => {
    const text = readFileSync(new URL(file.asset, root), 'utf8');
    if (createHash('sha256').update(text).digest('hex') !== file.sha256) throw Error(`Source fixture hash mismatch: ${file.path}`);
    return [file.path, text];
  }));
  const sourcePath = (value: string) => {
    const aliases = (file: SourceDescriptor['files'][number]) => [file.path, file.originalPath].filter((path): path is string => !!path);
    const exact = descriptor.files.find(file => aliases(file).includes(value));
    const suffix = descriptor.files.filter(file => aliases(file).some(path => value.endsWith('/' + path)));
    const basename = descriptor.files.filter(file => aliases(file).some(path => value.endsWith('/' + path.split('/').at(-1))));
    return (exact ?? (suffix.length === 1 ? suffix[0] : undefined) ?? (basename.length === 1 ? basename[0] : undefined))?.path ?? value.replace(/^.*\/prototype\//, '');
  };
  const raw = descriptor.evidence ? JSON.parse(readFileSync(new URL(descriptor.evidence, root), 'utf8')) : {};
  const evidence: NonNullable<RawPreviewSource['evidence']> = {};
  for (const [key, value] of Object.entries(raw.symbols ?? raw)) {
    const item = value as { file?: string; path?: string; source?: string; evidence_id?: string; line?: number; start?: number; endLine?: number; end?: number; expression?: string; snippet?: string; column?: number; endColumn?: number };
    if (!item || typeof item !== 'object' || !Number.isFinite(item.line ?? item.start)) continue;
    const path = item.file ?? item.path ?? item.source ?? raw.origin;
    if (typeof path !== 'string') continue;
    const line = (item.line ?? item.start)!;
    evidence[item.evidence_id ?? key] = { file: sourcePath(path), line, endLine: item.endLine ?? item.end ?? line,
      expression: item.expression ?? item.snippet ?? '', column: item.column ?? 0, endColumn: item.endColumn ?? 0 };
  }
  const [entryFile, symbol] = descriptor.entry.split('::');
  const entry = symbol ? entryFile.replace(/(?:\/__init__)?\.py$/, '').replaceAll('/', '.') + ':' + symbol.split('.')[0] : descriptor.entry;
  return { schema: 'archcanvas-preview-source/1', caseId: id, title: descriptor.title, entry, files, evidence, profile: descriptor.profile ?? {} };
}
export function registeredProjectionFixture(id: string) {
  const catalog = JSON.parse(readFileSync(new URL('data/catalog.json', root), 'utf8'));
  const item = catalog.cases.find((entry: { id: string }) => entry.id === id);
  if (!item) throw new Error(`Missing case ${id}`);
  const views: { key: string; json?: string }[] = item.views;
  const view = (key: string) => JSON.parse(readFileSync(new URL(views.find(view => view.key === key)?.json ?? views.find(view => view.json)?.json ?? 'snapshots/yworks_edge_router_lab/evidence/verification/overlap-fixture.json', root), 'utf8')) as Graph;
  const overview = view('overview'), detail = view('detailed');
  overview.recursive = { authority: { detail } };
  const children = new Set(detail.nodes.map(node => node.parent)), expanded = structuredClone(detail);
  expanded.nodes.forEach(node => { node.expanded = children.has(node.id); });
  expanded.recursive = { authority: { detail } };
  const source = registeredSource(id), document = previewPanelDocument({ caseId: id, graph: overview }, source);
  const initial: HistoryState = { document, past: [], future: [] };
  return { id, title: item.title as string, overview, detail, expanded, source, initial };
}

/** Two independent calls share one module instance, plus an explicit fork and
 * tuple slots. Distinct paths and return slots are known facts, not inferred
 * from a visual junction. The large fixture exercises the import node budget. */
export function syntheticProjectionFixture(size = 12, recursive = true) {
  if (size < 12 || size > 480) throw new Error('Fixture size outside import node budget');
  const files = [
    { path: 'models/__init__.py', text: '', sha256: 'empty' },
    { path: 'models/shared.py', text: 'from torch import nn\nclass Block(nn.Module):\n def forward(self, x):\n  return self.shared(x)\n', sha256: 'shared' },
    { path: 'models/network.py', text: 'from .shared import Block\nclass Network:\n def forward(self, x):\n  a = self.shared(x)\n  b = self.shared(x)\n  return (a, b)\n', sha256: 'network' },
  ];
  const spec: { id: string; kind: string; path: string; line: number; parent?: string; children: string[] }[] = [
    { id: 'net/root', kind: 'group', path: files[2].path, line: 2, children: ['branch/a', 'branch/b', 'tuple'] },
    { id: 'branch/a', kind: 'group', path: files[1].path, line: 2, parent: 'net/root', children: ['call/a', 'slot/0'] },
    { id: 'branch/b', kind: 'group', path: files[1].path, line: 2, parent: 'net/root', children: ['call/b', 'slot/1'] },
    { id: 'call/a', kind: 'linear', path: files[2].path, line: 4, parent: 'branch/a', children: [] },
    { id: 'call/b', kind: 'linear', path: files[2].path, line: 5, parent: 'branch/b', children: [] },
    { id: 'slot/0', kind: 'output', path: files[2].path, line: 6, parent: 'branch/a', children: [] },
    { id: 'slot/1', kind: 'output', path: files[2].path, line: 6, parent: 'branch/b', children: [] },
    { id: 'tuple', kind: 'opaque', path: files[2].path, line: 6, parent: 'net/root', children: [] },
  ];
  while (spec.length < size) {
    const ordinal = spec.length, parent = ordinal % 2 ? 'branch/a' : 'branch/b', id = `aux/${ordinal}`;
    spec.push({ id, kind: 'linear', path: files[1].path, line: 4, parent, children: [] });
    spec.find(node => node.id === parent)!.children.push(id);
  }
  const nodes: ArchitectureNode[] = spec.map(node => ({ id: node.id, label: node.id, kind: node.kind === 'group' ? 'Network' : node.kind === 'output' ? 'Output' : 'Linear',
    category: node.kind === 'group' ? 'container' : node.kind, ...(node.parent ? { parentId: node.parent } : {}), children: node.children,
    parameters: {}, evidence: 'source', ports: [{ id: 'out', name: 'out', direction: 'out', role: 'tensor', ordinal: 0 }, { id: 'in', name: 'in', direction: 'in', role: 'tensor', ordinal: 0 }],
    source: { path: node.path, line: node.line, endLine: node.line, expression: node.kind === 'linear' ? 'self.shared(x)' : node.id },
    ...(node.id.startsWith('call/') ? { instanceId: 'instance:models.network.Network.shared', callId: node.id } : {}),
    ...(node.id.startsWith('slot/') ? { outputPath: [{ kind: 'index' as const, index: Number(node.id.split('/')[1]) }] } : {}),
  }));
  const edges: Architecture['edges'] = [['net/root', 'call/a'], ['net/root', 'call/b'], ['call/a', 'slot/0'], ['call/b', 'slot/1']].map(([from, to], i) => ({
    id: `canonical/${i}`, source: { nodeId: from, portId: 'out' }, target: { nodeId: to, portId: 'in' }, tensorId: i < 2 ? 'shared-input' : `return-slot-${i - 2}`, role: 'data',
  }));
  for (const node of spec.slice(8)) edges.push({ id: `canonical/aux/${node.id}`, source: { nodeId: node.parent === 'branch/a' ? 'call/a' : 'call/b', portId: 'out' },
    target: { nodeId: node.id, portId: 'in' }, tensorId: node.parent === 'branch/a' ? 'shared-branch-a' : 'shared-branch-b', role: 'data' });
  const architecture: Architecture = { schemaVersion: 1, id: `generic-${size}`, label: 'Generic shared branch', entry: 'models.network:Network',
    sourceDigest: `generic-source-${size}`, irDigest: `generic-ir-${size}`, nodes, edges, diagnostics: [],
    sources: files.map(file => ({ path: file.path, content: file.text, digest: file.sha256 })) };
  const graphNodes: PreviewVisualNode[] = spec.map((node, i) => ({ id: node.id, label: node.id, ...(node.parent ? { parent: node.parent } : {}),
    x: node.id === 'net/root' ? 10 : node.parent === 'branch/b' ? 700 : 100, y: node.id === 'net/root' ? 20 : i * 90 + 80,
    w: 180, h: 64, expanded: !!node.children.length }));
  const detail: Graph = { caseId: `generic-${size}`, nodes: graphNodes, edges: edges.map(edge => ({ id: edge.id, source: edge.source.nodeId, target: edge.target.nodeId })) };
  const overview: Graph = { ...structuredClone(detail), nodes: detail.nodes.filter(node => !['branch/a', 'branch/b'].includes(node.parent ?? '')).map(node => ({ ...node, expanded: node.id === 'net/root' })) };
  if (recursive) overview.recursive = { authority: { detail } };
  const document: CanvasDocument = { schemaVersion: 1, id: `canvas-generic-${size}`, title: architecture.label, revision: 0, architecture, sourceBindingDigest: architecture.sourceDigest,
    displayAliases: {}, nodeStyleOverrides: {}, edgeStyleOverrides: {}, expandedIds: ['net/root'], layout: {}, layoutByFrontier: {}, pinnedObjects: [],
    legendItems: [], annotations: [], pageSpec: { widthMm: 180, background: '#ffffff', preset: 'paper' } };
  const source: PreviewSourceBundle = { schema: 'summary-source-adapter/1', id: detail.caseId!, entry: architecture.entry, sourceSha256: 'different-parser-manifest', irSha256: 'different-parser-ir', files };
  const initial = projectPreviewHistory({ document, past: [], future: [] }, overview, source);
  const expanded: Graph = structuredClone(detail);
  if (recursive) expanded.recursive = { authority: { detail } };
  return { id: detail.caseId!, title: architecture.label, overview, detail, expanded, source, initial };
}
