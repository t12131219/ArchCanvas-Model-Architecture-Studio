import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createDocument, buildScene } from '../src/core/index.ts';
import type { Architecture } from '../src/core/types.ts';
import type { AuthoredDraft } from '../src/authoring.ts';
import { removeDraftNode, moveDraftNodes, draftNodeBounds, sourceDraftCatalog } from '../src/authoring.ts';
import { projectSourceEditing } from '../src/sourceEditingProjection.ts';
import { invalidSourceDraftGeometry, prepareSourceRegionRestore, relocateSourceDraftAdditions, sourceDeletedRegions, sourceFrontierDocument, sourceRegionDocument } from '../src/sourceDraftFrontier.ts';
import { sourceStructureEntries, filterSourceStructure } from '../src/sourceStructureLibrary.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
function backend(expression: string, value?: unknown): Promise<any> {
  return new Promise((resolve, reject) => {
    const child = execFile(`${project}.venv/bin/python`, ['-I', '-S', '-B', '-c',
      `import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_python import analyze_source;from archcanvas_authoring.source_import import import_editable_source_draft,rebase_source_frontier,validate_source_draft;v=json.load(sys.stdin);${expression}`, project],
      { maxBuffer: 20_000_000 }, (error, stdout) => error ? reject(error) : resolve(JSON.parse(stdout)));
    child.stdin!.end(JSON.stringify(value ?? null));
  });
}
async function fixture() {
  const architecture = await backend('print(json.dumps(analyze_source(v,"model:Network")))', `from torch import nn
class Network(nn.Module):
 def __init__(self):
  super().__init__()
  self.projection=nn.Linear(4, 4)
  self.activation=nn.ReLU()
 def forward(self,x,flag):
  if flag:
   x=self.projection(x)
   return self.activation(x)
  else:
   return self.projection(x)
`) as Architecture;
  const view = createDocument(architecture), editing = projectSourceEditing(view);
  return (await backend('print(json.dumps(import_editable_source_draft(*v)))', [view, buildScene(view), editing.document, editing.scene])).draft as AuthoredDraft;
}
async function rebase(draft: AuthoredDraft, document = draft.sourceProvenance!.canvas) {
  return (await backend('print(json.dumps(rebase_source_frontier(*v)))', [draft, document, buildScene(document)])).draft as AuthoredDraft;
}

test('source branch deletion and durable recovery restore exact contents and source bindings after collapse and persistence', async () => {
  const original = await fixture(), source = original.sourceProvenance!;
  const branch = source.architecture.nodes.find(node => node.kind === 'SourceBranch' && node.label.startsWith('if '))!;
  const id = Object.entries(source.nodeRefs).find(([, ref]) => ref.nodeId === branch.id)![0];
  assert.ok(original.nodes.find(node => node.id === id)?.presentation?.group, 'source branches start with their contents visible');
  const descendant = original.nodes.find(node => node.presentation?.parentId === id)!;
  descendant.label = 'edited source call';
  const collapsed = await rebase(original, sourceFrontierDocument(original, id, false));
  removeDraftNode(collapsed, id);
  const deleted = await rebase(collapsed);
  assert.ok(sourceDeletedRegions(deleted).some(region => region.canonicalId === branch.id));
  const saved = JSON.parse(JSON.stringify(deleted)) as AuthoredDraft;
  const prepared = prepareSourceRegionRestore(saved, branch.children[0]);
  const restored = await rebase(prepared, sourceRegionDocument(prepared, branch.id));
  assert.equal(restored.nodes.find(node => node.id === descendant.id)?.label, 'edited source call');
  assert.equal(restored.sourceProvenance!.nodeRefs[descendant.id].nodeId, source.nodeRefs[descendant.id].nodeId);
  assert.ok(restored.nodes.find(node => node.id === id)?.presentation?.group);
  assert.ok(!sourceDeletedRegions(restored).some(region => region.canonicalId === branch.id));
  assert.equal((await backend('print(json.dumps(validate_source_draft(v)))', restored)).complete, true);
});

