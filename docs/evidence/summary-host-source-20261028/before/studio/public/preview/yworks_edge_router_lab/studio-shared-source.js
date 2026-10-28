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
    return {intern};
  }
  root.ArchCanvasSharedSource={pool};
})(typeof window==='undefined'?globalThis:window);
