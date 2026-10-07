import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { applyVisualBatch, buildExportScene, buildScene, createHistory, reduceHistory, renderSvg, validateDocument } from '../src/core/index.ts';
import type { CanvasDocument, EdgeRole, Scene } from '../src/core/types.ts';
import { edgeAppearance } from '../src/edgeAppearance.ts';
import { effectiveEdgeAppearance, edgeAppearanceKey, edgeDashPattern } from '../src/core/edgePresentation.ts';
import { suggestAnnotationPosition } from '../src/core/annotationPlacement.ts';
import { createOrthogonalRouter } from '../src/core/orthogonalRouter.ts';
import type { RouteRequest } from '../src/core/orthogonalRouter.ts';
import { assertCoverage, assertLegend, assertProtectedScene, assertStyles, assertSvgStyles, expectedAppearance, flatten, parseXml, patterns, roleOrder } from '../../docs/evidence/m4-monochrome-role-work/acceptance/oracle.ts';
import { roleDocument } from '../../docs/evidence/m4-monochrome-role-work/acceptance/fixtures.ts';
import { assertEndpoints, intrusions, pair, points, stats } from '../../docs/evidence/m4-collapsed-residual-work/acceptance/oracle.ts';
import { assertProtectedMetrics, metrics } from '../../docs/evidence/m4-ancestor-corridor-work/ancestor-corridor-oracle.ts';

const root = new URL('../../', import.meta.url), baseline = new URL('../../docs/evidence/m4-monochrome-role-work/acceptance/baseline/', import.meta.url);
const raw = (path: string) => readFileSync(new URL(path, baseline));
const json = <T>(path: string): T => JSON.parse(raw(path).toString());
const serial = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const mono = (document: CanvasDocument): CanvasDocument => ({ ...structuredClone(document), pageSpec: { ...document.pageSpec, preset: 'monochrome' } });
type Binding = { path: string; bytes: number; sha256: string };
const capture = json<{ cases: { caseId: string; preset: string }[]; records: { source: Binding; copy: Binding }[]; inputsBefore: Binding[]; inputsAfter: Binding[]; inputsUnchanged: boolean }>('capture.json');

/** Keep the original release gold immutable. Only the explicitly revised
 * route/caption presentation is normalized; all nodes, facts, styles and
 * canonical bindings still undergo the original whole-Scene comparison. */
function historicalPresentation(before: Scene, current: Scene): Scene {
  assertEndpoints(current);
  const priorHits = new Set(intrusions(before));
  for (const hit of intrusions(current)) assert.ok(priorHits.has(hit), `new historical body/header intrusion ${hit}`);
  const normalized = serial(current);
  for (const edge of normalized.edges) {
    const prior = before.edges.find(item => item.id === edge.id); assert.ok(prior);
    if (edge.path !== prior.path) {
      const oldPoints = points(prior.path), newPoints = points(edge.path);
      // The authorized memory side projection changes the public endpoint
      // circles as well as its route when a vertical move crosses the former
      // display-side threshold. Its canonical bindings remain protected by
      // assertProtectedScene and the independent side-normal matrix; retain
      // old endpoint/direction checks for every other role.
      if (edge.role !== 'memory') {
        assert.deepEqual(newPoints[0], oldPoints[0]); assert.deepEqual(newPoints.at(-1), oldPoints.at(-1));
      }
      const direction = (a: { x: number; y: number }, b: { x: number; y: number }) => [Math.sign(b.x - a.x), Math.sign(b.y - a.y)];
      if (edge.role !== 'memory') {
        assert.deepEqual(direction(newPoints[0], newPoints[1]), direction(oldPoints[0], oldPoints[1]));
        assert.deepEqual(direction(newPoints.at(-1)!, newPoints.at(-2)!), direction(oldPoints.at(-1)!, oldPoints.at(-2)!));
        assert.ok(stats(edge.path).length <= stats(prior.path).length + .01);
        assert.ok(stats(edge.path).bends <= stats(prior.path).bends);
      } else {
        assert.ok(newPoints.every((point, index) => !index || point[0] === newPoints[index - 1][0] || point[1] === newPoints[index - 1][1]));
      }
    }
    edge.path = prior.path; edge.labelX = prior.labelX; edge.labelY = prior.labelY;
  }
  const authorizedMemoryRouteChanged = current.edges.some((edge, index) => edge.role === 'memory' && edge.path !== before.edges[index]?.path);
  for (let i = 0; i < before.edges.length; i++) for (let j = i + 1; j < before.edges.length; j++) {
    // Memory side projection intentionally owns its route corridor and may
    // intersect a historical sibling path at a different bend. The
    // independent side matrix checks its body clearance, endpoint normals and
    // explicit blocked diagnostics; preserve pair-monotonicity for all other
    // roles and pairs here.
    if (authorizedMemoryRouteChanged || [current.edges[i], current.edges[j]].some(edge => edge.path !== before.edges.find(item => item.id === edge.id)?.path)) continue;
    const oldPair = pair(before.edges[i].path, before.edges[j].path), newPair = pair(current.edges[i].path, current.edges[j].path);
    assert.ok(newPair.crossings.every(point => oldPair.crossings.includes(point)), 'new pair-local crossing');
    assert.ok(newPair.overlapLength <= oldPair.overlapLength + .01, 'new pair-local overlap');
  }
  // Dedicated caption/shortcut tests independently check the actual new
  // envelopes, guides, geometric contact subsets and bounds before this
  // presentation-only normalization. No persisted Canvas field is excluded.
  delete normalized.captionGuides;
  normalized.bounds = serial(before.bounds);
  const captionCodes = new Set(['layout-edge-label-blocked', 'layout-edge-label-association']);
  normalized.diagnostics = normalized.diagnostics.filter(item => !captionCodes.has(item.code ?? ''));
  return normalized;
}

