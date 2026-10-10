import test from 'node:test';
import assert from 'node:assert/strict';
import { canvasSavePayload } from '../src/canvasPersistence.ts';
import { createDocument, createHistory } from '../src/core/index.ts';
import { readFileSync } from 'node:fs';
const a = JSON.parse(readFileSync(new URL('../../docs/evidence/browser-visual-matrix-boundary-final/captures/mlp-level1-paper-180/canvas.json', import.meta.url),'utf8')).architecture;
test('canvas save deduplicates source facts without changing current/history or hiding a foreign binding', () => {
  const document=createDocument(a), history=createHistory(document), before=JSON.stringify(history);
  history.past=[structuredClone(document),structuredClone(document)]; history.past[1].architecture.irDigest='foreign';
  const payload=canvasSavePayload(document,4,history);
  assert.deepEqual(payload.history?.document.architecture,{archcanvasSharedArchitecture:1});
  assert.deepEqual(payload.history?.past[0].architecture,{archcanvasSharedArchitecture:1});
  assert.equal((payload.history?.past[1].architecture as typeof a).irDigest,'foreign');
  assert.equal(JSON.stringify(createHistory(document)),before);
  assert.equal(document.architecture.irDigest,a.irDigest);
});
