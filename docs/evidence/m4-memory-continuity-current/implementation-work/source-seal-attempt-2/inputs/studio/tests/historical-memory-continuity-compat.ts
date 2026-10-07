import assert from 'node:assert/strict';
import type { CanvasDocument, Scene, SceneNode, ScenePort } from '../src/core/types.ts';
import * as prior from '../../docs/evidence/m4-memory-continuity-current/before-change/inputs/studio/src/core/index.ts';

const serial = <T>(value: T): T => value === undefined ? value : JSON.parse(JSON.stringify(value));
const round = (v: number) => Math.round(v * 100) / 100;
function points(path: string) {
  const tokens = path.match(/[MHV]|[-+]?(?:\d*\.\d+|\d+\.?\d*)/g)!; const result: { x: number; y: number }[] = [];
  for (let i = 0; i < tokens.length;) { const c = tokens[i++];
    result.push(c === 'M' ? { x: +tokens[i++], y: +tokens[i++] } : c === 'H'
      ? { x: +tokens[i++], y: result.at(-1)!.y } : { x: result.at(-1)!.x, y: +tokens[i++] }); }
  return result;
}
function sidePoint(node: SceneNode, side: 'right' | 'left') {
  const y = node.y + node.height * .55;
  const shifts = node.repeat && !node.expanded ? [0, 3.5, 7] : [0];
  const atRay = shifts.filter(shift => y >= node.y + shift && y <= node.y + shift + node.height);
  return { x: side === 'right' ? Math.max(...atRay.map(shift => node.x + shift + node.width))
    : Math.min(...atRay.map(shift => node.x + shift)), y };
}

/** Version adapter for historical tests only. It independently derives the
 * narrow side/midpoint geometry and chosen-consumer port coverage. It does not
 * certify adoption safety: dedicated peer/body tests and independent audit do.
 * No gold/oracle or actual scene is mutated; arbitrary memory paths fail. */
