import type { Architecture, ArchitectureNode, CanvasDocument, Scene, SceneEdge, SceneNode } from '../../../../studio/src/core/types.ts';

export function architecture(kind: 'different-tensors' | 'shared-trunk' | 'unavoidable-stub'): Architecture {
  const node = (id: string): ArchitectureNode => ({ id, label: id, kind: 'Linear', category: 'linear', children: [],
    parameters: {}, evidence: 'contract', ports: [{ id: 'in', name: 'input', direction: 'in', role: 'data', ordinal: 0 }, { id: 'out', name: 'output', direction: 'out', role: 'data', ordinal: 0 }] });
  const sharedSource = kind !== 'different-tensors';
  return { schemaVersion: 1, id: `independent:${kind}`, label: `Hand-written routing fixture ${kind}`, entry: 'manual:fixture',
    sourceDigest: 'hand-written-no-model-executed', irDigest: `manual-${kind}`, sources: [], diagnostics: [],
    nodes: (sharedSource ? ['a', 'b', 'd'] : ['a', 'b', 'c', 'd']).map(node), edges: [
      { id: 'ab', source: { nodeId: 'a', portId: 'out' }, target: { nodeId: 'b', portId: 'in' }, tensorId: 'tensor-a', role: 'data' },
      { id: 'cd', source: { nodeId: sharedSource ? 'a' : 'c', portId: 'out' }, target: { nodeId: 'd', portId: 'in' }, tensorId: kind === 'shared-trunk' ? 'tensor-a' : 'tensor-c', role: 'data' },
    ] };
}
export function placeFixture(document: CanvasDocument) {
  document.layout = { a: { x: 0, y: 0 }, b: { x: 300, y: 300 }, d: { x: 0, y: 300 },
    ...(document.architecture.nodes.some(node => node.id === 'c') ? { c: { x: 300, y: 0 } } : {}) };
  document.layoutByFrontier = {}; return document;
}
/** Small coherent figure for deliberate oracle contamination, not product routing evidence. */
export function cleanScene(): Scene {
  const raw = [['a', 0, 0], ['b', 0, 120], ['c', 100, 0], ['d', 100, 120]] as const;
  const nodes = raw.map(([id, x, y]): SceneNode => ({ id, x, y, width: 20, height: 20, localX: x, localY: y,
    label: id, subtitle: '', headerHeight: 20, kind: 'Linear', category: 'linear', fill: '#fff', stroke: '#000', glyph: 'operator',
    expanded: false, expandable: false, pinned: false, evidence: 'contract', ports: [] }));
  const edges = [['ab', 'a', 'b', 10], ['cd', 'c', 'd', 110]].map(([id, source, target, x]): SceneEdge => {
    const edgeId = String(id), sourceId = String(source), targetId = String(target), cx = Number(x);
    for (const [owner, direction, y] of [[sourceId, 'out', 20], [targetId, 'in', 120]] as const) nodes.find(node => node.id === owner)!.ports.push({ id: `${owner}:${direction}`, canonicalNodeId: owner,
      canonicalPortId: direction, canonicalBindings: [{ nodeId: owner, portId: direction }], canonicalEdgeIds: [edgeId], direction,
      role: 'data', name: direction, x: cx, y, proxy: false });
    return { id: edgeId, sourceId, targetId, source: { nodeId: sourceId, portId: 'out' }, target: { nodeId: targetId, portId: 'in' }, canonicalEdgeIds: [edgeId],
      tensorId: `tensor-${edgeId}`, role: 'data', path: `M ${cx} 20 V 120`, stroke: '#000', width: 1.5, dashed: false, label: '', labelX: cx, labelY: 80 };
  });
  return { version: '1.0', documentId: 'coherent-independent-control', revision: 0, title: 'Control', bounds: { x: -100, y: -100, width: 600, height: 600 },
    nodes, edges, hiddenEdges: [], legend: [], annotations: [], pageSpec: { widthMm: 180, background: '#fff', preset: 'paper' },
    sourceDigest: 'manual-control-source', irDigest: 'manual-control-ir', sourceFacts: [], diagnostics: [] };
}
