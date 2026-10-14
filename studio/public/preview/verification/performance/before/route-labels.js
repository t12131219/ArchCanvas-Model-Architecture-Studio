/* Source-owned edge captions; only their path anchor is editable. */
(function(root){
  'use strict';
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  function segments(points){let total=0;const out=[];for(let i=1;i<points.length;i++){
    const a=points[i-1],b=points[i],length=Math.hypot(b.x-a.x,b.y-a.y);
    if(length>1e-6){out.push({a,b,length,start:total});total+=length;}
  }return {items:out,total};}
  function project(points,p){const ss=segments(points);let best=null;
    for(const s of ss.items){const t=clamp(((p.x-s.a.x)*(s.b.x-s.a.x)+(p.y-s.a.y)*(s.b.y-s.a.y))/s.length**2,0,1);
      const q={x:s.a.x+t*(s.b.x-s.a.x),y:s.a.y+t*(s.b.y-s.a.y)},distance=Math.hypot(p.x-q.x,p.y-q.y);
      if(!best||distance<best.distance)best={...q,distance,along:s.start+t*s.length,ratio:(s.start+t*s.length)/ss.total,segment:s};
    }return best;
  }
  function initialize(label,points){
    const [x,y,w,h]=label.bbox,p={x:x+w/2,y:y+h/2},q=project(points,p);
    if(!q)return {ratio:.5,gap:7,side:{x:1,y:0}};
    return {mode:label.near||'ratio',ratio:q.ratio,distance:label.near==='target'?segments(points).total-q.along:q.along,
      gap:7,side:{x:p.x-q.x,y:p.y-q.y}};
  }
  const overlap=(a,b)=>Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x)>1e-5&&Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y)>1e-5;
  function place(graph,label,points,occupied=[]){
    const ss=segments(points);if(!ss.items.length)return null;
    const anchor=label.anchor||initialize(label,points),[bx,by,w,h]=label.bbox;
    const desired=clamp(anchor.mode==='source'?anchor.distance:anchor.mode==='target'?ss.total-anchor.distance:anchor.ratio*ss.total,0,ss.total);
    const obstacles=graph.nodes.flatMap(n=>n.expanded?(n.labelObstacles||[]).map(b=>({x:n.x+b.x,y:n.y+b.y,w:b.w,h:b.h})):
      n.junction?[]:[n]);
    const edge=graph.edges.find(e=>e.id===label.edge);
    const ancestors=id=>{const out=[];let n=graph.nodes.find(v=>v.id===id);while(n){if(n.expanded)out.push(n);n=graph.nodes.find(v=>v.id===n.parent);}return out;};
    // A caption may slide within the common source scope, never into another module.
    const scopes=graph.nodes.filter(n=>(label.scope||[]).includes(n.id));
    const candidates=[];
    for(const s of ss.items){const ux=(s.b.x-s.a.x)/s.length,uy=(s.b.y-s.a.y)/s.length;
      let nx=-uy,ny=ux;const sign=nx*(anchor.side?.x||0)+ny*(anchor.side?.y||0)<0?-1:1;nx*=sign;ny*=sign;
      for(const along of [clamp(desired-s.start,0,s.length),s.length/2,...[.1,.2,.35,.65,.8,.9].map(t=>s.length*t),...Array.from({length:Math.min(40,Math.floor(s.length/24))},(_,i)=>(i+1)*s.length/(Math.min(40,Math.floor(s.length/24))+1))]){
        const t=clamp(along,Math.min(10,s.length/2),Math.max(s.length-10,s.length/2));
        for(const flip of [1,-1])for(const extra of [0,4,9,14,20,25,57,89,121,185,249,377]){
          const x=s.a.x+ux*t,y=s.a.y+uy*t,gap=clamp(anchor.gap??7,4,24),distance=(Math.abs(nx)*w+Math.abs(ny)*h)/2+gap+extra;
          const cx=x+nx*flip*distance,cy=y+ny*flip*distance,box={x:cx-w/2,y:cy-h/2,w,h};
          let collisions=obstacles.filter(n=>overlap(box,n)).length+occupied.filter(n=>overlap(box,n)).length;
          collisions+=scopes.filter(n=>box.x<n.x+2||box.y<n.y+2||box.x+w>n.x+n.w-2||box.y+h>n.y+n.h-2).length*4;
          if(box.x<0||box.y<0||box.x+w>graph.canvas[0]||box.y+h>graph.canvas[1])collisions+=4;
          candidates.push({x:cx-(bx+w/2),y:cy-(by+h/2),point:{x,y},box,ratio:(s.start+t)/ss.total,
            score:collisions*1e6+Math.abs(s.start+t-desired)+(flip<0?80:0)+extra*1.5,leader:extra>25});
        }
      }
    }
    candidates.sort((a,b)=>a.score-b.score);return candidates[0];
  }
  function snap(label,points,p){const q=project(points,p);if(!q)return false;
    label.anchor={mode:'ratio',ratio:q.ratio,gap:7,side:{x:p.x-q.x,y:p.y-q.y}};return true;
  }
  function errors(graph){const out=[],ids=new Set();for(const a of graph.routeLabels||[]){
    if(ids.has(a.id))out.push('duplicate route label '+a.id);ids.add(a.id);
    if(!graph.edges.some(e=>e.id===a.edge)&&!(graph.sourceDraftOperations||[]).some(op=>op.kind==='remove-connection'&&op.id===a.edge))out.push('route label edge missing '+a.id);
    if(!Array.isArray(a.bbox)||a.bbox.length!==4||!a.bbox.every(Number.isFinite)||a.bbox[2]<=0||a.bbox[3]<=0)out.push('invalid route label bounds '+a.id);
    const p=a.anchor;if(p&&(!['ratio','source','target'].includes(p.mode)||!Number.isFinite(p.ratio)||p.ratio<0||p.ratio>1||!Number.isFinite(p.gap)||!p.side||!Number.isFinite(p.side.x)||!Number.isFinite(p.side.y)||p.mode!=='ratio'&&(!Number.isFinite(p.distance)||p.distance<0)))out.push('invalid route label anchor '+a.id);
  }return out;}
  const api={segments,project,initialize,place,snap,errors};root.SummaryRouteLabels=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
