import assert from 'node:assert/strict';
import type { CanvasDocument, Scene } from '../src/core/types.ts';
import * as preCaption from '../../docs/evidence/m4-caption-stability-current/before-change/inputs/studio/src/core/index.ts';

/** Adapt only the newly visible default memory text for an older oracle.
 * The observation must first retain the exact immediately prior routes,
 * nodes/ports, identities, styles and facts for this same actual document.
 * Historical gold/oracle bytes and actual Scene/SVG remain untouched. */
export function normalizeDefaultMemoryLabels(document: CanvasDocument, current: Scene, historical: Scene): Scene {
  const scope = current.exportScope ? { nodeId: current.exportScope.selectedNodeId, widthMm: current.pageSpec.widthMm } : {};
  const before = preCaption.buildExportScene(document, scope);
  const serial = <T>(input: T): T => input === undefined ? input : JSON.parse(JSON.stringify(input));
  assert.deepEqual(serial(current.nodes), serial(before.nodes), 'label revision cannot alter any owner or projected port');
  const protectedEdges = (scene: Scene) => scene.edges.map(({ label: _l, labelX: _x, labelY: _y, ...edge }) => edge);
  assert.deepEqual(serial(protectedEdges(current)), serial(protectedEdges(before)), 'label revision cannot alter any route, canonical binding or style');
  for (const key of ['documentId', 'revision', 'sourceDigest', 'irDigest', 'sourceFacts', 'hiddenEdges', 'pageSpec', 'annotations', 'legend', 'exportScope'] as const)
    assert.deepEqual(serial(current[key]), serial(before[key]), `label revision altered protected ${key}`);
  const copy = structuredClone(current);
  for (const edge of copy.edges) {
    const old = historical.edges.find(old => old.id === edge.id); assert.ok(old, 'historical edge coverage changed');
    if (edge.label === old.label) continue;
    assert.equal(edge.role, 'memory'); assert.equal(old.role, 'memory');
    assert.equal(old.label, ''); assert.equal(edge.label, 'memory');
    for (const id of edge.canonicalEdgeIds) {
      const canonical = document.architecture.edges.find(item => item.id === id); assert.ok(canonical);
      assert.equal(canonical.role, 'memory'); assert.equal(canonical.label, undefined, 'explicit empty/authored captions must not be normalized');
    }
    edge.label = old.label;
  }
  return copy;
}
