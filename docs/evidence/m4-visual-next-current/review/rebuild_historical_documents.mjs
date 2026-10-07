import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { buildScene, renderSvg } from '../../../../studio/src/core/index.ts';

const root = fileURLToPath(new URL('../../../../', import.meta.url));
const out = fileURLToPath(new URL('./historical-documents-current-core/', import.meta.url));
const historic = path.join(root, 'docs/evidence/browser-visual-matrix-au3-current');
const binding = async p => {
  const raw = await readFile(p);
  return { path: path.relative(root, p), bytes: raw.byteLength, sha256: createHash('sha256').update(raw).digest('hex') };
};
await mkdir(out, { recursive: true });
const manifest = JSON.parse(await readFile(path.join(historic, 'manifest.json'), 'utf8'));
const bindings = [], records = [];
for (const record of manifest.captures.filter(r => r.state === 'baseline' && r.pageSpec.widthMm === 180 && r.pageSpec.preset === 'paper')) {
  for (const file of Object.values(record.files)) {
    const current = await binding(path.join(historic, file.path));
    if (current.sha256 !== file.sha256 || current.bytes !== file.bytes) throw new Error(`Historical bytes changed: ${file.path}`);
    bindings.push(current);
  }
  const document = JSON.parse(await readFile(path.join(historic, record.files.canvas.path), 'utf8'));
  const scene = buildScene(document), svg = renderSvg(scene);
  await writeFile(path.join(out, `${record.caseId}.scene.json`), JSON.stringify(scene));
  await writeFile(path.join(out, `${record.caseId}.svg`), svg);
  records.push({ caseId: record.caseId, documentBinding: await binding(path.join(historic, record.files.canvas.path)),
    oldBrowserScreenshotBinding: await binding(path.join(historic, record.files.screenshot.path)),
    oldScreenshotBuild: manifest.buildFiles,
    currentSceneBinding: await binding(path.join(out, `${record.caseId}.scene.json`)),
    currentSvgBinding: await binding(path.join(out, `${record.caseId}.svg`)),
    sourceDigest: scene.sourceDigest, irDigest: scene.irDigest, bounds: scene.bounds, nodes: scene.nodes.length, edges: scene.edges.length,
    oldPixelsCertificationInherited: false });
}
await writeFile(new URL('./historical-document-binding.json', import.meta.url), JSON.stringify({
  schema: 'archcanvas-historical-documents-current-core/1',
  method: 'Read only frozen actual-UI CanvasDocument inputs; reconstruct Scene and SVG with current formal core. Old screenshot bytes are verified for historical reference, never counted as current-build pixels.',
  humanParticipants: 0, modelExecuted: false, currentBrowserCapturePerformed: false,
  historicalArtifactsChecked: bindings.length, manifestBinding: await binding(path.join(historic, 'manifest.json')), bindings, records
}, null, 2) + '\n');
process.stdout.write(JSON.stringify({ records: records.length, historicalArtifactsChecked: bindings.length }) + '\n');
