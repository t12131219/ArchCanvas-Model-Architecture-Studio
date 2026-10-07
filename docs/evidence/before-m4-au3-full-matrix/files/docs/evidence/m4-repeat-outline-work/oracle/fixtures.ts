import type { Architecture, ArchitectureNode, Scene, SceneNode } from '../../../../studio/src/core/types.ts';

export function architecture(nodes: ArchitectureNode[], edges: Architecture['edges']): Architecture {
  return { schemaVersion: 1, id: 'architecture:independent-repeat-outline', label: 'Independent Repeat outline cases', entry: 'oracle:Model',
    sourceDigest: 'independent-source', irDigest: 'independent-ir', sources: [], diagnostics: [], nodes, edges };
}
export function canonicalNode(id: string, options: Partial<ArchitectureNode> = {}): ArchitectureNode {
  return { id, label: id, kind: 'Linear', category: 'linear', children: [], parameters: {}, evidence: 'source',
    ports: [{ id: 'in', name: 'input', direction: 'in', role: 'data', ordinal: 0 }, { id: 'out', name: 'output', direction: 'out', role: 'data', ordinal: 0 }], ...options };
}
export const repeat = { count: 3, sharing: 'independent' as const };
export function cornerArchitecture(): Architecture {
  const source = canonicalNode('stack', { repeat }), target = canonicalNode('consumer');
  source.ports = Array.from({ length: 70 }, (_, index) => ({ id: `out-${index}`, name: `output-${index}`, direction: 'out', role: 'data', ordinal: index }));
  target.ports = Array.from({ length: 70 }, (_, index) => ({ id: `in-${index}`, name: `input-${index}`, direction: 'in', role: 'data', ordinal: index }));
  return architecture([source, target], source.ports.map((port, index) => ({ id: `corner-${index}`, source: { nodeId: source.id, portId: port.id },
    target: { nodeId: target.id, portId: target.ports[index].id }, tensorId: `corner-tensor-${index}`, role: 'data' })));
}
export function mixedSideArchitecture(): Architecture {
  const source = canonicalNode('stack', { repeat }); source.ports.find(port => port.id === 'out')!.role = 'memory';
  const below = canonicalNode('below'), right = canonicalNode('right');
  for (const node of [below, right]) node.ports.find(port => port.id === 'in')!.role = 'memory';
  // The bottom request is intentionally encountered before the right request.
  // A later in-place mutation of a reused port detaches the first path.
  return architecture([source, below, right], ['below', 'right'].map(id => ({ id: `to-${id}`, source: { nodeId: 'stack', portId: 'out' },
    target: { nodeId: id, portId: 'in' }, tensorId: 'same-canonical-memory', role: 'memory' })));
}
export function hierarchyArchitecture(): Architecture {
  return architecture([
    canonicalNode('root', { kind: 'Model', category: 'container', children: ['input', 'stack', 'output'] }),
    canonicalNode('input', { category: 'input', parentId: 'root' }),
    canonicalNode('stack', { category: 'container', kind: 'Repeat', parentId: 'root', children: ['leaf'], repeat }),
    canonicalNode('leaf', { parentId: 'stack' }), canonicalNode('output', { category: 'output', parentId: 'root' }),
  ], [
    { id: 'entry', source: { nodeId: 'input', portId: 'out' }, target: { nodeId: 'leaf', portId: 'in' }, tensorId: 'input-tensor', role: 'data' },
    { id: 'exit', source: { nodeId: 'leaf', portId: 'out' }, target: { nodeId: 'output', portId: 'in' }, tensorId: 'output-tensor', role: 'data' },
  ]);
}
export function sceneNode(id: string, x: number, y: number, width = 20, height = 20, repeating = false): SceneNode {
  return { id, x, y, width, height, localX: x, localY: y, label: id, subtitle: '', headerHeight: 20,
    kind: 'Linear', category: 'linear', fill: '#ffffff', stroke: '#000000', glyph: 'operator', expanded: false,
    expandable: false, pinned: false, evidence: 'source', ports: [], ...(repeating ? { repeat } : {}) };
}
export function manualScene(nodes: SceneNode[], path: string): Scene {
  return { version: '1.0', documentId: 'independent-repeat-outline', revision: 0, title: 'Independent Repeat outline oracle',
    bounds: { x: -20, y: -20, width: 240, height: 260 }, nodes,
    edges: [{ id: 'route', sourceId: 'a', targetId: 'b', source: { nodeId: 'a', portId: 'out' }, target: { nodeId: 'b', portId: 'in' },
      canonicalEdgeIds: ['route'], tensorId: 'tensor', role: 'data', path, stroke: '#000000', width: 1.5, dashed: false, label: '', labelX: 0, labelY: 0 }],
    hiddenEdges: [], legend: [], annotations: [], pageSpec: { widthMm: 180, background: '#ffffff', preset: 'paper' },
    sourceDigest: 'independent-source', irDigest: 'independent-ir', diagnostics: [], sourceFacts: [] };
}
