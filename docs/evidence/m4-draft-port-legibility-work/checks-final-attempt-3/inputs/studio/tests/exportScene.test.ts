import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { applyVisualBatch, buildExportScene, buildScene, createDocument, detailExportChoices, publicationPreflight, renderSvg } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode } from '../src/core/index.ts';
import { textWidth, wrapText } from '../src/core/typography.ts';

// Hand-authored graph: two incoming bindings share an external port; a nested
// collapsed block hides one internal fact; a skip outside the detail is omitted.
function oracle(): Architecture {
  const node = (id: string, parentId?: string, children: string[] = []): ArchitectureNode => ({
    id, label: id, parentId, children, kind: children.length ? 'Block' : 'Linear', category: children.length ? 'container' : 'linear',
    parameters: {}, evidence: 'source', ports: [{ id: 'in', name: 'features', direction: 'in', role: 'data', ordinal: 0 }, { id: 'out', name: 'result', direction: 'out', role: 'data', ordinal: 0 }],
  });
  const edge = (id: string, source: string, target: string, role: 'data' | 'residual' = 'data') => ({ id, source: { nodeId: source, portId: 'out' }, target: { nodeId: target, portId: 'in' }, tensorId: `${id}:tensor`, role });
  return { schemaVersion: 1, id: 'detail-oracle', label: 'Independent export boundary oracle', entry: 'oracle:Model', sourceDigest: 'source', irDigest: 'ir', sources: [], diagnostics: [],
    nodes: [node('root', undefined, ['source', 'block', 'consumer']), node('source', 'root'), node('block', 'root', ['norm', 'nested', 'linear']), node('norm', 'block'),
      node('nested', 'block', ['inner1', 'inner2']), node('inner1', 'nested'), node('inner2', 'nested'), node('linear', 'block'), node('consumer', 'root')],
    edges: [edge('incoming', 'source', 'norm'), edge('second-incoming', 'source', 'inner1'), edge('residual-incoming', 'source', 'linear', 'residual'),
      edge('first-internal', 'norm', 'inner1'), edge('hidden-internal', 'inner1', 'inner2'), edge('last-internal', 'inner2', 'linear'), edge('outgoing', 'linear', 'consumer'), edge('unrelated', 'source', 'consumer')],
  };
}

test('detail export partitions every canonical edge and visibly retains every crossing binding', () => {
  const document = applyVisualBatch(createDocument(oracle()), [{ type: 'expand', id: 'block', expanded: true }]);
  const before = JSON.stringify(document), scene = buildExportScene(document, { nodeId: 'block', widthMm: 85 }), scope = scene.exportScope!;
  assert.deepEqual(scope.canonicalNodeIds.sort(), ['block', 'inner1', 'inner2', 'linear', 'nested', 'norm']);
  assert.deepEqual(scope.internalEdgeIds.sort(), ['first-internal', 'hidden-internal', 'last-internal']);
  assert.deepEqual(scope.hiddenInternalEdgeIds, ['hidden-internal']);
  assert.deepEqual(scope.omittedEdgeIds, ['unrelated']);
  assert.deepEqual(scope.boundaryEdges.map(edge => edge.edgeId).sort(), ['incoming', 'outgoing', 'residual-incoming', 'second-incoming']);
  const partition = [...scope.internalEdgeIds, ...scope.boundaryEdges.map(edge => edge.edgeId), ...scope.omittedEdgeIds].sort();
  assert.deepEqual(partition, document.architecture.edges.map(edge => edge.id).sort());
  assert.equal(new Set(partition).size, partition.length);
  for (const expected of document.architecture.edges.filter(edge => scope.boundaryEdges.some(binding => binding.edgeId === edge.id))) {
    const rendered = scene.edges.find(edge => edge.id === expected.id)!;
    assert.ok(rendered); assert.deepEqual(rendered.source, expected.source); assert.deepEqual(rendered.target, expected.target);
    assert.equal(rendered.tensorId, expected.tensorId); assert.equal(rendered.role, expected.role);
    assert.deepEqual(rendered.canonicalEdgeIds, [expected.id]);
    const boundary = scene.nodes.find(node => node.id === (scope.boundaryEdges.find(binding => binding.edgeId === expected.id)!.direction === 'in' ? rendered.sourceId : rendered.targetId))!;
    assert.equal(boundary.boundary, true); assert.match(boundary.label, /^(FROM|TO) /);
    assert.equal(boundary.canonicalNodeId, expected.id === 'outgoing' ? 'consumer' : 'source');
    assert.ok(boundary.ports[0].canonicalEdgeIds.includes(expected.id));
  }
  assert.equal(scene.nodes.filter(node => node.boundary).length, 3); // Same source/data port is shared, edges remain separate.
  const visibleInternal = scene.edges.flatMap(edge => edge.canonicalEdgeIds).filter(id => scope.internalEdgeIds.includes(id));
  assert.deepEqual(visibleInternal.sort(), ['first-internal', 'last-internal']);
  assert.equal(JSON.stringify(document), before);
  assert.equal(scene.pageSpec.widthMm, 85); assert.equal(document.pageSpec.widthMm, 180);
  const metadata = JSON.parse(renderSvg(scene).match(/<metadata>(.*?)<\/metadata>/s)![1].replaceAll('&quot;', '"'));
  assert.deepEqual(metadata.exportScope.boundaryEdges, scope.boundaryEdges);
});