test('source recovery retains independently deleted edges', async () => {
  const original = await fixture();
  const source = original.sourceProvenance!;
  const target = original.nodes.find(node => source.nodeRefs[node.id]?.kind === 'ConditionalRegion')!;
  const removed = original.edges.find(edge => edge.target.nodeId === target.id)!;
  original.edges = original.edges.filter(edge => edge.id !== removed.id);
  const disconnected = await rebase(original);
  assert.ok(disconnected.sourceCache!.removedCanonicalEdgeIds.some(id => source.edgeRefs[removed.id].includes(id)));
  removeDraftNode(disconnected, target.id);
  const deleted = await rebase(disconnected);
  const prepared = prepareSourceRegionRestore(deleted, source.nodeRefs[target.id].nodeId);
  assert.ok(!prepared.edges.some(edge => edge.id === removed.id));
  const restored = await rebase(prepared, sourceRegionDocument(prepared, source.nodeRefs[target.id].nodeId));
  assert.ok(!restored.edges.some(edge => edge.id === removed.id));
});

test('source recovery preserves a newly occupied boundary and all cached custom descendants', async () => {
  const original = await fixture(), source = original.sourceProvenance!;
  const branch = source.architecture.nodes.find(node => node.kind === 'SourceBranch' && node.label.startsWith('if '))!;
  const branchId = Object.entries(source.nodeRefs).find(([, ref]) => ref.nodeId === branch.id)![0];
  const catalog = await backend('from archcanvas_authoring.draft import module_catalog;print(json.dumps(module_catalog()))');
  const identity = catalog.modules.find((module: any) => module.kind === 'Identity');
  original.nodes.push({ id: 'custom-in-branch', kind: 'Identity', label: 'cached user child', parameters: identity.defaults,
    position: { x: 100, y: 100 }, presentation: { width: 164, height: 80, fill: '#ffffff', stroke: '#355247', group: false, parentId: branchId, ports: {} } });
  const region = original.nodes.find(node => source.nodeRefs[node.id]?.kind === 'ConditionalRegion')!;
  const outputEdge = original.edges.find(edge => edge.source.nodeId === region.id)!;
  removeDraftNode(original, region.id);
  assert.ok(!original.nodes.some(node => node.id === 'custom-in-branch'));
  const replacement = { id: 'new-producer', kind: 'Identity', label: 'user producer', parameters: identity.defaults, position: { x: 300, y: 300 } };
  original.nodes.push(replacement);
  original.edges.push({ id: 'user-boundary', source: { nodeId: replacement.id, portId: identity.ports.find((port: any) => port.direction === 'out').id }, target: outputEdge.target });
  const restored = prepareSourceRegionRestore(original, source.nodeRefs[region.id].nodeId, catalog);
  assert.ok(restored.nodes.some(node => node.id === 'custom-in-branch'));
  assert.deepEqual(restored.edges.filter(edge => edge.target.nodeId === outputEdge.target.nodeId && edge.target.portId === outputEdge.target.portId).map(edge => edge.id), ['user-boundary']);
});

test('deleting every source card retains a durable complete source recovery path', async () => {
  const draft = await fixture(), source = draft.sourceProvenance!;
  const root = source.architecture.nodes.find(node => !node.parentId)!;
  const id = Object.entries(source.nodeRefs).find(([, ref]) => ref.nodeId === root.id)![0];
  removeDraftNode(draft, id);
  assert.equal(draft.nodes.length, 0);
  assert.ok(draft.sourceProvenance);
  const saved = JSON.parse(JSON.stringify(draft)) as AuthoredDraft;
  assert.ok(sourceDeletedRegions(saved).some(region => region.canonicalId === root.id));
  const prepared = prepareSourceRegionRestore(saved, root.id);
  const restored = await rebase(prepared, sourceRegionDocument(prepared, root.id));
  assert.ok(restored.nodes.length > 0);
  assert.deepEqual(restored.sourceProvenance!.architecture, source.architecture);
  assert.equal((await backend('print(json.dumps(validate_source_draft(v)))', restored)).complete, true);
});

test('source recovery rejects unknown identities without changing a draft', async () => {
  const draft = await fixture(), before = JSON.stringify(draft);
  assert.throws(() => prepareSourceRegionRestore(draft, 'missing'), /未知源码区域/);
  assert.throws(() => sourceRegionDocument(draft, 'missing'), /未知源码区域/);
  assert.equal(JSON.stringify(draft), before);
});

