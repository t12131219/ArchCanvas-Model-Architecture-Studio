import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { blankDraft, draftRoutes } from '../../../../studio/src/authoring.ts';
import { insertDraftPreset } from '../../../../studio/src/authoringPresets.ts';

const root = fileURLToPath(new URL('../../../../', import.meta.url));
const destination = fileURLToPath(new URL('./', import.meta.url));
const hash = value => createHash('sha256').update(value).digest('hex');
const catalog = JSON.parse((await promisify(execFile)(`${root}.venv/bin/python`, ['-I', '-S', '-B', '-c',
  'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import module_catalog;print(json.dumps(module_catalog()))', root], { encoding: 'utf8' })).stdout);
const baseline = blankDraft('draft-cnn-layout-candidates'); let counter = 0;
insertDraftPreset(baseline, catalog, 'cnn', { x: 0, y: 0 }, prefix => `${prefix}_layout${++counter}`);
const keys = ['input', 'conv', 'relu', 'pool', 'average', 'flatten', 'head', 'output'];
const candidates = [
  { id: 'baseline-one-row-248', description: 'Current product default, eight nodes in one left-to-right row.', coordinates: keys.map((_, i) => [i * 248, 0]) },
  { id: 'two-forward-rows-248-180', description: 'Four nodes per row; each row flows left to right; one row-return route.', coordinates: keys.map((_, i) => [(i % 4) * 248, Math.floor(i / 4) * 180]) },
  { id: 'two-forward-rows-224-180', description: 'Four nodes per row, 48-unit gutters and 80-unit row gap; one row-return route.', coordinates: keys.map((_, i) => [(i % 4) * 224, Math.floor(i / 4) * 180]) },
  { id: 'two-forward-rows-224-154', description: 'Four nodes per row, 48-unit gutters and 54-unit row gap; one row-return route.', coordinates: keys.map((_, i) => [(i % 4) * 224, Math.floor(i / 4) * 154]) },
  { id: 'three-forward-rows-248-154', description: 'Three, three and two nodes in left-to-right rows; two row-return routes.', coordinates: keys.map((_, i) => [(i % 3) * 248, Math.floor(i / 3) * 154]) },
  { id: 'three-forward-rows-224-154', description: 'Three, three and two nodes in left-to-right rows; 48-unit gutters; two row returns.', coordinates: keys.map((_, i) => [(i % 3) * 224, Math.floor(i / 3) * 154]) },
  { id: 'two-snake-rows-224-180', description: 'Second row reverses flow while its ports retain output-right/input-left orientation.', coordinates: keys.map((_, i) => [i < 4 ? i * 224 : (7 - i) * 224, i < 4 ? 0 : 180]) },
  { id: 'one-vertical-column-154', description: 'Vertical nodes with the actual horizontal port orientation.', coordinates: keys.map((_, i) => [0, i * 154]) },
];

