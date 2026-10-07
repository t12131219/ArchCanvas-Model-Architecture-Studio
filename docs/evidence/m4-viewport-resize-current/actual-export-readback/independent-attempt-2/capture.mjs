// Production APIs supply an observation. The Python auditor independently checks it.
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { buildExportScene, renderSvg } from '../../../../../studio/src/core/index.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../../../..');
const frozen = JSON.parse(readFileSync(path.join(here, 'input-manifest.json'))).files;
const snapshot = () => frozen.map(row => {
  const bytes = readFileSync(path.join(root, row.path));
  return { path: row.path, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') };
});
const before = snapshot();
if (JSON.stringify(before) !== JSON.stringify(frozen)) throw Error('A frozen input is already stale');
const document = JSON.parse(readFileSync(path.join(here, '../wholeSvg/document.json')));
const original = JSON.stringify(document);
const scene = buildExportScene(document, { widthMm: 180 });
writeFileSync(path.join(here, 'whole.scene.json'), JSON.stringify(scene, null, 2) + '\n');
writeFileSync(path.join(here, 'whole.raw.svg'), renderSvg(scene));
const after = snapshot();
if (JSON.stringify(document) !== original || JSON.stringify(after) !== JSON.stringify(before)) throw Error('Read-only observation mutated an input');
writeFileSync(path.join(here, 'capture-receipt.json'), JSON.stringify({
  schema: 'archcanvas-viewport-export-observation/1', nodeVersion: process.version, executable: process.execPath,
  frozenInputCount: frozen.length, inputDocumentMutated: false, frozenInputMutated: false,
  outputScene: 'whole.scene.json', outputRawSvg: 'whole.raw.svg', modelExecuted: false,
}, null, 2) + '\n');
console.log(JSON.stringify({ capturedScenes: 1, frozenInputCount: frozen.length, inputMutation: false }));
