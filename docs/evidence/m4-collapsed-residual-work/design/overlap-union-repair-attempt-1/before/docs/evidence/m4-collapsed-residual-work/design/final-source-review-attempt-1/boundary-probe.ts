import { createOrthogonalRouter } from '../../../../../studio/src/core/orthogonalRouter.ts';
import { literalRoutingCase, literalNode, literalPort } from '../../acceptance/fixtures.ts';
import { pair } from '../../acceptance/oracle.ts';

// Independent review probe, not a product test or acceptance conclusion.
// Uses trusted literal Scene inputs and executes no model source.
const fixture = literalRoutingCase();
const edgeId = 'protected/retraced', sourceId = 'protected/source', targetId = 'protected/target';
const start = { x: -10, y: 60 }, end = { x: 50, y: 80 };
const source = literalNode(sourceId, -30, 50, 20, 20, { parentId: 'shell' });
const target = literalNode(targetId, 20, 80, 30, 20, { parentId: 'shell' });
source.ports = [literalPort(sourceId, sourceId, 'out', edgeId, 'out', start.x, start.y)];
target.ports = [literalPort(targetId, targetId, 'in', edgeId, 'in', end.x, end.y)];
fixture.scene.nodes.push(source, target);
const protectedPath = 'M -10 60 H 55 H 50 H 55 H 50 V 80';
const protectedRequest = {
  sourceId, targetId, start, end, preferredPath: protectedPath,
  tensorId: fixture.requests[0].tensorId, role: 'data' as const,
  appearance: { stroke: '#115588', width: 2, dashed: false },
  canonicalSource: { nodeId: sourceId, portId: 'out' },
  canonicalTarget: { nodeId: targetId, portId: 'in' },
  canonicalEdgeIds: [edgeId], displaySide: 'bottom' as const,
};
const requests = [fixture.requests[0], protectedRequest];
const result = createOrthogonalRouter(fixture.scene.nodes).batch(requests);
process.stdout.write(JSON.stringify({
  scope: 'read-only synthetic source-review boundary probe; not browser or publication acceptance',
  inputPaths: requests.map(request => request.preferredPath),
  outputPaths: result.map(route => route.path), blockedBy: result.map(route => route.blockedBy),
  before: pair(requests[0].preferredPath, protectedPath),
  after: pair(result[0].path, result[1].path),
}, null, 2) + '\n');