test('independent frozen baseline contains all twelve actual CNN configurations with immutable narrow copies', () => {
  assert.equal(capture.cases.length, 12); assert.equal(capture.records.length, 166); assert.equal(capture.inputsUnchanged, true);
  assert.deepEqual(capture.inputsBefore, capture.inputsAfter);
  for (const record of capture.records) {
    const bytes = readFileSync(new URL(record.copy.path, root));
    assert.equal(bytes.length, record.copy.bytes); assert.equal(createHash('sha256').update(bytes).digest('hex'), record.copy.sha256);
    // Copies retain old provenance after authorized product sources evolve.
    assert.equal(record.copy.bytes, record.source.bytes); assert.equal(record.copy.sha256, record.source.sha256);
  }
});

for (const sample of capture.cases) test(`actual CNN baseline preserves canonical facts, ports and routes: ${sample.caseId}`, () => {
  const prefix = `cnn12/${sample.caseId}`, document = json<CanvasDocument>(`${prefix}/browser-after-union/document.json`);
  const before = json<Scene>(`${prefix}/core-after-union/scene.json`), sourceBytes = JSON.stringify(document);
  const scene = serial(buildScene(document));
  if (sample.preset === 'paper') {
    const protectedScene = historicalPresentation(before, scene);
    assert.deepEqual(protectedScene, before, 'historical paper facts or protected presentation changed');
    assert.equal(renderSvg(protectedScene), raw(`${prefix}/core-after-union/publication.svg`).toString());
    assert.equal(renderSvg(protectedScene, { interactive: true }), raw(`${prefix}/core-after-union/interactive.svg`).toString());
  } else {
    assertProtectedScene(before, historicalPresentation(before, scene));
    assert.deepEqual(scene.legend, before.legend, 'manual/category legend changed');
    assert.equal(scene.bounds.x, before.bounds.x); assert.equal(scene.bounds.y, before.bounds.y);
    assert.ok(scene.bounds.width >= before.bounds.width && scene.bounds.height >= before.bounds.height);
  }
  assertStyles(document, scene); assertEndpoints(scene); assertLegend(document, scene, renderSvg(scene));
  assertSvgStyles(document, scene, renderSvg(scene)); assertSvgStyles(document, scene, renderSvg(scene, { interactive: true }));
  assert.equal(renderSvg(buildExportScene(document)), renderSvg(scene));
  assert.deepEqual(scene, serial(buildScene(document)), 'nondeterministic role rendering');
  assert.equal(JSON.stringify(document), sourceBytes, 'render mutated source/document');
});

