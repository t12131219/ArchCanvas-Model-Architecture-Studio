import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createOrthogonalRouter } from '../../../../studio/src/core/orthogonalRouter.ts';
import { createOrthogonalRouter as frozenRouter } from '../before-change/inputs/studio/src/core/orthogonalRouter.ts';

const root = new URL('../../../../', import.meta.url);
const index = JSON.parse(readFileSync(new URL('docs/evidence/m4-visual-next-current/review/historical-document-current-geometry.json', root), 'utf8'));
const parse = value => {
  const points = [];
  for (const t of value.matchAll(/([MHV])\s*([-\d.]+)(?:\s+([-\d.]+))?/g)) {
    const p = t[1] === 'M' ? { x: +t[2], y: +t[3] } : t[1] === 'H' ? { x: +t[2], y: points.at(-1).y } : { x: points.at(-1).x, y: +t[2] };
    if (!points.length || p.x !== points.at(-1).x || p.y !== points.at(-1).y) points.push(p);
  }
  return points;
};
const metric = value => {
  const points = parse(value); let length = 0, bends = 0;
  for (let i = 1; i < points.length; i++) {
    length += Math.abs(points[i].x - points[i-1].x) + Math.abs(points[i].y - points[i-1].y);
    if (i > 1 && (points[i].x === points[i-1].x) !== (points[i-1].x === points[i-2].x)) bends++;
  }
  return { length, bends };
};
const records = [];
for (const input of index.records) {
  const bytes = readFileSync(new URL(input.currentSceneBinding.path, root));
  if (bytes.length !== input.currentSceneBinding.bytes || createHash('sha256').update(bytes).digest('hex') !== input.currentSceneBinding.sha256) throw new Error('Unbound source scene');
  const scene = JSON.parse(bytes.toString()), untouched = JSON.stringify(scene);
  const requests = scene.edges.map(e => {
    const p = parse(e.path);
    return { sourceId: e.sourceId, targetId: e.targetId, start: p[0], end: p.at(-1), preferredPath: e.path, tensorId: e.tensorId,
      canonicalSource: e.source, canonicalTarget: e.target, canonicalEdgeIds: e.canonicalEdgeIds, role: e.role,
      appearance: { stroke: e.stroke, width: e.width, dashed: e.dashed, dashPattern: e.dashPattern } };
  });
  const old = frozenRouter(scene.nodes).batch(requests), next = createOrthogonalRouter(scene.nodes).batch(requests);
  const changed = next.flatMap((result, i) => result.path === old[i].path ? [] : [{ edgeId: scene.edges[i].id,
    role: scene.edges[i].role, tensorId: scene.edges[i].tensorId, canonicalEdgeIds: scene.edges[i].canonicalEdgeIds,
    beforePath: old[i].path, afterPath: result.path, before: metric(old[i].path), after: metric(result.path) }]);
  if (JSON.stringify(scene) !== untouched) throw new Error('Input scene mutation');
  records.push({ caseId: input.caseId, sceneBinding: input.currentSceneBinding, nodeCount: scene.nodes.length, edgeCount: scene.edges.length,
    sourceDigest: scene.sourceDigest, irDigest: scene.irDigest, inputSceneUnchanged: true, changedRoutes: changed,
    lengthSaved: changed.reduce((n, r) => n + r.before.length - r.after.length, 0), bendsRemoved: changed.reduce((n, r) => n + r.before.bends - r.after.bends, 0) });
}
const summary = { sourceFrontiers: records.length, routesExaminedAcrossFrontiers: records.reduce((n, r) => n + r.edgeCount, 0),
  changedRouteOccurrencesAcrossDistinctFrontiers: records.reduce((n, r) => n + r.changedRoutes.length, 0),
  lengthSavedAcrossDistinctFrontiers: records.reduce((n, r) => n + r.lengthSaved, 0), bendsRemovedAcrossDistinctFrontiers: records.reduce((n, r) => n + r.bendsRemoved, 0),
  candidateCountInReferencedHistoricalJson: index.records.reduce((n, r) => n + r.safeShorterRouteProposals.length, 0),
  scope: 'Distinct nine source frontiers, not nine independent models. Repeated canonical IDs across levels are separate route occurrences, not additional unique tensor bindings. Current old/new router observations share frozen scene inputs; this file records geometry, not derived-label or browser/export certification.' };
writeFileSync(new URL('source-frontier-measurement.json', import.meta.url), JSON.stringify({ schema: 'archcanvas-shortcut-nine-source-frontier-observation/1', records, summary }, null, 2) + '\n');
console.log(JSON.stringify(summary));
