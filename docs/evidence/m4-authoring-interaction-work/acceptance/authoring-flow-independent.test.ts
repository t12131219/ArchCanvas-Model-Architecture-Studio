import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import type { AuthoredDraft, DraftCatalog, DraftModule, DraftNode } from '../../../../studio/src/authoring.ts';

// Only the observed implementation is swappable for before/after execution.
// Expected paths and invariants below do not call product helpers to derive gold.
const root = fileURLToPath(new URL('../../../../', import.meta.url));
const subject = await import(process.env.ARCHCANVAS_AUTHORING_FLOW_OBSERVED_MODULE ??
  pathToFileURL(root + 'studio/src/authoring.ts').href) as typeof import('../../../../studio/src/authoring.ts') & {
    draftFlow?: (draft: AuthoredDraft) => 'horizontal' | 'vertical';
  };
const frozen = JSON.parse(readFileSync(new URL('./frozen-before/docs/evidence/m4-collapse-continuity-work/authoring-browser-attempt-1/four-node-live-saved-draft-envelope.json', import.meta.url), 'utf8')).draft as AuthoredDraft;
type Point = [number, number];
type Flow = 'horizontal' | 'vertical';
const catalog: DraftCatalog = { schemaVersion: 1, mode: 'authored-draft', unsupported: [], modules: [
  ['Input', [], ['output']], ['Linear', ['input'], ['output']], ['GELU', ['input'], ['output']],
  ['Identity', ['input'], ['output']], ['Output', ['input'], []],
  ['Add', ['left', 'right'], ['output']], ['Concat', ['a', 'b'], ['output']],
].map(([kind, ins, outs]) => ({ kind: kind as string, label: kind as string, category: 'operator', description: 'Hand-authored tensor-port fixture', defaults: {}, parameters: [],
  ports: [...(ins as string[]).map(id => ({ id, name: id, direction: 'in' as const, type: 'tensor' as const })),
          ...(outs as string[]).map(id => ({ id, name: id, direction: 'out' as const, type: 'tensor' as const }))] })) };