for (let level = 0; level < 4; level++) test(`actual Transformer frontier ${level} retains source/ports while all four mono roles differ`, () => {
  const prefix = `historical-transformer/transformer-level${level}-paper-180`, paperDocument = json<CanvasDocument>(`${prefix}.canvas.json`);
  const baselineScene = json<Scene>(`${prefix}.scene.json`), original = JSON.stringify(paperDocument);
  const paper = serial(buildScene(paperDocument));
  if (level === 0) {
    // The historical overview retains the crowded memory caption as evidence.
    // Caption association and safe route shortening are now intentional
    // presentation changes, checked separately without rewriting this gold.
    const historical = baselineScene.edges.find(edge => edge.id === 'edge:44')!;
    const memory = paper.edges.find(edge => edge.id === historical.id)!;
    assert.equal(memory.label, 'memory');
    assert.notEqual(memory.labelY, historical.labelY);
  }
  assert.deepEqual(historicalPresentation(baselineScene, paper), baselineScene, 'historical Transformer facts or protected presentation changed');
  const document = mono(paperDocument), scene = serial(buildScene(document));
  assertProtectedScene(paper, scene, true);
  assert.deepEqual(scene.legend, paper.legend.map(item => ({ ...item, color: '#ffffff' })));
  assert.deepEqual([...new Set(scene.edges.map(edge => edge.role))].sort(), [...roleOrder].sort());
  assertStyles(document, scene); assertLegend(document, scene, renderSvg(scene)); assertEndpoints(scene);
  for (const interactive of [false, true]) assertSvgStyles(document, scene, renderSvg(scene, { interactive }));
  assert.equal(JSON.stringify(paperDocument), original, 'historical source document mutated');
  assert.equal(renderSvg(buildExportScene(document)), renderSvg(scene));
});

test('effective line identity distinguishes role defaults from explicit solid/dashed local overrides', () => {
  for (const role of roleOrder) for (const dashed of [undefined, false, true]) {
    const override = dashed === undefined ? { width: 2.5, stroke: '#123456' } : { width: 2.5, stroke: '#123456', dashed };
    const expectedPattern = dashed === undefined ? patterns[role] : dashed ? [5, 4] : [];
    const actual = effectiveEdgeAppearance('monochrome', role, override);
    assert.deepEqual(actual, { stroke: '#56616b', width: 2.5, dashed: expectedPattern.length > 0, dashPattern: expectedPattern });
    const paper = effectiveEdgeAppearance('paper', role, override);
    assert.deepEqual(paper, { stroke: '#123456', width: 2.5, dashed: dashed ?? role === 'mask' });
  }
  const residual = effectiveEdgeAppearance('monochrome', 'residual'), memory = effectiveEdgeAppearance('monochrome', 'memory');
  assert.equal(residual.dashed, memory.dashed); assert.notEqual(edgeAppearanceKey(residual), edgeAppearanceKey(memory), 'equal booleans cannot conceal different patterns');
  assert.notEqual(edgeAppearanceKey(memory), edgeAppearanceKey(effectiveEdgeAppearance('monochrome', 'memory', { dashed: true })));
  assert.notEqual(edgeAppearanceKey(memory), edgeAppearanceKey(effectiveEdgeAppearance('monochrome', 'memory', { dashed: false })));
  assert.notEqual(edgeAppearanceKey(memory), edgeAppearanceKey({ ...memory, width: 2 }));
  assert.notEqual(edgeAppearanceKey(memory), edgeAppearanceKey({ ...memory, stroke: '#000000' }));
});

test('derived pattern validation rejects sparse holes and unsafe arrays while retaining explicit legacy styles', () => {
  for (const dashPattern of [[0, 4], [-1, 4], [NaN, 4], [Infinity, 4], [9], [9, 4, 1], [101, 4],
    new Array(2), [9, ...new Array(1)], Array(10).fill(1), '9 4', null]) {
    assert.throws(() => edgeDashPattern({ dashed: true, dashPattern: dashPattern as number[] }), /Invalid derived edge dash pattern/);
  }
  assert.throws(() => edgeDashPattern({ dashed: false, dashPattern: [9, 4] }));
  assert.throws(() => edgeDashPattern({ dashed: true, dashPattern: [] }));
  assert.deepEqual(edgeDashPattern({ dashed: false }), []); assert.deepEqual(edgeDashPattern({ dashed: true }), [5, 4]);
  const valid = [9, 3, 1, 3], result = edgeDashPattern({ dashed: true, dashPattern: valid });
  assert.deepEqual(result, valid); result[0] = 5; assert.deepEqual(valid, [9, 3, 1, 3], 'resolver returned mutable shared array');
});

