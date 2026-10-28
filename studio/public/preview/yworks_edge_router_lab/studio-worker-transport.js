(function(root){
  'use strict';
  // Use Summary's native immutable-core transport in both directions. A channel
  // owns its cache; no references survive a failed send or a Worker generation.
  function endpoint(prefix){
    const native=root.SummaryNativeSemantic.transport(prefix);
    const sources=root.ArchCanvasSharedSource?.pool();
    return {
      pack(message){
        if(sources&&message.graph?.generic)message.graph.generic.ir=sources.intern(message.graph.generic.ir);
        return message.graph?{...message,graph:native.pack(message.graph)}:message;
      },
      unpack(message){
        if(sources&&message.graph?.nativeGeometryTransport===1&&message.graph.core){
          const packet=message.graph,core=packet.core;
          // Canonicalize before native.unpack installs the core in its cache.
          // Keep the packet and the caller's source object independently owned.
          message={...message,graph:{...packet,core:{...core,fields:{...core.fields,ir:sources.intern(core.fields.ir)}}}};
        }
        return message.graph?{...message,graph:native.unpack(message.graph)}:message;
      }
    };
  }
  function client(createWorker,onPending=()=>{}){
    let current=null,generation=0,request=0;
    function discard(channel,result=null){
      if(current===channel)current=null;
      channel.worker.terminate();
      for(const resolve of channel.pending.values())resolve(result);
      channel.pending.clear();onPending(false);
    }
    function ensure(){
      if(current)return current;
      try{
        const worker=createWorker();if(!worker)return null;
        const channel={worker,codec:endpoint('studio:'+ ++generation),pending:new Map()};
        current=channel;
        worker.onmessage=event=>{
          if(current!==channel)return;
          const resolve=channel.pending.get(event.data?.requestId);if(!resolve)return;
          // Cache misses are infrastructure failures, not a semantic refusal.
          // The caller re-evaluates the full original input with its usual gates.
          if(event.data.nativeTransportError){discard(channel);return;}
          try{
            const result=channel.codec.unpack(event.data);
            channel.pending.delete(event.data.requestId);resolve(result);if(!channel.pending.size)onPending(false);
          }catch(_){discard(channel);}
        };
        worker.onerror=()=>{if(current===channel)discard(channel);};
        worker.onmessageerror=()=>{if(current===channel)discard(channel);};
        return channel;
      }catch(_){return null;}
    }
    return {
      ensure,
      reset(){if(current)discard(current);},
      isPending(){return !!current?.pending.size;},
      cancel(){if(!current?.pending.size)return false;discard(current,{cancelled:true});return true;},
      async run(message){
        const channel=ensure();if(!channel)return null;
        return new Promise(resolve=>{
          const requestId=++request;channel.pending.set(requestId,resolve);
          try{channel.worker.postMessage(channel.codec.pack({...message,requestId,nativeWorkerTransport:1}));onPending(true);}
          catch(_){discard(channel);}
        });
      }
    };
  }
  root.ArchCanvasNativeWorkerTransport={endpoint,client};
})(typeof window==='undefined'?globalThis:window);
