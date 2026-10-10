import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement } from 'react';
import ts from 'typescript';
import { blankDraft, draftHistory, selectDraftNode, moveDraftNodes, changeDraft } from '../src/authoring.ts';
import { draftPortPresentation } from '../src/draftPortPresentation.ts';
import { draftNodeSize } from '../src/draftNodeGeometry.ts';
import type { DraftCatalog } from '../src/authoring.ts';
const studio = fileURLToPath(new URL('../', import.meta.url));
const temporary = mkdtempSync(`${studio}.source-authoring-ui-`); after(() => rmSync(temporary, { recursive: true, force: true }));
const source = readFileSync(`${studio}src/AuthoringStudio.tsx`, 'utf8');
const draft = blankDraft('draft-compact');
draft.nodes = [0, 1].map(i => ({ id: `short_${i}`, kind: 'Source_Input', label: `tokens ${i}`, parameters: {}, position: { x: 10 + 240 * i, y: 40 },
  presentation: { width: 176, height: 56, fill: '#fff', stroke: '#aaa', group: false, ports: { p_output: { x: 88, y: 56 } } } }));
draft.nodes.push({ id: 'wide_group', kind: 'Source_Group', label: 'Transformer', parameters: {}, position: { x: 0, y: 130 }, presentation: { width: 600, height: 300, fill: '#fff', stroke: '#aaa', group: true, ports: {} } });
const catalog: DraftCatalog = { schemaVersion: 1, mode: 'authored-draft', modules: [{ kind: 'Source_Input', label: 'Input', category: 'source', description: '', defaults: {}, parameters: [], ports: [{ id: 'p_output', name: 'source_tokens', direction: 'out', type: 'tensor' }] },
  { kind: 'Source_Group', label: 'Module', category: 'source', description: '', defaults: {}, parameters: [], ports: [] }], unsupported: [] };
function compile(input: string, name: string) {
  const output = ts.transpileModule(input, { fileName: `${name}.tsx`, compilerOptions: { jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText
    .replace(/import ['"]\.\/AuthoringStudio\.css['"];?/g, '')
    .replace(/(['"])\.\/([^'"]+\.ts)\1/g, (_match, _quote, file) => `'${pathToFileURL(`${studio}src/${file}`).href}'`)
    .replace(/(['"])\.\/(icons|WorkspaceModeSwitch|FloatingLegend|CustomModuleDialog)\1/g, (_match, _quote, file) => `'./${file}.mjs'`)
    .replace(/(['"])\.\/([A-Za-z][A-Za-z0-9]*)\1/g, (_match, _quote, file) => `'${pathToFileURL(`${studio}src/${file}.ts`).href}'`);
  writeFileSync(`${temporary}/${name}.mjs`, output);
}
for (const name of ['icons', 'WorkspaceModeSwitch', 'FloatingLegend', 'CustomModuleDialog']) compile(readFileSync(`${studio}src/${name}.tsx`, 'utf8'), name);
compile(source.replace('useState<DraftCatalog | null>(null)', `useState<DraftCatalog | null>(${JSON.stringify(catalog)})`), 'AuthoringStudio');
const { AuthoringStudio } = await import(pathToFileURL(`${temporary}/AuthoringStudio.mjs`).href);

test('actual compact source-card markup retains dimensions, dot-only port hit and a topmost body drag target', () => {
  const html = renderToStaticMarkup(createElement(AuthoringStudio, { initialWorkspace: { draft }, onClose: () => {}, onOpen: async () => {} }));
  const start = html.indexOf('data-draft-node="short_0"'), end = html.indexOf('data-draft-node="short_1"'), card = html.slice(start, end);
  assert.match(card, /<rect width="176" height="56"/); assert.match(card, /data-draft-drag-handle="short_0"/);
  assert.match(card, /class="draft-port-hit" x="77" y="45" width="22" height="22"/);
  assert.match(card, /text-anchor="end" pointer-events="none"/);
  assert.ok(card.lastIndexOf('data-draft-drag-handle') > card.indexOf('data-draft-port="p_output"'), 'title hit is painted above port hits');
  const group = html.slice(html.indexOf('data-draft-node="wide_group"'));
  assert.match(group, /<title>Transformer<\/title>Transformer<\/text>/);
  assert.equal(draftNodeSize(draft.nodes[0], catalog).height, 56, 'no layout expansion disguises the collision');
  const compactPort = draftPortPresentation(catalog.modules[0].ports[0], 88, 56, 'vertical', Infinity, 9, true);
  assert.ok(compactPort.hit.y > 28, 'the actual compact centre remains a node-select/drag region');
});

test('actual AuthoringStudio title clicks select two compact nodes and its pointer callbacks drag both as one undo action', () => {
  const ast = ts.createSourceFile('AuthoringStudio.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const component = ast.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === 'AuthoringStudio');
  assert.ok(component && ts.isFunctionDeclaration(component) && component.body);
  const names = ['pointerDown', 'pointerMove', 'pointerUp'], snippets = names.map(name => { const statement = component.body!.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === name); assert.ok(statement); return statement.getText(ast); });
  const selectedIds: string[] = [], gesture = { current: null as any }, currentRef = { current: draftHistory(draft) }; let preview: typeof draft | null = null, connections = 0;
  const element = { setPointerCapture: () => {}, hasPointerCapture: () => true, releasePointerCapture: () => {} };
  const env = { busy: false, portEditing: false, gesture, currentRef, tool: 'select', camera: { x: 0, y: 0, zoom: 1 }, catalog, selectedIds, connection: null, clearError: () => {}, selectDraftNode, moveDraftNodes, draftNodeSize,
    setSelection: (value: { nodes?: string[] }) => { selectedIds.splice(0, selectedIds.length, ...(value.nodes ?? [])); }, setConnection: (value: unknown) => { if (value) connections++; },
    setMarquee: () => {}, setNotice: () => {}, setPreview: (value: typeof draft) => { preview = value; }, point: (x: number, y: number) => ({ x, y }), connect: () => { connections++; },
    apply: (update: Parameters<typeof changeDraft>[1]) => { currentRef.current = changeDraft(currentRef.current, update); },
    cameraAtPanInput: () => null, beginCameraPan: () => null, panInput: () => null, setCamera: () => {} };
  const code = ts.transpileModule(snippets.join('\n'), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  const callbacks = new Function(...Object.keys(env), `${code};return {${names.join(',')}}`)(...Object.values(env));
  const event = (id: string, x = 0, y = 0, additive = false) => ({ pointerId: 1, button: 0, clientX: x, clientY: y, altKey: false, shiftKey: additive, ctrlKey: false, metaKey: false,
    preventDefault: () => {}, currentTarget: element, target: { closest: (selector: string) => selector === '[data-draft-node]' ? { getAttribute: () => id } : null } });
  callbacks.pointerDown(event('short_0')); callbacks.pointerUp(event('short_0')); callbacks.pointerDown(event('short_1', 0, 0, true));
  assert.deepEqual(selectedIds, ['short_0', 'short_1']); callbacks.pointerMove(event('short_1', 24, -16)); callbacks.pointerUp(event('short_1', 24, -16));
  assert.equal(connections, 0, 'node title clicks never become tensor connection gestures'); assert.equal(currentRef.current.past.length, 1);
  for (const id of selectedIds) { const old = draft.nodes.find(n => n.id === id)!, moved = currentRef.current.draft.nodes.find(n => n.id === id)!; assert.deepEqual(moved.position, { x: old.position.x + 24, y: old.position.y - 16 }); }
  assert.ok(preview);
});
