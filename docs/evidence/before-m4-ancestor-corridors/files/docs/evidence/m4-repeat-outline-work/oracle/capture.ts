import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { analyzeSvg, frontCards, ordinaryPorts } from './oracle.ts';
import type { CanvasDocument, Scene } from '../../../../studio/src/core/types.ts';

const evidence = new URL('./', import.meta.url), root = new URL('../../../../', import.meta.url);
const mode = process.argv[2];
if (mode !== 'before' && mode !== 'after') throw new Error('Explicit before or after capture required');
const core = mode === 'before' ? new URL('docs/evidence/before-m4-repeat-outline/files/studio/src/core/', root) : new URL('studio/src/core/', root);
const { buildScene, buildExportScene, renderSvg } = await import(new URL('index.ts', core).href);
const digest = (bytes: string | Buffer) => createHash('sha256').update(bytes).digest('hex');
const sourceBindings = () => readdirSync(core).filter(name => name.endsWith('.ts')).sort().map(name => {
  const bytes = readFileSync(new URL(name, core)); return { path: fileURLToPath(new URL(name, core)), bytes: bytes.length, sha256: digest(bytes) };
});
const bindingsBefore = sourceBindings();
const cases = ['mlp-level0-paper-180', 'mlp-level1-paper-180', 'residual_cnn-level0-paper-180', 'residual_cnn-level1-paper-180', 'residual_cnn-level2-paper-180',
  'transformer-level0-paper-180', 'transformer-level1-paper-180', 'transformer-level2-paper-180', 'transformer-level3-paper-180'];
const records: unknown[] = [];
mkdirSync(new URL(`${mode}/`, evidence), { recursive: true });
for (const caseId of cases) {
  const inputPath = `docs/evidence/browser-visual-matrix-chs-current/captures/${caseId}/canvas.json`;
  const raw = readFileSync(new URL(inputPath, root), 'utf8'), document = JSON.parse(raw) as CanvasDocument;
  const beforeDocument = JSON.stringify(document), scene = buildScene(document) as Scene;
  const record = (scene: Scene, detailNodeId?: string) => {
    const svg = renderSvg(scene) as string, report = analyzeSvg(scene, svg);
    const name = detailNodeId ? `${caseId}--detail-${encodeURIComponent(detailNodeId)}` : caseId;
    writeFileSync(new URL(`${mode}/${name}.svg`, evidence), svg);
    writeFileSync(new URL(`${mode}/${name}.scene.json`, evidence), JSON.stringify(scene, null, 2) + '\n');
    records.push({ caseId, ...(detailNodeId ? { detailNodeId } : {}), inputPath, inputSha256: digest(raw), svgPath: `${mode}/${name}.svg`, scenePath: `${mode}/${name}.scene.json`, svgSha256: digest(svg),
      frontCards: frontCards(scene, svg), ordinaryPorts: ordinaryPorts(scene), sourceDigest: scene.sourceDigest, irDigest: scene.irDigest,
      sourceFactsSha256: digest(JSON.stringify(scene.sourceFacts)), renderedBindings: scene.edges.map(edge => ({ id: edge.id, canonicalEdgeIds: edge.canonicalEdgeIds,
        source: edge.source, target: edge.target, tensorId: edge.tensorId, role: edge.role })), hiddenEdges: scene.hiddenEdges,
      collapsedRepeatCount: scene.nodes.filter(node => node.repeat && !node.expanded).length, visibleEdgeCount: scene.edges.length,
      ...(scene.exportScope ? { exportScope: scene.exportScope } : {}), report });
  };
  record(scene);
  for (const selected of scene.nodes.filter(node => node.expanded && node.expandable)) {
    const detail = buildExportScene(document, { nodeId: selected.id }) as Scene;
    if (detail.nodes.some(node => node.repeat && !node.expanded)) record(detail, selected.id);
  }
  if (JSON.stringify(document) !== beforeDocument || readFileSync(new URL(inputPath, root), 'utf8') !== raw) throw new Error('Capture mutated Canvas input');
}
const bindingsAfter = sourceBindings();
const stable = JSON.stringify(bindingsBefore) === JSON.stringify(bindingsAfter);
writeFileSync(new URL(`${mode}.json`, evidence), JSON.stringify({ schemaVersion: 1, scope: 'Independent final-SVG nominal-card geometry, endpoint and immutable Canvas verification; no browser or publication acceptance claim',
  mode, explicitTestTarget: fileURLToPath(core), sourceBindingsBefore: bindingsBefore, sourceBindingsAfter: bindingsAfter, stableSourceDuringCapture: stable,
  inputsUnchanged: true, records }, null, 2) + '\n');
console.log(JSON.stringify({ mode, stableSourceDuringCapture: stable, frontiers: records.filter((row: any) => !row.detailNodeId).length, details: records.filter((row: any) => row.detailNodeId).length,
  stackHits: records.reduce((sum: number, row: any) => sum + row.report.stackHits.length, 0), endpointMisses: records.reduce((sum: number, row: any) => sum + row.report.endpointMisses.length, 0) }));
if (!stable) process.exitCode = 2;
