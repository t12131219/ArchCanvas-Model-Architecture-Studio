import type { ArchitectureNode, CanvasDocument, EdgeRole, Scene, SceneNode, ScenePort } from '../../../../studio/src/core/types.ts';

// Literal contracts are authored here before validation; no product factory,
// layout, port projection or routing helper generates an expected value.
export function genericDocument(prefix: string, options: { role?: EdgeRole; repeat?: boolean; expanded?: boolean; sourceRepeat?: boolean; pinned?: boolean } = {}): CanvasDocument {
  const id = (name: string) => `${prefix}/${name}`;
  const root=id('frame'),feed=id('feed'),proxy=id('cell'),inner=id('operator'),merge=id('merge');
  const port = (owner:string,name:string,direction:'in'|'out') => ({id:`${owner}:${name}`,name,direction,role:'data',ordinal:0});
  const node = (identity:string,label:string,kind:string,category:string,children:string[],parentId?:string):ArchitectureNode =>
    ({id:identity,label,kind,category,children,parentId,ports:[],parameters:{},evidence:'contract'});
  const nodes=[node(root,'Frame','Module','container',[feed,proxy]),node(feed,'Feed','Linear','linear',[],root),
    node(proxy,'Cell',options.repeat===false?'Module':'Repeat','container',[inner,merge],root),
    node(inner,'Operator','Linear','linear',[],proxy),node(merge,'Merge','Add','residual',[],proxy)];
  nodes[1].ports=[port(feed,'out','out')];nodes[3].ports=[port(inner,'in','in')];nodes[4].ports=[port(merge,'in','in')];
  if(options.repeat!==false)nodes[2].repeat={count:2,sharing:'independent'};
  if(options.sourceRepeat)nodes[1].repeat={count:3,sharing:'shared'};
  const edges=[{id:id('ordinary'),source:{nodeId:feed,portId:`${feed}:out`},target:{nodeId:inner,portId:`${inner}:in`},tensorId:id('tensor'),role:'data' as const},
    {id:id('skip'),source:{nodeId:feed,portId:`${feed}:out`},target:{nodeId:merge,portId:`${merge}:in`},tensorId:id('tensor'),role:options.role??'residual'}];
  return {schemaVersion:1,id:`${prefix}-document`,title:'Independent generic fixture',revision:7,sourceBindingDigest:'a'.repeat(64),
    architecture:{schemaVersion:1,id:id('architecture'),label:'Generic graph',entry:id('entry'),sourceDigest:'a'.repeat(64),irDigest:'b'.repeat(64),
      nodes,edges,diagnostics:[],sources:[]},displayAliases:{},nodeStyleOverrides:{},edgeStyleOverrides:{},legendItems:[],annotations:[],
    pageSpec:{widthMm:180,background:'#ffffff',preset:'paper'},expandedIds:options.expanded?[root,proxy]:[root],
    layout:{[root]:{x:50,y:92},[feed]:{x:30,y:62},[proxy]:{x:30,y:162},[inner]:{x:30,y:62},[merge]:{x:30,y:162}},
    layoutByFrontier:{},pinnedObjects:options.pinned?[feed,proxy]:[]};
}

