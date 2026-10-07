import type { Architecture, ArchitectureNode, CanvasDocument, EdgeRole, Scene, SceneEdge } from '../../../../studio/src/core/types.ts';

const roles: EdgeRole[] = ['data', 'residual', 'memory', 'mask'];

/** Literal named bindings: no product construction/layout helper supplies expected facts. */
export function roleDocument(options: { allRoles?: boolean; duplicateResidual?: boolean; hiddenMemory?: boolean; empty?: boolean } = {}): CanvasDocument {
  const node = (id: string, parentId?: string, children: string[] = []): ArchitectureNode => ({
    id, label: `Literal ${id}`, kind: children.length ? 'Module' : 'Linear', category: children.length ? 'container' : 'linear',
    ...(parentId ? { parentId } : {}), children, parameters: {}, evidence: 'source',
    ports: [{ id: 'in', name: 'values', direction: 'in', role: 'data', ordinal: 0 },
      { id: 'out', name: 'result', direction: 'out', role: 'data', ordinal: 0 }],
  });
  const nodes = [node('shell', undefined, ['feed', 'unit', 'sink']), node('feed', 'shell'),
    node('unit', 'shell', ['inside']), node('inside', 'unit'), node('sink', 'shell')];
  const edge = (id: string, role: EdgeRole, target = 'inside') => ({ id, role, source: { nodeId: 'feed', portId: 'out' },
    target: { nodeId: target, portId: 'in' }, tensorId: 'literal-same-tensor' });
  const edges = options.empty ? [] : (options.allRoles ? roles : ['data', 'residual'] as EdgeRole[]).map(role => edge(`literal-${role}`, role));
  if (options.duplicateResidual) edges.push(edge('literal-residual-solid', 'residual'), edge('literal-residual-dashed', 'residual'));
  if (options.hiddenMemory) edges.push({ id: 'literal-hidden-memory', role: 'memory',
    source: { nodeId: 'inside', portId: 'out' }, target: { nodeId: 'unit', portId: 'in' }, tensorId: 'literal-hidden-tensor' });
  const architecture: Architecture = { schemaVersion: 1, id: 'literal-role-oracle', label: 'Independent role graph', entry: 'literal:Model',
    sourceDigest: 'literal-source-digest', irDigest: 'literal-ir-digest', sources: [], diagnostics: [], nodes, edges };
  return { schemaVersion: 1, id: 'literal-role-canvas', title: 'Independent role graph', revision: 0,
    sourceBindingDigest: architecture.sourceDigest, architecture, displayAliases: {}, nodeStyleOverrides: {}, edgeStyleOverrides: {},
    legendItems: [{ id: 'user-category', label: '手工类别与原顺序', color: '#eff0f1', glyph: 'module' }],
    annotations: [], pageSpec: { widthMm: 180, background: '#ffffff', preset: 'monochrome' },
    expandedIds: ['shell'], layout: { shell: { x: 50, y: 92 }, feed: { x: 30, y: 62 }, unit: { x: 30, y: 162 },
      sink: { x: 30, y: 262 }, inside: { x: 30, y: 62 } }, layoutByFrontier: {}, pinnedObjects: ['sink'] };
}

/** Pure literal renderer input for negative controls; not a product Scene snapshot. */
export function literalScene(): Scene {
  const emptyNode = (id: string, x: number, y: number) => ({ id, x, y, width: 40, height: 30,
    localX: x, localY: y, label: id, subtitle: '', headerHeight: 30, kind: 'Linear', category: 'linear',
    fill: '#ffffff', stroke: '#56616b', glyph: 'operator' as const, expanded: false,
    expandable: false, pinned: false, evidence: 'source' as const, ports: [] });
  const edges: SceneEdge[] = roles.map((role, i) => ({ id: `role-${role}`, sourceId: 'literal-start', targetId: 'literal-end',
    source: { nodeId: 'literal-start', portId: 'out' }, target: { nodeId: 'literal-end', portId: 'in' },
    canonicalEdgeIds: [`role-${role}`], tensorId: 'literal-common-tensor', role, path: `M ${80+i*20} 130 V 210`,
    stroke: '#56616b', width: 1.5, dashed: role !== 'data', label: '', labelX: 0, labelY: 0 }));
  return { version: '1.0', documentId: 'literal-renderer-scene', revision: 0, title: 'Literal line roles',
    bounds: { x: 0, y: 0, width: 560, height: 450 }, nodes: [emptyNode('literal-start', 70, 100), emptyNode('literal-end', 70, 210)],
    edges, hiddenEdges: [], legend: [], annotations: [], pageSpec: { widthMm: 180, background: '#ffffff', preset: 'monochrome' },
    sourceDigest: 'literal-source', irDigest: 'literal-ir', sourceFacts: [], diagnostics: [] };
}
