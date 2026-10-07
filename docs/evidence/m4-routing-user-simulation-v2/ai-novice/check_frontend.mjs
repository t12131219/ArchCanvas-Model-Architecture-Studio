import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { addDraftNode, blankDraft, changeDraft, draftHistory, parseDraftCache } from '../../../../studio/src/authoring.ts';
import { draftPresets, insertDraftPreset } from '../../../../studio/src/authoringPresets.ts';
import { draftParameterHelp } from '../../../../studio/src/draftParameterHelp.ts';

const root = fileURLToPath(new URL('../../../../', import.meta.url));
const here = fileURLToPath(new URL('./', import.meta.url));
const require = createRequire(`${root}studio/package.json`);
const ts = require('typescript');
const source = readFileSync(`${root}studio/src/AuthoringStudio.tsx`, 'utf8');
const ast = ts.createSourceFile('AuthoringStudio.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const backendReport = JSON.parse(readFileSync(`${here}contract-report.json`, 'utf8'));
const catalog = backendReport.inventory.catalog;
const backendBytes = readFileSync(`${root}src/archcanvas_authoring/draft.py`);
assert.equal(createHash('sha256').update(backendBytes).digest('hex'), backendReport.inputBindingsBeforeAndAfterExact.find(binding => binding.path === 'src/archcanvas_authoring/draft.py').sha256);
const module = kind => catalog.modules.find(module => module.kind === kind);
const checks = [];
const allHelp = catalog.modules.flatMap(module => module.parameters.map(field => ({ kind: module.kind, field: field.name, help: draftParameterHelp(module.kind, field.name) })));
assert.equal(allHelp.length, 34); assert.ok(allHelp.every(field => field.help?.label && field.help.description));
checks.push({ id: '34-registered-field-help', passed: true, fields: allHelp });

const presets = [];
for (const [id, expectedNodes, expectedEdges] of [['mlp', 5, 4], ['cnn', 8, 7], ['residual-mlp', 6, 6]]) {
  let identity = 0;
  const original = draftHistory(blankDraft('draft-ab456'));
  const inserted = changeDraft(original, draft => insertDraftPreset(draft, catalog, id, { x: 60, y: 90 }, prefix => `${prefix}${++identity}`));
  assert.equal(inserted.draft.nodes.length, expectedNodes); assert.equal(inserted.draft.edges.length, expectedEdges); assert.equal(inserted.past.length, 1);
  presets.push({ id, expectedNodes, expectedEdges, draft: inserted.draft, oneHistoryStep: true });
}
writeFileSync(`${here}preset-drafts.json`, JSON.stringify(presets, null, 2) + '\n');
checks.push({ id: 'transparent-preset-insertion', passed: true, presets: presets.map(({ draft, ...case_ }) => case_) });

// Use the actual component's AST expression; independently choose queries and
// intended category/lookup outcomes rather than asserting code-shaped text.
const initializer = name => {
  let result;
  const visit = node => { if (ts.isVariableDeclaration(node) && node.name.getText(ast) === name) result = node.initializer; ts.forEachChild(node, visit); };
  visit(ast); assert.ok(result, name); return result.getText(ast);
};
const searchModules = new Function('catalog', 'query', 'paletteView', `return ${initializer('matches')};`);
const searchPresets = new Function('draftPresets', 'query', 'paletteView', `return ${initializer('presetMatches')};`);
const searchResults = [];
for (const [query, expectedModuleKinds, expectedPresetIds] of [
  ['', ['Input','Output','Linear','ReLU','GELU','SiLU','Identity','Dropout','Flatten','Conv2d','MaxPool2d','AdaptiveAvgPool2d','BatchNorm2d','LayerNorm','Embedding','Add','Concat'], []],
  ['linear', ['Linear'], []], ['cnn', [], ['cnn']], ['mlp', [], ['mlp','residual-mlp']], ['卷积', ['Conv2d'], ['cnn']],
  ['激活', ['ReLU','GELU','SiLU'], []], ['激活函数', [], []], ['attention', [], []], ['注意力', [], []], ['sigmoid', [], []], ['softmax', [], []], ['lstm', [], []],
]) {
  const kinds = searchModules(catalog, query, 'modules').map(module => module.kind);
  const ids = searchPresets(draftPresets, query, 'modules').map(preset => preset.id);
  assert.deepEqual(kinds, expectedModuleKinds); assert.deepEqual(ids, expectedPresetIds);
  searchResults.push({ query, moduleKinds: kinds, presetIds: ids, currentEmptyMessage: kinds.length || ids.length ? null : '没有找到匹配的模块或网络；当前模块库尚不支持 Attention 和 LSTM。' });
}
const clearModules = searchModules(catalog, '', 'presets');
assert.equal(clearModules.length, 0); assert.equal(searchPresets(draftPresets, '', 'presets').length, 3);
checks.push({ id: 'actual-palette-search-and-view-expression', passed: true, searchResults, clearSearchOnPresetView: { modules: 0, presets: 3 }, limitations: 'Actual source expressions evaluated in isolation; not native input events.' });

// Concrete states that the enabled UI can create but cannot reload from cache.
const budget = blankDraft('draft-ab789');
for (let i = 0; i < 129; i++) addDraftNode(budget, module('Input'), `input${i}`, { x: 60, y: 70 + i * 128 });
assert.equal(budget.nodes.length, 129); assert.equal(parseDraftCache({ draft: budget, storageRevision: 0, savedRevision: -1 }), null);
const title = blankDraft('draft-ab790'); title.title = '';
assert.equal(parseDraftCache({ draft: title, storageRevision: 0, savedRevision: -1 }), null);
const label = blankDraft('draft-ab791'); addDraftNode(label, module('Input'), 'input1', { x: 60, y: 70 }); label.nodes[0].label = '';
assert.equal(parseDraftCache({ draft: label, storageRevision: 0, savedRevision: -1 }), null);
checks.push({ id: 'editable-state-cache-counterexamples', passed: true, counterexamples: [
  { state: '129 individual module additions', nodeCount: budget.nodes.length, cacheRejected: true, UIAvailable: 'module-card disabled depends on busy only; addDraftNode does not enforce max nodes', priority: 'P1' },
  { state: 'clear draft name to empty', cacheRejected: true, UIAvailable: 'header title onChange directly commits event.target.value', priority: 'P1' },
  { state: 'clear module display name to empty', cacheRejected: true, UIAvailable: 'inspector label onChange directly commits event.target.value', priority: 'P1' },
] });

let blankBody;
function visit(node) { if (ts.isFunctionDeclaration(node) && node.name?.text === 'startBlankDraft') blankBody = node.body; ts.forEachChild(node, visit); }
visit(ast); assert.ok(blankBody);
const compiledBody = ts.transpileModule(`function run(){${blankBody.getText(ast).slice(1, -1)}}`, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText.match(/function run\(\) \{([\s\S]*)\}/)[1];
const messages = [], unused = [], callbacks = { current: null };
new Function('dirty', 'history', 'cancel', 'setNotice', 'draftHistory', 'createBlank', 'currentRef', 'setHistory', 'setStorageRevision', 'setSavedRevision', 'setSelection', 'setGenerated', 'setCamera', 'clearError', compiledBody)(true, { draft: label }, () => {}, value => messages.push(value), draftHistory, () => { throw Error('unexpected blank creation'); }, callbacks, value => unused.push(value), () => {}, () => {}, () => {}, () => {}, () => {}, () => {});
assert.deepEqual(unused, []); assert.equal(messages.length, 1); assert.match(messages[0], /未保存编辑/);
checks.push({ id: 'actual-new-blank-guard', passed: true, observedNotice: messages[0], oldDraftPreserved: true, newDraftCreated: false, limitation: 'Exact current function body under controlled unsaved state; not a native click.' });

// Read the named DL-Playground reference's group registry as syntax only. Its
// own declaration count is not evidence of correctness, generation or runtime.
const ref = '/home/fzg/PycharmProjects/ArchCanvas/Source_Code_Project/DL-Playground/frontend/src/nodes/registry.ts';
const refData = readFileSync(ref), refAst = ts.createSourceFile(ref, refData.toString(), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
let groupInit; function findGroup(node) { if (ts.isVariableDeclaration(node) && node.name.getText(refAst) === 'NODE_GROUPS') groupInit = node.initializer; ts.forEachChild(node, findGroup); } findGroup(refAst);
const referenceGroups = groupInit.properties.map(group => {
  const nodes = group.initializer.properties.find(property => property.name?.getText(refAst) === 'nodes'); let entries = nodes.initializer;
  if (!ts.isObjectLiteralExpression(entries)) { let returned; function findReturn(node) { if (ts.isReturnStatement(node) && node.expression && ts.isObjectLiteralExpression(node.expression)) returned = node.expression; ts.forEachChild(node, findReturn); } findReturn(entries); entries = returned; }
  return { group: group.name.getText(refAst), entries: entries.properties.map(property => property.name.getText(refAst)) };
});
assert.equal(referenceGroups.length, 14); assert.equal(referenceGroups.reduce((count, group) => count + group.entries.length, 0), 80);
const reference = { path: ref, bytes: refData.length, sha256: createHash('sha256').update(refData).digest('hex'), groups: referenceGroups, declaredGroupEntries: 80, uniqueDeclaredNodeKeys: new Set(referenceGroups.flatMap(group => group.entries)).size, duplicateKey: 'repeat_layer (torch_ops + control)', caveat: 'Read-only inventory / UX reference. Reference application not run, imported, copied or independently certified.' };
writeFileSync(`${here}frontend-report.json`, JSON.stringify({ schema: 'archcanvas-ai-novice-frontend-contract-audit/1', reviewerKind: 'AI-simulation', humanParticipantsAdded: 0, modelsExecuted: false, sharedBrowserOperated: false, productFilesWritten: false, checks, reference }, null, 2) + '\n');
console.log(JSON.stringify({ checks: checks.length, fields: allHelp.length, presets: presets.length, searchQueries: searchResults.length, cacheCounterexamples: 3, referenceGroupEntries: 80, humans: 0 }));