test('detail keeps edited geometry, aliases, styles, legend and contained annotations, and declares omissions', () => {
  let document = applyVisualBatch(createDocument(oracle()), [{ type: 'expand', id: 'block', expanded: true }, { type: 'alias', id: 'block', label: 'Detailed block' },
    { type: 'alias', id: 'source', label: 'Edited external source' }, { type: 'alias', id: 'linear', label: 'Edited Projection' },
    { type: 'nodeStyle', id: 'linear', style: { fill: '#123456' } }, { type: 'edgeStyle', id: 'incoming', style: { stroke: '#bb3322', width: 3, dashed: true } },
    { type: 'edgeStyle', id: 'last-internal', style: { stroke: '#114499' } }, { type: 'move', ids: ['linear'], dx: 17, dy: 9 },
    { type: 'legend', items: [{ id: 'custom', label: 'Edited legend', color: '#123456', glyph: 'attention' }] }]);
  const full = buildScene(document), selected = full.nodes.find(node => node.id === 'block')!;
  document = applyVisualBatch(document, [{ type: 'annotation', annotation: { id: 'inside', text: 'Internal note', x: selected.x + 10, y: selected.y + 10, width: 160, height: 35 } },
    { type: 'annotation', annotation: { id: 'outside', text: 'Outside note', x: 9000, y: 9000 } }]);
  const scene = buildExportScene(document, { nodeId: 'block' }), detailBlock = scene.nodes.find(node => node.id === 'block')!;
  for (const node of full.nodes.filter(node => ['block', 'norm', 'nested', 'linear'].includes(node.id))) {
    const detail = scene.nodes.find(item => item.id === node.id)!;
    assert.deepEqual([detail.x - detailBlock.x, detail.y - detailBlock.y, detail.width, detail.height], [node.x - selected.x, node.y - selected.y, node.width, node.height]);
  }
  assert.equal(scene.nodes.find(node => node.id === 'linear')!.fill, '#123456');
  assert.equal(scene.nodes.find(node => node.id === 'linear')!.label, 'Edited Projection');
  assert.ok(scene.nodes.some(node => node.label === 'FROM Edited external source'));
  assert.deepEqual(scene.legend.map(({ x, y, ...item }) => item), document.legendItems);
  const incoming = scene.edges.find(edge => edge.id === 'incoming')!;
  assert.deepEqual([incoming.stroke, incoming.width, incoming.dashed], ['#bb3322', 3, true]);
  assert.equal(scene.edges.find(edge => edge.id === 'last-internal')!.stroke, '#114499');
  assert.deepEqual(scene.exportScope!.includedAnnotationIds, ['inside']);
  assert.deepEqual(scene.exportScope!.omittedAnnotationIds, ['outside']);
  assert.ok(renderSvg(scene).includes('Internal note')); assert.ok(!renderSvg(scene).includes('Outside note'));
});