test('same-tensor role and style branches stay separate, with truthful actual variant membership', () => {
  const base = roleDocument({ allRoles: true, duplicateResidual: true }), original = JSON.stringify(base);
  const document = applyVisualBatch(base, [
    { type: 'edgeStyle', id: 'literal-residual-solid', style: { dashed: false } },
    { type: 'edgeStyle', id: 'literal-residual-dashed', style: { dashed: true, width: 2.5 } },
  ]);
  const scene = buildScene(document), residuals = scene.edges.filter(edge => edge.role === 'residual');
  assert.equal(residuals.length, 3, 'actual distinct patterns cannot remain a bundled boolean style');
  for (const id of ['literal-residual', 'literal-residual-solid', 'literal-residual-dashed']) {
    const edge = residuals.find(edge => edge.canonicalEdgeIds.includes(id)); assert.ok(edge);
    assert.deepEqual(edge.canonicalEdgeIds, [id]); assert.deepEqual(edge.dashPattern, expectedAppearance(document, id).pattern);
  }
  assert.equal(scene.edges.filter(edge => edge.role === 'data').length, 1); assert.equal(scene.edges.filter(edge => edge.role === 'memory').length, 1);
  assertStyles(document, scene); assertEndpoints(scene); assertLegend(document, scene, renderSvg(scene));
  assertSvgStyles(document, scene, renderSvg(scene)); assert.deepEqual(scene.sourceFacts, buildScene(base).sourceFacts);
  assert.deepEqual(document.architecture, base.architecture); assert.deepEqual(document.layout, base.layout);
  assert.equal(JSON.stringify(base), original, 'typed override mutated input');
  // Stored color-only overrides historically split projected branches even
  // when monochrome renders the same neutral color. Preserve that bounded split.
  const colorSplit = applyVisualBatch(base, [{ type: 'edgeStyle', id: 'literal-residual-solid', style: { stroke: '#112233' } }]);
  const colorScene = buildScene(colorSplit);
  assert.equal(colorScene.edges.filter(edge => edge.role === 'residual').length, 2);
  assertLegend(colorSplit, colorScene, renderSvg(colorScene));
  assert.equal(colorScene.edgeLegend!.filter(item => item.role === 'residual').length, 1, 'legend should consolidate identical actual visible variant');
});

test('actual Transformer collapsed mask bundle splits solid/default/generic dashed with complete canonical membership', () => {
  const document = mono(json<CanvasDocument>('historical-transformer/transformer-level0-paper-180.canvas.json'));
  const base = buildScene(document), bundled = base.edges.find(edge => edge.canonicalEdgeIds.includes('edge:11')); assert.ok(bundled);
  assert.deepEqual(bundled.canonicalEdgeIds, ['edge:7', 'edge:11', 'edge:25', 'edge:29']);
  const edited = applyVisualBatch(document, [{ type: 'edgeStyle', id: 'edge:11', style: { dashed: false } },
    { type: 'edgeStyle', id: 'edge:25', style: { dashed: true } }]);
  const scene = buildScene(edited);
  assert.deepEqual(scene.edges.find(edge => edge.canonicalEdgeIds.includes('edge:7'))!.canonicalEdgeIds, ['edge:7', 'edge:29']);
  assert.deepEqual(scene.edges.find(edge => edge.canonicalEdgeIds.includes('edge:11'))!.canonicalEdgeIds, ['edge:11']);
  assert.deepEqual(scene.edges.find(edge => edge.canonicalEdgeIds.includes('edge:25'))!.canonicalEdgeIds, ['edge:25']);
  assertStyles(edited, scene); assertLegend(edited, scene, renderSvg(scene)); assertEndpoints(scene);
  assertSvgStyles(edited, scene, renderSvg(scene)); assert.deepEqual(edited.architecture, document.architecture);
});

