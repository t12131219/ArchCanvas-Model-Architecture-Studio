// Product functions supply observations only; acceptance uses its independent
// frozen public paths, SVG parser and geometry oracle for expectations.
import { readdirSync, readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildScene, buildExportScene, renderSvg } from '../../../studio/src/core/index.ts';
import type { CanvasDocument } from '../../../studio/src/core/types.ts';

const work = dirname(fileURLToPath(import.meta.url)), root = resolve(work, '../../..');
const fingerprint = (path: string) => {
  const bytes = readFileSync(path);
  return { path: path.startsWith(root + '/') ? path.slice(root.length + 1) : path,
    bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') };
};
const browser = join(work, 'browser-after-union'), output = join(work, 'core-after-union');
const cases = readdirSync(browser).filter(name => /^cnn-level[012]-(paper|monochrome)-(85|180)$/.test(name)).sort();
if (cases.length !== 12) throw new Error('Require all 12 actual browser cases');
mkdirSync(output);
const inputs = cases.map(name => join(browser, name, 'document.json'));
const before = inputs.map(fingerprint), records = [];
for (const name of cases) {
  const input = join(browser, name, 'document.json');
  const document = JSON.parse(readFileSync(input, 'utf8')) as CanvasDocument;
  const serialized = JSON.stringify(document), scene = buildScene(document), exported = buildExportScene(document);
  const svg = renderSvg(exported), canvasSvg = renderSvg(scene);
  if (svg !== canvasSvg || JSON.stringify(document) !== serialized) throw new Error(`Canvas/export disagreement: ${name}`);
  const directory = join(output, name); mkdirSync(directory);
  for (const [file, body] of [['scene.json', JSON.stringify(scene, null, 2) + '\n'],
    ['export.scene.json', JSON.stringify(exported, null, 2) + '\n'],
    ['publication.svg', svg], ['interactive.svg', renderSvg(scene, { interactive: true })]]) {
    writeFileSync(join(directory, file), body, { flag: 'wx' });
  }
  records.push({ caseId: name, input: fingerprint(input),
    files: ['scene.json', 'export.scene.json', 'publication.svg', 'interactive.svg'].map(file => fingerprint(join(directory, file))) });
}
const after = inputs.map(fingerprint);
if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Input bytes changed');
writeFileSync(join(output, 'receipt.json'), JSON.stringify({
  protocol: 'archcanvas-collapsed-residual-current-core-observation/1', records,
  inputsBefore: before, inputsAfter: after, inputBytesUnchanged: true,
  scope: 'Trusted formal renderer observations only. No model execution or independent acceptance implied.',
}, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ caseCount: records.length, receipt: fingerprint(join(output, 'receipt.json')) }));
