// Static construction only; no model execution or publication conversion.
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { buildExportScene, renderSvg } from '../../../../../studio/src/core/index.ts';

const out = dirname(fileURLToPath(import.meta.url));
const root = resolve(out, '../../../../..');
const browser = resolve(root, 'docs/evidence/m4-move-recovery-presets-browser/final-ChS0wIgb');
const input = resolve(browser, 'movement-final-envelope.json');
const rawInput = await readFile(input);
const envelope = JSON.parse(rawInput);
const svg = renderSvg(buildExportScene(envelope.document));
const receiptPath = resolve(browser, 'movement-final-export/figure.svg.receipt.json');
const receiptBytes = await readFile(receiptPath);
const receipt = JSON.parse(receiptBytes);
const digest = value => createHash('sha256').update(value).digest('hex');
const publicBytes = await readFile(resolve(browser, 'movement-final-saved.public.json'));
const publicSvg = JSON.parse(publicBytes).svg;
const record = {
  scope: 'Static renderSvg(buildExportScene(savedDocument)) reconstruction only; no model execution or converter export.',
  documentRevision: envelope.document.revision,
  inputEnvelopeSha256: digest(rawInput),
  originalReceiptSha256: digest(receiptBytes),
  candidateSvgSha256: digest(svg),
  receiptInputSvgDigest: receipt.inputSvgDigest,
  receiptSceneSvgDigest: receipt.sceneSvgDigest,
  candidateMatchesReceiptInput: digest(svg) === receipt.inputSvgDigest,
  candidateMatchesReceiptScene: digest(svg) === receipt.sceneSvgDigest,
  publicSvgSha256: digest(publicSvg),
  candidateEqualsPublicBytes: svg === publicSvg,
  candidateFilename: 'reconstructed-export-input.svg',
  limitation: 'Input reconstruction establishes the export serialization source. It does not establish whole public SVG equality or aesthetics; repeat-label position differences remain explicit.',
};
await writeFile(resolve(out, 'reconstructed-export-input.svg'), svg, { flag: 'wx' });
await writeFile(resolve(out, 'export-input-reconstruction.json'), JSON.stringify(record, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify(record, null, 2));
if (!record.candidateMatchesReceiptInput || !record.candidateMatchesReceiptScene) process.exitCode = 1;
