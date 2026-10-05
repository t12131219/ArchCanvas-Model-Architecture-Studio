// Read-only adapter for the already independently tested routing oracle.
// No product runtime, renderer, router, parser, scorer or user model is imported.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { metrics, intrusions, verifyEndpoints } from '../../m4-routing-refinement/independent/oracle.ts';
import { runControls } from '../../m4-routing-refinement/independent/controls.ts';

const input = process.argv[2];
if (input === '--controls') {
  process.stdout.write(JSON.stringify(runControls(), null, 2) + '\n');
} else {
  if (!input) throw new Error('Usage: analyze_scene.ts SCENE_JSON | --controls');
  const bytes = readFileSync(input), scene = JSON.parse(bytes.toString());
  if (!Array.isArray(scene.nodes) || !Array.isArray(scene.edges)) throw new Error('Scene nodes/edges required');
  const result = metrics(scene), bodyHeaderIntrusions = intrusions(scene);
  let endpointError: string | null = null;
  try { verifyEndpoints(scene); } catch (error) { endpointError = String(error); }
  const semantics = new Map(scene.edges.map((edge: any) => [edge.id, {
    sourceId: edge.sourceId, targetId: edge.targetId, source: edge.source, target: edge.target,
    tensorId: edge.tensorId, role: edge.role, canonicalEdgeIds: edge.canonicalEdgeIds,
  }]));
  const routes = result.routes.map(route => {
    const start = route.points[0], end = route.points.at(-1)!;
    const manhattanEndpointLowerBound = Math.abs(end.x - start.x) + Math.abs(end.y - start.y);
    return { ...route, ...semantics.get(route.id) as object, manhattanEndpointLowerBound,
      lengthAboveEndpointLowerBound: route.length - manhattanEndpointLowerBound };
  });
  process.stdout.write(JSON.stringify({
    schema: 'archcanvas-independent-routing-geometry/1',
    scope: 'Actual supplied Scene geometry only; no scene rebuilding, raster/font/aesthetic/human/performance certification.',
    inputSha256: createHash('sha256').update(bytes).digest('hex'),
    binding: { documentId: scene.documentId, revision: scene.revision, sourceDigest: scene.sourceDigest, irDigest: scene.irDigest },
    visibleNodes: scene.nodes.length, renderedRoutes: scene.edges.length,
    endpointAndViewBoxCheck: { passed: endpointError === null, error: endpointError, toleranceUnits: .15 },
    ...result, routes, bodyHeaderIntrusions,
    pairs: result.pairs.map(pair => ({ ...pair,
      firstBinding: semantics.get(pair.first), secondBinding: semantics.get(pair.second) })),
    definitions: {
      crossingPairs: 'Unordered edge pairs with >=1 strict-interior perpendicular crossings; excludes bends/endpoint contacts/T-junctions.',
      crossingPairPoints: 'Unique crossing positions within each edge pair; not globally unique crossings.',
      overlapLength: 'Positive collinear interval union length per edge pair/lane, summed over pairs.',
      sameTensor: 'Equal validated source-bound tensor IDs; shared trunks reported separately, not automatically a defect.',
      disjointOwners: 'Different tensors whose projected source/target owners have no identity in common.',
      bends: 'Direction changes after zero-length removal and same-direction collinear compaction; U-turns also counted separately.',
      intrusions: 'Route centerline in node body/header interior inset .25; ancestors of endpoints expose header only.',
      detour: 'Route length minus endpoint Manhattan lower bound; obstacles/direction/ports may require it. Never classified as unnecessary.',
    },
    limitations: [
      'No minimal/global-optimal route search or necessity/aesthetic verdict.',
      'Centerlines omit stroke width, arrowheads, labels, text boxes, decorative glyphs and near misses.',
      'Strict crossings omit segment endpoint contacts and T-junctions by contract.',
      'Projection can aggregate multiple canonical relations into one route; route counts are not semantic relation counts.',
      'Header band uses the separately parsed SVG divider plus documented four-unit padding.',
      'Only supplied actual artifacts establish capture scope; serialized Scene provenance must be separately bound.',
    ],
    aestheticCertified: false, humanCertified: false, publicationCertified: false, presentedPerformanceCertified: false,
  }, null, 2) + '\n');
}
