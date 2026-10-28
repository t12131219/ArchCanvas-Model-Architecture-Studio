/* Exact broad-phase queries. Callers retain their original narrow-phase math. */
(function(root){
  'use strict';
  const intersects=(a,b)=>a.x<=b.x+b.w&&a.x+a.w>=b.x&&a.y<=b.y+b.h&&a.y+a.h>=b.y;
  function boxes(items){
    function build(rows){
      if(!rows.length)return null;
      const x=Math.min(...rows.map(r=>r.x)),y=Math.min(...rows.map(r=>r.y));
      const node={x,y,w:Math.max(...rows.map(r=>r.x+r.w))-x,h:Math.max(...rows.map(r=>r.y+r.h))-y};
      if(rows.length<=12)node.rows=rows;else{
        const axis=node.w>=node.h?'x':'y';rows.sort((a,b)=>a[axis]-b[axis]);const mid=rows.length>>1;
        node.left=build(rows.slice(0,mid));node.right=build(rows.slice(mid));
      }return node;
    }
    const tree=build(items.slice());
    return {query(box){const found=[],todo=tree?[tree]:[];while(todo.length){const node=todo.pop();if(!intersects(node,box))continue;
      if(node.rows){for(const row of node.rows)if(intersects(row,box))found.push(row);}else todo.push(node.left,node.right);
    }return found;}};
  }
  // Append-only multiscale cells. A segment occupies at most four cells at
  // its own scale; long dependencies never populate thousands of tiny cells.
  // Exact bounding checks and insertion order are retained after each query.
  function segments(){
    const levels=new Map();let count=0;
    return {add(a,b){
      const row={vertical:a.x===b.x,x:a.x,y:a.y,left:Math.min(a.x,b.x),right:Math.max(a.x,b.x),top:Math.min(a.y,b.y),bottom:Math.max(a.y,b.y),order:count++};
      const size=2**Math.ceil(Math.log2(Math.max(1,row.right-row.left,row.bottom-row.top)));
      if(!levels.has(size))levels.set(size,{columns:new Map(),rows:new Map()});const level=levels.get(size);
      for(let x=Math.floor(row.left/size);x<=Math.floor(row.right/size);x++)for(let y=Math.floor(row.top/size);y<=Math.floor(row.bottom/size);y++){
        if(!level.columns.has(x))level.columns.set(x,new Map());if(!level.rows.has(y))level.rows.set(y,new Map());
        let cell=level.columns.get(x).get(y);if(!cell){cell=[];level.columns.get(x).set(y,cell);level.rows.get(y).set(x,cell);}cell.push(row);
      }
    },query(a,b){
      const left=Math.min(a.x,b.x),right=Math.max(a.x,b.x),top=Math.min(a.y,b.y),bottom=Math.max(a.y,b.y),found=new Set();
      const visit=cell=>{for(const r of cell)if(r.left<=right&&r.right>=left&&r.top<=bottom&&r.bottom>=top)found.add(r);};
      const range=(map,low,high,fn)=>{if(high-low+1<map.size){for(let at=low;at<=high;at++)if(map.has(at))fn(map.get(at));}else for(const [at,value]of map)if(at>=low&&at<=high)fn(value);};
      for(const [size,level]of levels){
        const x0=Math.floor(left/size),x1=Math.floor(right/size),y0=Math.floor(top/size),y1=Math.floor(bottom/size);
        if(x1-x0<=y1-y0)range(level.columns,x0,x1,column=>range(column,y0,y1,visit));else range(level.rows,y0,y1,row=>range(row,x0,x1,visit));
      }
      return [...found].sort((a,b)=>a.order-b.order);
    }};
  }
  const api={boxes,segments};root.SemanticGeometryIndex=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