function module(kind: string): DraftModule { return catalog.modules.find(m => m.kind === kind)!; }
function draft(nodes: [string,string,number,number][], edges: [string,string,string,string][]): AuthoredDraft {
  return { schemaVersion: 1, mode: 'authored-draft', id: 'draft-flow-independent', title: 'Independent flow fixture', revision: 0,
    nodes: nodes.map(([id,kind,x,y]) => ({ id,kind,label: kind, parameters: {},position:{x,y} })),
    edges: edges.map(([id,source,target,port]) => ({ id,source:{nodeId:source,portId:'output'},target:{nodeId:target,portId:port} })) };
}
function projected(n: DraftNode, port: string, flow: Flow): {x:number;y:number} {
  return (subject.portPoint as unknown as (n:DraftNode,m:DraftModule,id:string,flow:Flow)=>{x:number;y:number})(n,module(n.kind),port,flow);
}
function points(path: string): Point[] {
  const tokens = path.match(/[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?/g) ?? [];
  assert.equal(tokens.join(''),path.replace(/[\s,]/g,''));
  const result:Point[]=[];let x=0,y=0;
  for(let i=0;i<tokens.length;) {
    const command=tokens[i++];
    if(command==='M'||command==='L'){x=+tokens[i++];y=+tokens[i++];}
    else if(command==='V')y=+tokens[i++];else if(command==='H')x=+tokens[i++];else assert.fail(command);
    assert.ok(Number.isFinite(x)&&Number.isFinite(y));result.push([x,y]);
  }
  // Independent simplification only removes duplicate or forward-collinear
  // points. A geometric U-turn is preserved and rejected where applicable.
  const minimal:Point[]=[];
  for(const p of result){
    if(minimal.length&&p[0]===minimal.at(-1)![0]&&p[1]===minimal.at(-1)![1])continue;
    while(minimal.length>1){const a=minimal.at(-2)!,b=minimal.at(-1)!;
      if((a[0]===b[0]&&b[0]===p[0]&&(b[1]-a[1])*(p[1]-b[1])>=0)||
         (a[1]===b[1]&&b[1]===p[1]&&(b[0]-a[0])*(p[0]-b[0])>=0))minimal.pop();else break;}
    minimal.push(p);
  }return minimal;
}
function hits(a:Point,b:Point,n:DraftNode):boolean {
  const left=n.position.x+.001,right=n.position.x+176-.001,top=n.position.y+.001,bottom=n.position.y+100-.001;
  if(a[0]===b[0])return a[0]>left&&a[0]<right&&Math.max(Math.min(a[1],b[1]),top)<Math.min(Math.max(a[1],b[1]),bottom);
  assert.equal(a[1],b[1],'Every route segment is orthogonal');
  return a[1]>top&&a[1]<bottom&&Math.max(Math.min(a[0],b[0]),left)<Math.min(Math.max(a[0],b[0]),right);
}
function noStrictCrossings(first:Point[],second:Point[]) {
  for(let i=1;i<first.length;i++)for(let j=1;j<second.length;j++){
    const a=first[i-1],b=first[i],c=second[j-1],d=second[j];
    const av=a[0]===b[0],cv=c[0]===d[0];if(av===cv)continue;
    const v1=av?a:c,v2=av?b:d,h1=av?c:a,h2=av?d:b;
    assert.ok(!(v1[0]>Math.min(h1[0],h2[0])+.001&&v1[0]<Math.max(h1[0],h2[0])-.001&&
                h1[1]>Math.min(v1[1],v2[1])+.001&&h1[1]<Math.max(v1[1],v2[1])-.001),'Fixture branch/merge has avoidable strict crossing');
  }
}
function checkedRoutes(d:AuthoredDraft,flow:Flow,clear=true) {
  const bytes=JSON.stringify(d),out=subject.draftRoutes(d,catalog);
  assert.equal(out.routes.length,d.edges.length,'Each authored edge has one route');
  assert.equal(new Set(out.routes.map(r=>r.id)).size,d.edges.length);
  for(const edge of d.edges){
    const route=out.routes.find(r=>r.id===edge.id)!;const p=points(route.path);
    const source=d.nodes.find(n=>n.id===edge.source.nodeId)!,target=d.nodes.find(n=>n.id===edge.target.nodeId)!;
    const start=projected(source,edge.source.portId,flow),end=projected(target,edge.target.portId,flow);
    assert.ok(Math.hypot(p[0][0]-start.x,p[0][1]-start.y)<=.011,'Route start must agree with same projected public port');
    assert.ok(Math.hypot(p.at(-1)![0]-end.x,p.at(-1)![1]-end.y)<=.011,'Route end must agree with same projected public port');
    const crossed=d.nodes.filter(n=>p.slice(1).some((b,i)=>hits(p[i],b,n))).map(n=>n.id);
    if(clear){assert.deepEqual(crossed,[],edge.id);assert.deepEqual(route.blockedBy,[],edge.id);}
    else for(const id of crossed)assert.ok(route.blockedBy.includes(id),`Unreported body penetration ${id}`);
  }
  assert.equal(JSON.stringify(d),bytes,'Projection/routing must not edit draft');return out;
}
function branch(kind='Add') {
  return draft([['input','Input',200,30],['left','Identity',50,200],['right','Identity',350,200],['merge',kind,200,400],['output','Output',200,600]],
    [['fork-left','input','left','input'],['fork-right','input','right','input'],
     ['join-left','left','merge',kind==='Add'?'left':'a'],['join-right','right','merge',kind==='Add'?'right':'b'],['exit','merge','output','input']]);
}

test('flow interface projects frozen vertical chain and no-edge/horizontal default without semantic state',()=>{
  assert.equal(typeof subject.draftFlow,'function');
  assert.equal(subject.draftFlow!(frozen),'vertical');
  const isolated=structuredClone(frozen);isolated.edges=[];assert.equal(subject.draftFlow!(isolated),'horizontal');
  const a=frozen.nodes[0];assert.deepEqual(subject.portPoint(a,module(a.kind),'output'),{x:226,y:136});
  assert.deepEqual(projected(a,'output','vertical'),{x:138,y:170});
});
test('real frozen four-node vertical chain has three literal straight gap-only routes, preserving every source fact',()=>{
  const expected:Point[][]=[[[138,170],[138,224]],[[138,324],[138,378]],[[138,478],[138,532]]];
  const out=checkedRoutes(frozen,'vertical');
  frozen.edges.forEach((e,i)=>assert.deepEqual(points(out.routes.find(r=>r.id===e.id)!.path),expected[i]));
});
test('literal horizontal chain retains legacy side coordinates and zero-bend straight gaps',()=>{
  const d=draft([['input','Input',50,70],['hidden','Identity',298,70],['out','Output',546,70]],[['a','input','hidden','input'],['b','hidden','out','input']]);
  const out=checkedRoutes(d,'horizontal');
  assert.deepEqual(points(out.routes[0].path),[[226,136],[298,136]]);
  assert.deepEqual(points(out.routes[1].path),[[474,136],[546,136]]);
  if(subject.draftFlow)assert.equal(subject.draftFlow(d),'horizontal');
});
test('vertical Add branch keeps shared fanout identity, distinct ordered merge ports and unobstructed paths',()=>{
  const d=branch(),merge=d.nodes.find(n=>n.id==='merge')!;
  const left=projected(merge,'left','vertical'),right=projected(merge,'right','vertical');
  assert.equal(left.y,400);assert.equal(right.y,400);assert.ok(left.x>200&&left.x<right.x&&right.x<376);
  const out=checkedRoutes(d,'vertical');
  for(let i=0;i<out.routes.length;i++)for(let j=i+1;j<out.routes.length;j++)noStrictCrossings(points(out.routes[i].path),points(out.routes[j].path));
  assert.deepEqual(d.edges.filter(e=>e.source.nodeId==='input').map(e=>e.source),[{nodeId:'input',portId:'output'},{nodeId:'input',portId:'output'}]);
  assert.deepEqual(d.edges.filter(e=>e.target.nodeId==='merge').map(e=>e.target.portId),['left','right']);
});
test('vertical Concat named input projections never collapse a/b producer identities',()=>{
  const d=branch('Concat'),merge=d.nodes.find(n=>n.id==='merge')!;
  const a=projected(merge,'a','vertical'),b=projected(merge,'b','vertical');
  assert.equal(a.y,400);assert.equal(b.y,400);assert.ok(a.x<b.x);
  checkedRoutes(d,'vertical');assert.deepEqual(d.edges.filter(e=>e.target.nodeId==='merge').map(e=>[e.source.nodeId,e.target.portId]),[['left','a'],['right','b']]);
});
test('an independent intervening body forces a safe detour without node movement or false blocked success',()=>{
  const d=draft([['input','Input',50,70],['out','Output',50,370],['obstacle','Identity',50,220]],[['a','input','out','input']]);
  const out=checkedRoutes(d,'vertical');assert.ok(points(out.routes[0].path).length>2,'Straight port-to-port segment penetrates the declared obstacle');
});
test('a covering body blocking the target stays explicit and does not move user anchors',()=>{
  const d=draft([['input','Input',50,70],['out','Output',50,224],['cover','Identity',120,175]],[['a','input','out','input']]);
  const out=checkedRoutes(d,'vertical',false);assert.ok(out.overlaps.some(p=>[p.first,p.second].includes('cover')));
  assert.ok(out.routes[0].blockedBy.includes('cover'),'Impossible endpoint cover must not be called clear');
});
test('reverse-positioned vertical DAG leaves bottom ports outward and reaches top ports from outside bodies',()=>{
  const d=draft([['input','Input',50,600],['hidden','Identity',50,350],['out','Output',50,100]],[['a','input','hidden','input'],['b','hidden','out','input']]);
  const out=checkedRoutes(d,'vertical');
  for(const route of out.routes){const p=points(route.path);assert.equal(p[0][0],p[1][0]);assert.ok(p[1][1]>p[0][1]);
    assert.equal(p.at(-2)![0],p.at(-1)![0]);assert.ok(p.at(-1)![1]>p.at(-2)![1]);}
});
test('flow and geometry are insensitive to authored array ordering and equivariant under whole-draft translation',()=>{
  const d=structuredClone(frozen),before=subject.draftRoutes(d,catalog);
  const shuffled=structuredClone(d);shuffled.nodes.reverse();shuffled.edges.reverse();
  const after=subject.draftRoutes(shuffled,catalog);
  for(const route of before.routes)assert.deepEqual(points(route.path),points(after.routes.find(r=>r.id===route.id)!.path));
  const moved=structuredClone(d);for(const node of moved.nodes){node.position.x-=73;node.position.y+=81;}
  const translation=checkedRoutes(moved,'vertical');
  for(const route of before.routes)assert.deepEqual(points(translation.routes.find(r=>r.id===route.id)!.path),points(route.path).map(([x,y])=>[x-73,y+81]));
});
test('four directional visual moves retain graph, one-command history, undo/redo geometry and JSON persistence',()=>{
  for(const [dx,dy] of [[-40,0],[40,0],[0,-30],[0,30]]){
    const history=subject.draftHistory(structuredClone(frozen));const bytes=JSON.stringify(history);
    const moved=subject.changeDraft(history,d=>{d.nodes[1].position.x+=dx;d.nodes[1].position.y+=dy;});
    assert.equal(JSON.stringify(history),bytes);assert.equal(moved.past.length,1);assert.deepEqual(moved.draft.edges,frozen.edges);
    assert.deepEqual(moved.draft.nodes.map(({position,...n})=>n),frozen.nodes.map(({position,...n})=>n));
    checkedRoutes(moved.draft,'vertical');
    const undo=subject.travelDraft(moved,'undo'),redo=subject.travelDraft(undo,'redo');
    assert.deepEqual(undo.draft.nodes,frozen.nodes);assert.deepEqual(redo.draft.nodes,moved.draft.nodes);
    assert.deepEqual(subject.draftRoutes(redo.draft,catalog),subject.draftRoutes(moved.draft,catalog));
    const envelope={draft:redo.draft,storageRevision:3,savedRevision:redo.draft.revision};
    assert.deepEqual(subject.parseDraftCache(JSON.parse(JSON.stringify(envelope))),envelope);
  }
});

test('an independent horizontal graph cannot rotate the frozen vertical graph\'s public ports or three straight routes',()=>{
  const mixed=structuredClone(frozen),extra=draft([
    ['horizontal-input','Input',1000,70],['horizontal-a','Identity',1400,70],
    ['horizontal-b','Identity',1800,70],['horizontal-output','Output',2200,70],
  ],[['ha','horizontal-input','horizontal-a','input'],['hb','horizontal-a','horizontal-b','input'],['hc','horizontal-b','horizontal-output','input']]);
  mixed.nodes.push(...extra.nodes);mixed.edges.push(...extra.edges);
  const bytes=JSON.stringify(mixed),out=subject.draftRoutes(mixed,catalog);
  const expectedVertical:Point[][]=[[[138,170],[138,224]],[[138,324],[138,378]],[[138,478],[138,532]]];
  frozen.edges.forEach((edge,i)=>assert.deepEqual(points(out.routes.find(r=>r.id===edge.id)!.path),expectedVertical[i],
    'An unrelated network must not force an existing chain into side-return routing'));
  const expectedHorizontal:Point[][]=[[[1176,136],[1400,136]],[[1576,136],[1800,136]],[[1976,136],[2200,136]]];
  extra.edges.forEach((edge,i)=>assert.deepEqual(points(out.routes.find(r=>r.id===edge.id)!.path),expectedHorizontal[i]));
  const perNode=(subject as typeof subject & {draftNodeFlows?: (d:AuthoredDraft)=>Record<string,Flow>}).draftNodeFlows;
  assert.equal(typeof perNode,'function');const flow=perNode!(mixed);
  const returned=out as typeof out & {nodeFlows?:Record<string,Flow>};assert.deepEqual(returned.nodeFlows,flow);
  for(const node of frozen.nodes){assert.equal(flow[node.id],'vertical');
    for(const port of module(node.kind).ports){const actual=projected(node,port.id,flow[node.id]);
      assert.equal(actual.x,138);assert.equal(actual.y,node.position.y+(port.direction==='in'?0:100));}}
  for(const node of extra.nodes){assert.equal(flow[node.id],'horizontal');
    for(const port of module(node.kind).ports){const actual=projected(node,port.id,flow[node.id]);
      assert.equal(actual.x,node.position.x+(port.direction==='in'?0:176));assert.equal(actual.y,136);}}
  assert.equal(JSON.stringify(mixed),bytes,'Component projection cannot mutate graph/source/positions');
  const reversed=structuredClone(mixed);reversed.nodes.reverse();reversed.edges.reverse();
  const repeated=subject.draftRoutes(reversed,catalog);
  for(const route of out.routes)assert.deepEqual(points(route.path),points(repeated.routes.find(r=>r.id===route.id)!.path));
});
