#!/usr/bin/env node
// Node 24+ loads the formal TypeScript core directly. Never regenerate model facts.
import { readFile, writeFile, mkdir, access } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { dirname, resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildScene, renderSvg, validateDocument } from '../studio/src/core/index.ts';

const args = process.argv.slice(2);
const usage = 'Usage: node scripts/export_canvas.mjs --document CANVAS_OR_STORAGE_ENVELOPE.json --output FIGURE.svg|pdf|png [--format svg|pdf|png --dpi 300 --python .venv/bin/python]';
try {
  const options = {};
  for (let index = 0; index < args.length; index += 2) {
    const name = args[index];
    if (!['--document', '--output', '--format', '--dpi', '--python'].includes(name) || !args[index + 1] || args[index + 1].startsWith('--')) throw new Error(usage);
    if (options[name] !== undefined) throw new Error(`Duplicate option ${name}`);
    options[name] = args[index + 1];
  }
  const input = options['--document'], output = options['--output'];
  if (!input || !output) throw new Error(usage);
  const format = options['--format'] ?? (extname(output).slice(1).toLowerCase() || 'svg');
  if (!['svg', 'pdf', 'png'].includes(format)) throw new Error('Format must be svg, pdf or png');
  const dpi = Number(options['--dpi'] ?? '300');
  if (!Number.isInteger(dpi) || dpi < 72 || dpi > 1200) throw new Error('DPI must be an integer in 72–1200');
  const payload = JSON.parse(await readFile(resolve(input), 'utf8'));
  const document = validateDocument(payload.document ?? payload);
  const scene = buildScene(document);
  const svg = renderSvg(scene);
  const project = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  let python = options['--python'];
  if (!python) {
    const localPython = resolve(project, '.venv', 'bin', 'python');
    try { await access(localPython); python = localPython; } catch { python = 'python3'; }
  }
  // -I excludes PYTHONPATH/cwd and user site injection. Add only the formal
  // source tree; dependency loading is from the selected interpreter's site.
  const bootstrap = `import runpy,sys; sys.path.insert(0, ${JSON.stringify(resolve(project, 'src'))}); sys.argv[0]='archcanvas_publication'; runpy.run_module('archcanvas_publication', run_name='__main__')`;
  const converted = await new Promise((resolveConversion, reject) => {
    const child = spawn(python, ['-I', '-B', '-c', bootstrap, '--format', format, '--width-mm', String(scene.pageSpec.widthMm), '--dpi', String(dpi)], { cwd: project, timeout: 60_000, windowsHide: true });
    const outputChunks = [], errorChunks = []; let size = 0;
    child.stdout.on('data', chunk => { size += chunk.length; if (size > 64_000_000) { child.kill(); reject(new Error('Converted artifact exceeds the 64 MB output budget')); } else outputChunks.push(chunk); });
    child.stderr.on('data', chunk => { if (errorChunks.reduce((n, item) => n + item.length, 0) < 100_000) errorChunks.push(chunk); });
    child.on('error', reject);
    child.on('close', (status, signal) => { const stderr = Buffer.concat(errorChunks).toString(); if (status !== 0) reject(new Error(stderr.trim() || `Converter exited ${status ?? signal}`)); else resolveConversion({ stdout: Buffer.concat(outputChunks), stderr }); });
    child.stdin.on('error', reject);
    child.stdin.end(svg);
  });
  const conversionReceipt = JSON.parse(converted.stderr.trim());
  const path = resolve(output);
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, converted.stdout);
  const receipt = {
    ...conversionReceipt,
    path, documentId: document.id, revision: document.revision,
    sourceDigest: scene.sourceDigest, irDigest: scene.irDigest,
    sceneSvgDigest: createHash('sha256').update(svg).digest('hex'),
    widthMm: scene.pageSpec.widthMm,
    heightMm: conversionReceipt.heightMm,
    sceneHeightMm: scene.pageSpec.widthMm * scene.bounds.height / scene.bounds.width,
    renderer: 'archcanvas-svg/1.0', unresolved: scene.diagnostics,
  };
  await writeFile(`${path}.receipt.json`, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8');
  console.log(JSON.stringify(receipt, null, 2));
} catch (error) {
  console.error(JSON.stringify({ error: error.message }));
  process.exit(2);
}
