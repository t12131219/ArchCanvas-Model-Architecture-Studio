import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mkdir, writeFile } from 'node:fs/promises';
import { addDraftNode, blankDraft, changeDraft, connectDraft, draftHistory, draftRoutes, parseDraftCache, removeDraftNode, travelDraft } from '../src/authoring.ts';
import type { AuthoredDraft, DraftCatalog, DraftModule, DraftValue } from '../src/authoring.ts';
import { draftPresets, insertDraftPreset } from '../src/authoringPresets.ts';
import { buildScene, createDocument } from '../src/core/index.ts';
import type { Architecture, CanvasDocument } from '../src/core/types.ts';
import { projectSourceEditing } from '../src/sourceEditingProjection.ts';
import { createGeneratedCanvas } from '../src/generatedCanvas.ts';
import { readDraftValidation } from '../src/draftValidation.ts';
import type { CustomModuleDefinition } from '../src/customModules.ts';
import type { GeneratedDraft, ImportedSourceDraft } from '../src/api.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
const evidence = `${project}docs/evidence/rebuild-all-presets-20261010`;
function backend(expression: string, value: unknown = null): Promise<any> {
  return new Promise((resolve, reject) => {
    const child = execFile(`${project}.venv/bin/python`, ['-I', '-S', '-B', '-c',
      `import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from pathlib import Path;from archcanvas_python import analyze_project;from archcanvas_authoring import generate_model,validate_draft,module_catalog;from archcanvas_authoring.source_import import import_editable_source_draft;from archcanvas_authoring.custom_modules import preview_custom_module;v=json.load(sys.stdin);${expression}`, project],
      { maxBuffer: 24_000_000 }, (error, stdout, stderr) => {
        if (error) reject(new Error(stderr || String(error))); else try { resolve(JSON.parse(stdout)); } catch (error) { reject(error); }
      });
    child.stdin!.end(JSON.stringify(value));
  });
}
const catalog = await backend('print(json.dumps(module_catalog()))') as DraftCatalog;
// Explicit test declarations, not runtime observations. All operation/binding
// expectations come from each fixture's own static source graph, not its name.
const cases = [
  { id: 'transformer', entry: 'model:Transformer', shapes: [[2, 6], [2, 4], [6, 6], [4, 4], [4, 6]], dtypes: ['int64', 'int64', 'bool', 'bool', 'bool'] },
  { id: 'mlp', entry: 'model:MLP', shapes: [[2, 16]] },
  { id: 'residual_cnn', entry: 'model:ResidualCNN', shapes: [[2, 3, 32, 32]] },
  { id: 'holdout_vit', entry: 'model:PatchVisionEncoder', shapes: [[2, 3, 32, 32]] },
  { id: 'stress_300', entry: 'model:DenseStress300', shapes: [[2, 16]] },
  { id: 'rebind', entry: 'model:RebindDemo', shapes: [[2, 16]], unused: true },
  { id: 'multi_input', entry: 'model:MultiInputAttention', shapes: [[2, 3, 8], [2, 5, 8], [2, 5, 8], [2, 5]], dtypes: ['float32', 'float32', 'float32', 'bool'], unused: true },
];

function deleteOneByOne(original: AuthoredDraft) {
  let history = draftHistory(original);
  const leaves = original.nodes.filter(node => !node.presentation?.group).map(node => node.id);
  for (const id of leaves) history = changeDraft(history, draft => removeDraftNode(draft, id));
  assert.equal(history.draft.nodes.length, 0, 'last leaf deletion must also remove empty source containers');
  assert.equal(history.draft.edges.length, 0);
  assert.equal(history.draft.sourceProvenance, undefined, 'the deleted model cannot constrain a new composition');
  assert.equal(history.draft.sourceCache, undefined);
  const undone = travelDraft(history, 'undo'), redone = travelDraft(undone, 'redo');
  assert.ok(undone.draft.nodes.length > 0);
  assert.deepEqual(redone.draft.nodes, []);
  return history;
}

async function persist(draft: AuthoredDraft) {
  return backend('from archcanvas_cli.drafts import DraftStore;s=DraftStore(Path(sys.argv[1])/"docs/evidence/rebuild-all-presets-20261010/saved-drafts");previous=s.get(v["id"]);s.put(v["id"],v,previous["revision"] if previous else 0);print(json.dumps(s.get(v["id"])))', draft);
}

