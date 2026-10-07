import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { buildScene } from '../../../../../studio/src/core/scene.ts';
import { buildExportScene } from '../../../../../studio/src/core/exportScene.ts';
import { renderSvg } from '../../../../../studio/src/core/svg.ts';
import type { CanvasDocument } from '../../../../../studio/src/core/types.ts';

// Read-only deterministic replay from captured envelopes; not a geometry oracle.
const base = resolve('docs/evidence/m4-repeat-outline-work');
const destination = resolve(base, 'acceptance/browser-attempt-1/replay');
mkdirSync(destination, { recursive: true });
for (const id of ['transformer-l0', 'cnn-l0', 'mlp-l0', 'transformer-encoder-detail']) {
  const envelope = JSON.parse(readFileSync(resolve(base, 'browser/attempt-1', id, 'saved-envelope.json'), 'utf8'));
  const document: CanvasDocument = envelope.document;
  const whole = buildScene(document);
  const exported = buildExportScene(document, id === 'transformer-encoder-detail'
    ? { nodeId: 'repeat:instance:model.Transformer.encoder', widthMm: 180 } : { widthMm: 180 });
  for (const [suffix, value] of Object.entries({
    'whole-interactive.svg': renderSvg(whole, { interactive: true }),
    'whole-static.svg': renderSvg(whole),
    'export-static.svg': renderSvg(exported),
    'whole-scene.json': JSON.stringify(whole, null, 2) + '\n',
    'export-scene.json': JSON.stringify(exported, null, 2) + '\n',
  })) writeFileSync(resolve(destination, `${id}.${suffix}`), value, { flag: 'wx' });
  console.log(JSON.stringify({ id, documentId: document.id, revision: document.revision,
    nodes: whole.nodes.length, routes: whole.edges.length,
    exportNodes: exported.nodes.length, exportRoutes: exported.edges.length }));
}
