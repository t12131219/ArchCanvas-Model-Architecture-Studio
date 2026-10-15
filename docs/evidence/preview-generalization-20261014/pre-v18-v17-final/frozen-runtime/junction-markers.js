/* Source-authorized fork markers follow actual shared routes, never SVG paint order. */
(function(root){
  'use strict';
  const R=root.EdgeRouterLabRouting,EPS=1e-5;
  function onSegment(p,a,b){
    return Math.abs(a.x-b.x)<EPS?Math.abs(p.x-a.x)<EPS&&p.y>=Math.min(a.y,b.y)-EPS&&p.y<=Math.max(a.y,b.y)+EPS:
      Math.abs(a.y-b.y)<EPS&&Math.abs(p.y-a.y)<EPS&&p.x>=Math.min(a.x,b.x)-EPS&&p.x<=Math.max(a.x,b.x)+EPS;
  }
  function contains(route,p){return route.slice(1).some((b,i)=>onSegment(p,route[i],b));}
  function rays(routes,p){const result=new Set();
    for(const ps of routes)for(let i=1;i<ps.length;i++)if(onSegment(p,ps[i-1],ps[i]))for(const q of [ps[i-1],ps[i]]){
      if(R.dist(p,q)<EPS)continue;
      result.add(Math.abs(q.x-p.x)<EPS?(q.y>p.y?'down':'up'):(q.x>p.x?'right':'left'));
    }
    return result;
  }
  function point(graph,marker){
    const edges=marker.edges.map(id=>graph.edges.find(e=>e.id===id));
    // A visual draft can release a fork, but cannot leave its old dot floating.
    if(edges.some(e=>!e||e.draft))return null;
    const routes=edges.map(e=>e.route),owner=graph.nodes.find(n=>n.id===marker.owner);
    const expected={x:marker.original[0]+(owner?owner.x-owner.base[0]:0),y:marker.original[1]+(owner?owner.y-owner.base[1]:0)};
    const candidates=routes.flat().filter(p=>routes.every(ps=>contains(ps,p))&&rays(routes,p).size>=3);
    return candidates.sort((a,b)=>R.dist(a,expected)-R.dist(b,expected))[0]||null;
  }
  const api={point,contains,rays};root.SummaryJunctionMarkers=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
