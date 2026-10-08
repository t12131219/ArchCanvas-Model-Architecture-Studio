import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { createDocument, resolveMoveScope } from '../src/core/document.ts';
import { validateDocument } from '../src/core/validate.ts';
import { orthogonalPathPoints } from '../src/core/orthogonalRouter.ts';
import { routeLaneConflicts } from '../src/core/routeLaneConflicts.ts';
import { nodeVisualOutline } from '../src/core/nodeVisualOutline.ts';
import { edgeLabelBounds } from '../src/core/edgeLabelPlacement.ts';
import { TOKENS } from '../src/core/tokens.ts';
import type { ArchitectureNode, Bounds, CanvasDocument, Scene, SceneEdge, SceneNode } from '../src/core/types.ts';

function fixture(): { document: CanvasDocument; scene: Scene } {
  const ids = ['chosen', 'blocker', 'remote', 'sink'];
  const nodes: ArchitectureNode[] = ids.map(id => ({ id, label: id, kind: 'Linear', category: 'linear', children: [],
    parameters: {}, evidence: 'source', ports: [{ id: 'in', name: 'in', direction: 'in', role: 'data', ordinal: 0 },
      { id: 'out', name: 'out', direction: 'out', role: 'data', ordinal: 0 }] }));
  const document = createDocument({ schemaVersion: 1, id: 'recovery-acceptance', label: 'Recovery acceptance', entry: 'Model',
    sourceDigest: 'manual-source', irDigest: 'manual-ir', sources: [], diagnostics: [], nodes, edges: [] });
  document.layout = { chosen: { x: 0, y: 100 }, blocker: { x: 180, y: 100 }, remote: { x: 500, y: 300 }, sink: { x: 750, y: 300 } };
  const sceneNodes: SceneNode[] = nodes.map(node => ({ ...node, ...document.layout[node.id], width: 194, height: 62, headerHeight: 24,
    localX: document.layout[node.id].x, localY: document.layout[node.id].y, subtitle: '', expanded: false, expandable: false,
    pinned: false, evidence: 'source', fill: '#ffffff', stroke: '#000000', glyph: 'operator', ports: [] }));
  return { document, scene: { version: '1.0', documentId: document.id, revision: 0, title: document.title,
    bounds: { x: -100, y: -100, width: 1200, height: 800 }, nodes: sceneNodes, edges: [], hiddenEdges: [], legend: [],
    annotations: [], pageSpec: document.pageSpec, sourceDigest: 'manual-source', irDigest: 'manual-ir',
    sourceFacts: [], diagnostics: [{ level: 'warning', code: 'layout-overlap', objectIds: ['chosen', 'blocker'], message: 'overlap' }] } };
}
function edge(id: string, path: string, sourceId = 'remote', label = ''): SceneEdge {
  return { id, sourceId, targetId: 'sink', source: { nodeId: sourceId, portId: 'out' }, target: { nodeId: 'sink', portId: 'in' },
    canonicalEdgeIds: [id], tensorId: `tensor:${id}`, role: 'data', path, stroke: '#000000', width: 1, dashed: false,
    label, labelX: 50, labelY: 50 };
}
function overlapDiagnostic(first: string, second: string) {
  return { level: 'warning', code: 'layout-route-overlap' as const, edgeId: first, relatedEdgeIds: [first, second], message: 'ambiguous lane' };
}

