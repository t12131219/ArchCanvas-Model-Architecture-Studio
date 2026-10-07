import test from 'node:test';
import assert from 'node:assert/strict';
import { applyVisualBatch, buildScene, createDocument, renderSvg } from '../src/core/index.ts';
import type { Architecture } from '../src/core/types.ts';
import { textWidth, wrapText } from '../src/core/typography.ts';

const cnn = 'Each residual block combines transformed features with its skip path.';
const cnnLines = ['Each residual block combines transformed features with its skip', 'path.'];

test('the actual CNN sentence breaks before path instead of splitting a fitting word', () => {
  assert.deepEqual(wrapText(cnn, 360, 11), cnnLines);
  // Independently calculated widths from the published .56/.32 ASCII advances.
  assert.ok(Math.abs(textWidth(cnnLines[0], 11) - 348.48) < 1e-9);
  assert.ok(Math.abs(textWidth(cnnLines[1], 11) - 28.16) < 1e-9);
  assert.deepEqual(wrapText('xx elephant', 44.8, 10), ['xx', 'elephant']);
  assert.deepEqual(wrapText('cross-attention context', 84, 10), ['cross-attention', 'context']);
});

test('CJK characters and whole English tokens can share lines without inserted text', () => {
  assert.deepEqual(wrapText('中文 linear 层', 43, 10), ['中文', 'linear 层']);
  assert.deepEqual(wrapText('AB中文CD', 22, 10), ['AB中', '文CD']);
  assert.deepEqual(wrapText('编码Encoder解码Decoder', 45, 10), ['编码', 'Encoder', '解码', 'Decoder']);
  assert.deepEqual(wrapText('甲乙丙丁', 20, 10), ['甲乙', '丙丁']);
});

test('explicit line breaks and blank lines remain while soft line boundaries discard whitespace', () => {
  assert.deepEqual(wrapText('ab\n\ncd\n', 100, 10), ['ab', '', 'cd', '']);
  assert.deepEqual(wrapText('ab\r\n\r\ncd\r', 100, 10), ['ab', '', 'cd', '']);
  assert.deepEqual(wrapText('', 100), ['']);
  assert.deepEqual(wrapText('  alpha  beta  ', 100, 10), ['alpha  beta']);
  assert.deepEqual(wrapText('alpha   beta', 30, 10), ['alpha', 'beta']);
  assert.deepEqual(wrapText(' \t\n \t', 100, 10), ['', '']);
});

test('oversized source identifiers have finite code-point fallback without dropping characters', () => {
  assert.deepEqual(wrapText('abcdefghijk', 30, 10), ['abcde', 'fghij', 'k']);
  const identifier = 'call:instance:model.Transformer.encoder.0.feedforward.activation';
  const rows = wrapText(identifier, 45, 10);
  assert.equal(rows.join(''), identifier);
  assert.ok(rows.length > 1 && rows.length <= [...identifier].length);
  assert.ok(rows.every(row => row.length > 0 && textWidth(row, 10) <= 45));
  // A long single identifier exercises progress without a timing-sensitive benchmark.
  const long = 'q'.repeat(12_000);
  const longRows = wrapText(long, 28, 10);
  assert.equal(longRows.length, 2_400);
  assert.equal(longRows.join(''), long);
  assert.ok(longRows.every(row => row === 'qqqqq'));
});

test('Unicode code points stay intact and an individually oversized point still makes progress', () => {
  assert.deepEqual(wrapText('😀😀', 10, 10), ['😀', '😀']);
  assert.deepEqual(wrapText('😀elephant', 44.8, 10), ['😀', 'elephant']);
  assert.deepEqual(wrapText('𠮷野家', 20, 10), ['𠮷野', '家']);
  assert.deepEqual(wrapText('😀A中', 1, 10), ['😀', 'A', '中']);
  assert.deepEqual(wrapText('éé', 10, 10), ['é', 'é']);
  for (const width of [0, -1]) assert.deepEqual(wrapText('word', width), ['w', 'o', 'r', 'd']);
  for (const width of [NaN, Infinity]) assert.throws(() => wrapText('word', width), RangeError);
  for (const size of [0, -1, NaN, Infinity]) assert.throws(() => wrapText('word', 100, size), RangeError);
});

function model(): Architecture {
  return { schemaVersion: 1, id: 'architecture:typography', label: 'Typography geometry', entry: 'oracle:Model',
    sourceDigest: 'typography-source', irDigest: 'typography-ir', sources: [], diagnostics: [],
    nodes: [{ id: 'root', label: 'Model', kind: 'Model', category: 'container', children: ['leaf'], ports: [], parameters: {}, evidence: 'source' },
      { id: 'leaf', label: 'Layer', kind: 'Linear', category: 'linear', parentId: 'root', children: [], ports: [], parameters: {}, evidence: 'source' }], edges: [] };
}

test('Scene annotation height and both SVG modes use the independently expected CNN lines', () => {
  const document = applyVisualBatch(createDocument(model()), [
    { type: 'annotation', annotation: { id: 'cnn-note', text: cnn, x: 50, y: 800, width: 380 } },
  ]);
  const before = JSON.stringify(document), scene = buildScene(document);
  const annotation = scene.annotations.find(item => item.id === 'cnn-note')!;
  assert.equal(annotation.height, 50); // Two independent expected rows ×15 +20.
  assert.ok(scene.bounds.y + scene.bounds.height >= 870);
  const expected = '<text x="60" y="820" fill="#827453" font-size="11"><tspan x="60" dy="0">Each residual block combines transformed features with its skip</tspan><tspan x="60" dy="15">path.</tspan></text>';
  for (const interactive of [false, true]) {
    const svg = renderSvg(scene, { interactive });
    assert.ok(svg.includes('<rect x="50" y="800" width="380" height="50"'));
    assert.ok(svg.includes(expected));
    assert.equal((svg.match(/>path\.<\/tspan>/g) ?? []).length, 1);
    assert.ok(!svg.includes('>ath.</tspan>'));
  }
  assert.equal(JSON.stringify(document), before);
});

test('a valid annotation narrower than its text inset still builds and renders', () => {
  const document = applyVisualBatch(createDocument(model()), [
    { type: 'annotation', annotation: { id: 'narrow-note', text: '中A', x: 50, y: 800, width: 10 } },
  ]);
  const scene = buildScene(document), annotation = scene.annotations.find(item => item.id === 'narrow-note')!;
  assert.equal(annotation.width, 10);
  assert.equal(annotation.height, 50); // No usable inset width: two code points still make progress.
  for (const interactive of [false, true]) {
    const svg = renderSvg(scene, { interactive });
    assert.ok(svg.includes('<rect x="50" y="800" width="10" height="50"'));
    assert.ok(svg.includes('<tspan x="60" dy="0">中</tspan><tspan x="60" dy="15">A</tspan>'));
  }
});
