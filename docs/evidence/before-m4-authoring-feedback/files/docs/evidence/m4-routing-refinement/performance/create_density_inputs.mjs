import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const directory = dirname(fileURLToPath(import.meta.url));
const core = await import(pathToFileURL(join(directory, 'baseline-core/index.ts')).href);
const hash = value => createHash('sha256').update(value).digest('hex');
const records = [];
for (const count of [4, 8, 16, 32]) {
  const id = `synthetic-density-${count}`;
  const node = (id, parentId, children = []) => ({
    id, label: id, kind: children.length ? 'SyntheticContainer' : 'SyntheticIdentity',
    category: children.length ? 'container' : 'operator', parentId, children,
    ports: [{ id: 'in', name: 'input', direction: 'in', role: 'data', ordinal: 0 },
      { id: 'out', name: 'output', direction: 'out', role: 'data', ordinal: 0 }],
    parameters: {}, evidence: 'contract',
  });
  const children = Array.from({ length: count }, (_, i) => `source-${i}`).concat(Array.from({ length: count }, (_, i) => `target-${i}`));
  const architecture = { schemaVersion: 1, id, label: id,
    sourceDigest: hash(id), irDigest: hash(`${id}:geometry-only`), entry: 'synthetic:GeometryOnly', sources: [],
    diagnostics: [{ level: 'info', message: 'Artificial geometry/CPU fixture, not model accuracy or real-user evidence.' }],
    nodes: [node('root', undefined, children), ...children.map(child => node(child, 'root'))],
    edges: Array.from({ length: count * count }, (_, index) => {
      const source = Math.floor(index / count), target = index % count;
      return { id: `edge-${source}-${target}`, source: { nodeId: `source-${source}`, portId: 'out' },
        target: { nodeId: `target-${target}`, portId: 'in' }, tensorId: `tensor-${source}-${target}`, role: 'data' };
    }),
  };
  const document = core.createDocument(architecture);
  for (let index = 0; index < count; index++) {
    document.layout[`source-${index}`] = { x: 40 + index * 240, y: 60 };
    document.layout[`target-${index}`] = { x: 40 + index * 240, y: 760 };
  }
  core.validateDocument(document);
  const scene = core.buildScene(document);
  assert.equal(scene.nodes.length, 2 * count + 1);
  assert.equal(scene.edges.length, count * count);
  const path = join(directory, `inputs/${id}.canvas.json`);
  assert.equal(existsSync(path), false, 'refuse overwrite of frozen artificial input');
  const bytes = JSON.stringify(document, null, 2) + '\n';
  writeFileSync(path, bytes);
  records.push({ id, kind: 'artificial-adversarial-dense-geometry', path: `inputs/${id}.canvas.json`,
    sha256: hash(bytes), sourceCount: count, targetCount: count, nodes: scene.nodes.length, projectedEdges: scene.edges.length });
}
writeFileSync(join(directory, 'density-inputs.json'), JSON.stringify({ schemaVersion: 1, generatorSha256: hash(readFileSync(fileURLToPath(import.meta.url))),
  inputFiles: records, limitation: 'Artificial dense geometry, no executed model or model semantics claim.' }, null, 2) + '\n');
console.log(JSON.stringify(records, null, 2));