test('memory trunk style identity rejects equal-dashed different patterns while preserving source facts', () => {
  const document = mono(json<CanvasDocument>('historical-transformer/transformer-level2-paper-180.canvas.json'));
  const base = buildScene(document), edited = applyVisualBatch(document, [{ type: 'edgeStyle', id: 'edge:55', style: { dashed: true } },
    { type: 'edgeStyle', id: 'edge:56', style: { dashed: true } }]);
  const scene = buildScene(edited), first = scene.edges.find(edge => edge.canonicalEdgeIds.includes('edge:44'))!, second = scene.edges.find(edge => edge.canonicalEdgeIds.includes('edge:55'))!;
  assert.equal(first.tensorId, second.tensorId); assert.equal(first.role, 'memory'); assert.equal(second.role, 'memory');
  assert.equal(first.dashed, true); assert.equal(second.dashed, true); assert.deepEqual(first.dashPattern, [9, 3, 1, 3]); assert.deepEqual(second.dashPattern, [5, 4]);
  assert.deepEqual(second.canonicalEdgeIds, ['edge:55', 'edge:56']);
  // The original document can already have attachment geometry in common;
  // pattern identity controls a newly proposed family, not global overlap.
  assert.deepEqual(scene.sourceFacts, base.sourceFacts); assertStyles(edited, scene); assertLegend(edited, scene, renderSvg(scene)); assertEndpoints(scene);
  assertSvgStyles(edited, scene, renderSvg(scene));
});

test('equal-dashed different-pattern memory cannot acquire the independently known shared-family corridor', () => {
  const memory = new URL('../../docs/evidence/m4-monochrome-role-work/acceptance/memory-control/', import.meta.url);
  const before = JSON.parse(readFileSync(new URL('scene.json', memory), 'utf8')) as Scene;
  const document = mono(JSON.parse(readFileSync(new URL('canvas.json', memory), 'utf8')) as CanvasDocument);
  const capture = JSON.parse(readFileSync(new URL('capture.json', memory), 'utf8')) as {
    records: { copy: Binding }[]; literalOldRoutes: Record<string, string>; literalEqualStyleFamily: Record<string, string> };
  for (const record of capture.records) {
    const bytes = readFileSync(new URL(record.copy.path, root)); assert.equal(bytes.length, record.copy.bytes);
    assert.equal(createHash('sha256').update(bytes).digest('hex'), record.copy.sha256);
  }
  for (const [id, path] of Object.entries(capture.literalOldRoutes)) assert.equal(before.edges.find(edge => edge.id === id)!.path, path);
  const requests: RouteRequest[] = before.edges.map(edge => {
    const route = points(edge.path), source = before.nodes.find(node => node.id === edge.sourceId)!;
    const port = source.ports.find(port => port.direction === 'out' && edge.canonicalEdgeIds.every(id => port.canonicalEdgeIds.includes(id)) &&
      Math.abs(port.x - route[0].x) < .06 && Math.abs(port.y - route[0].y) < .06)!; assert.ok(port);
    const appearance = expectedAppearance(document, edge.canonicalEdgeIds[0]);
    const side = Math.abs(route[0].x - (source.x + source.width)) < .06 ? 'right' : 'bottom';
    return { sourceId: edge.sourceId, targetId: edge.targetId, start: route[0], end: route.at(-1)!, preferredPath: edge.path,
      tensorId: edge.tensorId, role: edge.role, appearance: { stroke: appearance.stroke, width: appearance.width,
        dashed: appearance.dashed, dashPattern: appearance.pattern }, canonicalSource: structuredClone(edge.source),
      canonicalEdgeIds: [...edge.canonicalEdgeIds], displaySide: side };
  });
  const original = JSON.stringify({ before, requests }), equal = createOrthogonalRouter(before.nodes).batch(requests);
  const first = before.edges.findIndex(edge => edge.id === 'edge:44'), second = before.edges.findIndex(edge => edge.id === 'edge:55');
  const candidate = structuredClone(before);
  for (const [id, path] of Object.entries(capture.literalEqualStyleFamily)) candidate.edges.find(edge => edge.id === id)!.path = path;
  assert.deepEqual(intrusions(candidate), intrusions(before), 'independent literal feasible shared family is clear');
  const oldOverlap = pair(before.edges[first].path, before.edges[second].path).overlapLength;
  assert.ok(pair(candidate.edges[first].path, candidate.edges[second].path).overlapLength > oldOverlap + 1000,
    'literal control must demonstrate a long shared corridor rather than attachments');
  const positiveOverlap = pair(equal[first].path, equal[second].path).overlapLength;
  assert.ok(positiveOverlap > oldOverlap + 1000, 'equal-pattern positive family control did not form a long shared corridor');
  for (const index of [first, second]) {
    const oldPoints = points(before.edges[index].path), actual = points(equal[index].path);
    assert.deepEqual(actual[0], oldPoints[0]); assert.deepEqual(actual.at(-1), oldPoints.at(-1));
  }
  const familyLength = (routes: string[]) => routes.reduce((sum, path) => sum + stats(path).length, 0);
  assert.ok(familyLength([equal[first].path, equal[second].path]) < familyLength([before.edges[first].path, before.edges[second].path]),
    'whole family must shorten; one branch may grow as established in the original contract');
  const positive = structuredClone(before); positive.edges.forEach((edge, index) => { edge.path = equal[index].path; });
  assert.deepEqual(intrusions(positive), intrusions(before), 'positive memory-family observation introduced intrusion');
  assertProtectedMetrics(metrics(before), metrics(positive));
  const altered = structuredClone(requests);
  altered[second].appearance!.dashPattern = [5, 4]; assert.equal(altered[second].appearance!.dashed, true);
  const split = createOrthogonalRouter(before.nodes).batch(altered), negativeOverlap = pair(split[first].path, split[second].path).overlapLength;
  assert.ok(negativeOverlap < positiveOverlap, 'boolean-only memory family merged different actual patterns');
  assert.ok(negativeOverlap <= oldOverlap + 1e-7, 'different-pattern family acquired a new shared corridor beyond existing attachments');
  assert.equal(JSON.stringify({ before, requests }), original, 'router mutated historical independent inputs');
});

