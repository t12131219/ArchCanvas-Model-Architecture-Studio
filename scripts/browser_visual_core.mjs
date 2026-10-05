// Produce independent expected DOM/publication markup from saved Canvas facts.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { buildScene, renderSvg, validateDocument } from '../studio/src/core/index.ts';

try {
  const [input, directory] = process.argv.slice(2);
  const records = JSON.parse(await readFile(input, 'utf8'));
  await mkdir(directory, { recursive: true });
  const results = [];
  for (let index = 0; index < records.length; index++) {
    const document = validateDocument(records[index].document);
    const scene = buildScene(document);
    await writeFile(join(directory, `${index}.interactive.svg`), renderSvg(scene, { interactive: true }));
    await writeFile(join(directory, `${index}.publication.svg`), renderSvg(scene));
    results.push({ documentId: document.id, revision: document.revision, sourceDigest: scene.sourceDigest,
      irDigest: scene.irDigest, pageSpec: scene.pageSpec, visibleNodes: scene.nodes.length,
      expandedIds: document.expandedIds, bounds: scene.bounds, diagnostics: scene.diagnostics });
  }
  await writeFile(join(directory, 'facts.json'), JSON.stringify(results));
} catch (error) {
  console.error(error.message);
  process.exit(1);
}
