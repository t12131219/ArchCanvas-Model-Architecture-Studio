import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { applyVisualBatch, buildExportScene, createDocument, renderSvg, validateDocument } from '../studio/src/core/index.ts';

const [action, input, output] = process.argv.slice(2);
const payload = JSON.parse(await readFile(input, 'utf8'));
await mkdir(output, { recursive: true });
if (action === 'create') {
  const architecture = payload;
  const operations = architecture.nodes.filter(node => node.parentId && node.children.length)
    .map(node => ({ type: 'expand', id: node.id, expanded: true }));
  const calls = architecture.nodes.filter(node => node.instanceId && architecture.nodes.some(peer => peer.id !== node.id && peer.instanceId === node.instanceId));
  const selected = calls[0] ?? architecture.nodes.find(node => node.evidence === 'opaque');
  if (selected) operations.push({ type: 'alias', id: selected.id, label: 'Reviewed source object' },
    { type: 'nodeStyle', id: selected.id, style: { fill: '#cddfda' } }, { type: 'pin', ids: [selected.id], pinned: true });
  const document = applyVisualBatch(createDocument(architecture), operations);
  await writeFile(resolve(output, 'canvas.json'), `${JSON.stringify(document, null, 2)}\n`);
} else if (action === 'render') {
  const document = validateDocument(payload.document ?? payload);
  const scene = buildExportScene(document);
  await writeFile(resolve(output, 'scene.json'), `${JSON.stringify(scene, null, 2)}\n`);
  await writeFile(resolve(output, 'figure.raw.svg'), renderSvg(scene));
} else throw new Error('Expected create or render');
