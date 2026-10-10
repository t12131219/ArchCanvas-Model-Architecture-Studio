import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createDocument, buildScene } from '../../../studio/src/core/index.ts';
import { renderSvg } from '../../../studio/src/core/svg.ts';
import { projectSourceEditing } from '../../../studio/src/sourceEditingProjection.ts';
import { draftSourceRelations } from '../../../studio/src/draftSourceRelations.ts';
import { draftRoutes, sourceDraftCatalog } from '../../../studio/src/authoring.ts';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const directory = fileURLToPath(new URL('./', import.meta.url));
const architecture = JSON.parse(fs.readFileSync(`${directory}patchtst-final-analysis.json`, 'utf8'));
console.log('analyzed', architecture.nodes.length);
const view = createDocument(architecture), compact = buildScene(view);
console.log('compact', compact.nodes.length);
const start = performance.now(), editing = projectSourceEditing(view);
const sceneSeconds = (performance.now() - start) / 1000;
console.log('expanded', editing.scene.nodes.length, sceneSeconds);
fs.writeFileSync(`${directory}patchtst-final-import-payload.json`, JSON.stringify([view, compact, editing.document, editing.scene]));
const imported = JSON.parse(execFileSync(`${root}.venv/bin/python`, ['-I', '-S', '-B', '-c',
  'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring.source_import import import_editable_source_draft;print(json.dumps(import_editable_source_draft(*json.load(open(sys.argv[2])))))', root, `${directory}patchtst-final-import-payload.json`],
{ maxBuffer: 30_000_000, timeout: 45000 }));
console.log('imported', imported.draft.nodes.length);
const catalog = sourceDraftCatalog(imported.draft, { schemaVersion: 1, mode: 'authored-draft', modules: [], unsupported: [] });
const editorStart = performance.now(), tensorRoutes = draftRoutes(imported.draft, catalog);
console.log('draft tensors routed', tensorRoutes.routes.length, (performance.now() - editorStart) / 1000);
const sourceRoutes = draftSourceRelations(imported.draft, catalog);
const summary = {
  nodes: architecture.nodes.length,
  tensorEdges: architecture.edges.length,
  sourceRelations: architecture.sourceRelations.length,
  sourceDigest: architecture.sourceDigest,
  irDigest: architecture.irDigest,
  sceneSeconds,
  blockedSourceRoutes: editing.scene.diagnostics.filter(d => d.code === 'layout-route-blocked' && d.message.startsWith('Source dependency')).length,
  draftNodes: imported.draft.nodes.length,
  draftTensorRoutes: tensorRoutes.routes.length,
  draftSourceRelations: sourceRoutes.relations.length,
  blockedDraftTensorRoutes: tensorRoutes.routes.filter(r => r.blockedBy.length).length,
  blockedDraftSourceRoutes: sourceRoutes.diagnostics.length,
  draftRoutingSeconds: (performance.now() - editorStart) / 1000,
  sourceStructureTruncated: architecture.diagnostics.filter(d => /budget|truncat/i.test(d.message)),
};
fs.writeFileSync(`${directory}patchtst-final-expanded-document.json`, JSON.stringify(editing.document));
fs.writeFileSync(`${directory}patchtst-final-expanded.svg`, renderSvg(editing.scene));
fs.writeFileSync(`${directory}patchtst-final-summary.json`, JSON.stringify(summary, null, 2));
if (summary.sourceRelations !== 119 || summary.blockedSourceRoutes || summary.blockedDraftSourceRoutes || summary.draftTensorRoutes !== imported.draft.edges.length) throw new Error(JSON.stringify(summary));
console.log(JSON.stringify(summary, null, 2));