export function normalizeMemoryContinuityGeometry(document: CanvasDocument, current: Scene): Scene {
  const scope = current.exportScope ? { nodeId: current.exportScope.selectedNodeId, widthMm: current.pageSpec.widthMm } : {};
  const before = prior.buildExportScene(document, scope);
  const canonical = new Map(document.architecture.edges.map((e, index) => [e.id, { edge: e, index }]));
  assert.equal(current.nodes.length, before.nodes.length);
  assert.equal(current.edges.length, before.edges.length);
  for (const key of ['documentId', 'revision', 'sourceDigest', 'irDigest', 'sourceFacts', 'hiddenEdges', 'pageSpec', 'annotations', 'legend', 'exportScope'] as const)
    assert.deepEqual(serial(current[key]), serial(before[key]), `memory projection altered protected ${key}`);
  const expectedMemory = new Map<string, Map<string, ScenePort>>();
  const memoryPort = (p: ScenePort) => p.canonicalEdgeIds.length > 0 && p.canonicalEdgeIds.every(id => canonical.get(id)?.edge.role === 'memory');
  for (let i = 0; i < before.edges.length; i++) {
    const old = before.edges[i], actual = current.edges[i];
    const { path: _op, labelX: _ox, labelY: _oy, ...oldFixed } = old;
    const { path: _ap, labelX: _ax, labelY: _ay, ...actualFixed } = actual;
    assert.deepEqual(serial(actualFixed), serial(oldFixed), 'memory projection cannot alter canonical identities, styles or labels');
    if (old.role !== 'memory') { assert.equal(actual.path, old.path, 'every nonmemory path must remain exact'); continue; }
    const original = points(old.path), source = before.nodes.find(n => n.id === old.sourceId)!, target = before.nodes.find(n => n.id === old.targetId)!;
    const a = sidePoint(source, 'right'), b = sidePoint(target, 'left'), lane = round((round(a.x) + round(b.x)) / 2);
    const proposed = round(a.y) === round(b.y) ? `M ${round(a.x)} ${round(a.y)} H ${round(b.x)}`
      : `M ${round(a.x)} ${round(a.y)} H ${lane} V ${round(b.y)} H ${round(b.x)}`;
    const changed = actual.path !== old.path;
    if (changed) {
      assert.equal(source.expanded, false); assert.equal(target.expanded, false);
      const bottom = (n: SceneNode) => n.y + n.height + (n.repeat && !n.expanded ? 7 : 0);
      assert.ok(Math.min(bottom(source), bottom(target)) > Math.max(source.y, target.y));
      assert.ok(lane - round(a.x) >= 6 - 1e-7 && round(b.x) - lane >= 6 - 1e-7);
      assert.equal(actual.path, proposed, 'only the independently derived side midpoint path can be adapted');
    }
    for (const direction of ['out', 'in'] as const) {
      const owner = direction === 'out' ? source : target;
      const endpoint = direction === 'out' ? original[0] : original.at(-1)!;
      const template = owner.ports.find(p => p.direction === direction && old.canonicalEdgeIds.every(id => p.canonicalEdgeIds.includes(id)) &&
        Math.abs(p.x - endpoint.x) <= .051 && Math.abs(p.y - endpoint.y) <= .051);
      assert.ok(template, 'frozen public port coverage is required');
      const side = direction === 'out' ? 'right' : 'left';
      const id = changed ? `${template.canonicalNodeId}:${template.canonicalPortId}:memory:${side}` : template.id;
      const group = expectedMemory.get(owner.id) ?? new Map<string, ScenePort>();
      let port = group.get(id);
      if (!port) {
        port = { ...structuredClone(template), id, canonicalEdgeIds: [], canonicalBindings: [], ...(changed ? direction === 'out' ? a : b : {}) };
        group.set(id, port); expectedMemory.set(owner.id, group);
      }
      for (const id of old.canonicalEdgeIds) if (!port.canonicalEdgeIds.includes(id)) port.canonicalEdgeIds.push(id);
      port.canonicalBindings = id === template.id && JSON.stringify(port.canonicalEdgeIds) === JSON.stringify(template.canonicalEdgeIds)
        ? structuredClone(template.canonicalBindings)
        : port.canonicalEdgeIds.map(id => canonical.get(id)!).sort((a, b) => a.index - b.index)
          .map(({ edge }) => direction === 'out' ? edge.source : edge.target);
    }
  }
  for (let index = 0; index < before.nodes.length; index++) {
    const old = before.nodes[index], actual = current.nodes[index];
    const { ports: _o, ...oldBody } = old, { ports: _a, ...actualBody } = actual;
    assert.deepEqual(serial(actualBody), serial(oldBody), 'node bodies/facts/anchors must remain exact');
    assert.deepEqual(serial(actual.ports.filter(p => !memoryPort(p))), serial(old.ports.filter(p => !memoryPort(p))), 'nonmemory ports must remain exact');
    const memory = actual.ports.filter(memoryPort), expected = [...(expectedMemory.get(old.id)?.values() ?? [])];
    assert.equal(memory.length, expected.length, 'no memory ports may be dropped or invented');
    for (const p of memory) assert.deepEqual(serial(p), serial(expected.find(e => e.id === p.id)), 'chosen memory consumer coverage and port geometry must be exact');
  }
  const copy = structuredClone(current);
  copy.nodes = before.nodes.map((old, index) => {
    const node = structuredClone(old);
    // Preserve whether this test supplied a raw or JSON-serialized Scene.
    for (const key of Object.keys(node) as (keyof SceneNode)[])
      if (node[key] === undefined && !Object.hasOwn(current.nodes[index], key)) delete node[key];
    return node;
  });
  for (let i = 0; i < copy.edges.length; i++) if (copy.edges[i].role === 'memory') copy.edges[i].path = before.edges[i].path;
  return copy;
}
