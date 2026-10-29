importScripts('router.js','physical-ports.js','junction-markers.js','route-labels.js','source-contracts.js','semantic-constraints.js','graph-engine.js','recursive-graph.js','source-controls.js','frontier-task.js');
importScripts('../semantic_studio/symbolic-values.js','../semantic_studio/structural-representatives.js','../semantic_studio/role-path-stages.js','../semantic_studio/role-operation-stages.js','../semantic_studio/contract-stages.js','../semantic_studio/dimension-paths.js','../semantic_studio/local-pipelines.js','../semantic_studio/local-expressions.js','../semantic_studio/role-frontier.js','../semantic_studio/frame-ownership.js','../semantic_studio/sequence-frontier.js','../semantic_studio/local-relations.js','../semantic_studio/relation-constraints.js','../semantic_studio/expression-goals.js','../semantic_studio/architecture.js','../semantic_studio/geometry-index.js','../semantic_studio/architecture-layout.js','../semantic_studio/semantic-engine.js','../semantic_studio/branch-regions.js','../semantic_studio/presentation-regions.js','../semantic_studio/invocation-inputs.js','../semantic_studio/module-arguments.js','../semantic_studio/transform-configurations.js','../semantic_studio/publication.js','../semantic_studio/composition-layout.js','../semantic_studio/authoring-model.js','../semantic_studio/summary-goals.js','../semantic_studio/adaptive-frontier.js','../semantic_studio/semantic-evidence.js','flow-optimizer.js','source-runtime.js','generic-semantic.js','studio-shared-source.js','studio-worker-transport.js','studio-adaptive.js','studio-semantic.js');
const validateView=graph=>SummaryEngine.validateView(graph);
const transport=ArchCanvasNativeWorkerTransport.endpoint('worker');
self.onmessage = event => {
  const {requestId,nativeWorkerTransport}=event.data;
  let message;
  try{message=nativeWorkerTransport===1?transport.unpack(event.data):event.data;}
  catch(error){self.postMessage({requestId,ok:false,nativeTransportError:true,error:error.message});return;}
  const {task,graph,ids,options,id,dx,dy}=message;
  const reply=value=>self.postMessage(nativeWorkerTransport===1?transport.pack(value):value);
  try{
    if(task==='generic-build'||task==='generic-route'||task==='frontier'&&graph.generic){reply({requestId,...ArchCanvasSemanticView.prepare(message)});}
    else if(task==='frontier'){reply({requestId,...SummaryFrontierTask.run(graph,message.transition,options)});}
    else if(task==='optimize'){const result=SummaryEngine.optimizeRoutes(graph,ids,options);SummarySourceControls.refresh(graph);reply({requestId,...result});}
    else if(task==='validate'){const validation=validateView(graph);SummarySourceControls.refresh(graph);reply({requestId,ok:true,graph,validation});}
    else if(task==='move'){
      SummaryEngine.move(graph,id,dx,dy,options);
      const validation=validateView(graph),invalid=validation.edges.filter(([,check])=>!check.ok).map(([id])=>id);
      if(!validation.source.ok||!validation.layout.ok||invalid.length)throw new Error('移动后的图未通过完整校验: '+[...validation.source.violations,...validation.layout.violations,...invalid].join('; '));
      SummarySourceControls.refresh(graph);
      reply({requestId,ok:true,graph,validation});
    }else {const result=SummaryEngine.routeBatch(graph,ids,{...options,edgeIds:ids}),validation=validateView(graph);SummarySourceControls.refresh(graph);reply({requestId,ok:true,...result,validation});}
  }catch(error){reply({requestId,ok:false,error:error.message});}
};
