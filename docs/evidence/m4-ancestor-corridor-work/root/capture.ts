import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { buildScene, buildExportScene, renderSvg } from '../../../../studio/src/core/index.ts';
import type { CanvasDocument } from '../../../../studio/src/core/types.ts';

const project = new URL('../../../../', import.meta.url), attempt = process.argv[2] ?? 'capture-attempt-1';
if (!/^capture-attempt-[1-9][0-9]*$/.test(attempt)) throw new Error('Explicit capture attempt required');
const base = new URL(`./${attempt}/`, import.meta.url);
mkdirSync(base, { recursive: false });
const frozen = JSON.parse(readFileSync(new URL('docs/evidence/m4-repeat-outline-work/oracle/after.json', project), 'utf8'));
const records = [];
for (const row of frozen.records) {
  const input = new URL(row.inputPath, project), bytes = readFileSync(input), document = JSON.parse(bytes.toString()) as CanvasDocument;
  const serialized = JSON.stringify(document);
  const scene = row.detailNodeId ? buildExportScene(document, { nodeId: row.detailNodeId }) : buildScene(document);
  const svg = renderSvg(scene), name = row.detailNodeId ? `${row.caseId}--detail-${encodeURIComponent(row.detailNodeId)}` : row.caseId;
  writeFileSync(new URL(`${name}.scene.json`, base), JSON.stringify(scene, null, 2) + '\n');
  writeFileSync(new URL(`${name}.svg`, base), svg);
  if (serialized !== JSON.stringify(document) || !bytes.equals(readFileSync(input))) throw new Error('Projection changed input');
  records.push({ caseId: row.caseId, detailNodeId: row.detailNodeId, inputPath: row.inputPath,
    inputSha256: createHash('sha256').update(bytes).digest('hex'), nodes: scene.nodes.length, edges: scene.edges.length,
    svgSha256: createHash('sha256').update(svg).digest('hex') });
}
writeFileSync(new URL('report.json', base), JSON.stringify({ records, inputUnchanged: true, modelExecution: 'not_run', browserAcceptance: false }, null, 2) + '\n');
console.log(JSON.stringify({ frontiers: records.filter(row => !row.detailNodeId).length, details: records.filter(row => row.detailNodeId).length }));