test('every advertised source example can be deleted to zero and rebuilt one module/edge at a time', async () => {
  await mkdir(evidence, { recursive: true });
  const advertised = await backend('from archcanvas_cli.server import EXAMPLES;print(json.dumps([e["id"] for e in EXAMPLES]))');
  assert.deepEqual(cases.map(item => item.id), advertised, 'new source examples must join this matrix');
  const results = [];
  for (const fixture of cases) {
    const architecture = await backend('print(json.dumps(analyze_project(Path(sys.argv[1])/"fixtures"/v[0],v[1])))', [fixture.id, fixture.entry]) as Architecture;
    const view = createDocument(architecture), before = JSON.stringify(view), editing = projectSourceEditing(view);
    const imported = await backend('print(json.dumps(import_editable_source_draft(*v)))', [view, buildScene(view), editing.document, editing.scene]) as ImportedSourceDraft;
    let history = deleteOneByOne(imported.draft);
    const blank = readDraftValidation(await backend('print(json.dumps(validate_draft(v)))', history.draft));
    assert.equal(blank.complete, false);
    assert.deepEqual(blank.issues.map(issue => issue.code), ['missing-input', 'missing-output']);
    assert.deepEqual((await persist(history.draft)).draft.nodes, []);

    // Container plumbing is removed; all real leaf-to-leaf tensor bindings,
    // including dead branches, cross-attention and mask inputs, are recreated.
    const atoms = architecture.nodes.filter(node => !node.children.length && !['Module', 'Repeat'].includes(node.kind));
    const atomIds = new Set(atoms.map(node => node.id));
    const bindings = architecture.edges.filter(edge => atomIds.has(edge.source.nodeId) && atomIds.has(edge.target.nodeId));
    const modules = new Map<string, DraftModule>(), ids = new Map<string, string>(), kinds = new Map<string, string>();
    let inputIndex = 0;
    for (const [index, atom] of atoms.entries()) {
      const id = `n_${index}`, mask = atom.ports.find(port => port.direction === 'in' && ['attn_mask', 'key_padding_mask'].includes(port.name));
      let module = catalog.modules.find(item => item.kind === atom.kind)!;
      let definition: CustomModuleDefinition | undefined;
      if (mask) {
        // A custom atom supplies the absent mask contract; it is not an
        // opaque whole-model shortcut and its source names every tensor slot.
        const source = `from torch import nn\nclass MaskedAttention(nn.Module):\n def __init__(self, embed_dim=32, num_heads=4, dropout=0.1, batch_first=True):\n  super().__init__()\n  self.attention=nn.MultiheadAttention(embed_dim,num_heads,dropout=dropout,batch_first=batch_first)\n def forward(self, query, key, value, ${mask.name}):\n  return self.attention(query=query,key=key,value=value,${mask.name}=${mask.name},need_weights=False)\n`;
        const custom = await backend('print(json.dumps(preview_custom_module(v)))', { source, entry: 'MaskedAttention', label: 'MaskedAttention', constructorValues: atom.parameters });
        module = custom.module; definition = custom.definition;
      }
      assert.ok(module, `palette missing ${atom.kind}`);
      modules.set(atom.id, module); ids.set(atom.id, id); kinds.set(id, atom.kind);
      history = changeDraft(history, draft => {
        if (definition) {
          draft.customModules ??= [];
          if (!draft.customModules.some(item => item.kind === definition.kind)) draft.customModules.push(definition);
        }
        addDraftNode(draft, module, id, { x: index * 280, y: 100 });
        const node = draft.nodes.at(-1)!; node.label = atom.label;
        for (const field of module.parameters) if (Object.hasOwn(atom.parameters, field.name)) {
          const value = atom.parameters[field.name] as DraftValue;
          node.parameters[field.name] = field.type === 'integer-array' && typeof value === 'number' ? Array(field.length ?? 1).fill(value) : value;
        }
        if (atom.kind === 'Input') {
          node.parameters.shape = fixture.shapes[inputIndex]; node.parameters.dtype = fixture.dtypes?.[inputIndex] ?? 'float32'; inputIndex++;
        }
        if (fixture.unused) draft.allowUnusedNodes = true;
      });
    }
    function endpoint(end: { nodeId: string; portId: string }, direction: 'in' | 'out') {
      const atom = atoms.find(node => node.id === end.nodeId)!, port = atom.ports.find(port => port.id === end.portId)!;
      let portId = port.name;
      if (atom.kind === 'Input') portId = 'output';
      if (atom.kind === 'Output') portId = 'input';
      assert.ok(modules.get(atom.id)!.ports.some(item => item.id === portId && item.direction === direction), `${atom.kind}.${portId}`);
      return { nodeId: ids.get(atom.id)!, portId };
    }
    const composedCatalog = { ...catalog, modules: [...catalog.modules, ...[...modules.values()].filter(module => module.category === 'custom')] };
    for (const [index, binding] of bindings.entries()) history = changeDraft(history, draft => connectDraft(draft, composedCatalog, endpoint(binding.source, 'out'), endpoint(binding.target, 'in'), `e_${index}`));
    const rebuilt = history.draft;
    assert.equal(rebuilt.nodes.length, atoms.length); assert.equal(rebuilt.edges.length, bindings.length);
    const validation = readDraftValidation(await backend('print(json.dumps(validate_draft(v,require_complete=True)))', rebuilt));
    assert.equal(validation.complete, true, fixture.id);
    await writeFile(`${evidence}/${fixture.id}-draft.json`, JSON.stringify(rebuilt, null, 2));
    const generated = await backend('print(json.dumps(generate_model(v)))', rebuilt) as GeneratedDraft;
    assert.equal(generated.verification.status, 'passed');
    assert.equal(generated.verification.modelExecution, 'not_run');
    assert.equal(Object.keys(generated.nodeBindings).length, atoms.length);
    // Independently resolve the actual producer and exact consumer port,
    // including the real output anchor inside each custom adapter.
    for (const edge of rebuilt.edges) {
      function actual(end: typeof edge.source, direction: 'in' | 'out') {
        const node = rebuilt.nodes.find(node => node.id === end.nodeId)!;
        let fact = generated.architecture.nodes.find(node => node.id === generated.nodeBindings[end.nodeId])!;
        if (node.kind.startsWith('Custom_') && direction === 'out') fact = generated.architecture.nodes.find(node => node.instanceId === `${fact.instanceId}.${end.portId}`)!;
        const name = node.kind === 'Output' ? 'value' : end.portId;
        const ports = fact.ports.filter(port => port.direction === direction && (node.kind === 'Input' || port.name === name));
        assert.equal(ports.length, 1, `${fixture.id}: ${node.label}.${name}`);
        return { nodeId: fact.id, portId: ports[0].id };
      }
      const source = actual(edge.source, 'out'), target = actual(edge.target, 'in');
      const matches = generated.architecture.edges.filter(item => JSON.stringify(item.source) === JSON.stringify(source) && JSON.stringify(item.target) === JSON.stringify(target));
      assert.equal(matches.length, 1, `${fixture.id}: exact rebuilt binding ${edge.id}`);
      if (generated.edgeBindings) assert.deepEqual(generated.edgeBindings[edge.id], [matches[0].id]);
    }
    const saved = await persist(rebuilt);
    assert.deepEqual(saved.draft, rebuilt);
    assert.ok(parseDraftCache({ ...saved, storageRevision: saved.revision, savedRevision: rebuilt.revision }));
    const canvas = createGeneratedCanvas(generated.architecture, rebuilt, generated).document;
    const reopened = JSON.parse(JSON.stringify(canvas)) as CanvasDocument;
    assert.equal(buildScene(reopened).edges.length, buildScene(canvas).edges.length);
    assert.deepEqual(reopened.architecture, generated.architecture);
    assert.equal(JSON.stringify(view), before, 'original source/view stays unchanged');
    const geometry = draftRoutes(rebuilt, composedCatalog);
    assert.equal(geometry.routes.length, bindings.length);
    assert.ok(geometry.routes.every(route => route.points.length >= 2));
    await writeFile(`${evidence}/${fixture.id}-rebuilt.json`, JSON.stringify({ draft: rebuilt, generated, canvas }, null, 2));
    results.push({ id: fixture.id, importedNodes: imported.draft.nodes.length, blankNodes: 0, blankEdges: 0, rebuiltNodes: atoms.length, rebuiltEdges: bindings.length, customKinds: rebuilt.customModules?.length ?? 0, unusedBranches: fixture.unused ?? false, verification: generated.verification.status, savedRevision: saved.revision, visibleEdges: buildScene(reopened).edges.length });
  }
  await writeFile(`${evidence}/source-example-matrix.json`, JSON.stringify(results, null, 2));
});

