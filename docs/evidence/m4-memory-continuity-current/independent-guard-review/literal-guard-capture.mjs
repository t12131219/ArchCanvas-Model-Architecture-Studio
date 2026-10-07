import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const owner = path.join(root, 'docs/evidence/m4-memory-continuity-current/independent-guard-review');
const attempt = process.argv[2];
if (!attempt || !/^literal-attempt-[1-9][0-9]*$/.test(attempt)) throw new Error('An append-only literal-attempt-N argument is required');
const output = path.join(owner, attempt);
if (existsSync(output)) throw new Error('Do not overwrite existing evidence');
const bindings = ['studio/src/core/memoryContinuity.ts', 'studio/src/core/scene.ts',
  'studio/src/core/nodeVisualOutline.ts', 'studio/src/core/edgePresentation.ts', 'studio/src/core/types.ts',
  'docs/evidence/m4-memory-continuity-current/independent-guard-review/literal-guard-capture.mjs'].map(rel => {
  const bytes = readFileSync(path.join(root, rel));
  return { path: rel, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') };
});
const { projectMemoryContinuity, MEMORY_CONTINUITY_BUDGET } = await import(path.join(root, 'studio/src/core/memoryContinuity.ts'));
const clone = input => structuredClone(input), p = (x, y) => ({ x, y });
function node(id, x, y, extra = {}) {
  return { id, x, y, width: 100, height: 100, localX: x, localY: y, headerHeight: 20,
    label: id, subtitle: '', kind: 'Block', category: 'container', fill: '#fff', stroke: '#000', glyph: 'box',
    expanded: false, expandable: true, pinned: false, evidence: 'source', ports: [], ...extra };
}
const memory = (extra = {}) => ({ sourceId: 'a', targetId: 'b', start: p(50, 100), end: p(210, 10), preferredPath: '',
  tensorId: 't', role: 'memory', appearance: { stroke: '#000', width: 2, dashed: false },
  canonicalEdgeIds: ['memory'], canonicalSource: { nodeId: 'a', portId: 'out' }, ...extra });
const baseline = (points = [p(50,100), p(50,130), p(240,130), p(240,-20), p(210,-20), p(210,10)]) =>
  ({ points, path: points.map((point, i) => i === 0 ? `M ${point.x} ${point.y}` : point.x === points[i-1].x ? `V ${point.y}` : `H ${point.x}`).join(' '), changed: false, blockedBy: [] });
const base = () => ({ nodes: [node('a',0,0), node('b',160,10)], requests: [memory()], baseline: [baseline()] });
const peer = (points, extra = {}) => ({ request: { sourceId: 'peer-source', targetId: 'peer-target', start: points[0], end: points.at(-1),
  preferredPath: '', tensorId: 'peer-tensor', role: 'data', appearance: { stroke: '#000', width: 2, dashed: false }, ...extra }, result: baseline(points) });
const rows = [];
function run(name, state, expected, options = {}) {
  const before = structuredClone(state);
  let actual, thrown;
  try { actual = projectMemoryContinuity(state.nodes, state.requests, state.baseline, options.limits ?? MEMORY_CONTINUITY_BUDGET); }
  catch (error) { thrown = String(error); }
  const accepted = actual ? [...actual].map(([index, proposal]) => ({ index, ...proposal })) : null;
  const expectedIds = expected.map(e => e.index);
  const relations = {
    doesNotThrow: !thrown,
    acceptedIdsExact: accepted !== null && JSON.stringify(accepted.map(e => e.index)) === JSON.stringify(expectedIds),
    expectedGeometryExact: accepted !== null && JSON.stringify(accepted) === JSON.stringify(expected),
    inputUnchanged: identical(state, before),
    deterministic: actual ? identical([...projectMemoryContinuity(before.nodes, before.requests, before.baseline, options.limits ?? MEMORY_CONTINUITY_BUDGET)], [...actual]) : false,
  };
  rows.push({ name, input: serialize(state), limits: options.limits ?? MEMORY_CONTINUITY_BUDGET, expected, actual: accepted, thrown: thrown ?? null,
    relations, passed: Object.values(relations).every(Boolean) });
}
function serialize(value) {
  if (typeof value === 'number' && !Number.isFinite(value)) return { nonFinite: String(value) };
  if (Array.isArray(value)) return value.map(serialize);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v]) => [k,serialize(v)]));
  return value;
}
const identical = (a,b) => JSON.stringify(serialize(a)) === JSON.stringify(serialize(b));
const positive = [{ index: 0, start: p(100,55), end: p(160,65), points: [p(100,55),p(130,55),p(130,65),p(160,65)], path: 'M 100 55 H 130 V 65 H 160' }];
run('isolated-HVH-positive', base(), positive);
let state = base(); state.nodes[1].y = 0; state.nodes[1].localY = 0;
run('equal-y-straight-positive', state, [{ index:0, start:p(100,55), end:p(160,55), points:[p(100,55),p(160,55)], path:'M 100 55 H 160' }]);
for (const [name, points] of [
  ['joint-only', [p(130,30),p(130,55),p(145,55)]],
  ['whole-peer-endpoint', [p(130,55),p(130,30)]],
  ['collinear-shared-span', [p(110,55),p(115,55),p(120,55)]],
  ['collinear-retraced-span', [p(110,55),p(120,55),p(115,55),p(125,55)]],
  ['near-stroke-no-centerline-contact', [p(110,56.9),p(120,56.9)]],
  ['exact-stroke-tangent', [p(110,57),p(120,57)]],
]) for (const sameTensor of [false,true]) {
  state = base(); const q = peer(points, sameTensor ? { tensorId:'t', canonicalSource:{nodeId:'a',portId:'out'}, role:'memory' } : {});
  state.requests.push(q.request); state.baseline.push(q.result);
  run(`${name}-${sameTensor ? 'same-tensor-and-source' : 'unrelated'}`, state, []);
}
state = base(); { const q = peer([p(110,57.01),p(120,57.01)]); state.requests.push(q.request); state.baseline.push(q.result); }
run('stroke-separation-positive-2.01', state, positive);
for (const [name, bad] of [['zero',0],['negative',-1],['NaN',NaN],['positive-infinity',Infinity],['negative-infinity',-Infinity],['missing',undefined]]) {
  for (const target of ['candidate','peer']) {
    state=base();
    if (target==='peer') { const q=peer([p(0,-50),p(300,-50)]); q.request.appearance.width=bad; state.requests.push(q.request);state.baseline.push(q.result); }
    else state.requests[0].appearance.width=bad;
    run(`invalid-${target}-width-${name}`,state,[]);
  }
}
for (const [name, obstruction] of [
  ['unrelated-gap-body',node('c',126,56,{width:8,height:8})],
  ['unrelated-expanded-full-body',node('c',125,30,{width:10,height:50,expanded:true,headerHeight:10})],
  ['repeat-backplate-only',node('c',119,54,{width:6,height:6,repeat:{count:2}})],
]) { state=base();state.nodes.push(obstruction);run(name,state,[]); }
state=base();state.nodes.push(node('owner',-20,50,{width:300,height:200,expanded:true,headerHeight:10}));
state.nodes[0].parentId='owner';state.nodes[1].parentId='owner';run('shared-ancestor-header-obstruction',state,[]);
state=base();state.nodes.push(node('owner',-20,-40,{width:300,height:220,expanded:true,headerHeight:10}));
state.nodes[0].parentId='owner';state.nodes[1].parentId='owner';run('shared-ancestor-interior-positive',state,positive);
state=base();state.nodes[0].repeat={count:2};
run('repeat-exposed-right-positive',state,[{index:0,start:p(107,55),end:p(160,65),points:[p(107,55),p(133.5,55),p(133.5,65),p(160,65)],path:'M 107 55 H 133.5 V 65 H 160'}]);
state=base();state.nodes[0].repeat={count:2};state.nodes[0].height=10;state.nodes[1].height=10;
run('short-repeat-ray-near-plate-positive',state,[{index:0,start:p(103.5,5.5),end:p(160,15.5),points:[p(103.5,5.5),p(131.75,5.5),p(131.75,15.5),p(160,15.5)],path:'M 103.5 5.5 H 131.75 V 15.5 H 160'}]);
for (const gap of [11.99,12,12.01,15.49,15.5,15.51]) {
  state=base();state.nodes[1].x=100+gap;state.nodes[1].localX=100+gap;
  const expectedCoordinates={11.99:[111.99,106],12:[112,106],12.01:[112.01,106.01],15.49:[115.49,107.75],15.5:[115.5,107.75],15.51:[115.51,107.76]};
  const [end,lane]=expectedCoordinates[gap];
  const expected=gap<12?[]:[{index:0,start:p(100,55),end:p(end,65),points:[p(100,55),p(lane,55),p(lane,65),p(end,65)],path:`M 100 55 H ${lane} V 65 H ${end}`}];
  run(`gap-with-own-padding-${gap}`,state,expected);
}
for (const [name, change] of [
  ['expanded-source',s=>s.nodes[0].expanded=true], ['expanded-target',s=>s.nodes[1].expanded=true],
  ['no-shared-band',s=>s.nodes[1].y=120], ['missing-source',s=>s.requests[0].sourceId='missing'],
  ['missing-parent',s=>s.nodes[0].parentId='missing'], ['self-parent-cycle',s=>s.nodes[0].parentId='a'],
  ['two-parent-cycle',s=>{s.nodes[0].parentId='b';s.nodes[1].parentId='a'}],
  ['zero-height',s=>s.nodes[0].height=0], ['negative-width',s=>s.nodes[0].width=-1],
  ['NaN-coordinate',s=>s.nodes[0].x=NaN], ['infinite-height',s=>s.nodes[0].height=Infinity],
  ['invalid-baseline-nonorthogonal',s=>s.baseline[0].points=[p(0,0),p(1,1)]],
  ['invalid-baseline-nonfinite',s=>s.baseline[0].points=[p(0,0),p(0,Infinity)]],
  ['invalid-baseline-repeated-point',s=>s.baseline[0].points=[p(0,0),p(0,0)]],
  ['already-blocked-baseline',s=>s.baseline[0].blockedBy=['owner']],
  ['too-short-baseline',s=>s.baseline[0]=baseline([p(100,55),p(105,55)])],
  ['baseline-route-count-mismatch',s=>s.baseline.push(baseline())],
]) { state=base();change(state);run(name,state,[]); }
for (const [key, required] of [['maxNodes',2],['maxRoutes',1],['maxRoutePoints',6],['maxPairChecks',1],['maxSegmentChecks',1],['maxObstacleChecks',6],['maxCandidates',1]]) {
  for (const delta of [-1,0,1]) { const limits={...MEMORY_CONTINUITY_BUDGET,[key]:required+delta};run(`isolated-budget-${key}-${required+delta}`,base(),delta<0?[]:positive,{limits}); }
}
for (const invalid of [NaN,Infinity,-1,.5]) run(`invalid-budget-${String(invalid)}`,base(),[],{limits:{...MEMORY_CONTINUITY_BUDGET,maxPairChecks:invalid}});
for (const key of Object.keys(MEMORY_CONTINUITY_BUDGET)) { const limits={...MEMORY_CONTINUITY_BUDGET};delete limits[key];run(`unknown-missing-budget-${key}`,base(),[],{limits}); }
run('unknown-extra-budget-key',base(),[],{limits:{...MEMORY_CONTINUITY_BUDGET,extra:1}});
state=base();state.nodes[1].y=0;state.nodes[1].localY=0;state.baseline[0]=baseline([p(100,55),p(160,55)]);
run('identical-straight-baseline-retains-without-adoption',state,[]);
state=base();state.requests.push(memory({canonicalEdgeIds:['second']}));state.baseline.push(baseline([p(45,100),p(45,140),p(250,140),p(250,-30),p(215,-30),p(215,10)]));
run('chosen-peer-new-identical-route-second-rejects',state,positive);
state=base();
for (let i=0;i<4;i++) {const q=peer([p(0,-50-i*10),p(300,-50-i*10)]);state.requests.push(q.request);state.baseline.push(q.result)}
{const q=peer([p(130,30),p(130,55),p(145,55)]);state.requests.push(q.request);state.baseline.push(q.result)}
run('complete-late-last-peer-joint-obstruction',state,[]);
for (const key of ['maxPairChecks','maxSegmentChecks','maxObstacleChecks']) {
  const limits={...MEMORY_CONTINUITY_BUDGET,[key]:0};run(`peer-budget-${key}-zero`,state,[],{limits});
}

