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

test('public flow metadata and projected committed endpoints agree for vertical and horizontal fixtures',()=>{
  const vertical=subject.draftRoutes(frozen,catalog) as ReturnType<typeof subject.draftRoutes> & {flow?:Flow};
  assert.equal(vertical.flow,'vertical');
  const horizontalDraft=draft([['in','Input',50,70],['out','Output',298,70]],[['a','in','out','input']]);
  const horizontal=subject.draftRoutes(horizontalDraft,catalog) as ReturnType<typeof subject.draftRoutes> & {flow?:Flow};
  assert.equal(horizontal.flow,'horizontal');
  assert.deepEqual(points(vertical.routes[0].path)[0],[138,170]);
  assert.deepEqual(points(horizontal.routes[0].path)[0],[226,136]);
});

test('single-port click region contains the complete dot and dot-to-label gap in both flows',async()=>{
  const {draftPortPresentation}=await import('../../../../studio/src/draftPortPresentation.ts');
  const contains=(r:{x:number;y:number;width:number;height:number},x:number,y:number)=>
    x>=r.x&&x<=r.x+r.width&&y>=r.y&&y<=r.y+r.height;
  for(const flow of ['horizontal','vertical'] as const)for(const direction of ['in','out'] as const){
    const port={id:'p',name:'port',direction,type:'tensor' as const};
    const presentation=draftPortPresentation(port,88,100,flow);
    const r=presentation.hit;
    assert.ok(Number.isFinite(r.x)&&Number.isFinite(r.y)&&r.width>0&&r.height>=20);
    // Actual dots have radius5. Their full clickable surroundings, including
    // the old invisible gap towards the visible label, must be contiguous.
    for(const [dx,dy] of [[-5,-5],[-5,5],[5,-5],[5,5],[0,0]])assert.ok(contains(r,88+dx,100+dy));
    assert.ok(contains(r,88+(direction==='in'?9:-9),103),'Previously dead circle-to-label gap');
    assert.ok(contains(r,presentation.labelX,presentation.labelY),'Label anchor must be clickable');
  }
});

test('two-port merge hit regions cannot capture each other\'s dot or gap-center identity',async()=>{
  const {draftPortPresentation}=await import('../../../../studio/src/draftPortPresentation.ts');
  const contains=(r:{x:number;y:number;width:number;height:number},x:number,y:number)=>
    x>r.x&&x<r.x+r.width&&y>r.y&&y<r.y+r.height;
  for(const flow of ['horizontal','vertical'] as const){
    const m=module('Add'),n={id:'merge',kind:'Add',label:'Add',parameters:{},position:{x:0,y:0}};
    const a=projected(n,'left',flow),b=projected(n,'right',flow);
    // These are the literal current catalog's two merge inputs: horizontal
    // centers12 apart; vertical centers176/3 apart. No direction score copied.
    const spacing=flow==='horizontal'?12:176/3;
    const ar=draftPortPresentation(m.ports[0],a.x,a.y,flow,spacing).hit;
    const br=draftPortPresentation(m.ports[1],b.x,b.y,flow,spacing).hit;
    assert.ok(contains(ar,a.x,a.y)&&contains(br,b.x,b.y));
    assert.ok(!contains(ar,b.x,b.y)&&!contains(br,a.x,a.y),'Peer dot captured by wrong canonical input');
    assert.ok(contains(ar,a.x+9,a.y+3)&&contains(br,b.x+9,b.y+3));
    assert.ok(!contains(ar,b.x+9,b.y+3)&&!contains(br,a.x+9,a.y+3),'Label gap captured by wrong canonical input');
  }
});