// Execute the actual proposal/acceptance implementation. Only scene production
// is controlled infrastructure: recorded final geometry isolates safety gates
// from routing revisions. This is not router or rendered-pixel acceptance.
function proposal(before: Scene, document: CanvasDocument, after: (dx: number, dy: number) => Scene) {
  const source = readFileSync(new URL('../src/core/layoutRecovery.ts', import.meta.url), 'utf8');
  const ast = ts.createSourceFile('layoutRecovery.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const program = ast.statements.filter(statement => !ts.isImportDeclaration(statement)).map(statement =>
    statement.getText(ast).replace(/^export\s+/, '')).join('\n');
  const compiled = ts.transpileModule(program, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
  const environment = { resolveMoveScope, validateDocument, orthogonalPathPoints, routeLaneConflicts, edgeLabelBounds,
    nodeVisualOutline, TOKENS, buildScene: () => structuredClone(before), prepareMovePreview: () => ({}),
    previewMoveScene: (_session: unknown, dx: number, dy: number) => after(dx, dy) };
  const plan = new Function(...Object.keys(environment), `${compiled}\nreturn planLayoutRecovery;`)(...Object.values(environment)) as
    (document: CanvasDocument, id: string) => ReturnType<typeof import('../src/core/layoutRecovery.ts').planLayoutRecovery>;
  return plan(document, 'chosen');
}
function moved(before: Scene, dx: number, dy: number): Scene {
  const scene = structuredClone(before), chosen = scene.nodes.find(node => node.id === 'chosen')!;
  chosen.x += dx; chosen.y += dy;
  scene.diagnostics = scene.diagnostics.filter(diagnostic => diagnostic.code !== 'layout-overlap');
  return scene;
}
// Independent geometry without the product lane/family helper. These paths
// have different tensor facts, so every positive collinear span is ambiguous.
function sharedLength(aPath: string, bPath: string): number {
  function points(path: string): { x: number; y: number }[] {
    const result: { x: number; y: number }[] = [];
    for (const [, command, first, second] of path.matchAll(/([MHV])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g)) {
      const last = result.at(-1);
      result.push(command === 'M' ? { x: +first, y: +second } : command === 'H' ? { x: +first, y: last!.y } : { x: last!.x, y: +first });
    }
    return result;
  }
  const a = points(aPath), b = points(bPath); let length = 0;
  for (let i = 1; i < a.length; i++) for (let j = 1; j < b.length; j++) {
    const av = a[i].x === a[i - 1].x, bv = b[j].x === b[j - 1].x;
    if (av !== bv || (av ? a[i].x !== b[j].x : a[i].y !== b[j].y)) continue;
    const axis = av ? 'y' : 'x';
    length += Math.max(0, Math.min(Math.max(a[i][axis], a[i - 1][axis]), Math.max(b[j][axis], b[j - 1][axis])) -
      Math.max(Math.min(a[i][axis], a[i - 1][axis]), Math.min(b[j][axis], b[j - 1][axis])));
  }
  return length;
}
function intersection(a: Bounds, b: Bounds): number {
  return Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) *
    Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
}

test('retained route pair cannot grow actual collinear length after selected body clearance', () => {
  const { document, scene } = fixture();
  scene.edges = [edge('a', 'M 0 20 H 20 V 40'), edge('b', 'M 10 20 H 30 V 50')];
  scene.diagnostics.push(overlapDiagnostic('a', 'b'));
  const candidate = (dx: number, dy: number) => { const next = moved(scene, dx, dy); next.edges[1].path = 'M 0 20 H 30 V 50'; return next; };
  assert.equal(sharedLength(scene.edges[0].path, scene.edges[1].path), 10);
  assert.equal(sharedLength(candidate(-56, 0).edges[0].path, candidate(-56, 0).edges[1].path), 20);
  assert.equal(proposal(scene, document, candidate).status, 'unavailable');
});

test('a different overlap peer is new damage even when primary edge and length agree', () => {
  const { document, scene } = fixture();
  scene.edges = [edge('a', 'M 0 20 H 20 V 40'), edge('b', 'M 10 20 H 30 V 50'), edge('c', 'M 0 70 H 20')];
  scene.diagnostics.push(overlapDiagnostic('a', 'b'));
  const candidate = (dx: number, dy: number) => {
    const next = moved(scene, dx, dy); next.edges[1].path = 'M 0 70 H 30'; next.edges[2].path = 'M 10 20 H 30';
    next.diagnostics = [overlapDiagnostic('a', 'c')]; return next;
  };
  assert.equal(sharedLength(scene.edges[0].path, scene.edges[1].path), sharedLength(candidate(-56, 0).edges[0].path, candidate(-56, 0).edges[2].path));
  assert.equal(proposal(scene, document, candidate).status, 'unavailable');
});

test('unchanged ambiguous lane may remain after genuine selected-body clearance', () => {
  const { document, scene } = fixture();
  scene.edges = [edge('a', 'M 0 20 H 20 V 40'), edge('b', 'M 10 20 H 30 V 50')];
  scene.diagnostics.push(overlapDiagnostic('a', 'b'));
  const plan = proposal(scene, document, (dx, dy) => moved(scene, dx, dy));
  assert.equal(plan.status, 'ready');
  assert.equal(sharedLength(plan.scene.edges[0].path, plan.scene.edges[1].path), 10);
  assert.equal(intersection(plan.scene.nodes.find(node => node.id === 'chosen')!, plan.scene.nodes.find(node => node.id === 'blocker')!), 0);
});

