import test from 'node:test';
import assert from 'node:assert/strict';
import { createInputObserver } from '../scripts/m4_input_observer.mjs';

// A small, hand-authored DOM surface exercises the actual observer's trigger
// decision. It deliberately has no Studio state, renderer or dispatch function.
function surface({ tool = 'select', pressed = false, kind = 'viewport', inCanvas = true, control = false, editing = false } = {}) {
  let now = 1;
  const listeners = new Map();
  const rect = { x: 230, y: 115, width: 500, height: 400 };
  const matrix = { a: 1, b: 0, c: 0, d: 1, e: 100, f: 40 };
  class Element {
    constructor(attributes = {}) { this.attributes = attributes; }
    getAttribute(name) { return this.attributes[name] ?? null; }
    closest(selector) {
      if (selector === '.canvas-viewport') return inCanvas ? viewport : null;
      if (selector === 'button') return control ? new Element({ 'aria-label': '适合画布' }) : null;
      if (selector === 'input,textarea,select,[contenteditable]') return editing ? this : null;
      if (selector === '[data-expand-id]' && kind === 'toggle') return new Element({ 'data-expand-id': 'node:A' });
      if (selector === '[data-canonical-id]' && ['node', 'port', 'toggle'].includes(kind)) return new Element({ 'data-node-id': 'node:A' });
      if (selector === '[data-port-id]' && kind === 'port') return new Element({ 'data-port-id': 'node:A:in' });
      return null;
    }
  }
  const viewport = new Element({ 'data-canvas-tool': tool });
  viewport.getBoundingClientRect = () => rect;
  const button = new Element({ 'aria-pressed': String(pressed) });
  const svg = new Element({ 'data-document-id': 'canvas-observer-trigger', 'data-revision': '3' });
  svg.outerHTML = '<svg data-document-id="canvas-observer-trigger"/>';
  svg.querySelector = selector => selector === 'metadata'
    ? { textContent: JSON.stringify({ sourceDigest: 'a'.repeat(64), irDigest: 'b'.repeat(64) }) } : null;
  svg.querySelectorAll = () => [];
  const host = { querySelector: () => svg, dataset: { expandedIds: '[]', pinnedIds: '[]' } };
  const document = {
    querySelector: selector => selector === '.publication-scene' ? host : selector === '.paper' ? {} : selector === '.canvas-viewport' ? viewport
      : selector === '.canvas-toolbar button[aria-label="平移画布"]' ? button : null,
    querySelectorAll: () => [], visibilityState: 'visible', hasFocus: () => true, scripts: [],
    fonts: Object.assign([], { status: 'loaded' }), addEventListener() {}, removeEventListener() {},
  };
  const window = {
    document, Element, performance: { now: () => now++, timeOrigin: 1_000_000 },
    DOMMatrixReadOnly: class { constructor() { Object.assign(this, matrix); } },
    getComputedStyle: () => ({ transform: 'matrix(1,0,0,1,100,40)' }), requestAnimationFrame: () => 1,
    cancelAnimationFrame() {}, location: { href: 'http://localhost/studio' }, navigator: { userAgent: 'authored-test' },
    innerWidth: 500, innerHeight: 400, devicePixelRatio: 1, frameElement: null, CSS: { escape: value => value },
    addEventListener(type, handler) {
      const list = listeners.get(type) ?? []; list.push(handler); listeners.set(type, list);
    }, removeEventListener() {},
  };
  window.parent = window;
  function emit(type, overrides = {}) {
    const event = { type, target: new Element(), isTrusted: true, timeStamp: now, pointerId: 1, pointerType: 'mouse',
      button: 0, buttons: 1, clientX: 350, clientY: 250, ...overrides };
    for (const handler of listeners.get(type) ?? []) handler(event);
  }
  return { window, emit, viewport, button };
}
function observe(config, operation = 'pan', before = () => {}) {
  const fake = surface(config), observer = createInputObserver(fake.window);
  observer.start({ label: 'trigger authored DOM' });
  before(fake);
  observer.arm({ operation, targetIds: operation === 'drag' ? ['node:A'] : [] });
  fake.emit('pointerdown');
  observer.finishTrial();
  return observer.stop();
}

test('observer v2 starts left pan only when both public tool controls report active', () => {
  const good = observe({ tool: 'pan', pressed: true });
  assert.equal(good.protocol, 'archcanvas-input-observation/2');
  assert.equal(good.trials[0].status, 'finished');
  assert.equal(good.events[0].target.canvasTool, 'pan');
  assert.equal(good.events[0].target.handToolPressed, true);
  assert.deepEqual(good.events[0].viewport, { x: 230, y: 115, width: 500, height: 400 });
  assert.equal(good.trials[0].before.svgMarkup, '<svg data-document-id="canvas-observer-trigger"/>');
  for (const config of [{ tool: 'select', pressed: false }, { tool: 'pan', pressed: false }, { tool: 'select', pressed: true }]) {
    assert.equal(observe(config).trials[0].status, 'no-input');
  }
});

test('observer routes hand input on expand/port to pan and never to armed object drag', () => {
  for (const kind of ['node', 'port', 'toggle']) {
    assert.equal(observe({ tool: 'pan', pressed: true, kind }).trials[0].status, 'finished');
  }
  assert.equal(observe({ tool: 'pan', pressed: true, kind: 'node' }, 'drag').trials[0].status, 'no-input');
  assert.equal(observe({ tool: 'select', pressed: false, kind: 'node' }, 'drag').trials[0].status, 'finished');
});

test('observer will not classify toolbar/HTML controls as a canvas pan', () => {
  assert.equal(observe({ tool: 'pan', pressed: true, inCanvas: false }).trials[0].status, 'no-input');
  assert.equal(observe({ tool: 'pan', pressed: true, control: true }).trials[0].status, 'no-input');
});

test('observer Space-left pan clears its held flag on blur', () => {
  assert.equal(observe({}, 'pan', fake => fake.emit('keydown', { code: 'Space', key: ' ' })).trials[0].status, 'finished');
  const afterBlur = observe({}, 'pan', fake => {
    fake.emit('keydown', { code: 'Space', key: ' ' });
    fake.emit('blur', { target: fake.window });
  });
  assert.equal(afterBlur.trials[0].status, 'no-input');
  assert.equal(afterBlur.events.find(e => e.type === 'pointerdown').spaceHeld, false);
});

test('observer does not treat descendant blur as a cancelled window or typed Space as navigation', () => {
  const internalBlur = observe({ tool: 'pan', pressed: true }, 'pan', fake => fake.emit('blur'));
  assert.equal(internalBlur.events.some(e => e.type === 'blur'), false);
  const typed = observe({ editing: true }, 'pan', fake => fake.emit('keydown', { code: 'Space', key: ' ' }));
  assert.equal(typed.trials[0].status, 'no-input');
  assert.equal(typed.events.find(e => e.type === 'pointerdown').spaceHeld, false);
});
