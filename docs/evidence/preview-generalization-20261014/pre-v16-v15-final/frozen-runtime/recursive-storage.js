/* Per-model recursive documents can exceed localStorage's legacy draft quota. */
(function(root){
  let connection;
  function database(){if(!connection)connection=new Promise((resolve,reject)=>{const request=indexedDB.open('summary-merge-recursive',1);request.onupgradeneeded=()=>request.result.createObjectStore('models');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});return connection;}
  async function get(key){const db=await database();return new Promise((resolve,reject)=>{const tx=db.transaction('models','readonly'),request=tx.objectStore('models').get(key);request.onsuccess=()=>resolve(request.result||null);request.onerror=()=>reject(request.error);});}
  async function put(key,value){const db=await database();return new Promise((resolve,reject)=>{const tx=db.transaction('models','readwrite');tx.objectStore('models').put(value,key);tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);});}
  root.SummaryRecursiveStorage={get,put};
})(window);
