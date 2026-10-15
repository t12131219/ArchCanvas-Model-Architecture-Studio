importScripts('router.js','physical-ports.js','junction-markers.js','route-labels.js','source-contracts.js','semantic-constraints.js','graph-engine.js','recursive-graph.js','frontier-task.js');
const validateView=graph=>SummaryEngine.validateView(graph);
self.onmessage = event => {
  const {requestId,task,graph,ids,options,id,dx,dy}=event.data;
  try{
    if(task==='frontier'){self.postMessage({requestId,...SummaryFrontierTask.run(graph,event.data.transition,options)});}
    else if(task==='validate'){self.postMessage({requestId,ok:true,graph,validation:validateView(graph)});}
    else if(task==='move'){
      SummaryEngine.move(graph,id,dx,dy,options);
      const validation=validateView(graph),invalid=validation.edges.filter(([,check])=>!check.ok).map(([id])=>id);
      if(!validation.source.ok||!validation.layout.ok||invalid.length)throw new Error('移动后的图未通过完整校验: '+[...validation.source.violations,...validation.layout.violations,...invalid].join('; '));
      self.postMessage({requestId,ok:true,graph,validation});
    }else {const result=SummaryEngine.routeBatch(graph,ids,options);self.postMessage({requestId,ok:true,...result,validation:validateView(graph)});}
  }catch(error){self.postMessage({requestId,ok:false,error:error.message});}
};