export function literalNode(id:string,x:number,y:number,width:number,height:number,options:Partial<SceneNode>={}):SceneNode {
  return {id,x,y,width,height,localX:x,localY:y,label:id,subtitle:'',kind:'Linear',category:'linear',headerHeight:20,
    fill:'#ffffff',stroke:'#000000',glyph:'operator',expanded:false,expandable:false,pinned:false,evidence:'contract',ports:[],...options};
}
export function literalPort(owner:string,canonical:string,canonicalPort:string,edgeId:string,direction:'in'|'out',x:number,y:number,proxy=false):ScenePort {
  return {id:`${owner}/${direction}/${edgeId}`,canonicalNodeId:canonical,canonicalPortId:canonicalPort,
    canonicalBindings:[{nodeId:canonical,portId:canonicalPort}],canonicalEdgeIds:[edgeId],direction,role:'data',name:direction,x,y,proxy};
}
export function literalRoutingCase(options:{role?:EdgeRole;targetExpanded?:boolean;targetProxy?:boolean;upward?:boolean;misaligned?:boolean;repeat?:boolean;pinned?:boolean}={}) {
  const edgeId='branch/skip', source='arbitrary-producer',target='collapsed-unit',canonicalTarget='hidden-join',
    endX=options.misaligned?70:50,endY=options.upward?-50:100;
  const start={x:50,y:50},end={x:endX,y:endY};
  const sourceNode=literalNode(source,0,0,100,50,{parentId:'shell',pinned:options.pinned??false});
  const targetNode=literalNode(target,endX-50,endY,100,50,{parentId:'shell',kind:'Module',category:'container',expandable:true,
    expanded:options.targetExpanded??false,pinned:options.pinned??false,repeat:options.repeat?{count:2,sharing:'shared'}:undefined});
  sourceNode.ports=[literalPort(source,source,'producer-output',edgeId,'out',start.x,start.y)];
  targetNode.ports=[literalPort(target,options.targetProxy===false?target:canonicalTarget,'hidden-input',edgeId,'in',end.x,end.y,options.targetProxy!==false)];
  targetNode.ports[0].role=options.role??'residual';
  const frame=literalNode('shell',-20,options.upward?-90:-30,180,options.upward?210:220,{expanded:true,expandable:true,kind:'Module',category:'container'});
  const path=options.upward?'M 50 50 V 60 H 130 V -60 H 50 V -50':`M 50 50 V 60 H 150 V 90 H ${endX} V 100`;
  const role=options.role??'residual',appearance={stroke:'#b69967',width:1.5,dashed:false};
  const edge={id:edgeId,sourceId:source,targetId:target,source:{nodeId:source,portId:'producer-output'},
    target:{nodeId:options.targetProxy===false?target:canonicalTarget,portId:'hidden-input'},canonicalEdgeIds:[edgeId],tensorId:'same-source-tensor',role,path,...appearance,label:'',labelX:157,labelY:75};
  const scene:Scene={version:'1.0',documentId:'manual-independent',revision:0,title:'Literal routing case',bounds:{x:-100,y:-100,width:400,height:400},
    nodes:[frame,sourceNode,targetNode],edges:[edge],hiddenEdges:[],legend:[],annotations:[],pageSpec:{widthMm:180,background:'#fff',preset:'paper'},
    sourceDigest:'a'.repeat(64),irDigest:'b'.repeat(64),sourceFacts:[],diagnostics:[]};
  const request={sourceId:source,targetId:target,start,end,preferredPath:path,tensorId:edge.tensorId,role,appearance,
    canonicalSource:{...edge.source},canonicalTarget:{...edge.target},canonicalEdgeIds:[edgeId],displaySide:'bottom' as const};
  return {scene,requests:[request],edgeId,sourceId:source,targetId:target,literalExpected:'M 50 50 V 100'};
}

export function addProtectedRoute(fixture:ReturnType<typeof literalRoutingCase>, shape:'horizontal'|'overlap'|'split-vertical'|'bend-vertex',sameTensor:boolean,role:EdgeRole='data') {
  const id='protected/edge',source='protected/producer',target='protected/consumer';
  const positions=shape==='horizontal'?{a:{x:-20,y:75},b:{x:70,y:75},nodes:[literalNode(source,-40,65,20,20),literalNode(target,70,65,20,20)],path:'M -20 75 H 70'}:
    shape==='overlap'?{a:{x:-20,y:65},b:{x:-20,y:85},nodes:[literalNode(source,-40,55,20,20),literalNode(target,-40,75,20,20)],path:'M -20 65 H 50 V 85 H -20'}:
    shape==='split-vertical'?{a:{x:60,y:65},b:{x:60,y:85},nodes:[literalNode(source,58,63,4,2),literalNode(target,58,85,4,2)],path:'M 60 65 V 75 V 85'}:
    {a:{x:-20,y:75},b:{x:-20,y:80},nodes:[literalNode(source,-40,73,20,2),literalNode(target,-40,80,20,2)],path:'M -20 75 H 50 V 80 H -20'};
  const [a,b]=positions.nodes;a.parentId='shell';b.parentId='shell';a.ports=[literalPort(source,source,'out',id,'out',positions.a.x,positions.a.y)];
  b.ports=[literalPort(target,target,'in',id,'in',positions.b.x,positions.b.y)];
  fixture.scene.nodes.push(a,b);
  const appearance={stroke:'#115588',width:2,dashed:role==='mask'};
  const edge={id,sourceId:source,targetId:target,source:{nodeId:source,portId:'out'},target:{nodeId:target,portId:'in'},canonicalEdgeIds:[id],
    tensorId:sameTensor?fixture.requests[0].tensorId:'independent-other-tensor',role,path:positions.path,...appearance,label:'',labelX:0,labelY:0};
  fixture.scene.edges.push(edge);
  fixture.requests.push({sourceId:source,targetId:target,start:positions.a,end:positions.b,preferredPath:positions.path,tensorId:edge.tensorId,role,
    appearance,canonicalSource:{...edge.source},canonicalTarget:{...edge.target},canonicalEdgeIds:[id],displaySide:'bottom'});
  return fixture;
}