test('repeated source visibility changes apply a real moved-group delta once and preserve its descendants', async () => {
  let draft = await fixture();
  const fact = draft.sourceProvenance!.architecture.nodes.find(node => node.kind === 'SourceBranch' && node.label.startsWith('if '))!;
  const id = Object.entries(draft.sourceProvenance!.nodeRefs).find(([, ref]) => ref.nodeId === fact.id)![0];
  moveDraftNodes(draft, [id], -4, 4);
  const expected = new Map(draft.nodes.filter(node => node.id === id || node.presentation?.parentId === id).map(node => [node.id, structuredClone(node.position)]));
  for (let iteration = 0; iteration < 2; iteration++) {
    draft = await rebase(draft, sourceFrontierDocument(draft, id, false));
    draft = JSON.parse(JSON.stringify(draft)) as AuthoredDraft;
    draft = await rebase(draft, sourceFrontierDocument(draft, id, true));
    assert.equal(invalidSourceDraftGeometry(draft), false);
    for (const [identity, position] of expected) assert.deepEqual(draft.nodes.find(node => node.id === identity)!.position, position);
  }
});

test('upgrading a compact saved frontier grows styled source containers and relocates connected user additions without overlap', async () => {
  let compact = await fixture();
  const branches = compact.sourceProvenance!.architecture.nodes.filter(node => node.kind === 'SourceBranch');
  for (const branch of branches) {
    const id = Object.entries(compact.sourceProvenance!.nodeRefs).find(([, ref]) => ref.nodeId === branch.id)![0];
    compact = await rebase(compact, sourceFrontierDocument(compact, id, false));
  }
  const rawCatalog = await backend('from archcanvas_authoring.draft import module_catalog;print(json.dumps(module_catalog()))');
  const catalog = sourceDraftCatalog(compact, rawCatalog)!;
  for (const node of compact.nodes) { const box = draftNodeBounds(node, catalog); node.visual = { width: box.width, height: box.height, fill: '#f0f8f2', stroke: '#355247' }; }
  const root = compact.nodes.find(node => !node.presentation?.parentId)!, rootBox = draftNodeBounds(root, catalog);
  const output = compact.nodes.find(node => compact.sourceProvenance!.nodeRefs[node.id]?.kind === 'Output')!;
  const original = compact.edges.find(edge => edge.target.nodeId === output.id)!;
  const identity = rawCatalog.modules.find((module: any) => module.kind === 'Identity');
  compact.edges = compact.edges.filter(edge => edge.id !== original.id);
  compact.nodes.push({ id: 'identity-one', kind: identity.kind, label: 'Identity one', parameters: identity.defaults, position: { x: output.position.x, y: rootBox.y + rootBox.height + 28 } },
    { id: 'identity-two', kind: identity.kind, label: 'Identity two', parameters: identity.defaults, position: { x: output.position.x, y: rootBox.y + rootBox.height + 156 } });
  compact.edges.push({ id: 'source-to-one', source: original.source, target: { nodeId: 'identity-one', portId: 'input' } },
    { id: 'one-to-two', source: { nodeId: 'identity-one', portId: 'output' }, target: { nodeId: 'identity-two', portId: 'input' } },
    { id: 'two-to-output', source: { nodeId: 'identity-two', portId: 'output' }, target: original.target });
  const projection = projectSourceEditing(compact.sourceProvenance!.canvas);
  const grown = await rebase(compact, projection.document), result = relocateSourceDraftAdditions(compact, grown, rawCatalog);
  const resultCatalog = sourceDraftCatalog(result, rawCatalog)!, byId = new Map(result.nodes.map(node => [node.id, node]));
  const ancestor = (id: string, child: string) => {
    let parent = byId.get(child)?.presentation?.parentId;
    while (parent) { if (parent === id) return true; parent = byId.get(parent)?.presentation?.parentId; }
    return false;
  };
  for (const node of result.nodes) {
    const box = draftNodeBounds(node, resultCatalog), parent = node.presentation?.parentId && byId.get(node.presentation.parentId);
    if (parent) {
      const bounds = draftNodeBounds(parent, resultCatalog);
      assert.ok(box.x >= bounds.x && box.y >= bounds.y + 30 && box.x + box.width <= bounds.x + bounds.width + .01 && box.y + box.height <= bounds.y + bounds.height + .01, `${node.label} stays inside its grown owner`);
    }
    for (const other of result.nodes) if (node.id < other.id && !ancestor(node.id, other.id) && !ancestor(other.id, node.id)) {
      const peer = draftNodeBounds(other, resultCatalog);
      assert.ok(!(box.x < peer.x + peer.width && peer.x < box.x + box.width && box.y < peer.y + peer.height && peer.y < box.y + box.height), `${node.label} overlaps ${other.label}`);
    }
  }
  for (const branch of branches) {
    const node = result.nodes.find(node => result.sourceProvenance!.nodeRefs[node.id]?.nodeId === branch.id)!;
    assert.equal(node.presentation!.group, true);
    assert.equal(node.visual!.width, node.presentation!.width);
    assert.equal(node.visual!.height, node.presentation!.height);
    assert.equal(node.visual!.fill, '#f0f8f2');
  }
  assert.equal(result.nodes.find(node => node.id === 'identity-two')!.position.y - result.nodes.find(node => node.id === 'identity-one')!.position.y, 128);
  assert.deepEqual(result.edges, grown.edges);
  // Simulate a previously saved migration that mixed compact card positions
  // and visual dimensions with expanded source presentation dimensions.
  const stale = structuredClone(grown), compactById = new Map(compact.nodes.map(node => [node.id, node]));
  for (const node of stale.nodes) {
    const previous = compactById.get(node.id);
    if (previous && stale.sourceProvenance!.nodeRefs[node.id]) { node.position = structuredClone(previous.position); node.visual = structuredClone(previous.visual); }
  }
  assert.equal(invalidSourceDraftGeometry(stale), true);
  const repairedDocument = sourceFrontierDocument(stale, root.id, true);
  const repaired = relocateSourceDraftAdditions(stale, await rebase(stale, repairedDocument), rawCatalog);
  assert.equal(invalidSourceDraftGeometry(repaired), false);
  // A later no-op reveal and JSON save/reload do not accumulate offsets.
  const persisted = JSON.parse(JSON.stringify(repaired)) as AuthoredDraft;
  const repeated = relocateSourceDraftAdditions(persisted, await rebase(persisted, sourceFrontierDocument(persisted, root.id, true)), rawCatalog);
  assert.deepEqual(repeated.nodes.map(node => node.position), repaired.nodes.map(node => node.position));
  // Expanding a deep interior and returning to this frontier must reverse its
  // exterior displacement. A stale internal output position cannot accumulate
  // another source-relative delta on the independent user component.
  const deep = structuredClone(result), deepRoot = deep.nodes.find(node => node.id === root.id)!;
  deepRoot.presentation!.height += 2000;
  if (deepRoot.visual) deepRoot.visual.height += 2000;
  const deepOutput = deep.nodes.find(node => node.id === output.id)!;
  deepOutput.position.y += 500;
  const deepMoved = relocateSourceDraftAdditions(result, deep, rawCatalog);
  const folded = structuredClone(result);
  for (const node of folded.nodes.filter(node => !folded.sourceProvenance!.nodeRefs[node.id])) node.position = structuredClone(deepMoved.nodes.find(item => item.id === node.id)!.position);
  const returned = relocateSourceDraftAdditions(deepMoved, folded, rawCatalog);
  for (const id of ['identity-one', 'identity-two']) assert.deepEqual(returned.nodes.find(node => node.id === id)!.position, result.nodes.find(node => node.id === id)!.position);
});

