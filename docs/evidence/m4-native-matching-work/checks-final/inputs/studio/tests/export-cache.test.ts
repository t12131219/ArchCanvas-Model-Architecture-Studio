import test from 'node:test';
import assert from 'node:assert/strict';
import type { CanvasDocument } from '../src/core/types.ts';
import type { ExportArtifact } from '../src/api.ts';
import { readExportCache, writeExportCache } from '../src/exportCache.ts';

const document = { id: 'canvas', revision: 4, architecture: { sourceDigest: 'source', irDigest: 'ir' }, pageSpec: { widthMm: 180 } } as CanvasDocument;
const artifact: ExportArtifact = { id: 'export', format: 'svg', url: '/api/exports/export/figure.svg', receiptUrl: '/api/exports/export/receipt',
  receipt: { documentId: 'canvas', revision: 4, sourceDigest: 'source', irDigest: 'ir', widthMm: 180, dpi: 300, exportScope: { kind: 'document' } } };
const svg = '<svg><text><tspan>skip</tspan><tspan>path.</tspan></text></svg>';

test('renderer changes invalidate an old export even when canvas revision and source digests match', () => {
  const legacy = JSON.stringify(artifact);
  assert.equal(readExportCache(legacy, document, svg), null);
  const oldRenderer = '<svg><text><tspan>skip p</tspan><tspan>ath.</tspan></text></svg>';
  assert.equal(readExportCache(writeExportCache(artifact, oldRenderer), document, svg), null);
  assert.deepEqual(readExportCache(writeExportCache(artifact, svg), document, svg), artifact);
  for (const raw of [null, '', 'broken', 'null', '{}', '[]']) assert.equal(readExportCache(raw, document, svg), null);
});

test('a restored artifact must describe the default document, width, revision, source and PNG resolution', () => {
  for (const receipt of [{ documentId: 'other' }, { revision: 3 }, { sourceDigest: 'changed' }, { irDigest: 'changed' }, { widthMm: 86 }, { exportScope: { kind: 'detail', selectedNodeId: 'block' } }]) {
    assert.equal(readExportCache(writeExportCache({ ...artifact, receipt: { ...artifact.receipt, ...receipt } }, svg), document, svg), null);
  }
  const png = { ...artifact, format: 'png' };
  assert.deepEqual(readExportCache(writeExportCache(png, svg), document, svg), png);
  assert.equal(readExportCache(writeExportCache({ ...png, receipt: { ...png.receipt, dpi: 600 } }, svg), document, svg), null);
  assert.equal(readExportCache(writeExportCache({ ...artifact, format: 'html' }, svg), document, svg), null);
});