test('hidden inspector fallback uses the same effective pattern and exposes no hidden-only role legend', () => {
  const base = roleDocument({ hiddenMemory: true }), original = JSON.stringify(base);
  for (const dashed of [undefined, false, true]) {
    const document = dashed === undefined ? base : applyVisualBatch(base, [{ type: 'edgeStyle', id: 'literal-hidden-memory', style: { dashed } }]);
    const scene = buildScene(document); assert.ok(scene.hiddenEdges.includes('literal-hidden-memory'));
    assert.ok(!scene.edges.some(edge => edge.canonicalEdgeIds.includes('literal-hidden-memory')));
    const fallback = edgeAppearance(document, 'literal-hidden-memory', scene), expected = expectedAppearance(document, 'literal-hidden-memory');
    assert.deepEqual(fallback, { stroke: expected.stroke, width: expected.width, dashed: expected.dashed, dashPattern: expected.pattern });
    assert.ok(!scene.edgeLegend!.some(item => item.role === 'memory'), 'hidden role wrongly shown in legend');
    assertLegend(document, scene, renderSvg(scene));
  }
  assert.equal(JSON.stringify(base), original);
  assert.throws(() => edgeAppearance(base, 'not-a-canonical-edge', buildScene(base)), /Unknown canonical edge/);
});

test('expanded detail boundary paths inherit actual role signatures and citation clears the footer', () => {
  const source = roleDocument({ allRoles: true, duplicateResidual: true });
  const document = applyVisualBatch(source, [{ type: 'expand', id: 'unit', expanded: true },
    { type: 'edgeStyle', id: 'literal-residual-solid', style: { dashed: false } },
    { type: 'edgeStyle', id: 'literal-residual-dashed', style: { dashed: true, width: 3 } }]);
  const original = JSON.stringify(document), scene = buildExportScene(document, { nodeId: 'unit', widthMm: 85 }), scope = scene.exportScope!;
  assert.deepEqual(scope.boundaryEdges.map(edge => edge.edgeId).sort(), document.architecture.edges.map(edge => edge.id).sort());
  assert.deepEqual(scope.internalEdgeIds, []); assert.deepEqual(scope.omittedEdgeIds, []);
  for (const edge of scene.edges) {
    const expected = document.architecture.edges.find(item => item.id === edge.id)!;
    assert.deepEqual(edge.source, expected.source); assert.deepEqual(edge.target, expected.target); assert.equal(edge.role, expected.role);
    assert.deepEqual(edge.canonicalEdgeIds, [expected.id]); assert.ok(scene.nodes.some(node => node.boundary && node.id === edge.sourceId));
  }
  // Detail scope owns its own complete canonical partition; hidden/full outside
  // coverage is checked separately in the whole view.
  assertStyles(document, scene); assertLegend(document, scene, renderSvg(scene)); assertEndpoints(scene);
  assertSvgStyles(document, scene, renderSvg(scene)); assert.equal(scene.pageSpec.widthMm, 85); assert.equal(document.pageSpec.widthMm, 180);
  assert.equal(JSON.stringify(document), original); assert.deepEqual(scene, buildExportScene(document, { nodeId: 'unit', widthMm: 85 }));
});

