import test from 'node:test';
import assert from 'node:assert/strict';
import { draftCanvasTextScale } from '../src/draftTextReadability.ts';
import { placeDraftTooltip } from '../src/draftTooltipPlacement.ts';

test('overview text compensation is bounded and leaves normal zoom unchanged', () => {
  assert.equal(draftCanvasTextScale(1), 1);
  assert.equal(draftCanvasTextScale(0.58), 0.9 / 0.58);
  assert.equal(draftCanvasTextScale(0.1), 1.8);
  assert.equal(draftCanvasTextScale(Number.NaN), 1.8);
});

test('horizontal input and output hints prefer opposite sides of their node', () => {
  const node = { x: 400, y: 120, width: 176, height: 100 };
  const input = placeDraftTooltip({ port: { x: 400, y: 170 }, node, direction: 'in', flow: 'horizontal' }, { width: 256, height: 114 }, { width: 900, height: 600 });
  const output = placeDraftTooltip({ port: { x: 576, y: 170 }, node, direction: 'out', flow: 'horizontal' }, { width: 256, height: 114 }, { width: 900, height: 600 });
  assert.equal(input.side, 'left');
  assert.equal(output.side, 'right');
  assert.ok(input.left + 256 <= node.x);
  assert.ok(output.left >= node.x + node.width);
});

test('vertical hints fall back to a visible, non-overlapping side near viewport edges', () => {
  const node = { x: 8, y: 8, width: 176, height: 100 };
  const position = placeDraftTooltip({ port: { x: 96, y: 8 }, node, direction: 'in', flow: 'vertical' }, { width: 220, height: 100 }, { width: 500, height: 300 });
  assert.ok(position.left >= 12 && position.top >= 12);
  assert.ok(position.left + 220 <= 488);
  assert.ok(position.top + 100 <= 288);
  const overlaps = position.left < node.x + node.width && position.left + 220 > node.x && position.top < node.y + node.height && position.top + 100 > node.y;
  assert.equal(overlaps, false);
});
