/* Camera-only navigation. No graph, route, source or history mutation. */
(function(root){
  'use strict';
  function readable(node,viewport,nodes=[]){
    const width=Math.max(120,viewport.width),height=Math.max(120,viewport.height);
    // A source frame can be much wider than its first visible content. Anchor
    // the reading camera to actual leaf glyphs, not an empty frame corner.
    // This is camera-only: no cut, graph positions, routes or selection change.
    if(node.expanded&&nodes.length){
      const by=new Map(nodes.map(n=>[n.id,n])),within=n=>{let at=n;while(at){if(at.parent===node.id)return true;at=by.get(at.parent);}return false;};
      const leaves=nodes.filter(n=>!n.expanded&&!n.junction&&within(n)).sort((a,b)=>a.y-b.y||a.x-b.x);
      if(leaves.length){
        const first=leaves[0],band=leaves.filter(n=>n.y<first.y+180&&Math.abs(n.x-first.x)<700);
        const left=Math.min(...band.map(n=>n.x)),top=Math.min(...band.map(n=>n.y));
        node={x:left,y:top,w:Math.max(...band.map(n=>n.x+n.w))-left,h:Math.max(...band.map(n=>n.y+n.h))-top};
      }
    }
    // A very deep container opens at its heading and first content band;
    // fitting its entire subtree would make navigation unreadable again.
    const scale=Math.min(1,(width-48)/Math.min(node.w,900),(height-48)/Math.min(node.h,420));
    const w=width/scale,h=height/scale;
    return {x:node.x+Math.min(node.w,w-48)/2-w/2,y:node.y+Math.min(node.h,h-48)/2-h/2,w,h};
  }
  function overview(canvas,viewport){
    const ratio=viewport.width/Math.max(1,viewport.height),[w,h]=canvas;
    return w/h>ratio?{x:0,y:(h-w/ratio)/2,w,h:w/ratio}:{x:(w-h*ratio)/2,y:0,w:h*ratio,h};
  }
  root.ArchCanvasViewNavigation={readable,overview};
})(typeof window!=='undefined'?window:globalThis);