test('a route-only warning incident through the second edge needs genuine reduction', () => {
  const { document, scene } = fixture();
  scene.edges = [edge('a', 'M 0 20 H 20 V 40'), edge('b', 'M 10 20 H 30 V 50', 'chosen')];
  scene.diagnostics = [overlapDiagnostic('a', 'b')];
  assert.equal(proposal(scene, document, (dx, dy) => moved(scene, dx, dy)).status, 'unavailable');
  const improved = proposal(scene, document, (dx, dy) => { const next = moved(scene, dx, dy); next.edges[1].path = 'M 15 20 H 30 V 50'; return next; });
  assert.equal(improved.status, 'ready');
  assert.equal(sharedLength(improved.scene.edges[0].path, improved.scene.edges[1].path), 5);
});

test('unchanged unrelated caption warning cannot conceal growing penetration into the same body', () => {
  const { document, scene } = fixture();
  scene.nodes.find(node => node.id === 'remote')!.x = 65; scene.nodes.find(node => node.id === 'remote')!.y = 39;
  scene.edges = [edge('caption-owner', 'M 0 0 H 400', 'remote', 'TEXT')];
  scene.diagnostics.push({ level: 'warning', code: 'layout-edge-label-blocked', edgeId: 'caption-owner', objectIds: ['remote'], message: 'caption blocked' });
  const candidate = (dx: number, dy: number) => { const next = moved(scene, dx, dy); next.edges[0].labelX = 60; return next; };
  // Four characters use the public 9-unit font envelope [x-2,y-11,40,16].
  // Penetration into remote is 23 units before, 33 after.
  const body = scene.nodes.find(node => node.id === 'remote')!;
  assert.equal(intersection({ x: 48, y: 39, width: 40, height: 16 }, body), 23 * 16);
  assert.equal(intersection({ x: 58, y: 39, width: 40, height: 16 }, body), 33 * 16);
  assert.equal(proposal(scene, document, candidate).status, 'unavailable');
});

test('original unrelated caption obstruction may stay unchanged during selected-body repair', () => {
  const { document, scene } = fixture();
  scene.nodes.find(node => node.id === 'remote')!.x = 65; scene.nodes.find(node => node.id === 'remote')!.y = 39;
  scene.edges = [edge('caption-owner', 'M 0 0 H 400', 'remote', 'TEXT')];
  scene.diagnostics.push({ level: 'warning', code: 'layout-edge-label-blocked', edgeId: 'caption-owner', objectIds: ['remote'], message: 'caption blocked' });
  assert.equal(proposal(scene, document, (dx, dy) => moved(scene, dx, dy)).status, 'ready');
});

test('a blocked route may not transfer penetration from one retained body to another', () => {
  const { document, scene } = fixture();
  const remote = scene.nodes.find(node => node.id === 'remote')!, sink = scene.nodes.find(node => node.id === 'sink')!;
  Object.assign(remote, { x: 0, y: 0, width: 50, height: 50 });
  Object.assign(sink, { x: 100, y: 0, width: 50, height: 50 });
  scene.edges = [edge('blocked', 'M -10 25 H 10 V -10 H 110 V 10 H 140')];
  scene.diagnostics.push({ level: 'warning', code: 'layout-route-blocked', edgeId: 'blocked', objectIds: ['remote', 'sink'], message: 'blocked bodies' });
  const candidate = (dx: number, dy: number) => {
    const next = moved(scene, dx, dy);
    next.edges[0].path = 'M -10 25 H 30 V -10 H 110 V 10 H 120';
    return next;
  };
  // Before: remote 10+25=35, sink 10+30=40. After: remote
  // 30+25=55, sink 10+10=20. Total remains 75 yet remote worsens.
  assert.equal(35 + 40, 55 + 20);
  assert.equal(proposal(scene, document, candidate).status, 'unavailable');
});

test('an unrelated caption association warning may not move farther from its owned route', () => {
  const { document, scene } = fixture();
  scene.edges = [edge('far-caption', 'M 0 0 H 400', 'remote', 'TEXT')];
  scene.diagnostics.push({ level: 'warning', code: 'layout-edge-label-association', edgeId: 'far-caption', objectIds: [], message: 'too far' });
  const candidate = (dx: number, dy: number) => { const next = moved(scene, dx, dy); next.edges[0].labelY = 60; return next; };
  // The lower boundary of the nominal caption envelope moves from y=39
  // to y=49 while its owned route stays at y=0.
  assert.equal(proposal(scene, document, candidate).status, 'unavailable');
});

