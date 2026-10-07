import assert from 'node:assert/strict';
import type { CanvasDocument, EdgeRole, Scene } from '../../../../studio/src/core/types.ts';
import { bodyRectangles, intrusions, pair, points } from '../../m4-collapsed-residual-work/acceptance/oracle.ts';

export const roleOrder: EdgeRole[] = ['data', 'residual', 'memory', 'mask'];
// These values are the preimplementation design contract, not product tokens.
export const patterns: Record<EdgeRole, number[]> = { data: [], residual: [9, 4], memory: [9, 3, 1, 3], mask: [3, 3] };
const colors: Record<EdgeRole, string> = { data: '#718495', residual: '#b69967', memory: '#8e91c3', mask: '#a194a8' };
const near = (a: number, b: number) => Math.abs(a - b) <= .06;
type Rect = { x: number; y: number; width: number; height: number };
type Element = { name: string; attributes: Record<string, string>; children: Element[]; text: string };
const unescape = (s: string) => s.replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');

/** Complete standalone XML parser: attributes and ignored route bytes fail closed. */
export function parseXml(svg: string): Element {
  assert.ok(!/<!DOCTYPE|<!ENTITY/i.test(svg));
  const root: Element = { name: 'root', attributes: {}, children: [], text: '' }, stack = [root];
  for (const token of svg.match(/<[^>]*>|[^<]+/g) ?? []) {
    if (token.startsWith('<?') || token.startsWith('<!--')) continue;
    if (token.startsWith('</')) { assert.equal(stack.pop()?.name, token.slice(2, -1).trim()); continue; }
    if (!token.startsWith('<')) { stack.at(-1)!.text += unescape(token); continue; }
    const match = token.match(/^<([\w:-]+)([\s\S]*?)\/?\s*>$/); assert.ok(match, `Malformed XML ${token}`);
    const attributes: Record<string, string> = {};
    let rest = match[2];
    while (rest.trim()) {
      const attr = rest.match(/^\s+([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/); assert.ok(attr, `Unparsed XML attribute ${rest}`);
      assert.ok(!(attr[1] in attributes), `Duplicate XML attribute ${attr[1]}`);
      attributes[attr[1]] = unescape(attr[2] ?? attr[3]); rest = rest.slice(attr[0].length);
    }
    const node: Element = { name: match[1], attributes, children: [], text: '' };
    stack.at(-1)!.children.push(node); if (!/\/\s*>$/.test(token)) stack.push(node);
  }
  assert.equal(stack.length, 1, 'Unclosed XML'); assert.equal(root.children.length, 1);
  assert.equal(root.children[0].name, 'svg'); return root.children[0];
}
export const flatten = (node: Element): Element[] => [node, ...node.children.flatMap(flatten)];
function svgPattern(path: Element) {
  const raw = path.attributes['stroke-dasharray'];
  if (raw === undefined || raw === 'none') return [];
  assert.match(raw, /^\s*\d+(?:\.\d+)?(?:[ ,]+\d+(?:\.\d+)?)*\s*$/);
  const values = raw.trim().split(/[ ,]+/).map(Number); assert.ok(values.every(value => Number.isFinite(value) && value > 0));
  return values;
}
export function expectedAppearance(document: CanvasDocument, edgeId: string) {
  const edge = document.architecture.edges.find(edge => edge.id === edgeId); assert.ok(edge);
  const style = document.edgeStyleOverrides[edgeId] ?? {}, mono = document.pageSpec.preset === 'monochrome';
  const pattern = style.dashed === true ? [5, 4] : style.dashed === false ? [] : mono ? patterns[edge.role] : edge.role === 'mask' ? [5, 4] : [];
  return { stroke: mono ? '#56616b' : style.stroke ?? colors[edge.role], width: style.width ?? 1.5,
    dashed: pattern.length > 0, pattern: [...pattern] };
}
export function assertCoverage(document: CanvasDocument, scene: Scene) {
  const members = [...scene.hiddenEdges, ...scene.edges.flatMap(edge => edge.canonicalEdgeIds)];
  assert.deepEqual([...members].sort(), document.architecture.edges.map(edge => edge.id).sort(), 'canonical coverage');
  assert.equal(new Set(members).size, members.length, 'canonical duplicate');
  assert.equal(scene.sourceDigest, document.architecture.sourceDigest); assert.equal(scene.irDigest, document.architecture.irDigest);
  for (const edge of scene.edges) {
    assert.ok(edge.canonicalEdgeIds.length); assert.ok(edge.canonicalEdgeIds.includes(edge.id));
    const canonical = edge.canonicalEdgeIds.map(id => document.architecture.edges.find(item => item.id === id)!);
    assert.ok(canonical.every(Boolean));
    for (const member of canonical) {
      assert.equal(member.role, edge.role, 'role changed/merged'); assert.equal(member.tensorId, edge.tensorId, 'tensor changed/merged');
      assert.deepEqual(member.source, edge.source, 'source binding changed/merged');
    }
    assert.deepEqual(canonical[0].target, edge.target, 'target binding changed');
  }
}
export function assertStyles(document: CanvasDocument, scene: Scene) {
  assertCoverage(document, scene);
  for (const edge of scene.edges) {
    const expected = expectedAppearance(document, edge.canonicalEdgeIds[0]);
    assert.equal(edge.stroke, expected.stroke, `stroke ${edge.id}`); assert.equal(edge.width, expected.width, `width ${edge.id}`);
    assert.equal(edge.dashed, expected.dashed, `actual dashed ${edge.id}`);
    for (const id of edge.canonicalEdgeIds) assert.deepEqual(expectedAppearance(document, id), expected, `incompatible bundled style ${id}`);
    if (document.pageSpec.preset === 'monochrome') assert.deepEqual(edge.dashPattern, expected.pattern, `role pattern ${edge.id}`);
    else assert.equal(Object.hasOwn(edge, 'dashPattern'), false, 'paper must not add derived pattern fields');
  }
}
/** SVG is separately parsed; no product serializer or resolver supplies expected attributes. */
export function assertSvgStyles(document: CanvasDocument, scene: Scene, svg: string) {
  const root = parseXml(svg), all = flatten(root), groups = all.filter(node => node.attributes['data-edge-id']);
  assert.equal(groups.length, scene.edges.length, 'SVG missing/extra edge');
  const metadata = all.find(node => node.name === 'metadata'); assert.ok(metadata);
  const facts = JSON.parse(metadata.text);
  assert.equal(facts.sourceDigest, scene.sourceDigest); assert.equal(facts.irDigest, scene.irDigest);
  assert.deepEqual(facts.sourceFacts, scene.sourceFacts);
  assert.deepEqual(facts.renderedBindings, scene.edges.map(edge => ({ sceneEdgeId: edge.id, canonicalEdgeIds: edge.canonicalEdgeIds,
    source: edge.source, target: edge.target, tensorId: edge.tensorId, role: edge.role })));
  for (const edge of scene.edges) {
    const group = groups.find(node => node.attributes['data-edge-id'] === edge.id); assert.ok(group);
    assert.equal(group.attributes['data-tensor-id'], edge.tensorId);
    const path = group.children.find(node => node.name === 'path'); assert.ok(path);
    assert.equal(path.attributes.d, edge.path, `SVG route ${edge.id}`);
    const expected = expectedAppearance(document, edge.canonicalEdgeIds[0]);
    assert.equal(path.attributes.stroke, expected.stroke); assert.equal(Number(path.attributes['stroke-width']), expected.width);
    assert.deepEqual(svgPattern(path), expected.pattern, `SVG actual pattern ${edge.id}`);
    assert.match(path.attributes['marker-end'] ?? '', /^url\(#archcanvas-arrow-\d+\)$/);
  }
  return root;
}
const intersects = (a: Rect, b: Rect) => a.x < b.x + b.width - 1e-7 && a.x + a.width > b.x + 1e-7 &&
  a.y < b.y + b.height - 1e-7 && a.y + a.height > b.y + 1e-7;
const contains = (outer: Rect, inner: Rect) => inner.x >= outer.x && inner.y >= outer.y &&
  inner.x + inner.width <= outer.x + outer.width + .06 && inner.y + inner.height <= outer.y + outer.height + .06;

export function assertLegend(document: CanvasDocument, scene: Scene, svg?: string) {
  if (document.pageSpec.preset === 'paper') {
    assert.equal(Object.hasOwn(scene, 'edgeLegend'), false); assert.equal(Object.hasOwn(scene, 'edgeLegendLayout'), false); return;
  }
  const entries = scene.edgeLegend ?? [];
  assert.ok(!scene.edges.length || scene.edgeLegend, 'missing actual mono edge legend');
  const variants = new Map<string, { role: EdgeRole; appearance: ReturnType<typeof expectedAppearance>; edgeIds: string[]; canonicalIds: string[] }>();
  for (const edge of scene.edges) {
    const appearance = expectedAppearance(document, edge.canonicalEdgeIds[0]), key = JSON.stringify([edge.role, appearance]);
    const group = variants.get(key) ?? { role: edge.role, appearance, edgeIds: [], canonicalIds: [] };
    group.edgeIds.push(edge.id); group.canonicalIds.push(...edge.canonicalEdgeIds); variants.set(key, group);
  }
  assert.equal(entries.length, variants.size, 'lying/missing visible variants');
  const used = new Set<string>(), samples = svg ? flatten(parseXml(svg)).filter(node => node.attributes['data-edge-legend-id']) : [];
  if (svg) assert.equal(samples.length, entries.length, 'SVG legend membership');
  for (const entry of entries) {
    assert.ok(!used.has(entry.id)); used.add(entry.id);
    assert.ok(!document.legendItems.some(item => item.id === entry.id), 'manual/generated legend identity collision');
    assert.ok(roleOrder.includes(entry.role));
    const appearance = { stroke: entry.stroke, width: entry.lineWidth, dashed: entry.dashed, pattern: entry.dashPattern ?? (entry.dashed ? [5, 4] : []) };
    const variant = variants.get(JSON.stringify([entry.role, appearance])); assert.ok(variant, `lying pattern/sample ${entry.id}`);
    assert.deepEqual([...entry.sceneEdgeIds].sort(), [...variant.edgeIds].sort(), 'sample scene membership');
    assert.deepEqual([...entry.canonicalEdgeIds].sort(), [...variant.canonicalIds].sort(), 'sample canonical membership');
    variants.delete(JSON.stringify([entry.role, appearance]));
    assert.ok(entry.sampleLength >= 36); assert.ok(entry.width > entry.sampleLength && entry.height >= entry.lineWidth);
    assert.ok(contains(scene.bounds, entry), `off-page sample ${entry.id}`);
    for (const node of scene.nodes) for (const rect of bodyRectangles(node)) assert.ok(!intersects(entry, rect), `body/header/backplate sample ${entry.id}/${node.id}`);
    for (const annotation of scene.annotations.filter(item => item.id !== 'detail-provenance')) assert.ok(!intersects(entry, annotation), `annotation sample ${entry.id}/${annotation.id}`);
    for (const old of scene.legend) assert.ok(!intersects(entry, { x: old.x, y: old.y - 11, width: 175, height: 26 }), `manual category sample ${entry.id}/${old.id}`);
    for (const other of entries) if (entry !== other) assert.ok(!intersects(entry, other), `sample overlap ${entry.id}/${other.id}`);
    assert.match(entry.label, new RegExp(entry.role, 'i'), `role sample label ${entry.id}`);
    const count = entries.filter(item => item.role === entry.role).length;
    if (count > 1) assert.match(entry.label, /样式\s*\d+/, 'multiple visible variants need a truthful style label');
    if (svg) {
      const group = samples.find(node => node.attributes['data-edge-legend-id'] === entry.id); assert.ok(group);
      const path = flatten(group).find(node => node.name === 'path'); assert.ok(path);
      assert.equal(path.attributes.stroke, entry.stroke); assert.equal(Number(path.attributes['stroke-width']), entry.lineWidth);
      assert.deepEqual(svgPattern(path), appearance.pattern, 'SVG lying legend sample');
      const route = points(path.attributes.d); assert.ok(near(Math.abs(route.at(-1)!.x - route[0].x), entry.sampleLength));
    }
  }
  assert.equal(variants.size, 0, 'unrepresented actual variant');
  const citation = scene.annotations.find(item => item.id === 'detail-provenance');
  if (citation && entries.length) assert.ok(citation.y >= Math.max(...entries.map(item => item.y + item.height)), 'detail citation overlaps role footer');
}

/** Preservation allows new mono line grammar and footer, not route rewrites. */
export function assertProtectedScene(before: Scene, after: Scene, allowPalette = false) {
  const normalizeNode = (node: Scene['nodes'][number]) => allowPalette ? { ...node, fill: '#ffffff', stroke: '#56616b' } : node;
  assert.deepEqual(after.nodes, before.nodes.map(normalizeNode), 'node/port/manual geometry changed');
  for (const key of ['documentId', 'revision', 'title', 'hiddenEdges', 'sourceDigest', 'irDigest', 'sourceFacts', 'diagnostics', 'annotations', 'exportScope'] as const)
    assert.deepEqual(after[key], before[key], `protected scene ${key}`);
  const normalizeEdge = (edge: Scene['edges'][number]) => {
    const { dashPattern: _pattern, dashed: _dashed, stroke: _stroke, ...rest } = edge; return rest;
  };
  assert.deepEqual(after.edges.map(normalizeEdge), before.edges.map(normalizeEdge), 'path/label/canonical target changed');
  const oldHits = intrusions(before); assert.deepEqual(intrusions(after), oldHits, 'new body/header/backplate intrusion');
  for (let i = 0; i < before.edges.length; i++) for (let j = i + 1; j < before.edges.length; j++)
    assert.deepEqual(pair(after.edges[i].path, after.edges[j].path), pair(before.edges[i].path, before.edges[j].path), 'new pair-local crossing/overlap');
}