// This oracle uses public node rectangles and route points, not router diagnostics.
function clean(points) {
  const result = [];
  for (const p of points) {
    if (result.length && p.x === result.at(-1).x && p.y === result.at(-1).y) continue;
    while (result.length >= 2) {
      const a = result.at(-2), b = result.at(-1);
      if ((a.x === b.x && b.x === p.x && (b.y - a.y) * (p.y - b.y) > 0) || (a.y === b.y && b.y === p.y && (b.x - a.x) * (p.x - b.x) > 0)) result.pop();
      else break;
    }
    result.push({ ...p });
  }
  return result;
}
const segments = points => points.slice(1).map((b, i) => [points[i], b]);
function bodyHit(a, b, node) {
  const { x, y } = node.position, right = x + 176, bottom = y + 100;
  if (a.x === b.x) return a.x > x && a.x < right && Math.max(Math.min(a.y, b.y), y) < Math.min(Math.max(a.y, b.y), bottom);
  if (a.y === b.y) return a.y > y && a.y < bottom && Math.max(Math.min(a.x, b.x), x) < Math.min(Math.max(a.x, b.x), right);
  throw new Error('Non-orthogonal route');
}
function conflict(a, b, c, d) {
  const horizontalA = a.y === b.y, horizontalB = c.y === d.y;
  if (horizontalA === horizontalB) {
    if (horizontalA ? a.y !== c.y : a.x !== c.x) return null;
    const axis = horizontalA ? 'x' : 'y';
    const length = Math.min(Math.max(a[axis], b[axis]), Math.max(c[axis], d[axis])) - Math.max(Math.min(a[axis], b[axis]), Math.min(c[axis], d[axis]));
    return length > 0 ? { kind: 'overlap', length } : null;
  }
  const h = horizontalA ? [a, b] : [c, d], v = horizontalA ? [c, d] : [a, b];
  const x = v[0].x, y = h[0].y;
  return x > Math.min(h[0].x, h[1].x) && x < Math.max(h[0].x, h[1].x) && y > Math.min(v[0].y, v[1].y) && y < Math.max(v[0].y, v[1].y) ? { kind: 'crossing', x, y } : null;
}
function assess(draft, geometry) {
  const bodyHits = [], crossings = [], overlaps = [], nodeOverlaps = [];
  for (const [i, node] of draft.nodes.entries()) for (const other of draft.nodes.slice(i + 1)) if (Math.abs(node.position.x - other.position.x) < 176 && Math.abs(node.position.y - other.position.y) < 100) nodeOverlaps.push([node.id, other.id]);
  const routes = geometry.routes.map(route => ({ ...route, points: clean(route.points) }));
  let bends = 0, uTurns = 0, length = 0;
  for (const route of routes) {
    const parts = segments(route.points); bends += Math.max(0, route.points.length - 2);
    for (const [a, b] of parts) {
      length += Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
      for (const node of draft.nodes) if (bodyHit(a, b, node)) bodyHits.push({ edge: route.id, node: node.id, a, b });
    }
    for (let i = 1; i < parts.length; i++) {
      const [a, b] = parts[i - 1], [, c] = parts[i];
      if ((a.x === b.x && b.x === c.x && (b.y - a.y) * (c.y - b.y) < 0) || (a.y === b.y && b.y === c.y && (b.x - a.x) * (c.x - b.x) < 0)) uTurns++;
    }
  }
  for (let i = 0; i < routes.length; i++) for (const other of routes.slice(i + 1)) {
    for (const [a, b] of segments(routes[i].points)) for (const [c, d] of segments(other.points)) {
      const collision = conflict(a, b, c, d); if (!collision) continue;
      (collision.kind === 'crossing' ? crossings : overlaps).push({ first: routes[i].id, second: other.id, ...collision });
    }
  }
  const all = [...draft.nodes.flatMap(node => [node.position, { x: node.position.x + 176, y: node.position.y + 100 }]), ...routes.flatMap(route => route.points)];
  const box = { x: Math.min(...all.map(p => p.x)), y: Math.min(...all.map(p => p.y)), right: Math.max(...all.map(p => p.x)), bottom: Math.max(...all.map(p => p.y)) };
  const viewport = { width: 815, height: 535.5, provenance: 'Root actual public SVGrect read reported width815,height535.5,x220,y118; this script does not itself operate the browser.' };
  const fitZoom = Math.min(1, (viewport.width - 30) / (box.right - box.x + 64), (viewport.height - 30) / (box.bottom - box.y + 64));
  return { bodyHits, crossings, overlaps, nodeOverlaps, bends, uTurns, length, routes: routes.map(route => ({ id: route.id, points: route.points, bends: Math.max(0, route.points.length - 2), routerBlockedBy: route.blockedBy })), box, viewport, calculatedFitZoom: fitZoom, titleScreenPx: 13 * fitZoom, typeScreenPx: 10 * fitZoom, portScreenPx: 9 * fitZoom };
}
const escape = text => text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
function diagram(draft, assessment) {
  const zoom = assessment.calculatedFitZoom, left = assessment.box.x - 32, top = assessment.box.y - 32;
  const width = assessment.box.right - left + 32, height = assessment.box.bottom - top + 32;
  const transform = `translate(${(815 - width * zoom) / 2 - left * zoom} ${(535.5 - height * zoom) / 2 - top * zoom}) scale(${zoom})`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="815" height="535.5" viewBox="0 0 815 535.5"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10Z" fill="#628572"/></marker></defs><rect width="815" height="535.5" fill="#f7faf7"/><g transform="${transform}">${assessment.routes.map(route => `<polyline points="${route.points.map(p => `${p.x},${p.y}`).join(' ')}" fill="none" stroke="#628572" stroke-width="1.8" marker-end="url(#arrow)"/>`).join('')}${draft.nodes.map(node => `<g transform="translate(${node.position.x} ${node.position.y})"><rect width="176" height="100" rx="9" fill="#fff" stroke="#b9d0bf" stroke-width="1.3"/><rect x="1" y="1" width="174" height="36" rx="8" fill="#edf4eb"/><text x="13" y="23" fill="#355247" font-family="sans-serif" font-size="13">${escape(node.label)}</text><text x="13" y="92" fill="#819487" font-family="monospace" font-size="10">${escape(node.kind)}</text>${node.kind !== 'Input' ? '<circle cx="0" cy="66" r="5" fill="#eef5ed" stroke="#729b82" stroke-width="1.5"/><text x="12" y="69" font-family="sans-serif" font-size="9" fill="#718578">input</text>' : ''}${node.kind !== 'Output' ? '<circle cx="176" cy="66" r="5" fill="#729b82" stroke="#729b82" stroke-width="1.5"/><text x="164" y="69" text-anchor="end" font-family="sans-serif" font-size="9" fill="#718578">output</text>' : ''}</g>`).join('')}</g></svg>`;
}
await mkdir(destination, { recursive: true });
const results = [];
for (const candidate of candidates) {
  const draft = structuredClone(baseline);
  draft.nodes.forEach((node, i) => { const [x, y] = candidate.coordinates[i]; node.position = { x, y }; });
  const geometry = draftRoutes(draft, catalog), assessment = assess(draft, geometry);
  results.push({ id: candidate.id, description: candidate.description, coordinates: Object.fromEntries(keys.map((key, i) => [key, candidate.coordinates[i]])), ...assessment });
  await writeFile(`${destination}${candidate.id}.draft.json`, JSON.stringify(draft, null, 2) + '\n');
  await writeFile(`${destination}${candidate.id}.svg`, diagram(draft, assessment));
}
const inputs = ['studio/src/authoringPresets.ts', 'studio/src/authoring.ts', 'studio/src/core/orthogonalRouter.ts', 'studio/src/authoringFeedback.ts'];
const inputBindings = await Promise.all(inputs.map(async path => ({ path, sha256: hash(await readFile(root + path)) })));
await writeFile(`${destination}catalog.json`, JSON.stringify(catalog, null, 2) + '\n');
await writeFile(`${destination}comparison.json`, JSON.stringify({ scope: 'Read-only candidate geometry and calculated CSS scaling; no product change, browser interaction, human acceptance or presented-frame observation.', inputBindings, results }, null, 2) + '\n');
process.stdout.write(JSON.stringify(results.map(result => ({ id: result.id, fit: result.calculatedFitZoom, titlePx: result.titleScreenPx, bends: result.bends, bodyHits: result.bodyHits.length, crossings: result.crossings.length, overlaps: result.overlaps.length, length: result.length })), null, 2) + '\n');