test('all 23 library starting graphs survive deletion and incremental palette reconstruction', async () => {
  const results = [];
  for (const [index, preset] of draftPresets.entries()) {
    const original = blankDraft(`draft-${index.toString(16)}aa`);
    insertDraftPreset(original, catalog, preset.id, { x: 0, y: 0 });
    let history = deleteOneByOne(original);
    for (const node of original.nodes) history = changeDraft(history, draft => {
      addDraftNode(draft, catalog.modules.find(item => item.kind === node.kind)!, node.id, node.position);
      Object.assign(draft.nodes.at(-1)!, { label: node.label, parameters: structuredClone(node.parameters) });
    });
    for (const edge of original.edges) history = changeDraft(history, draft => connectDraft(draft, catalog, edge.source, edge.target, edge.id));
    assert.deepEqual(history.draft.nodes, original.nodes); assert.deepEqual(history.draft.edges, original.edges);
    const generated = await backend('print(json.dumps(generate_model(v)))', history.draft);
    assert.equal(generated.verification.status, 'passed');
    const saved = await persist(history.draft); assert.deepEqual(saved.draft, history.draft);
    const canvas = createGeneratedCanvas(generated.architecture, history.draft, generated).document;
    assert.ok(buildScene(JSON.parse(JSON.stringify(canvas))).edges.length);
    assert.equal(draftRoutes(history.draft, catalog).routes.length, original.edges.length);
    results.push({ id: preset.id, blankNodes: 0, blankEdges: 0, rebuiltNodes: original.nodes.length, rebuiltEdges: original.edges.length, verification: 'passed' });
  }
  await writeFile(`${evidence}/library-preset-matrix.json`, JSON.stringify(results, null, 2));
});
