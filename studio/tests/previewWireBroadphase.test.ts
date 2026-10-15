import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

type Point = { x: number; y: number };
type SegmentContact = (a: Point, b: Point, c: Point, d: Point) => boolean;
function contact(path: URL): SegmentContact {
  const source = readFileSync(path, 'utf8');
  assert.ok(source.includes('const api = { routeEdge,'));
  const context = vm.createContext({});
  vm.runInContext(source.replace('const api = { routeEdge,', 'const api = { wireContact, routeEdge,'), context);
  return context.EdgeRouterLabRouting.wireContact;
}
const current = contact(new URL('../public/preview/yworks_edge_router_lab/router.js', import.meta.url));
const original = contact(new URL('../../docs/evidence/act-source-support-20261015/routing-performance/before/router.js', import.meta.url));

test('short near-parallel segments retain the original fuzzy contact beyond an EPS-wide envelope', () => {
  const a = { x: .0025, y: .00001 }, b = { x: .0075, y: .00001 }, c = { x: 0, y: 0 }, d = { x: .01, y: 0 };
  assert.equal(original(a, b, c, d), true, 'the frozen reference establishes the short-segment contract');
  for (const first of [[a, b], [b, a]]) for (const second of [[c, d], [d, c]]) {
    assert.equal(current(first[0], first[1], second[0], second[1]), true);
    assert.equal(current(second[0], second[1], first[0], first[1]), true);
  }
});

test('line-contact predicate matches the frozen reference at tiny, normal and large scales, including degenerate segments', () => {
  let seed = 20261015, checked = 0;
  const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296);
  const compare = (points: Point[]) => {
    const [a, b, c, d] = points;
    assert.equal(current(a, b, c, d), original(a, b, c, d), JSON.stringify(points)); checked++;
  };
  for (let i = 0; i < 30000; i++) {
    const scale = 10 ** (random() * 8 - 5), angle = random() * Math.PI * 2,
      x = (random() - .5) * 1000, y = (random() - .5) * 1000;
    const transform = (p: Point) => ({ x: x + (p.x * Math.cos(angle) - p.y * Math.sin(angle)) * scale,
      y: y + (p.x * Math.sin(angle) + p.y * Math.cos(angle)) * scale });
    let a: Point, b: Point, c: Point, d: Point;
    if (i % 3 === 0) {
      const length = .1 + random() * 10, offset = (random() - .5) * 50e-6 / scale;
      a = { x: length * .2, y: offset }; b = { x: length * .8, y: offset };
      c = { x: 0, y: 0 }; d = { x: length, y: 0 };
    } else {
      a = { x: random() * 10, y: random() * 10 }; b = { x: random() * 10, y: random() * 10 };
      c = { x: random() * 10, y: random() * 10 }; d = { x: random() * 10, y: random() * 10 };
      if (i % 5 === 0) b = { ...a };
      if (i % 7 === 0) c = { ...b };
      if (i % 11 === 0) d = { ...c };
    }
    compare([a, b, c, d].map(transform));
  }
  for (const scale of [.001, .01, .1, 1, 10, 1000]) for (let turn = 0; turn < 4; turn++) for (const offset of [0, 100]) {
    const transform = (p: Point) => {
      for (let n = 0; n < turn; n++) p = { x: -p.y, y: p.x };
      return { x: p.x * scale + offset, y: p.y * scale - offset };
    };
    for (const gap of [0, .5e-6, 1e-6, 2e-6, 10e-6, .001])
      compare([{ x: .25, y: gap }, { x: .75, y: gap }, { x: 0, y: 0 }, { x: 1, y: 0 }].map(transform));
  }
  assert.equal(checked, 30288);
});