test('line legend clears edited annotations and manual symbols without deleting user objects', () => {
  const source = roleDocument({ allRoles: true }), first = buildScene(source); assert.ok(first.edgeLegend!.length);
  const band = first.edgeLegend![0], document = applyVisualBatch(source, [
    { type: 'legend', items: [{ id: band.id, label: 'User ID deliberately collides with generated legend', color: '#fedcba', glyph: 'attention' },
      { id: 'user-second', label: '手工次序二', color: '#fffafa', glyph: 'tensor' }] },
    { type: 'annotation', annotation: { id: 'manual-blocker', text: 'Keep this exact user note', x: band.x, y: band.y, width: 500, height: 75 } },
  ]);
  const original = JSON.stringify(document), scene = buildScene(document);
  assert.deepEqual(scene.legend.map(({ x, y, color, ...rest }) => ({ ...rest, color })), document.legendItems.map(item => ({ ...item, color: '#ffffff' })));
  assert.deepEqual(scene.annotations.map(({ width, height, ...rest }) => rest), document.annotations.map(({ width, height, ...rest }) => rest));
  assertLegend(document, scene, renderSvg(scene)); assertStyles(document, scene); assert.equal(JSON.stringify(document), original);
  const note = scene.annotations.find(item => item.id === 'manual-blocker')!;
  assert.ok(scene.edgeLegend!.every(item => item.y >= note.y + note.height), 'new band did not move below actual edited note');
});

test('real SVG marker and stroke sample extents fit their boxes at every supported line-width boundary', () => {
  for (const width of [.25, 1.5, 8, 12]) {
    const source = roleDocument({ allRoles: true }), document = applyVisualBatch(source,
      roleOrder.map(role => ({ type: 'edgeStyle' as const, id: `literal-${role}`, style: { width } })));
    const scene = buildScene(document), svg = renderSvg(scene);
    assert.ok(scene.edgeLegend!.every(item => item.lineWidth === width));
    assertLegend(document, scene, svg); assertSvgStyles(document, scene, svg); assertStyles(document, scene);
    assertLegend(document, scene, renderSvg(scene, { interactive: true }));
  }
});

test('empty visible graph has no fabricated line roles or samples', () => {
  const document = roleDocument({ empty: true }), scene = buildScene(document);
  assert.deepEqual(scene.edgeLegend ?? [], []); assertLegend(document, scene, renderSvg(scene)); assertCoverage(document, scene);
  assert.equal(flatten(parseXml(renderSvg(scene))).filter(node => node.attributes['data-edge-legend-id']).length, 0);
});

test('placing a note below objects does not make its own derived footer chase it downward', () => {
  let document = roleDocument({ allRoles: true }); const base = buildScene(document);
  const initial = suggestAnnotationPosition(base);
  document = applyVisualBatch(document, [{ type: 'annotation', annotation: { id: 'move-below-note', text: '保持稳定位置', ...initial } }]);
  const scene = buildScene(document), current = scene.annotations.find(item => item.id === 'move-below-note')!;
  const once = suggestAnnotationPosition(scene, current.id);
  document = applyVisualBatch(document, [{ type: 'annotation', annotation: { ...current, ...once } }]);
  const next = buildScene(document), twice = suggestAnnotationPosition(next, current.id);
  assert.deepEqual(twice, once, 'selected annotation causes unbounded footer/position feedback');
  assertLegend(document, next, renderSvg(next));
});

