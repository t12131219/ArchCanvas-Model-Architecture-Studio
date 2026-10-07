import assert from 'node:assert/strict';
import type { Scene, SceneNode } from '../../../../studio/src/core/types.ts';

export type Point = { x: number; y: number };
export type Rect = { x: number; y: number; width: number; height: number };
const epsilon = 1e-7;
const near = (a: number, b: number, tolerance = epsilon) => Math.abs(a - b) <= tolerance;

// A separate complete parser: ignored bytes, diagonal segments and subpaths
// cannot silently become a shorter path in the acceptance measurement.
export function points(path: string): Point[] {
  const tokens = path.match(/[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?/g) ?? [];
  assert.equal(tokens.join(''), path.replace(/\s+/g, ''), 'unparsed route bytes');
  const result: Point[] = [];
  for (let i = 0; i < tokens.length;) {
    const command = tokens[i++]; let point: Point;
    if (command === 'M' && !result.length || command === 'L' && result.length) point = { x: Number(tokens[i++]), y: Number(tokens[i++]) };
    else if (command === 'H' && result.length) point = { x: Number(tokens[i++]), y: result.at(-1)!.y };
    else if (command === 'V' && result.length) point = { x: result.at(-1)!.x, y: Number(tokens[i++]) };
    else throw new Error(`unsupported route/subpath ${command}`);
    assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y), 'nonfinite/partial route');
    assert.ok(!result.length || point.x === result.at(-1)!.x || point.y === result.at(-1)!.y, 'diagonal route');
    result.push(point);
  }
  assert.ok(result.length >= 2, 'missing route');
  return result;
}
function segments(path: string) {
  const result: Point[] = [];
  for (const point of points(path)) {
    if (result.length && near(point.x, result.at(-1)!.x) && near(point.y, result.at(-1)!.y)) continue;
    while (result.length > 1) {
      const a = result.at(-2)!, b = result.at(-1)!;
      const vertical = a.x === b.x && b.x === point.x && (b.y-a.y)*(point.y-b.y) >= 0;
      const horizontal = a.y === b.y && b.y === point.y && (b.x-a.x)*(point.x-b.x) >= 0;
      if (!vertical && !horizontal) break;
      result.pop();
    }
    result.push(point);
  }
  return result.slice(1).map((b, i) => ({ a: result[i], b }));
}
export function stats(path: string) {
  const s = segments(path), axes = s.map(({ a, b }) => a.x === b.x ? 'v' : 'h');
  return { length: s.reduce((total, { a, b }) => total + Math.abs(a.x-b.x) + Math.abs(a.y-b.y), 0),
    bends: axes.slice(1).filter((axis, i) => axis !== axes[i]).length };
}
export function pair(first: string, second: string) {
  const crosses = new Set<string>(), intervals = new Map<string, [number, number][]>();
  const endpoints=[points(first)[0],points(first).at(-1)!,points(second)[0],points(second).at(-1)!];
  for (const a of segments(first)) for (const b of segments(second)) {
    const av = a.a.x === a.b.x, bv = b.a.x === b.b.x;
    if (av !== bv) {
      const v = av ? a : b, h = av ? b : a;
      // The new repair contract protects all whole-polyline interior point
      // contacts, including actual bends as well as collinear split vertices.
      // A whole-edge start/end contact remains an attachment, not a crossing.
      if (v.a.x >= Math.min(h.a.x,h.b.x)-epsilon && v.a.x <= Math.max(h.a.x,h.b.x)+epsilon &&
          h.a.y >= Math.min(v.a.y,v.b.y)-epsilon && h.a.y <= Math.max(v.a.y,v.b.y)+epsilon &&
          !endpoints.some(point=>near(point.x,v.a.x)&&near(point.y,h.a.y))) crosses.add(`${v.a.x}/${h.a.y}`);
    } else {
      const coordinateA = av ? a.a.x : a.a.y, coordinateB = bv ? b.a.x : b.a.y;
      if (!near(coordinateA, coordinateB)) continue;
      const coordinates = av ? [a.a.y,a.b.y,b.a.y,b.b.y] : [a.a.x,a.b.x,b.a.x,b.b.x];
      const low = Math.max(Math.min(coordinates[0],coordinates[1]),Math.min(coordinates[2],coordinates[3]));
      const high = Math.min(Math.max(coordinates[0],coordinates[1]),Math.max(coordinates[2],coordinates[3]));
      if (high > low+epsilon) { const key = `${av?'v':'h'}/${coordinateA}`; intervals.set(key,[...intervals.get(key)??[],[low,high]]); }
    }
  }
  let overlapLength = 0;
  for (const values of intervals.values()) {
    values.sort((a,b)=>a[0]-b[0]); let low = values[0][0], high = values[0][1];
    for (const [nextLow,nextHigh] of values.slice(1)) {
      if (nextLow <= high+epsilon) high = Math.max(high,nextHigh);
      else { overlapLength += high-low; low=nextLow; high=nextHigh; }
    }
    overlapLength += high-low;
  }
  return { crossings: [...crosses].sort(), overlapLength };
}
export function penetrates(path: string, rect: Rect) {
  return segments(path).some(({ a,b }) => a.x === b.x
    ? a.x > rect.x+epsilon && a.x < rect.x+rect.width-epsilon && Math.max(Math.min(a.y,b.y),rect.y+epsilon) < Math.min(Math.max(a.y,b.y),rect.y+rect.height-epsilon)
    : a.y > rect.y+epsilon && a.y < rect.y+rect.height-epsilon && Math.max(Math.min(a.x,b.x),rect.x+epsilon) < Math.min(Math.max(a.x,b.x),rect.x+rect.width-epsilon));
}
export function bodyRectangles(node: SceneNode): Rect[] {
  const front = { x: node.x, y: node.y, width: node.width, height: node.height };
  return node.repeat && !node.expanded ? [front, { ...front, x: front.x+3.5, y: front.y+3.5 }, { ...front, x: front.x+7, y: front.y+7 }] : [front];
}
export function intrusions(scene: Scene) {
  const nodes = new Map(scene.nodes.map(node=>[node.id,node])), hits: string[] = [];
  const ancestry = (id: string) => { const ids = new Set<string>(); let parent = nodes.get(id)?.parentId;
    while (parent) { assert.ok(!ids.has(parent),'cyclic ancestry'); ids.add(parent); parent=nodes.get(parent)?.parentId; } return ids; };
  for (const edge of scene.edges) {
    const ancestors = new Set([...ancestry(edge.sourceId),...ancestry(edge.targetId)]);
    for (const node of scene.nodes) {
      if (ancestors.has(node.id) && node.id !== edge.sourceId && node.id !== edge.targetId) {
        if (node.expanded && penetrates(edge.path,{ x:node.x,y:node.y,width:node.width,height:node.headerHeight })) hits.push(`${edge.id}|${node.id}|header`);
      } else for (const [index,rect] of bodyRectangles(node).entries()) {
        if (penetrates(edge.path,rect)) hits.push(`${edge.id}|${node.id}|${index?'backplate'+index:'body'}`);
      }
    }
  }
  return hits.sort();
}
type Element = { name: string; attributes: Record<string,string>; children: Element[]; text: string };
const unescape = (v: string) => v.replace(/&quot;/g,'"').replace(/&apos;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
function xml(value: string) {
  const root: Element = { name:'root',attributes:{},children:[],text:'' }, stack=[root];
  assert.ok(!/<!DOCTYPE|<!ENTITY/i.test(value),'entity declarations');
  for (const token of value.match(/<[^>]*>|[^<]+/g)??[]) {
    if (token.startsWith('<?') || token.startsWith('<!--')) continue;
    if (token.startsWith('</')) { const end=token.slice(2,-1).trim(); assert.equal(stack.pop()!.name,end); continue; }
    if (!token.startsWith('<')) { stack.at(-1)!.text += unescape(token); continue; }
    const name=token.match(/^<([\w:-]+)/)![1], attributes:Record<string,string>={};
    for (const [,key,val] of token.matchAll(/([\w:-]+)="([^"]*)"/g)) attributes[key]=unescape(val);
    const child={name,attributes,children:[],text:''};stack.at(-1)!.children.push(child);
    if (!token.endsWith('/>')) stack.push(child);
  }
  assert.equal(stack.length,1);return root.children[0];
}
export function assertSvg(scene: Scene, svg: string) {
  const root=xml(svg), all:Element[]=[];
  const visit=(node:Element)=>{ all.push(node);node.children.forEach(visit); };visit(root);
  const metadata=JSON.parse(all.find(node=>node.name==='metadata')!.text);
  assert.equal(metadata.documentId,scene.documentId);assert.equal(metadata.revision,scene.revision);
  assert.equal(metadata.sourceDigest,scene.sourceDigest);assert.equal(metadata.irDigest,scene.irDigest);
  assert.deepEqual(metadata.sourceFacts,JSON.parse(JSON.stringify(scene.sourceFacts)));
  const groups=all.filter(node=>node.attributes['data-edge-id']);
  assert.equal(groups.length,scene.edges.length);
  for(const edge of scene.edges) {
    const group=groups.find(node=>node.attributes['data-edge-id']===edge.id);assert.ok(group,`missing SVG edge ${edge.id}`);
    const path=group.children.find(node=>node.name==='path');assert.ok(path);
    assert.equal(path.attributes.d,edge.path);assert.equal(path.attributes.stroke,edge.stroke);
    assert.equal(Number(path.attributes['stroke-width']),edge.width);
    assert.equal(Boolean(path.attributes['stroke-dasharray']),edge.dashed);
    const binding=metadata.renderedBindings.find((item:{sceneEdgeId:string})=>item.sceneEdgeId===edge.id);
    assert.deepEqual(binding,{sceneEdgeId:edge.id,canonicalEdgeIds:edge.canonicalEdgeIds,source:edge.source,target:edge.target,tensorId:edge.tensorId,role:edge.role});
  }
  const cards=all.filter(node=>node.attributes['data-canonical-id'] && node.attributes['data-node-id']);
  assert.equal(cards.length,scene.nodes.length);
  for(const node of scene.nodes) {
    const group=cards.find(item=>item.attributes['data-node-id']===node.id);assert.ok(group);
    const rects=group.children.filter(item=>item.name==='rect');
    assert.equal(rects.length,bodyRectangles(node).length);
    const expected=bodyRectangles(node), actual=rects.map(rect=>Object.fromEntries(['x','y','width','height'].map(k=>[k,Number(rect.attributes[k])])));
    for(const rect of expected)assert.ok(actual.some(item=>['x','y','width','height'].every(k=>near(item[k],rect[k as keyof Rect],.06))),`SVG body/backplate ${node.id}`);
    const portElements=all.filter(item=>item.attributes['data-port-id'] && item.attributes['data-node-id']===node.id);
    assert.equal(portElements.length,node.ports.length);
    for(const port of node.ports) {
      const element=portElements.find(item=>item.attributes['data-port-id']===port.id);assert.ok(element,`SVG port ${port.id}`);
      const circle=element.name==='circle'?element:element.children.filter(item=>item.name==='circle').at(-1);assert.ok(circle);
      assert.ok(near(Number(circle.attributes.cx),port.x,.06)&&near(Number(circle.attributes.cy),port.y,.06),`SVG circle detached ${port.id}`);
    }
  }
}
export function assertEndpoints(scene: Scene) {
  for(const edge of scene.edges) for(const [id,direction,point] of [[edge.sourceId,'out',points(edge.path)[0]],[edge.targetId,'in',points(edge.path).at(-1)!]] as const) {
    const node=scene.nodes.find(node=>node.id===id);assert.ok(node);
    const ports=node.ports.filter(port=>port.direction===direction&&edge.canonicalEdgeIds.every(id=>port.canonicalEdgeIds.includes(id)));
    assert.ok(ports.some(port=>near(port.x,point.x,.06)&&near(port.y,point.y,.06)),`detached ${edge.id} ${direction}`);
  }
}
export function assertRefinement(before: Scene, after: Scene, svg?: string) {
  for(const key of ['documentId','revision','sourceDigest','irDigest','sourceFacts','hiddenEdges','nodes','legend','annotations','pageSpec','exportScope'] as const)
    assert.deepEqual(after[key],before[key],`changed protected ${key}`);
  assert.deepEqual(after.edges.map(({path,labelX,labelY,...rest})=>rest),before.edges.map(({path,labelX,labelY,...rest})=>rest),'canonical branch/role/style/identity');
  assertEndpoints(after);if(svg)assertSvg(after,svg);
  const oldHits=new Set(intrusions(before));for(const hit of intrusions(after))assert.ok(oldHits.has(hit),`new intrusion ${hit}`);
  for(let i=0;i<before.edges.length;i++)for(let j=i+1;j<before.edges.length;j++) {
    const old=pair(before.edges[i].path,before.edges[j].path), current=pair(after.edges[i].path,after.edges[j].path);
    assert.ok(current.crossings.length<=old.crossings.length,`new protected crossing ${before.edges[i].id}/${before.edges[j].id}`);
    assert.ok(current.overlapLength<=old.overlapLength+epsilon,`new protected overlap ${before.edges[i].id}/${before.edges[j].id}`);
  }
}
