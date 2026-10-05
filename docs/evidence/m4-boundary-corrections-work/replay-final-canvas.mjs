// Read-only formal-core reconstruction from the actual saved browser envelope.
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { validateDocument, buildScene, renderSvg } from '../../../studio/src/core/index.ts';

const [input, destination] = process.argv.slice(2);
const envelope = JSON.parse(await readFile(input, 'utf8'));
const document = validateDocument(envelope.document);
const scene = buildScene(document);
await writeFile(resolve(destination, 'final-canvas-replayed-scene.json'), `${JSON.stringify(scene, null, 2)}\n`, { flag: 'wx' });
await writeFile(resolve(destination, 'final-canvas-replayed-interactive.svg'), renderSvg(scene, { interactive: true }), { flag: 'wx' });
process.stdout.write(`${JSON.stringify({ passed: true, documentId: document.id, visualRevision: document.revision,
  storageRevision: envelope.revision, bounds: scene.bounds, sceneNodes: scene.nodes.length, sceneEdges: scene.edges.length })}\n`);
