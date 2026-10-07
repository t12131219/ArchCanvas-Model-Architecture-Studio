// The trial package uses the authoritative formal core; it never derives a second Scene.
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createDocument, validateDocument, buildExportScene, renderSvg } from '../studio/src/core/index.ts';

const hash = value => createHash('sha256').update(value).digest('hex');
try {
  const [action, input, output] = process.argv.slice(2);
  const payload = JSON.parse(await readFile(input, 'utf8'));
  if (action === 'create') {
    await writeFile(output, `${JSON.stringify(createDocument(payload), null, 2)}\n`);
  } else if (action === 'verify') {
    const document = validateDocument(payload.document);
    const scenes = payload.receipts.map(receipt => {
      const scope = receipt.exportScope;
      if (!scope || !['document', 'detail'].includes(scope.kind)) throw new Error('Unsupported export scope');
      const scene = buildExportScene(document, { widthMm: receipt.widthMm,
        ...(scope.kind === 'detail' ? { nodeId: scope.selectedNodeId } : {}) });
      const sceneSvg = renderSvg(scene), sceneSvgDigest = hash(sceneSvg);
      if (sceneSvgDigest !== receipt.sceneSvgDigest || sceneSvgDigest !== receipt.inputSvgDigest)
        throw new Error('Export Scene digest differs from the exact final CanvasDocument');
      return { sceneSvgDigest, scope: scene.exportScope ?? { kind: 'document' },
        ...(receipt.format === 'svg' ? { sceneSvg } : {}) };
    });
    await writeFile(output, `${JSON.stringify({ documentId: document.id, revision: document.revision, scenes })}\n`);
  } else throw new Error('Expected create or verify');
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
