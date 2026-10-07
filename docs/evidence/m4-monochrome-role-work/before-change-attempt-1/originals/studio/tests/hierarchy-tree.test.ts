import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { promisify } from 'node:util';
import { Fragment, createElement } from 'react';
import type { ComponentType } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import { applyVisualBatch, createDocument } from '../src/core/index.ts';
import type { Architecture, ArchitectureNode, CanvasDocument } from '../src/core/index.ts';

// Node's strip-types loader cannot read TSX. Compile the actual two component
// sources, using the already installed React/TypeScript packages, into an
// ephemeral Studio directory. No browser or replacement React renderer is used.
const project = fileURLToPath(new URL('../../', import.meta.url));
const studio = fileURLToPath(new URL('../', import.meta.url));
const temporary = mkdtempSync(`${studio}.hierarchy-regression-`);
after(() => rmSync(temporary, { recursive: true, force: true }));
function compile(source: string, filename: string) {
  const output = ts.transpileModule(source, { fileName: `${filename}.tsx`, reportDiagnostics: true,
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
  assert.equal(output.diagnostics?.filter(item => item.category === ts.DiagnosticCategory.Error).length ?? 0, 0);
  writeFileSync(`${temporary}/${filename}.mjs`, output.outputText.replace(/(['"])\.\/icons(?:\.tsx)?\1/g, "'./icons.mjs'"));
}
compile(readFileSync(`${studio}src/icons.tsx`, 'utf8'), 'icons');
compile(readFileSync(`${studio}src/HierarchyTree.tsx`, 'utf8'), 'HierarchyTree');
const previousApp = readFileSync(`${project}docs/evidence/before-hierarchy-optimization/files/studio/src/App.tsx`, 'utf8');
const previousTree = previousApp.match(/function TreeNode\([\s\S]+$/)?.[0];
assert.ok(previousTree, 'the archived formal-product tree must remain available as a regression baseline');
compile(`import { Icon } from './icons';\nexport ${previousTree}`, 'PreviousTree');
interface Props {
  architecture: Architecture; document: CanvasDocument; selected: readonly string[];
  onSelect: (id: string) => void; onExpand: (id: string, expanded: boolean) => void;
}
const { HierarchyTree } = await import(pathToFileURL(`${temporary}/HierarchyTree.mjs`).href) as { HierarchyTree: ComponentType<Props> };
const { TreeNode: PreviousTree } = await import(pathToFileURL(`${temporary}/PreviousTree.mjs`).href) as { TreeNode: ComponentType<Props & { node: ArchitectureNode }> };
const select = (_id: string) => {}, expand = (_id: string, _expanded: boolean) => {};
function markup(document: CanvasDocument, selected: readonly string[] = []) {
  return renderToStaticMarkup(createElement(HierarchyTree, { architecture: document.architecture, document,
    selected, onSelect: select, onExpand: expand }));
}
function previousMarkup(document: CanvasDocument, selected: readonly string[] = []) {
  return renderToStaticMarkup(createElement(Fragment, null, document.architecture.nodes.filter(node => !node.parentId)
    .map(node => createElement(PreviousTree, { key: node.id, node, architecture: document.architecture,
      document, selected, onSelect: select, onExpand: expand }))));
}
function node(id: string, label: string, children: string[] = [], parentId?: string, category = 'module'): ArchitectureNode {
  return { id, label, kind: 'AuthoredFixture', category, children, parentId, parameters: {}, ports: [], evidence: 'source' };
}
function fixture(): CanvasDocument {
  // Array order deliberately differs from each parent's child order. The
  // expected rows below are authored by hand, independently of the tree code.
  const architecture: Architecture = { schemaVersion: 1, id: 'tree-oracle', label: 'Tree oracle', entry: 'model:Oracle',
    sourceDigest: 'a'.repeat(64), irDigest: 'b'.repeat(64), edges: [], diagnostics: [], sources: [], nodes: [
      node('a2', 'Second A leaf', [], 'a', 'operator'), node('b', 'Root B', ['b1']),
      { ...node('middle', 'Repeat group', ['a1', 'latent'], 'a'), repeat: { count: 3, sharing: 'independent' } },
      node('a', 'Root A', ['middle', 'a2']), node('b1', 'Aliased B leaf', [], 'b', 'opaque'),
      node('a1', 'First A leaf', [], 'middle', 'tensor'), node('latent', 'Nested group', ['nested'], 'middle'),
      node('nested', 'Nested leaf', [], 'latent', 'operator'),
    ] };
  return { schemaVersion: 1, id: 'canvas-tree-oracle', title: 'Oracle', revision: 0, sourceBindingDigest: architecture.sourceDigest,
    architecture, displayAliases: { b1: '', a1: '& <Visible "label">' }, nodeStyleOverrides: {}, edgeStyleOverrides: {},
    legendItems: [], annotations: [], pageSpec: { widthMm: 180, background: '#ffffff', preset: 'paper' },
    expandedIds: ['a', 'b', 'middle', 'latent'], layout: {}, layoutByFrontier: {}, pinnedObjects: ['a', 'a1'] };
}
function rows(html: string) {
  return [...html.matchAll(/<div role="treeitem"([^>]*)><div class="tree-row ([^"]*)" style="padding-left:(\d+)px">([\s\S]*?)<\/div>/g)]
    .map(match => {
      const attributes = match[1];
      const id = attributes.match(/data-tree-node-id="([^"]+)"/)![1];
      const depth = Number(attributes.match(/data-tree-depth="(\d+)"/)![1]);
      const toggle = match[4].match(/<button class="tree-toggle ([^"]*)"([^>]*)>/)!;
      const label = match[4].match(/<button class="tree-label"><span class="tree-node-dot ([^"]*)"><\/span><span>(.*?)<\/span>(.*?)<\/button>/)!;
      return { id, depth, padding: Number(match[3]), selected: attributes.includes('aria-selected="true"'),
        expanded: attributes.match(/aria-expanded="(true|false)"/)?.[1], rowClass: match[2],
        toggleClass: toggle[1], toggleDisabled: toggle[2].includes('disabled=""'),
        toggleLabel: toggle[2].match(/aria-label="([^"]+)"/)![1], category: label[1], label: label[2],
        repeat: label[3], pinned: match[4].includes('width="10" height="10"') };
    });
}

test('hierarchy order and depth follow authored roots and child lists, independent of flat node order', () => {
  const document = fixture(), html = markup(document);
  assert.deepEqual(rows(html).map(({ id, depth, padding }) => [id, depth, padding]), [
    ['b', 0, 14], ['b1', 1, 27], ['a', 0, 14], ['middle', 1, 27],
    ['a1', 2, 40], ['latent', 2, 40], ['nested', 3, 53], ['a2', 1, 27],
  ]);
  assert.equal(html, previousMarkup(document));
});

test('empty aliases, escaped labels, repeat badges, pins and leaf/toggle ARIA stay exact', () => {
  const document = fixture(), html = markup(document, ['b', 'a1', 'a1', 'absent']);
  const indexed = Object.fromEntries(rows(html).map(row => [row.id, row]));
  assert.equal(indexed.b1.label, ''); // Empty display aliases are deliberate, not a missing value.
  assert.equal(indexed.a1.label, '&amp; &lt;Visible &quot;label&quot;&gt;');
  assert.equal(indexed.middle.repeat, '<small>×3</small>');
  assert.deepEqual(rows(html).filter(row => row.pinned).map(row => row.id), ['a', 'a1']);
  assert.deepEqual(rows(html).filter(row => row.selected).map(row => row.id), ['b', 'a1']);
  assert.equal(indexed.a1.rowClass, 'selected');
  assert.equal(indexed.b1.category, 'opaque');
  assert.equal(indexed.a1.category, 'tensor');
  for (const id of ['b1', 'a1', 'nested', 'a2']) {
    assert.equal(indexed[id].expanded, undefined);
    assert.equal(indexed[id].toggleDisabled, true);
  }
  assert.equal(indexed.a.expanded, 'true');
  assert.equal(indexed.a.toggleClass, 'open');
  assert.equal(indexed.a.toggleDisabled, false);
  assert.equal(indexed.a1.toggleLabel, '展开 First A leaf');
  assert.equal(html, previousMarkup(document, ['b', 'a1', 'a1', 'absent']));
});

test('collapsed ancestors hide latent descendants without erasing their expansion or selection', () => {
  const document = fixture();
  document.expandedIds = ['b', 'middle', 'latent'];
  const hidden = markup(document, ['nested']);
  assert.deepEqual(rows(hidden).map(row => row.id), ['b', 'b1', 'a']);
  assert.equal(rows(hidden).find(row => row.id === 'a')!.expanded, 'false');
  assert.equal(hidden, previousMarkup(document, ['nested']));
  document.expandedIds = [...document.expandedIds, 'a'];
  const reopened = markup(document, ['nested']);
  assert.deepEqual(rows(reopened).map(row => row.id), ['b', 'b1', 'a', 'middle', 'a1', 'latent', 'nested', 'a2']);
  assert.equal(rows(reopened).find(row => row.id === 'nested')!.selected, true);
  assert.equal(reopened, previousMarkup(document, ['nested']));
});

test('a replacement architecture with the same IDs displays new labels, categories and topology', () => {
  const first = fixture(), oldHtml = markup(first), replacement = structuredClone(first);
  for (const item of replacement.architecture.nodes) item.label = `New ${item.label}`;
  replacement.architecture.nodes.find(item => item.id === 'b')!.children.push('a2');
  replacement.architecture.nodes.find(item => item.id === 'a2')!.parentId = 'b';
  replacement.architecture.nodes.find(item => item.id === 'a2')!.category = 'opaque';
  replacement.architecture.nodes.find(item => item.id === 'a')!.children = ['middle'];
  replacement.architecture.nodes.find(item => item.id === 'middle')!.children = ['latent', 'a1'];
  const html = markup(replacement);
  assert.deepEqual(rows(html).map(({ id, depth }) => [id, depth]), [
    ['b', 0], ['b1', 1], ['a2', 1], ['a', 0], ['middle', 1], ['latent', 2], ['nested', 3], ['a1', 2],
  ]);
  assert.equal(rows(html).find(row => row.id === 'a2')!.label, 'New Second A leaf');
  assert.equal(rows(html).find(row => row.id === 'a2')!.category, 'opaque');
  assert.equal(rows(html).find(row => row.id === 'a1')!.label, '&amp; &lt;Visible &quot;label&quot;&gt;');
  assert.equal(html, previousMarkup(replacement));
  assert.equal(markup(first), oldHtml);
});

test('an empty architecture renders no rows and non-hierarchy visual changes leave row HTML exact', () => {
  const document = fixture(), before = markup(document, ['middle']);
  document.revision++;
  document.layout.a = { x: 123, y: -17 };
  document.pageSpec.widthMm = 250;
  document.nodeStyleOverrides.a = { fill: '#123456' };
  document.annotations.push({ id: 'note', text: 'Unrelated canvas annotation', x: 0, y: 0 });
  assert.equal(markup(document, ['middle']), before);
  document.architecture = { ...document.architecture, nodes: [] };
  assert.equal(markup(document), '');
  assert.equal(previousMarkup(document), '');
});

test('the actual formal source-backed 304-node model keeps precise old/new hierarchy HTML before and after expansion', async () => {
  const local = `${project}.venv/bin/python`;
  const { stdout } = await promisify(execFile)(existsSync(local) ? local : 'python3', ['-I', '-S', '-B', '-c',
    'import sys,json; from pathlib import Path; root=Path(sys.argv[1]); sys.path.insert(0,str(root/"src")); from archcanvas_python import analyze_project; print(json.dumps(analyze_project(root/"fixtures/stress_300","model:DenseStress300")))',
    project], { encoding: 'utf8', maxBuffer: 2_000_000 });
  const architecture = JSON.parse(stdout) as Architecture;
  assert.equal(architecture.nodes.length, 304);
  const initial = createDocument(architecture), container = architecture.nodes.find(item => item.label === 'network')!;
  assert.equal(container.children.length, 300);
  assert.equal(rows(markup(initial)).length, 4);
  assert.equal(markup(initial), previousMarkup(initial));
  const expanded = applyVisualBatch(initial, [{ type: 'expand', id: container.id, expanded: true },
    { type: 'alias', id: container.children[0], label: 'Edited projection' },
    { type: 'pin', ids: [container.children[1]], pinned: true }]);
  const selected = [container.children[0], container.children[299]], html = markup(expanded, selected);
  const rendered = rows(html);
  assert.equal(rendered.length, 304);
  assert.deepEqual(rendered.filter(row => row.depth === 2).map(row => row.id), container.children);
  assert.equal(rendered.find(row => row.id === container.children[0])!.label, 'Edited projection');
  assert.equal(rendered.find(row => row.id === container.children[1])!.pinned, true);
  assert.equal(html, previousMarkup(expanded, selected));
});

// These checks certify static hierarchy output and source-backed regression
// coverage. SSR does not certify memo behavior across client updates, native
// event timing, layout/paint or sustained presented FPS.
