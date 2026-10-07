// Production APIs are used only to capture the current observation, not as the independent oracle.
import { readFileSync, writeFileSync, statSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { buildExportScene, renderSvg } from '../../../../studio/src/core/index.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../../..');
const checksFile = path.resolve(here, '../checks-final-attempt-2/receipt.json');
const checks = JSON.parse(readFileSync(checksFile));
const digest = file => createHash('sha256').update(readFileSync(file)).digest('hex');
const files = [checksFile, ...[...checks.inputs, ...checks.build, ...checks.publicationInputs].map(row => path.join(root, row.path)),
  ...['saved-rev31-envelope.json', 'ui-export-identities.json',
    'wholePdf/document.json', 'wholePdf/figure.pdf', 'wholePdf/figure.pdf.receipt.json',
    'wholeSvg/document.json', 'wholeSvg/figure.svg', 'wholeSvg/figure.svg.receipt.json',
    'detailSvg/document.json', 'detailSvg/figure.svg', 'detailSvg/figure.svg.receipt.json'].map(file => path.join(here, file)),
  ...['34-final-saved-reopened.json', '34-final-saved-reopened.svg', '35-whole-180-pdf-ui.json',
    '36-whole-180-svg-ui.json', '37-detail-180-svg-ui.json'].map(file => path.resolve(here, '../browser', file))];
const snapshot = () => files.map(file => ({ path: file, bytes: statSync(file).size, sha256: digest(file) }));
const before = snapshot();
const document = JSON.parse(readFileSync(path.join(here, 'wholeSvg/document.json')));
const beforeJson = JSON.stringify(document);
for (const [label, options] of [['whole', { widthMm: 180 }], ['detail', { widthMm: 180, nodeId: 'call:instance:model.Transformer' }]]) {
  const scene = buildExportScene(document, options);
  if (JSON.stringify(document) !== beforeJson) throw Error('Capture mutated document');
  writeFileSync(path.join(here, label + '.scene.json'), JSON.stringify(scene, null, 2) + '\n');
  writeFileSync(path.join(here, label + '.raw.svg'), renderSvg(scene));
}
const after = snapshot();
if (JSON.stringify(before) !== JSON.stringify(after)) throw Error('Capture changed a frozen input');
writeFileSync(path.join(here, 'capture-receipt.json'), JSON.stringify({ schema: 'archcanvas-readonly-scene-capture/1',
  runtime: process.execPath, nodeVersion: process.version, inputDocumentMutation: false, frozenInputMutation: false,
  inputs: before, inputsAfter: after, sceneFiles: ['whole.scene.json', 'whole.raw.svg', 'detail.scene.json', 'detail.raw.svg'],
  modelExecution: false }, null, 2) + '\n');
console.log(JSON.stringify({ captured: 2, inputDocumentMutation: false, frozenInputs: before.length, frozenInputMutation: false }));