test('distinct external node/port tuples cannot collide when their identities contain delimiters', () => {
  const source = (id: string, portId: string): ArchitectureNode => ({ id, label: id, kind: 'Input', category: 'input', children: [], parameters: {}, evidence: 'source',
    ports: [{ id: portId, name: portId, direction: 'out', role: 'data', ordinal: 0 }] });
  const architecture: Architecture = { schemaVersion: 1, id: 'delimiter-oracle', label: 'Delimiter oracle', entry: 'oracle:Model', sourceDigest: 'source', irDigest: 'ir', sources: [], diagnostics: [],
    nodes: [source('a|b', 'c'), source('a', 'b|c'), { id: 'block', label: 'block', kind: 'Block', category: 'container', children: ['leaf'], ports: [], parameters: {}, evidence: 'source' },
      { id: 'leaf', label: 'leaf', kind: 'Linear', category: 'linear', parentId: 'block', children: [], ports: [{ id: 'in', name: 'features', direction: 'in', role: 'data', ordinal: 0 }], parameters: {}, evidence: 'source' }],
    edges: [{ id: 'first', source: { nodeId: 'a|b', portId: 'c' }, target: { nodeId: 'leaf', portId: 'in' }, tensorId: 'first-tensor', role: 'data' },
      { id: 'second', source: { nodeId: 'a', portId: 'b|c' }, target: { nodeId: 'leaf', portId: 'in' }, tensorId: 'second-tensor', role: 'data' }] };
  const document = applyVisualBatch(createDocument(architecture), [{ type: 'expand', id: 'block', expanded: true }]);
  const scene = buildExportScene(document, { nodeId: 'block' });
  assert.equal(scene.nodes.filter(node => node.boundary).length, 2);
  for (const expected of architecture.edges) {
    const edge = scene.edges.find(edge => edge.id === expected.id)!;
    const boundary = scene.nodes.find(node => node.id === edge.sourceId)!;
    assert.equal(boundary.canonicalNodeId, expected.source.nodeId);
    assert.deepEqual(boundary.ports[0].canonicalBindings, [expected.source]);
    assert.deepEqual(boundary.ports[0].canonicalEdgeIds, [expected.id]);
    assert.deepEqual(edge.source, expected.source);
  }
});

test('detail metadata and projected objects are detached from the input CanvasDocument', () => {
  const document = applyVisualBatch(createDocument(oracle()), [{ type: 'expand', id: 'block', expanded: true }]);
  const original = JSON.stringify(document), scene = buildExportScene(document, { nodeId: 'block' }), scope = scene.exportScope!;
  const crossing = scope.boundaryEdges[0];
  crossing.source.nodeId = 'metadata-source-edit'; crossing.target.portId = 'metadata-target-edit';
  scope.canonicalNodeIds.push('metadata-node'); scope.internalEdgeIds.push('metadata-edge'); scope.includedAnnotationIds.push('metadata-annotation');
  scene.nodes[0].label = 'Scene title edit';
  scene.nodes.find(node => node.boundary)!.ports[0].canonicalBindings[0].portId = 'Scene port edit';
  scene.edges[0].source.nodeId = 'Scene source edit';
  scene.legend[0].label = 'Scene legend edit';
  scene.pageSpec.widthMm = 85;
  assert.equal(JSON.stringify(document), original);
});