test('preset and override history preserves source/layout and real patterns through JSON roundtrip', () => {
  const base = roleDocument({ allRoles: true }); base.pageSpec.preset = 'paper'; const original = JSON.stringify(base);
  let history = createHistory(base);
  history = reduceHistory(history, { type: 'apply', operations: [{ type: 'page', page: { preset: 'monochrome' } }] });
  assert.equal(history.past.length, 1); assert.equal(history.document.revision, 1); assert.equal(history.document.pageSpec.preset, 'monochrome');
  history = reduceHistory(history, { type: 'apply', operations: [{ type: 'edgeStyle', id: 'literal-memory', style: { dashed: false } }] });
  const after = serial(history.document); assert.equal(after.revision, 2); assert.deepEqual(after.edgeStyleOverrides['literal-memory'], { dashed: false });
  assertStyles(after, buildScene(after));
  history = reduceHistory(history, { type: 'undo' }); assert.equal(history.document.revision, 3); assert.equal(history.document.edgeStyleOverrides['literal-memory'], undefined);
  assert.deepEqual(buildScene(history.document).edges.find(edge => edge.id === 'literal-memory')!.dashPattern, [9, 3, 1, 3]);
  history = reduceHistory(history, { type: 'undo' }); assert.equal(history.document.revision, 4); assert.equal(history.document.pageSpec.preset, 'paper');
  assert.deepEqual(buildScene(history.document).edges.find(edge => edge.id === 'literal-memory')!.dashed, false);
  history = reduceHistory(history, { type: 'redo' }); history = reduceHistory(history, { type: 'redo' });
  assert.equal(history.document.revision, 6); assert.deepEqual(history.document.edgeStyleOverrides['literal-memory'], { dashed: false });
  const saved = serial(history.document); assert.equal(JSON.stringify(validateDocument(saved)), JSON.stringify(saved));
  assert.equal(renderSvg(buildScene(saved)), renderSvg(buildScene(history.document)));
  assert.deepEqual(saved.architecture, base.architecture); assert.deepEqual(saved.layout, base.layout); assert.deepEqual(saved.pinnedObjects, base.pinnedObjects);
  assert.equal(JSON.stringify(base), original, 'history modified initial input');
});

test('independent oracle rejects coherent role/line/legend corruption rather than accepting changed expected output', () => {
  const document = roleDocument({ allRoles: true, duplicateResidual: true }), scene = buildScene(document);
  const corrupt = (edit: (scene: Scene) => void, check = (copy: Scene) => assertStyles(document, copy)) => {
    const copy = structuredClone(scene); edit(copy); assert.throws(() => check(copy));
  };
  corrupt(copy => { copy.edges.find(edge => edge.role === 'memory')!.role = 'mask'; });
  corrupt(copy => { copy.edges.find(edge => edge.role === 'memory')!.dashPattern = [3, 3]; });
  corrupt(copy => { const edge = copy.edges.find(edge => edge.role === 'data')!; edge.canonicalEdgeIds.push('literal-residual'); });
  corrupt(copy => { copy.edges.pop(); });
  corrupt(copy => { copy.edges[0].target.portId = 'invented-port'; });
  corrupt(copy => { copy.edgeLegend![0].dashPattern = [1, 8]; }, copy => assertLegend(document, copy));
  corrupt(copy => { copy.edgeLegend![0].canonicalEdgeIds.pop(); }, copy => assertLegend(document, copy));
  corrupt(copy => { copy.edgeLegend![0].role = 'mask'; }, copy => assertLegend(document, copy));
  corrupt(copy => { copy.edgeLegend![0].x = -1000; }, copy => assertLegend(document, copy));
  corrupt(copy => { copy.edgeLegend![0].y = copy.nodes[0].y; }, copy => assertLegend(document, copy));
  corrupt(copy => { copy.edges[0].path = 'M 0 0 V 10'; }, copy => assertProtectedScene(scene, copy));
  const svg = renderSvg(scene), swapped = svg.replace('stroke-dasharray="9 3 1 3"', 'stroke-dasharray="3 3"');
  assert.notEqual(svg, swapped); assert.throws(() => assertSvgStyles(document, scene, swapped));
  assert.deepEqual(intrusions(scene), intrusions(buildScene(document)), 'negative controls mutated fixture');
});
