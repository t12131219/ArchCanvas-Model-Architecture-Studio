import assert from 'node:assert/strict';
import { cleanScene } from './fixtures.ts';
import { metrics, verifyEndpoints, verifyRefinement } from './oracle.ts';
import type { Scene } from '../../../../studio/src/core/types.ts';

export function runControls() {
  const rows: { name: string; rejected: boolean; reason: string; coherentEndpoints?: boolean }[] = [];
  const control = (name: string, mutate: (scene: Scene) => void, expected: RegExp, setup?: (scene: Scene) => void, coherentEndpoints = false) => {
    const before = cleanScene(); setup?.(before); const after = structuredClone(before); mutate(after);
    if (coherentEndpoints) verifyEndpoints(after);
    let reason = ''; try { verifyRefinement(before, after); } catch (error) { reason = String(error); }
    assert.match(reason, expected, `${name} must be rejected for its intended failure`);
    rows.push({ name, rejected: true, reason, coherentEndpoints });
  };
  const clean = cleanScene(); verifyRefinement(clean, structuredClone(clean));
  assert.deepEqual(metrics(clean).distinctTensor, { crossingPairs: 0, crossingPairPoints: 0, overlapPairs: 0, overlapLength: 0 });
  control('new distinct-tensor crossing at two strict interiors', scene => {
    scene.edges[0].path = 'M 10 20 V 45 H 70 V 95 H 10 V 120';
    scene.edges[1].path = 'M 110 20 V 65 H 50 V 105 H 110 V 120';
    assert.equal(metrics(scene).distinctTensor.crossingPairPoints, 2);
  }, /distinctTensor crossingPairs regressed/, undefined, true);
  control('positive collinear overlap with unchanged anchors', scene => {
    scene.edges[0].path = 'M 10 20 V 50 H 110 V 80 H 10 V 120';
    scene.edges[1].path = 'M 110 20 V 50 H 10 V 90 H 110 V 120';
    assert.equal(metrics(scene).distinctTensor.overlapPairs, 1);
  }, /distinctTensor overlapPairs regressed/, undefined, true);
  control('unrelated-body penetration', scene => { scene.edges[0].path = 'M 10 20 V 40 H 50 V 90 H 10 V 120'; }, /new body\/header intrusion/, scene => {
    scene.nodes.push({ ...structuredClone(scene.nodes[0]), id: 'unrelated-body', x: 40, y: 50, localX: 40, localY: 50, ports: [] });
  }, true);
  control('owner-ancestor header penetration', scene => { scene.edges[0].path = 'M 10 20 V 30 H 50 V 0 H 60 V 40 H 10 V 120'; }, /"obstacle":"header"/, scene => {
    const frame = { ...structuredClone(scene.nodes[0]), id: 'frame', x: 0, y: -30, localY: -30, width: 70, height: 210,
      headerHeight: 40, expanded: true, expandable: true, ports: [] };
    scene.nodes.push(frame); scene.nodes[0].parentId = 'frame'; scene.nodes[1].parentId = 'frame';
  }, true);
  control('new route U-turn outside bodies', scene => { scene.edges[0].path = 'M 10 20 V 60 V 40 V 120'; }, /new U-turn/, undefined, true);
  control('departure direction changed with valid canonical endpoint', scene => { scene.edges[0].path = 'M 10 20 H 30 V 120 H 10'; }, /departure direction changed/, undefined, true);
  control('subpixel 0.03 start anchor drift', scene => { scene.edges[0].path = 'M 10.03 20 V 70 H 10 V 120'; }, /start anchor moved/, undefined, true);
  control('canonical tensor tampering', scene => { scene.edges[0].tensorId = 'forged-tensor'; }, /altered edge semantics\/style/, undefined, true);
  control('semantic concealment of geometrical crossings', scene => {
    scene.edges[0].path = 'M 10 20 V 45 H 70 V 95 H 10 V 120'; scene.edges[1].path = 'M 110 20 V 65 H 50 V 105 H 110 V 120';
    scene.edges[1].tensorId = scene.edges[0].tensorId; assert.equal(metrics(scene).distinctTensor.crossingPairs, 0);
  }, /altered edge semantics\/style/, undefined, true);
  control('coherent target node+port+route displacement', scene => {
    scene.nodes[1].x += 20; scene.nodes[1].localX += 20; scene.nodes[1].ports[0].x += 20;
    scene.edges[0].path = 'M 10 20 V 70 H 30 V 120';
  }, /moved\/resized\/relabeled/, undefined, true);
  control('coherent whole figure translation', scene => {
    for (const node of scene.nodes) { node.x += 25; node.y += 35; node.localX += 25; node.localY += 35; for (const port of node.ports) { port.x += 25; port.y += 35; } }
    scene.edges[0].path = 'M 35 55 V 155'; scene.edges[1].path = 'M 135 55 V 155'; scene.bounds.x += 25; scene.bounds.y += 35;
  }, /moved\/resized\/relabeled/, undefined, true);
  control('pin mutation despite clear geometry', scene => { scene.nodes[0].pinned = true; }, /moved\/resized\/relabeled/, undefined, true);
  control('source digest substitution', scene => { scene.sourceDigest = 'forged-source'; }, /altered sourceDigest/, undefined, true);
  control('route clipped by bounded viewBox', scene => { scene.bounds.width = 105; }, /route clipped by scene/);
  control('nonorthogonal L route', scene => { scene.edges[0].path = 'M 10 20 L 30 50 V 120'; }, /nonorthogonal path/);
  return { positiveUnchangedControlPassed: true, negativeControls: rows.length, rejected: rows.length,
    scope: 'Deliberate contamination of coherent scene endpoints, owner geometry, tensors, bodies/headers, route direction, clip and parser. Not generated model or human evidence.', rows };
}
