#!/usr/bin/env node
// Node 24+ loads the formal TypeScript core directly. Never regenerate model facts.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, resolve } from 'node:path';
import { buildScene, renderSvg, validateDocument } from '../studio/src/core/index.ts';

const args = process.argv.slice(2);
const input = args[args.indexOf('--document') + 1];
const output = args[args.indexOf('--output') + 1];
if (!args.includes('--document') || !args.includes('--output') || !input || !output) {
  console.error('Usage: node scripts/export_canvas.mjs --document CANVAS_OR_STORAGE_ENVELOPE.json --output FIGURE.svg');
  process.exit(2);
}
try {
  const payload = JSON.parse(await readFile(resolve(input), 'utf8'));
  const document = validateDocument(payload.document ?? payload);
  const scene = buildScene(document);
  const svg = renderSvg(scene);
  const path = resolve(output);
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, svg, 'utf8');
  const receipt = {
    path, documentId: document.id, revision: document.revision,
    sourceDigest: scene.sourceDigest, irDigest: scene.irDigest,
    svgDigest: createHash('sha256').update(svg).digest('hex'),
    widthMm: scene.pageSpec.widthMm,
    heightMm: scene.pageSpec.widthMm * scene.bounds.height / scene.bounds.width,
    renderer: 'archcanvas-svg/1.0', unresolved: scene.diagnostics,
  };
  await writeFile(`${path}.receipt.json`, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
  console.log(JSON.stringify(receipt, null, 2));
} catch (error) {
  console.error(JSON.stringify({ error: error.message }));
  process.exit(2);
}
