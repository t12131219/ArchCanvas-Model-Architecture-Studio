import { readFileSync, writeFileSync, readdirSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

// This harness captures product output; the oracle is independent Python geometry.
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../../..');
const tag = process.argv[2] ?? 'attempt-1';
const baseline = await import(pathToFileURL(path.join(here, 'snapshots/baseline/core/index.ts')));
const candidate = await import(pathToFileURL(path.join(here, `snapshots/${tag}/core/index.ts`)));
const inputRoot = path.join(root, 'docs/evidence/m4-visual-next-current/review/fresh-source-core');
const out = path.join(here, tag); mkdirSync(out, { recursive: true });
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const omit = (object, keys) => Object.fromEntries(Object.entries(object).filter(([key]) => !keys.includes(key)));
function semantics(scene) {
  return {
    documentId: scene.documentId, revision: scene.revision, sourceDigest: scene.sourceDigest,
    irDigest: scene.irDigest, nodes: scene.nodes, hiddenEdges: scene.hiddenEdges,
    sourceFacts: scene.sourceFacts, pageSpec: scene.pageSpec, exportScope: scene.exportScope,
    edges: scene.edges.map(e => omit(e, ['path', 'labelX', 'labelY'])),
    legend: scene.legend.map(l => omit(l, ['x', 'y'])),
    edgeLegend: (scene.edgeLegend ?? []).map(l => omit(l, ['x','y','width','height'])),
  };
}
function metadata(svg) {
  const encoded = svg.match(/<metadata>([\s\S]*?)<\/metadata>/)?.[1];
  if (!encoded) return null;
  return JSON.parse(encoded.replaceAll('&quot;', '"').replaceAll('&apos;', "'").replaceAll('&lt;', '<').replaceAll('&gt;', '>').replaceAll('&amp;', '&'));
}
const records = [];
for (const name of readdirSync(inputRoot).filter(n => n.endsWith('.canvas.json')).sort()) {
  const bytes = readFileSync(path.join(inputRoot, name)), document = JSON.parse(bytes.toString());
  const original = JSON.stringify(document), sourceHash = digest(bytes);
  const full = baseline.buildScene(document);
  const scopes = [undefined, ...full.nodes.filter(n => n.expanded && n.expandable).map(n => n.id)];
  for (const [index, nodeId] of scopes.entries()) {
    const scope = nodeId ? { nodeId } : {};
    const old = baseline.buildExportScene(document, scope);
    const next = candidate.buildExportScene(document, scope);
    const repeated = candidate.buildExportScene(document, scope);
    const stem = name.slice(0, -12) + (index ? `-detail${index}` : '-overview');
    const oldSvg = baseline.renderSvg(old), nextSvg = candidate.renderSvg(next);
    writeFileSync(path.join(out, `${stem}.old.scene.json`), JSON.stringify(old, null, 2)+'\n');
    writeFileSync(path.join(out, `${stem}.new.scene.json`), JSON.stringify(next, null, 2)+'\n');
    writeFileSync(path.join(out, `${stem}.new.svg`), nextSvg);
    const oldMeta=metadata(oldSvg), newMeta=metadata(nextSvg);
    records.push({ stem, input: name, nodeId: nodeId ?? null, sourceHash,
      documentUnchanged: JSON.stringify(document) === original && digest(readFileSync(path.join(inputRoot,name))) === sourceHash,
      semanticProjectionUnchanged: JSON.stringify(semantics(old)) === JSON.stringify(semantics(next)),
      renderedBindingsUnchanged: JSON.stringify(oldMeta?.renderedBindings) === JSON.stringify(newMeta?.renderedBindings),
      deterministic: JSON.stringify(next) === JSON.stringify(repeated),
      oldEdgeCount: old.edges.length, newEdgeCount: next.edges.length, guideCount: (next.captionGuides??[]).length,
      metadataGuides: newMeta?.presentationDecorations ?? [],
      outputSha256: { scene: digest(JSON.stringify(next,null,2)+'\n'), svg: digest(nextSvg) } });
  }
}
const report = { schema: 'archcanvas-independent-output-capture/1', tag,
  nodeRuntime: { executable: process.execPath, version: process.version },
  inputs: new Set(records.map(r=>r.input)).size, captures: records.length,
  failedInvariants: records.filter(r=>!r.documentUnchanged||!r.semanticProjectionUnchanged||!r.renderedBindingsUnchanged||!r.deterministic), records };
writeFileSync(path.join(out, 'capture.json'), JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({tag,inputs:report.inputs,captures:report.captures,failedInvariants:report.failedInvariants.map(r=>r.stem)}));
