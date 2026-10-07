import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
// Exact pre-atomic port/route compatibility is a historical M4 contract.
import { buildScene, applyVisualBatch } from './historical-routing-core.ts';
import * as prior from '../../docs/evidence/m4-caption-stability-current/before-change/inputs/studio/src/core/index.ts';
import { normalizeDefaultMemoryLabels } from './historical-memory-caption-compat.ts';
import type { CanvasDocument, Scene } from '../src/core/types.ts';

test('historical caption compatibility rejects route/port/binding corruption and explicit or nonmemory text changes', () => {
  const fixture = new URL('../../docs/evidence/m4-caption-route-current/browser/pre-ui/saved-transformer-final-envelope.json', import.meta.url);
  const base = JSON.parse(readFileSync(fixture, 'utf8')).document as CanvasDocument;
  const document = applyVisualBatch(base, [{ type: 'move', ids: ['repeat:instance:model.Transformer.encoder'], dx: 0, dy: 24 }]);
  const scene = buildScene(document), before = prior.buildScene(document), bytes = JSON.stringify({ document, scene, before });
  const normalized = normalizeDefaultMemoryLabels(document, scene, before);
  assert.equal(normalized.edges.find(e => e.id === 'edge:44')!.label, '');
  const reject = (mutate: (scene: Scene) => void) => { const forged = structuredClone(scene); mutate(forged); assert.throws(() => normalizeDefaultMemoryLabels(document, forged, before)); };
  reject(s => { s.edges.find(e => e.id === 'edge:44')!.path = 'M 1 1 V 2'; });
  reject(s => { s.nodes.flatMap(n => n.ports)[0].x += .01; });
  reject(s => { s.edges[0].canonicalEdgeIds = ['forged']; });
  reject(s => { s.edges[0].label = 'memory'; });
  const authored = structuredClone(document); authored.architecture.edges.find(e => e.id === 'edge:44')!.label = '';
  assert.throws(() => normalizeDefaultMemoryLabels(authored, scene, before), 'an explicit empty caption cannot become a default caption exception');
  assert.equal(JSON.stringify({ document, scene, before }), bytes, 'compatibility must not mutate evidence or actual observations');
});
