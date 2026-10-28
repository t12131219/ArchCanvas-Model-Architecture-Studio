/* Selection is presentation state. It never changes graph facts or history. */
(function(root){
  'use strict';
  function update(current, ids, mode='replace') {
    if(!['replace','add','toggle'].includes(mode))throw new Error('选择方式无效。');
    const result=new Set(mode==='replace'?[]:current);
    for(const id of ids)if(mode==='toggle'&&result.has(id))result.delete(id);else result.add(id);
    return result;
  }
  function inBox(nodes,a,b) {
    const left=Math.min(a.x,b.x),right=Math.max(a.x,b.x),top=Math.min(a.y,b.y),bottom=Math.max(a.y,b.y);
    // Expanded frames are scopes; selecting their children avoids parent/child
    // ambiguity when a rectangle spans multiple levels.
    return nodes.filter(n=>!n.junction&&!n.expanded&&n.x>=left&&n.y>=top&&n.x+n.w<=right&&n.y+n.h<=bottom).map(n=>n.id);
  }
  function targets(nodes, selected, scope) {
    const candidates=nodes.filter(n=>!n.junction);
    if(scope==='siblings') {
      const first=candidates.find(n=>selected.has(n.id));
      if(!first)throw new Error('先选择一个节点，再选择同级节点。');
      return candidates.filter(n=>(n.parent||null)===(first.parent||null)).map(n=>n.id);
    }
    if(scope==='all')return candidates.filter(n=>!n.expanded).map(n=>n.id);
    throw new Error('选择范围无效。');
  }
  root.ArchCanvasStudioSelection={update,inBox,targets};
})(typeof window==='undefined'?globalThis:window);