test('detail rejects leaf, collapsed or hidden containers and invalid options; whole keeps the ordinary scene', () => {
  const document = createDocument(oracle());
  for (const nodeId of ['linear', 'block', 'nested', 'missing']) assert.throws(() => buildExportScene(document, { nodeId }), /visible expanded container/);
  document.expandedIds.push('nested'); // An expanded descendant beneath a collapsed parent remains ineligible.
  assert.throws(() => buildExportScene(document, { nodeId: 'nested' }), /visible expanded container/);
  for (const widthMm of [0, 24, 1001, NaN, Infinity, true as never]) assert.throws(() => buildExportScene(document, { widthMm }), /25–1000/);
  assert.throws(() => buildExportScene(document, { arbitrary: true } as never), /Unknown export/);
  const expected = buildScene(document); expected.pageSpec.widthMm = 85;
  assert.deepEqual(buildExportScene(document, { widthMm: 85 }), expected);
});

test('detail bounds retain manually offset descendants instead of clipping negative coordinates', () => {
  const document = applyVisualBatch(createDocument(oracle()), [{ type: 'expand', id: 'block', expanded: true }, { type: 'move', ids: ['norm'], dx: -600, dy: -500 }]);
  const scene = buildExportScene(document, { nodeId: 'block' });
  assert.ok(scene.bounds.x < 0); assert.ok(scene.bounds.y < 0);
  for (const node of scene.nodes) {
    assert.ok(node.x >= scene.bounds.x && node.y >= scene.bounds.y);
    assert.ok(node.x + node.width <= scene.bounds.x + scene.bounds.width);
    assert.ok(node.y + node.height <= scene.bounds.y + scene.bounds.height);
  }
});

test('long boundary text and provenance fit their boxes and 85/180 mm preflight measures actual scale', () => {
  const document = applyVisualBatch(createDocument(oracle(), 'A long source citation '.repeat(18)), [{ type: 'expand', id: 'block', expanded: true },
    { type: 'alias', id: 'source', label: 'Full external label '.repeat(12) }, { type: 'alias', id: 'block', label: 'Long selected container '.repeat(6) }]);
  const scene = buildExportScene(document, { nodeId: 'block', widthMm: 85 });
  for (const node of scene.nodes.filter(node => node.boundary)) assert.ok(node.height >= wrapText(node.label, node.width - 62).length * 16 + 26);
  const citation = scene.annotations.find(annotation => annotation.id === 'detail-provenance')!;
  assert.ok(citation.height >= wrapText(citation.text, citation.width - 20, 11).length * 15 + 20);
  assert.ok(scene.bounds.width >= 50 + textWidth(scene.title, 19));
  const small = publicationPreflight(scene), wide = publicationPreflight(buildExportScene(document, { nodeId: 'block', widthMm: 180 }));
  assert.ok(small.minTextPt > 0); assert.ok(small.minTextPt < 7);
  assert.ok(Math.abs(wide.minTextPt / small.minTextPt - 180 / 85) < 1e-12);
  assert.equal(wide.suggestedWidthFor7Pt, small.suggestedWidthFor7Pt);
  assert.match(small.claim, /not a universal/);
  const heavier = structuredClone(scene);
  heavier.edges.forEach(edge => { edge.width = 3; });
  assert.ok(Math.abs(publicationPreflight(heavier).minMainLinePt - 3 * 85 / scene.bounds.width * 72 / 25.4) < 1e-12);
});

