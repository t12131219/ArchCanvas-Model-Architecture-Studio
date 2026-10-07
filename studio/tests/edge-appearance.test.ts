import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { applyVisualBatch, buildScene } from '../src/core/index.ts';
import { edgeAppearance } from '../src/edgeAppearance.ts';

test('sealed Transformer mask edge inspector reflects the actual displayed style', () => {
  const document = JSON.parse(readFileSync(new URL('../../docs/evidence/browser-visual-matrix-hierarchy-final/captures/transformer-level3-paper-180/canvas.json', import.meta.url), 'utf8'));
  const scene = buildScene(document), edge = scene.edges.find(item => item.id === 'edge:11') ?? scene.edges.find(item => item.canonicalEdgeIds.includes('edge:11'));
  assert.ok(edge, 'expanded Transformer exposes the atomic mask edge:11');
  assert.ok(scene.hiddenEdges.includes('edge:7'), 'coarse expanded layer mask is provenance, not a second displayed arrow');
  assert.deepEqual(edgeAppearance(document, 'edge:11', scene), { stroke: '#a194a8', width: 1.5, dashed: true });
  assert.notEqual(document.edgeStyleOverrides['edge:11']?.stroke ?? '#64748b', edge!.stroke);
  assert.notEqual(document.edgeStyleOverrides['edge:11']?.dashed ?? false, edge!.dashed);

  const edited = applyVisualBatch(document, [{ type: 'edgeStyle', id: 'edge:11', style: { stroke: '#224466', width: 3, dashed: false } }]);
  const editedScene = buildScene(edited);
  assert.deepEqual(edgeAppearance(edited, 'edge:11', editedScene), { stroke: '#224466', width: 3, dashed: false });
  assert.deepEqual(edited.edgeStyleOverrides['edge:11'], { stroke: '#224466', width: 3, dashed: false });

  // At the collapsed L0 frontier edge:7 is bundled with edge:11/25/29. A
  // canonical override must split that display bundle and stay on its own edge.
  const bundleDocument = JSON.parse(readFileSync(new URL('../../docs/evidence/browser-visual-matrix-hierarchy-final/captures/transformer-level0-paper-180/canvas.json', import.meta.url), 'utf8'));
  const bundleScene = buildScene(bundleDocument);
  assert.deepEqual(bundleScene.edges.find(item => item.canonicalEdgeIds.includes('edge:11'))?.canonicalEdgeIds, ['edge:7', 'edge:11', 'edge:25', 'edge:29']);
  const split = applyVisualBatch(bundleDocument, [{ type: 'edgeStyle', id: 'edge:11', style: { stroke: '#aa2244', width: 2.5, dashed: false } }]);
  const splitScene = buildScene(split);
  assert.deepEqual(edgeAppearance(split, 'edge:11', splitScene), { stroke: '#aa2244', width: 2.5, dashed: false });
  assert.deepEqual(edgeAppearance(split, 'edge:7', splitScene), { stroke: '#a194a8', width: 1.5, dashed: true });
});
