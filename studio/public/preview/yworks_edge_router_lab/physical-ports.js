/* Presentation ports are movable; canonical model fields and SVG evidence are not. */
(function(root){
  'use strict';
  const R=root.EdgeRouterLabRouting,EPS=1e-5;
  const key=side=>side[0].toUpperCase()+side.slice(1);
  const active=(e,side)=>e['physical'+key(side)]||e['fixed'+key(side)];
  function point(n,f){const p=R.port(n,f.side,f.fraction);return f.offset?{...p,x:n.x+f.offset.x,y:n.y+f.offset.y}:p;}
  function slot(e,side){if(e.projection?.presentationSlots?.[side])return e.projection.presentationSlots[side];if(e.portPolicy?.[side]?.presentationSlot)return e.portPolicy[side].presentationSlot;const b=e.binding||{},c=b.endpoint_binding?.canonical,which=side==='source'?'src':'dst';
    return b['canonical_'+which]||(c?.[which]?c[which]+':'+c[which+'_port']:null)||
      (b['semantic_'+which]?b['semantic_'+which]+':'+b['semantic_'+which+'_port']:null)||b[which]||e.id+':'+side;}
  function peers(graph,e,side){return graph.edges.flatMap(v=>['source','target'].filter(s=>v!==e&&v[s]===e[side]).map(s=>({edge:v,side:s})));}
  function policy(graph,e,side){return e.portPolicy?.[side]||{mode:'fixed',reason:'unregistered source interface'};}
  function permitted(graph,e,side,f){
    const n=graph.nodes.find(n=>n.id===e[side]),p=policy(graph,e,side),original=e['fixed'+key(side)];
    if(!n||!f||!R.SIDE[f.side]||!Number.isFinite(f.fraction)||f.fraction<0||f.fraction>1)return false;
    if(JSON.stringify(f)===JSON.stringify(original)){
      // Registered original slots may be closer than the free-port spacing.
      // That exemption does not license returning onto a peer which moved
      // into this slot while it was vacant earlier in the routing batch.
      const xy=point(n,f),identity=(v,s)=>n.visualBinding?.canonical||slot(v,s);
      return !peers(graph,e,side).some(({edge:v,side:s})=>!v.draft&&identity(v,s)!==identity(e,side)&&
        JSON.stringify(active(v,s))!==JSON.stringify(v['fixed'+key(s)])&&R.dist(xy,point(n,active(v,s)))<(p.spacing||12)-EPS);
    }
    if(p.mode==='fixed')return JSON.stringify(f)===JSON.stringify(original);
    if(f.inward!==original?.inward||p.mode==='side'&&f.side!==original?.side)return false;
    const xy=point(n,f),boundary=R.port(n,f.side,f.fraction);
    if(R.dist(xy,boundary)>EPS)return false;
    // A semantic junction has a position, but no painted left/right edge or
    // competing operand slots. Its approach direction follows the routed bus.
    if(n.junction)return true;
    if(p.shape==='circle'&&Math.abs(f.fraction-.5)>EPS)return false;
    const size=['left','right'].includes(f.side)?n.h:n.w,pad=Math.min(12,size/4);
    if(p.shape!=='circle'&&(f.fraction*size<pad-EPS||(1-f.fraction)*size<pad-EPS))return false;
    // A value alias represents one tensor even when its consumers name
    // different canonical fields. Use the allocator's same slot identity.
    const identity=(v,s)=>n.visualBinding?.canonical||slot(v,s);
    // A pending visual reconnection does not redefine registered model slots.
    // Its occupied route is still considered by the geometry router.
    return !peers(graph,e,side).some(({edge:v,side:s})=>!v.draft&&identity(v,s)!==identity(e,side)&&
      R.dist(xy,point(n,active(v,s)))<(p.spacing||12)-EPS);
  }
  function candidates(graph,e,side,rule='any'){
    const n=graph.nodes.find(n=>n.id===e[side]),other=graph.nodes.find(n=>n.id===e[side==='source'?'target':'source']),p=policy(graph,e,side),original=e['fixed'+key(side)],out=[];
    const add=f=>{if(f&&permitted(graph,e,side,f)&&!out.some(v=>R.dist(point(n,v),point(n,f))<EPS&&v.side===f.side))out.push(f);};
    add(active(e,side));add(original);if(p.mode==='fixed')return out;
    if(n.junction){for(const s of p.mode==='side'?[original.side]:R.candidateSides(n,other,rule))add({side:s,fraction:.5,inward:original.inward});return out;}
    const otherPort=active(e,side==='source'?'target':'source'),op=otherPort?point(other,otherPort):{x:other.x+other.w/2,y:other.y+other.h/2};
    for(const s of p.mode==='side'?[original.side]:R.candidateSides(n,other,rule)){
      const vertical=s==='left'||s==='right',size=vertical?n.h:n.w,origin=vertical?n.y:n.x;
      const fractions=p.shape==='circle'?[.5]:[.5,(op[vertical?'y':'x']-origin)/size,((vertical?other.y+other.h/2:other.x+other.w/2)-origin)/size,original.fraction];
      // Do not clamp an out-of-range projection onto a rounded corner: that
      // creates an artificial shortcut and a visually misplaced terminal.
      const pad=Math.min(12,size/4);
      for(const fraction of fractions)if(fraction>=pad/size&&fraction<=1-pad/size)add({side:s,fraction,inward:original.inward});
    }
    return out;
  }
  function errors(graph,e,points=e.route){
    const result=[];
    for(const [side,index]of [['source',0],['target',-1]]){
      const f=e['physical'+key(side)],n=graph.nodes.find(n=>n.id===e[side]);
      if(f&&!permitted(graph,e,side,f))result.push('unregistered or colliding physical '+side+' port');
      const a=active(e,side),p=points?.at(index);
      if(n&&a&&p&&R.dist(point(n,a),p)>EPS)result.push('physical endpoint differs from registered '+side+' port');
    }
    return result;
  }
  const api={active,point,slot,policy,permitted,candidates,errors};
  root.SummaryPhysicalPorts=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
