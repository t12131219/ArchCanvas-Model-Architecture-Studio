import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createElement } from 'react';
import type { ComponentType } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

// Render the actual component with React. TypeScript alone cannot detect a
// removed inspector because its parameter editor can remain unused and valid.
const studio = fileURLToPath(new URL('../', import.meta.url));
const temporary = mkdtempSync(`${studio}.authoring-inspector-regression-`);
after(() => rmSync(temporary, { recursive: true, force: true }));
const source = readFileSync(`${studio}src/AuthoringStudio.tsx`, 'utf8');
function compile(input: string, name: string) {
  const output = ts.transpileModule(input, { fileName: `${name}.tsx`, reportDiagnostics: true,
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
  assert.equal(output.diagnostics?.filter(item => item.category === ts.DiagnosticCategory.Error).length ?? 0, 0);
  const resolved = output.outputText.replace(/import ['"]\.\/AuthoringStudio\.css['"];?/g, '')
    .replace(/(['"])\.\/icons\1/g, "'./icons.mjs'")
    .replace(/(['"])\.\/([A-Za-z][A-Za-z0-9]*)\1/g, (_match, _quote, file) => `'${pathToFileURL(`${studio}src/${file}.ts`).href}'`);
  writeFileSync(`${temporary}/${name}.mjs`, resolved);
}
compile(readFileSync(`${studio}src/icons.tsx`, 'utf8'), 'icons');
compile(source, 'AuthoringStudio');
type Props = { onClose: () => void; onOpen: () => Promise<void> };
const { AuthoringStudio, unsupportedPaletteMessage } = await import(pathToFileURL(`${temporary}/AuthoringStudio.mjs`).href) as {
  AuthoringStudio: ComponentType<Props>;
  unsupportedPaletteMessage: (value: string) => string | null;
};
function markup(Component = AuthoringStudio) {
  return renderToStaticMarkup(createElement(Component, { onClose: () => {}, onOpen: async () => {} }));
}
function inspector(html: string) {
  const found = html.match(/<aside class="draft-inspector">([\s\S]*?)<\/aside>/);
  assert.ok(found, 'From-zero authoring requires a visible properties and validation inspector');
  return found[1];
}

test('the actual blank authoring component exposes visible steps, a static-check entry and the draft count', () => {
  const actual = inspector(markup());
  assert.match(actual, /每一步都在图上完成/);
  for (const step of ['拖入 Input，设置输入形状。', '拖入常用模块，编辑参数。', '连接端口，加入 Output。', '保存草稿，生成模型与论文图。']) assert.ok(actual.includes(step));
  assert.match(actual, /aria-label="模型静态检查"/);
  assert.match(actual, /<button[^>]*>检查模型<\/button>/);
  assert.match(actual, /<div class="draft-summary"><b>0<\/b> 模块 <b>0<\/b> 连接<\/div>/);
});

test('the inspector assertion rejects the same compilable component with only that visible panel removed', async () => {
  const ast = ts.createSourceFile('AuthoringStudio.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let panel: ts.JsxElement | undefined;
  function visit(node: ts.Node) {
    if (ts.isJsxElement(node) && node.openingElement.tagName.getText(ast) === 'aside' && node.openingElement.attributes.properties.some(attribute =>
      ts.isJsxAttribute(attribute) && attribute.name.getText(ast) === 'className' && attribute.initializer && ts.isStringLiteral(attribute.initializer) && attribute.initializer.text === 'draft-inspector')) panel = node;
    ts.forEachChild(node, visit);
  }
  visit(ast); assert.ok(panel);
  compile(source.slice(0, panel.getStart(ast)) + source.slice(panel.end), 'WithoutInspector');
  const mutated = await import(pathToFileURL(`${temporary}/WithoutInspector.mjs`).href) as { AuthoringStudio: ComponentType<Props> };
  assert.throws(() => inspector(markup(mutated.AuthoringStudio)), /requires a visible properties/);
});

test('unavailable activation searches name their missing operation and disclose differences in available options', () => {
  for (const [query, difference] of [
    ['Sigmoid', '激活行为不同'], ['Softmax', '不提供概率归一化'], ['Tanh', '输出范围'],
  ]) {
    const message = unsupportedPaletteMessage(` ${query.toUpperCase()} `);
    assert.ok(message);
    assert.ok(message.includes(`暂不支持 ${query}`));
    assert.match(message, /ReLU、GELU 或 SiLU/);
    assert.ok(message.includes(difference));
  }
});

test('unavailable tensor module searches explain the current dimensional or pooling limits', () => {
  for (const [query, option, limit] of [
    ['Conv1d', 'Conv2d', '二维空间输入'],
    ['AvgPool2d', 'AdaptiveAvgPool2d', '池化方式或输出尺寸设置不同'],
    ['BatchNorm1d', 'BatchNorm2d', '四维图像张量'],
  ]) {
    const message = unsupportedPaletteMessage(query);
    assert.ok(message);
    assert.ok(message.includes(`暂不支持 ${query}`));
    assert.ok(message.includes(option));
    assert.ok(message.includes(limit));
  }
});

test('attention and recurrent searches expose the missing behavior without promising an equivalent network', () => {
  for (const query of ['MultiheadAttention', 'Attention', '注意力']) {
    const message = unsupportedPaletteMessage(query);
    assert.ok(message);
    assert.ok(message.includes('暂不支持 MultiheadAttention / Attention'));
    assert.match(message, /Embedding、LayerNorm、Linear 或 MLP 网络起点/);
    assert.match(message, /不提供注意力计算/);
  }
  for (const query of ['LSTM', 'GRU']) {
    const message = unsupportedPaletteMessage(query);
    assert.ok(message);
    assert.ok(message.includes(`暂不支持 ${query}`));
    assert.match(message, /Embedding、Linear 或 MLP 网络起点/);
    assert.match(message, /不提供循环状态/);
  }
});

test('ordinary and empty searches retain the generic palette message', () => {
  for (const query of ['', '  ', 'dropout', 'hello', '卷积', 'Linear', 'MLP']) assert.equal(unsupportedPaletteMessage(query), null);
});

test('the actual palette visibly exposes classification and alias/parameter discovery', () => {
  const actual = markup();
  assert.match(actual, /aria-label="筛选模块分类"/);
  assert.match(actual, /名称、别名或参数，如 FC \/ padding/);
  assert.match(actual, /网络起点也按组成模块匹配/);
});

test('actual palette rendering uses the runtime inventory, alias search and the selected module category', async () => {
  const project = fileURLToPath(new URL('../../', import.meta.url));
  const data = await promisify(execFile)(`${project}.venv/bin/python`, ['-I', '-S', '-B', '-c',
    'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import module_catalog;print(json.dumps(module_catalog()))', project]);
  const loaded = source.replace('useState<DraftCatalog | null>(null)', `useState<DraftCatalog | null>(${data.stdout.trim()})`);
  assert.notEqual(loaded, source);
  for (const [query, category, expectedModule, missingModule, summary] of [
    ['FC', '', 'Linear', 'Conv2d', '基础模块 1 · 网络起点 3'],
    ['kernel_size', 'pooling', 'MaxPool2d', 'Conv2d', '基础模块 1（池化） · 网络起点 1'],
  ]) {
    const configured = loaded.replace("const [search, setSearch] = useState('');", `const [search, setSearch] = useState('${query}');`)
      .replace("const [paletteCategory, setPaletteCategory] = useState('');", `const [paletteCategory, setPaletteCategory] = useState('${category}');`);
    const name = `Palette-${expectedModule}`;
    compile(configured, name);
    const component = await import(pathToFileURL(`${temporary}/${name}.mjs`).href) as { AuthoringStudio: ComponentType<Props> };
    const actual = markup(component.AuthoringStudio);
    if (query === 'FC') assert.match(actual, /搜索结果：基础模块 1 · 网络起点 \d+/);
    else assert.match(actual, /搜索结果：基础模块 \d+（池化） · 网络起点 \d+/);
    assert.ok(actual.includes(`aria-label="添加 ${expectedModule}"`));
    assert.ok(!actual.includes(`aria-label="添加 ${missingModule}"`));
    assert.match(actual, /全部分类 · \d+/);
    assert.match(actual, /归一化 · \d+/);
    assert.match(actual, /模块类型：/);
  }
});

// SSR verifies the actual component's rendered structure; browser gestures,
// focus, field commits and actual pixels still require the browser walkthrough.
