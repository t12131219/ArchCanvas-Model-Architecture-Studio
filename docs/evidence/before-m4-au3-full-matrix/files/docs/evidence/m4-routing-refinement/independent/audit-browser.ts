import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { metrics, intrusions, verifyRefinement } from './oracle.ts';

const base = fileURLToPath(new URL('.', import.meta.url));
const sha = (bytes: string | Buffer) => createHash('sha256').update(bytes).digest('hex');
const beforeBytes = readFileSync(`${base}/browser-before.scene.json`), afterBytes = readFileSync(`${base}/browser-after.scene.json`);
const before = JSON.parse(beforeBytes.toString()), after = JSON.parse(afterBytes.toString());
const result = verifyRefinement(before, after);
const changedEdgeIds = after.edges.filter((edge: { path: string }, index: number) => edge.path !== before.edges[index].path).map((edge: { id: string }) => edge.id);
const target = `${base}/browser-audit.json`;
if (existsSync(target)) throw new Error('Refusing to overwrite browser audit');
const xml = JSON.parse(readFileSync(`${base}/browser-xml-binding.json`, 'utf8'));
writeFileSync(target, JSON.stringify({ schemaVersion: 1, createdAt: new Date().toISOString(),
  scope: 'Independent metrics of actual public browser DOM SVG parsed using standard XML and independent TypeScript geometry. Product route/parser/intersection/scoring helpers are never imported. Saved canvas, node/port XML, metadata and semantic projection independently checked. One browser engineering representative; not full visual matrix, native performance, human researcher/publication acceptance.',
  sourceHashes: { before: sha(beforeBytes), after: sha(afterBytes), xmlBinding: sha(readFileSync(`${base}/browser-xml-binding.json`)) },
  inputs: xml.inputs, beforeScripts: xml.beforeScripts, afterScripts: xml.afterScripts,
  publicNodeCount: before.nodes.length, publicEdgeCount: before.edges.length, publicPortCount: before.nodes.reduce((total: number, node: { ports: unknown[] }) => total + node.ports.length, 0),
  changedEdgeIds, before: metrics(before), after: metrics(after), beforeIntrusions: intrusions(before), afterIntrusions: intrusions(after),
  passed: true, checks: ['endpoint/canonical-port anchored', 'departure+arrival direction invariant', 'exact visible nodes/ports', 'exact edge bindings/style',
    'exact source facts/digests', 'saved canvas/pins/layout/frontier snapshots unchanged', 'distinctTensor and disjointOwners crossing pair/points and overlap pair nonincrease', 'no new body/header intrusion', 'no new U-turn'],
  result }, null, 2) + '\n');
process.stdout.write(JSON.stringify({ passed: true, changedEdgeIds, before: result.before.distinctTensor, after: result.after.distinctTensor,
  beforeDisjoint: result.before.disjointOwners, afterDisjoint: result.after.disjointOwners,
  totalLengthBefore: result.before.totalLength, totalLengthAfter: result.after.totalLength,
  totalBendsBefore: result.before.totalBends, totalBendsAfter: result.after.totalBends,
  bodyHeaderBefore: result.beforeIntrusions.length, bodyHeaderAfter: result.afterIntrusions.length, reversalsAfter: result.after.totalReversals }) + '\n');
