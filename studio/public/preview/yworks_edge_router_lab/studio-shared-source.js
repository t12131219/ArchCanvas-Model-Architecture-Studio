(function(root){
  'use strict';
  // Native build defensively copies its input IR. Intern complete equal JSON
  // facts at the integration boundary so cuts/history can share frozen source.
  // A digest only filters candidates; it never establishes equality or trust.
  function pool(){
    const entries=[],frozen=new WeakSet();
    function freeze(value){
      if(!value||typeof value!=='object'||frozen.has(value))return;
      frozen.add(value);for(const child of Object.values(value))freeze(child);Object.freeze(value);
    }
    function equal(a,b){
      if(Object.is(a,b))return true;
      if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;
      if(Array.isArray(a)&&a.length!==b.length)return false;
      const keys=Object.keys(a);if(keys.length!==Object.keys(b).length)return false;
      return keys.every(key=>Object.hasOwn(b,key)&&equal(a[key],b[key]));
    }
    function intern(ir){
      if(!ir||typeof ir!=='object')return ir;
      freeze(ir);
      const index=entries.findIndex(value=>value.schema===ir.schema&&value.ir_digest===ir.ir_digest&&equal(value,ir));
      if(index>=0){const [value]=entries.splice(index,1);entries.push(value);return value;}
      entries.push(ir);if(entries.length>4)entries.shift();return ir;
    }
    // Build an independent JSON snapshot without serializing complete source
    // IR on every host notification. Structured clone preserves these shared
    // immutable references across graph, adapter and original document.
    // This is lossless sharing, not source validation or a portable JSON codec.
    function copy(value){
      const active=new WeakSet(),sources=new Map();
      function visit(item,array=false){
        if(item===null||typeof item==='string'||typeof item==='boolean')return item;
        if(typeof item==='number')return Number.isFinite(item)?item:null;
        if(typeof item==='bigint')throw new TypeError('Cannot snapshot BigInt as JSON');
        if(typeof item!=='object')return array?null:undefined;
        if(item.schema==='archcanvas-source-semantic/2'&&Array.isArray(item.nodes)&&Array.isArray(item.edges)){
          // A workspace may contain more than four distinct module fragments.
          // The bounded session pool can evict its original IR while copying
          // them; retain exact aliases only for this one snapshot as well.
          const candidates=sources.get(item.ir_digest)||[],known=candidates.find(value=>equal(value,item));
          if(known)return known;
          const canonical=intern(item);candidates.push(canonical);sources.set(item.ir_digest,candidates);return canonical;
        }
        if(active.has(item))throw new TypeError('Cannot snapshot cyclic JSON');
        active.add(item);
        const result=Array.isArray(item)?Array.from(item,v=>visit(v,true)):Object.fromEntries(Object.keys(item).flatMap(key=>{const next=visit(item[key]);return next===undefined?[]:[[key,next]];}));
        active.delete(item);return result;
      }
      return visit(value);
    }
    return {intern,copy};
  }
  root.ArchCanvasSharedSource={pool};
})(typeof window==='undefined'?globalThis:window);