// The function returns adoption decisions; exact retained routes/port coverage
// are integration claims outside this literal helper report.
mkdirSync(output);
const checks=rows.flatMap(r=>Object.values(r.relations));
const report={schema:'archcanvas-independent-memory-literal-guard/1',createdUtc:new Date().toISOString(),bindings,
  cases:rows.length,casePassed:rows.filter(r=>r.passed).length,relations:checks.length,relationsPassed:checks.filter(Boolean).length,
  failures:rows.filter(r=>!r.passed).map(r=>({name:r.name,expected:r.expected,actual:r.actual,thrown:r.thrown,relations:r.relations})),rows,
  scope:'Literal public node/request/result guard API only. Independent exact expected geometry; no product geometry helpers used as an oracle. Not whole-scene canonical port integration, source-backed matrix, browser/rendered pixels, physical publication, human task acceptance or presented performance.'};
writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
for (const b of bindings) { const bytes=readFileSync(path.join(root,b.path));if(bytes.length!==b.bytes||createHash('sha256').update(bytes).digest('hex')!==b.sha256)throw new Error(`Source changed during capture: ${b.path}`); }
writeFileSync(path.join(output,'bindings-exact.json'),JSON.stringify({exact:true,bindings},null,2)+'\n');
console.log(JSON.stringify({cases:report.cases,casePassed:report.casePassed,relations:report.relations,relationsPassed:report.relationsPassed,failures:report.failures}));
