import test from 'node:test';
import assert from 'node:assert/strict';
import { draftCanvasTextScale, draftFittedText } from '../src/draftTextReadability.ts';
import { draftPortPresentation } from '../src/draftPortPresentation.ts';
import { placeDraftTooltip } from '../src/draftTooltipPlacement.ts';
import type { DraftTooltipAnchor, DraftTooltipRect, DraftTooltipSize } from '../src/draftTooltipPlacement.ts';
import type { DraftPort } from '../src/authoring.ts';

// Hand-authored geometry expectations, not the product's candidate selection
// score or snapshots. These tests do not certify browser font fallback/pixels.
function intersects(a: DraftTooltipRect, b: DraftTooltipRect) {
  return Math.min(a.x + a.width, b.x + b.width) > Math.max(a.x, b.x)
    && Math.min(a.y + a.height, b.y + b.height) > Math.max(a.y, b.y);
}
function placed(anchor: DraftTooltipAnchor, size: DraftTooltipSize, viewport: { width: number; height: number }, nodes?: readonly DraftTooltipRect[]) {
  const before = JSON.stringify([anchor, size, viewport, nodes]);
  const position = placeDraftTooltip(anchor, size, viewport, nodes);
  assert.equal(JSON.stringify([anchor, size, viewport, nodes]), before, 'feedback placement must not edit camera/node geometry');
  const rect = { x: position.left, y: position.top, ...size };
  assert.ok(Number.isFinite(rect.x) && Number.isFinite(rect.y));
  assert.ok(rect.x >= 12 && rect.y >= 12, 'within viewport inset');
  assert.ok(rect.x + rect.width <= viewport.width - 12, 'right viewport inset');
  assert.ok(rect.y + rect.height <= viewport.height - 12, 'bottom viewport inset');
  return { position, rect };
}
const port = (name: string, direction: 'in' | 'out'): DraftPort => ({ id: name, name, direction, type: 'tensor' });

test('independent compensation supports a 58percent overview without claiming readable minimum zoom', () => {
  const overview = draftCanvasTextScale(.58);
  assert.ok(overview >= 1 && overview <= 1.8);
  assert.ok(9 * overview * .58 >= 8, 'sampled single port text exceeds8 CSSpx');
  for (const zoom of [.15, .4, .58, 1, 3]) {
    const compensation = draftCanvasTextScale(zoom);
    assert.ok(Number.isFinite(compensation) && compensation >= 1 && compensation <= 1.8);
  }
  assert.equal(draftCanvasTextScale(1), 1);
  assert.equal(draftCanvasTextScale(3), 1);
  assert.ok(9 * draftCanvasTextScale(.15) * .15 < 6, 'minimum zoom remains an explicit local-readability limit');
});

test('independent CJK title fitting prevents the original234world-wide truncated title', () => {
  const original = '特征编码特征编码特征编码特征编码特征编码';
  for (const size of [13, 13 * draftCanvasTextScale(.58), 23.4]) {
    const value = draftFittedText(original, size, 134);
    assert.ok(value.endsWith('…'));
    assert.ok(original.startsWith(value.slice(0, -1)), 'only trailing text is omitted');
    // In this all-CJK sample, each visible code point is one em, including….
    assert.ok([...value].length * size <= 134 + 1e-9, 'title stays before the badge reserve');
  }
  assert.equal(original, '特征编码特征编码特征编码特征编码特征编码');
});

test('independent fitting retains a short label, empty string and Unicode code points', () => {
  assert.equal(draftFittedText('GELU', 13, 134), 'GELU');
  assert.equal(draftFittedText('', 13, 134), '');
  const original = '🧠🧠🧠🧠🧠🧠🧠🧠';
  const label = draftFittedText(original, 23.4, 134);
  assert.ok(label.endsWith('…'));
  assert.ok([...label].length * 23.4 <= 134 + 1e-9);
  assert.ok(original.startsWith(label.slice(0, -1)));
  assert.equal(/(?:[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF])/u.test(label), false, 'no unpaired surrogate');
});

test('independent mono samples fit150world using equal ASCII columns rather than narrow punctuation', () => {
  for (const original of ['AdaptiveAvgPool2d', '声明 [1,3,224,224,224]', '声明 [1000000,1000000,1000000,1000000]']) {
    const value = draftFittedText(original, 18, 150, true);
    assert.ok(value.endsWith('…'));
    assert.ok(original.startsWith(value.slice(0, -1)));
    const points = [...value], ascii = points.filter(char => char.codePointAt(0)! <= 255).length;
    const nonAscii = points.length - ascii;
    // A0.6em mono column is a separate hand-written conservative browser-font
    // estimate, not the previous product i/comma/space0.32em approximation.
    assert.ok((ascii * .6 + nonAscii) * 18 <= 150 + 1e-9);
  }
  assert.equal(draftFittedText('声明 [1,16]', 10, 150, true), '声明 [1,16]');
});

test('independent wide-Latin title fitting stays inside134world even for repeated W', () => {
  const original = 'WWWWWWWWWWWWWWWWWWWW';
  const shown = draftFittedText(original, 23.4, 134);
  assert.ok(original.startsWith(shown.slice(0, -1)));
  assert.ok(shown.endsWith('…'));
  assert.ok([...shown].length * 23.4 <= 134 + 1e-9, 'W andellipsis have a one-em upper advance');
});

