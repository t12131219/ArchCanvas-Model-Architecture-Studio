import { createOrthogonalRouter } from './before/core/orthogonalRouter.ts';
import { writeFileSync } from 'node:fs';

const EPS = 1e-7;
const pointKey = p => `${p.x}:${p.y}`;
function selfGeometry(points) {
  const contacts = [], overlaps = [];
  for (let i = 1; i < points.length; i++) for (let j = i + 2; j < points.length; j++) {
    const a=points[i-1], b=points[i], c=points[j-1], d=points[j], av=a.x===b.x, cv=c.x===d.x;
    if (av !== cv) {
      const v=av?[a,b]:[c,d], h=av?[c,d]:[a,b], p={x:v[0].x,y:h[0].y};
      if (p.x >= Math.min(h[0].x,h[1].x)-EPS && p.x <= Math.max(h[0].x,h[1].x)+EPS &&
          p.y >= Math.min(v[0].y,v[1].y)-EPS && p.y <= Math.max(v[0].y,v[1].y)+EPS) contacts.push({i,j,p});
    } else if (Math.abs((av?a.x:a.y)-(av?c.x:c.y))<EPS) {
      const low=Math.max(Math.min(av?a.y:a.x,av?b.y:b.x),Math.min(av?c.y:c.x,av?d.y:d.x));
      const high=Math.min(Math.max(av?a.y:a.x,av?b.y:b.x),Math.max(av?c.y:c.x,av?d.y:d.x));
      if (high >= low-EPS) {
        if(high > low+EPS) overlaps.push({i,j,axis:av?'v':'h',coordinate:av?a.x:a.y,low,high});
        else contacts.push({i,j,p:{x:av?a.x:low,y:av?low:a.y}});
      }
    }
  }
  return {contacts,overlaps};
}
function node(id,x,y,width=8,height=8) {return {id,x,y,width,height,localX:x,localY:y,label:id,subtitle:'',headerHeight:4,kind:'Linear',category:'linear',fill:'#fff',stroke:'#000',glyph:'module',expanded:false,expandable:false,pinned:false,evidence:'source',ports:[]};}
function endpointNode(id,p,outward) {
  return node(id,p.x-4-(outward.x*4),p.y-4-(outward.y*4));
}
function penetrates(a,b,n,pad=0) {return a.x===b.x ? a.x>n.x-pad+EPS && a.x<n.x+n.width+pad-EPS &&
  Math.max(Math.min(a.y,b.y),n.y-pad)<Math.min(Math.max(a.y,b.y),n.y+n.height+pad)-EPS :
  a.y>n.y-pad+EPS&&a.y<n.y+n.height+pad-EPS&&Math.max(Math.min(a.x,b.x),n.x-pad)<Math.min(Math.max(a.x,b.x),n.x+n.width+pad)-EPS;}
const dir=(a,b)=>({x:Math.sign(b.x-a.x),y:Math.sign(b.y-a.y)});
const path=p=>p.map((v,i)=>!i?`M ${v.x} ${v.y}`:v.x===p[i-1].x?`V ${v.y}`:`H ${v.x}`).join(' ');
let seed=0x435a13bc;
const random=n=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)%n;};
const stats={seed:0x435a13bc,attempts:0,simpleOriginals:0,acceptedChanges:0,outputContacts:0,outputOverlaps:0,found:[]};
for(let attempt=0;attempt<100000;attempt++) {
  stats.attempts++;
  const points=[{x:0,y:0}]; let vertical=!!random(2);
  for(let j=0,count=6+random(14);j<count;j++) {
    const last=points.at(-1),move=(random(2)?1:-1)*(16+random(10)*8);
    points.push(vertical?{x:last.x,y:last.y+move}:{x:last.x+move,y:last.y});vertical=!vertical;
    if(selfGeometry(points).contacts.length||selfGeometry(points).overlaps.length) {points.pop();break;}
  }
  if(points.length<6) continue;
  const nodes=[endpointNode('from',points[0],dir(points[0],points[1])),endpointNode('to',points.at(-1),dir(points.at(-1),points.at(-2)))];
  if(nodes.some(n=>points.slice(1).some((b,i)=>penetrates(points[i],b,n)))) continue;
  for(let j=0,count=random(6);j<count;j++) {
    const n=node(`wall${j}`,(random(33)-16)*8,(random(33)-16)*8,8+random(4)*8,8+random(4)*8);
    if(!points.slice(1).some((b,i)=>penetrates(points[i],b,n))) nodes.push(n);
  }
  const requests=[{sourceId:'from',targetId:'to',start:points[0],end:points.at(-1),preferredPath:path(points),tensorId:'any'}];
  stats.simpleOriginals++;
  const next=createOrthogonalRouter(nodes).batch(requests)[0];
  if(next.path===requests[0].preferredPath)continue;
  stats.acceptedChanges++;
  const self=selfGeometry(next.points);stats.outputContacts+=self.contacts.length;stats.outputOverlaps+=self.overlaps.length;
  if(self.contacts.length||self.overlaps.length) {
    stats.found.push({attempt,nodes,requests,originalSelf:selfGeometry(points),next,nextSelf:self});
    if(stats.found.length>=5)break;
  }
}
writeFileSync(new URL('./exploration-before.json',import.meta.url),JSON.stringify(stats,null,2)+'\n');
console.log(JSON.stringify({...stats,found:stats.found.map(v=>({attempt:v.attempt,before:v.requests[0].preferredPath,after:v.next.path,self:v.nextSelf}))},null,2));