test('real source-derived MLP network detail accounts for adapters and exposes model input/output', async () => {
  const project = fileURLToPath(new URL('../../', import.meta.url)), local = `${project}.venv/bin/python`;
  const { stdout } = await promisify(execFile)(existsSync(local) ? local : 'python3', ['-I', '-S', '-B', '-c',
    'import sys,json; from pathlib import Path; root=Path(sys.argv[1]);sys.path.insert(0,str(root/"src"));from archcanvas_python import analyze_project;print(json.dumps(analyze_project(root/"fixtures/mlp","model:MLP")))', project], { encoding: 'utf8', maxBuffer: 2_000_000 });
  const architecture = JSON.parse(stdout) as Architecture, network = architecture.nodes.find(node => node.label === 'network')!;
  const document = applyVisualBatch(createDocument(architecture), [{ type: 'expand', id: network.id, expanded: true }]);
  const scene = buildExportScene(document, { nodeId: network.id }), scope = scene.exportScope!;
  // Two input bindings exist: the container adapter plus its first operation.
  // Keeping all three crossings is deliberate; projection must not silently
  // erase the adapter merely because its source is the same model input.
  assert.equal(scope.boundaryEdges.length, 3);
  assert.deepEqual(scope.boundaryEdges.map(edge => edge.direction).sort(), ['in', 'in', 'out']);
  const ids = [...scope.internalEdgeIds, ...scope.boundaryEdges.map(edge => edge.edgeId), ...scope.omittedEdgeIds];
  assert.deepEqual(ids.sort(), architecture.edges.map(edge => edge.id).sort());
  assert.ok(scene.nodes.some(node => node.boundary && node.label.startsWith('FROM')));
  assert.ok(scene.nodes.some(node => node.boundary && node.label.startsWith('TO')));
  assert.equal(scene.nodes.filter(node => !node.boundary && !node.expandable).length, 4);
});

test('physical advice accounts for tall pages and rounds the required width upward', () => {
  const scene = buildScene(createDocument(oracle()));
  scene.bounds = { x: 0, y: 0, width: 1000, height: 2000 };
  scene.pageSpec.widthMm = 85;
  scene.edges[0].label = 'binding'; // Visible edge label is 9 units, below the 10-unit footer.
  const result = publicationPreflight(scene);
  assert.equal(result.heightMm, 170);
  assert.equal(result.minTextPt, 9 * 85 / 1000 * 72 / 25.4);
  assert.equal(result.suggestedWidthFor7Pt, 275); // 274.3827… mm would reach exactly 7 pt.
  assert.equal(result.suggestedHeightFor7Pt, 550);
  const adjusted = structuredClone(scene);
  adjusted.pageSpec.widthMm = 275;
  assert.ok(publicationPreflight(adjusted).minTextPt >= 7);
  adjusted.pageSpec.widthMm = 274;
  assert.ok(publicationPreflight(adjusted).minTextPt < 7);
});

test('detail choices distinguish equal labels by identity/path and preserve the current frontier and edits', () => {
  const document = applyVisualBatch(createDocument(oracle()), [
    { type: 'expand', id: 'block', expanded: true }, { type: 'expand', id: 'nested', expanded: true },
    { type: 'alias', id: 'block', label: 'Same label' }, { type: 'alias', id: 'nested', label: 'Same label' },
    { type: 'move', ids: ['norm'], dx: -600, dy: 0 },
  ]);
  const before = JSON.stringify(document), choices = detailExportChoices(document, 85);
  assert.deepEqual(choices.map(choice => choice.nodeId).sort(), ['block', 'nested', 'root']);
  const block = choices.find(choice => choice.nodeId === 'block')!, nested = choices.find(choice => choice.nodeId === 'nested')!;
  assert.equal(block.pathLabel, 'root › Same label');
  assert.equal(nested.pathLabel, 'root › Same label › Same label');
  assert.equal(block.boundaryBindingCount, 4);
  assert.equal(nested.boundaryBindingCount, 3);
  assert.equal(block.visibleNodeCount, 6);
  assert.equal(nested.visibleNodeCount, 3);
  assert.ok(nested.minTextPt > block.minTextPt); // Moved sibling is excluded only from the explicit nested scope.
  assert.ok(nested.heightMm > 0 && nested.suggestedHeightFor7Pt > 0);
  assert.equal(JSON.stringify(document), before);
  const collapsed = applyVisualBatch(document, [{ type: 'expand', id: 'block', expanded: false }]);
  assert.deepEqual(detailExportChoices(collapsed).map(choice => choice.nodeId), ['root']);
  for (const width of [24, 1001, NaN, Infinity]) assert.throws(() => detailExportChoices(document, width), /25–1000/);
});