test('independent scaled single-port hits contain both label endpoints and the dot', () => {
  // Hand-summed registered ASCII estimates: input is2.56em, output3.36em.
  // These are geometry-model estimates, not measured browser glyph advances.
  // Testing fixed samples avoids using the product's textWidth as an oracle.
  for (const size of [9, 9 * draftCanvasTextScale(.58), 16.2]) {
    for (const [name, direction, x, advance] of [
      ['input', 'in', 0, 2.56], ['output', 'out', 176, 3.36],
    ] as const) {
      const presentation = draftPortPresentation(port(name, direction), x, 66, 'horizontal', Infinity, size);
      const labelLeft = direction === 'in' ? presentation.labelX : presentation.labelX - advance * size;
      const labelRight = direction === 'in' ? presentation.labelX + advance * size : presentation.labelX;
      assert.ok(presentation.hit.x <= Math.min(x - 5, labelLeft));
      assert.ok(presentation.hit.x + presentation.hit.width >= Math.max(x + 5, labelRight));
      assert.ok(presentation.hit.y <= 61 && presentation.hit.y + presentation.hit.height >= 71);
    }
  }
});

test('independent horizontal merge port names stay inside12world slots when overview text is enlarged', () => {
  const tops = [60, 72], names = ['left', 'right'];
  const rows = tops.map((y, index) => draftPortPresentation(port(names[index], 'in'), 0, y, 'horizontal', 12, 16.2));
  for (const [index, row] of rows.entries()) {
    assert.ok(row.labelFontSize > 0 && row.labelFontSize <= 9, 'text fits its narrow merge slot');
    // One-em line box with the returned baseline: the visible title is not
    // allowed to intrude into the neighboring peer slot.
    const textTop = row.labelY - row.labelFontSize;
    const textBottom = row.labelY;
    assert.ok(textTop >= tops[index] - 6 - 1e-9);
    assert.ok(textBottom <= tops[index] + 6 + 1e-9);
    assert.ok(row.hit.y <= tops[index] - 5 && row.hit.y + row.hit.height >= tops[index] + 5);
  }
  assert.ok(rows[0].hit.y + rows[0].hit.height <= rows[1].hit.y, 'transparentpeer hits do not compete');
});

test('independent vertical registered merge labels do not paint into the later port hit', () => {
  const first = draftPortPresentation(port('left', 'in'), 176 / 3, 0, 'vertical', 176 / 3, 16.2);
  const next = draftPortPresentation(port('right', 'in'), 352 / 3, 0, 'vertical', 176 / 3, 16.2);
  // The hand-summed sans four-letter left sample is2em. It must remain before
  // the later transparent hit, which would otherwise intercept those pixels.
  assert.ok(first.labelX + 2 * first.labelFontSize <= next.hit.x);
  assert.ok(first.hit.x + first.hit.width <= next.hit.x);
  // Peer clamping does not promise one rectangular hit covers all vertical
  // label paint; text itself receives pointer events in the current Studio.
});

test('independent tooltip avoids the downstream card instead of covering its label', () => {
  const source = { x: 200, y: 200, width: 176, height: 100 };
  const downstream = { x: 420, y: 200, width: 176, height: 100 };
  const { rect } = placed({ port: { x: 376, y: 266 }, node: source, direction: 'out', flow: 'horizontal' },
    { width: 230, height: 110 }, { width: 900, height: 600 }, [source, downstream]);
  assert.equal(intersects(rect, source), false);
  assert.equal(intersects(rect, downstream), false);
});

test('independent58percent chain tooltip does not cover any of four scaled cards', () => {
  const camera = { x: 30, y: 40, zoom: .58 };
  const nodes = [50, 320, 590, 860].map(x => ({ x: camera.x + x * camera.zoom, y: camera.y + 100 * camera.zoom, width: 176 * camera.zoom, height: 100 * camera.zoom }));
  const anchor = { node: nodes[1], port: { x: nodes[1].x + nodes[1].width, y: nodes[1].y + 66 * camera.zoom }, direction: 'out', flow: 'horizontal' } as const;
  const { rect } = placed(anchor, { width: 230, height: 110 }, { width: 600, height: 550 }, nodes);
  for (const node of nodes) assert.equal(intersects(rect, node), false);
});

test('independent vertical input tooltip avoids an upstream card with a free side', () => {
  const node = { x: 300, y: 300, width: 176, height: 100 };
  const upstream = { x: 300, y: 130, width: 176, height: 100 };
  const { rect } = placed({ node, port: { x: 388, y: 300 }, direction: 'in', flow: 'vertical' },
    { width: 230, height: 110 }, { width: 900, height: 600 }, [node, upstream]);
  assert.equal(intersects(rect, node), false);
  assert.equal(intersects(rect, upstream), false);
});

test('independent edge clamp uses a visible free side without intruding into its owner', () => {
  for (const [node, portAt, direction] of [
    [{ x: 8, y: 8, width: 176, height: 100 }, { x: 96, y: 8 }, 'in'],
    [{ x: 710, y: 490, width: 176, height: 100 }, { x: 798, y: 590 }, 'out'],
  ] as const) {
    const { rect } = placed({ node, port: portAt, direction, flow: 'vertical' },
      { width: 230, height: 110 }, { width: 900, height: 600 });
    assert.equal(intersects(rect, node), false);
  }
});

test('independent no-clear-region fallback remains bounded and does not alter obstacles', () => {
  const node = { x: 200, y: 120, width: 176, height: 100 };
  const curtain = { x: 12, y: 12, width: 576, height: 336 };
  placed({ node, port: { x: 376, y: 186 }, direction: 'out', flow: 'horizontal' },
    { width: 230, height: 110 }, { width: 600, height: 360 }, [node, curtain]);
  // A viewport-filling obstacle makes zero overlap impossible. No inference of
  // universal no-occlusion or aesthetically optimal placement follows here.
});
