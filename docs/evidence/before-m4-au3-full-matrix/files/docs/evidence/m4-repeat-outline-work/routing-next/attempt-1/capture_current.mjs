import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { buildScene, renderSvg } from '../../../../../studio/src/core/index.ts';

const base = new URL('./', import.meta.url);
const input = new URL('../../../browser-visual-matrix-chs-current/captures/transformer-level3-paper-180/canvas.json', import.meta.url);
const bytes = readFileSync(input), document = JSON.parse(bytes), original = JSON.stringify(document);
const scene = buildScene(document), svg = renderSvg(scene);
if (JSON.stringify(document) !== original) throw new Error('Scene projection changed input');
mkdirSync(new URL('current/', base), { recursive: true });
writeFileSync(new URL('current/transformer-level3-paper-180.scene.json', base), JSON.stringify(scene, null, 2) + '\n');
writeFileSync(new URL('current/transformer-level3-paper-180.svg', base), svg);
const hash = value => createHash('sha256').update(value).digest('hex');
const prior = readFileSync(new URL('../../oracle/after/transformer-level3-paper-180.scene.json', import.meta.url));
const report = { scope: 'Read-only current formal projection, no build/browser/model execution', input: { path: input.pathname, bytes: bytes.length, sha256: hash(bytes) }, inputUnchanged: readFileSync(input).equals(bytes),
  currentSceneNodes: scene.nodes.length, currentSceneEdges: scene.edges.length, sameAsIndependentRepeatAfterScene: JSON.stringify(JSON.parse(prior)) === JSON.stringify(scene),
  currentSvg: { bytes: Buffer.byteLength(svg), sha256: hash(svg) } };
writeFileSync(new URL('current/projection-receipt.json', base), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report));