test('source library inventories unopened facts and retains nested search and recovery after full deletion', async () => {
  const draft = await fixture(), source = draft.sourceProvenance!;
  const entries = sourceStructureEntries(draft);
  assert.equal(entries.length, source.architecture.nodes.length);
  const branch = entries.find(entry => entry.kind === 'SourceBranch' && entry.label.startsWith('if '))!;
  assert.ok(branch.children.length);
  const match = entries.find(entry => branch.children.includes(entry.id))!;
  const filtered = filterSourceStructure(entries, match.label);
  assert.ok(filtered.has(match.id)); assert.ok(filtered.has(branch.id));
  removeDraftNode(draft, branch.draftId!);
  const deleted = sourceStructureEntries(JSON.parse(JSON.stringify(draft)));
  assert.ok(deleted.find(entry => entry.id === branch.id)!.deleted);
  assert.ok(deleted.find(entry => entry.id === match.id)!.deleted);
  assert.equal(deleted.find(entry => entry.id === match.id)!.draftId, undefined);
});

test('edge deliberately disconnected before node deletion stays disconnected without an intermediate rebase', async () => {
  const draft = await fixture(), source = draft.sourceProvenance!;
  const region = draft.nodes.find(node => source.nodeRefs[node.id]?.kind === 'ConditionalRegion')!;
  const edge = draft.edges.find(edge => edge.target.nodeId === region.id)!;
  draft.edges = draft.edges.filter(item => item.id !== edge.id);
  removeDraftNode(draft, region.id);
  const canonical = source.nodeRefs[region.id].nodeId;
  const prepared = prepareSourceRegionRestore(JSON.parse(JSON.stringify(draft)), canonical);
  const restored = await rebase(prepared, sourceRegionDocument(prepared, canonical));
  assert.ok(!restored.edges.some(item => item.id === edge.id));
});
