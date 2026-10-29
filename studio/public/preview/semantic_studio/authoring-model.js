/* Editable documents own their changes. Source evidence is retained as provenance,
 * never silently resealed or presented as certification of an edited program. */
(function(root){
  'use strict';
  const copy=x=>JSON.parse(JSON.stringify(x));
  const schema='semantic-authoring/1';
  // A storage/cache key, not a source certificate. Counts and a revision alone
  // collide across independent drafts, so include the actual declared facts.
  function draftKey(value){const text=JSON.stringify(value);let a=2166136261,b=3339675911;for(let i=0;i<text.length;i++){a=Math.imul(a^text.charCodeAt(i),16777619);b=Math.imul(b^text.charCodeAt(i),2246822519);}return 'authored:'+text.length+':'+(a>>>0).toString(16)+':'+(b>>>0).toString(16);}
  function empty(title='未命名模型'){return {schema,title,nodes:[],edges:[],sources:[],modules:{},library:[],open:[],offsets:{},serial:0,editorScope:null,baseline:null,recipe:null};}
  function closure(doc,ids){const found=new Set(ids),children=new Map();for(const n of doc.nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}const todo=[...found];for(let i=0;i<todo.length;i++)for(const id of children.get(todo[i])||[])if(!found.has(id)){found.add(id);todo.push(id);}return found;}
  function validate(doc){
    if(doc?.schema!==schema||!Array.isArray(doc.nodes)||!Array.isArray(doc.edges)||doc.nodes.length>16000||doc.edges.length>50000)throw Error('不是有效的编辑文档或超过图规模限制');
    if(!Array.isArray(doc.sources)||!Array.isArray(doc.library)||!Array.isArray(doc.open)||!doc.modules||typeof doc.modules!=='object'||!doc.offsets||typeof doc.offsets!=='object'||!Number.isFinite(doc.serial))throw Error('编辑文档缺少源码、模块库或展示状态');
    const by=new Map(doc.nodes.map(n=>[n.id,n]));if(by.size!==doc.nodes.length)throw Error('重复节点身份');const edgeIds=new Set();
    for(const n of doc.nodes){if(!n.id||!n.label)throw Error('节点缺少身份或名称');if(n.parent&&(!by.has(n.parent)||by.get(n.parent).kind!=='composite'))throw Error('父模块不存在或不是容器');const seen=new Set();let at=n;while(at){if(seen.has(at.id))throw Error('模块包含关系成环');seen.add(at.id);at=by.get(at.parent);}}
    for(const e of doc.edges){if(edgeIds.has(e.id)||!by.has(e.source)||!by.has(e.target)||e.source_port==null||e.target_port==null)throw Error('连接身份、端点或槽位无效');edgeIds.add(e.id);}
    for(const id of Object.keys(doc.modules||{}))if(!by.has(id))throw Error('模块定义没有对应节点');
    return true;
  }
  function fromIR(ir){const doc=empty(ir.title);doc.nodes=copy(ir.nodes);doc.edges=copy(ir.edges);doc.sources=copy(ir.sources||[]);doc.baseline=copy(ir);return doc;}
  function fragment(ir,ids,title){const inside=closure(ir,ids),nodes=copy(ir.nodes.filter(n=>inside.has(n.id))),edges=copy(ir.edges.filter(e=>inside.has(e.source)&&inside.has(e.target)));
    const parents={};for(const n of nodes)if(n.parent&&!inside.has(n.parent)){parents[n.id]=n.parent;n.parent=null;}
    return {schema:'semantic-module/1',title:title||nodes[0]?.label||'组合模块',entry:null,constructor:{},ir:{schema:'archcanvas-source-semantic/2',title:title||'组合模块',nodes,edges,sources:copy(ir.sources||[])},parents,
      boundary:copy(ir.edges.filter(e=>inside.has(e.source)!==inside.has(e.target)))};
  }
  function remap(value,ids){if(Array.isArray(value))return value.map(v=>remap(v,ids));if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[ids.get(k)||k,remap(v,ids)]));return ids.get(value)||value;}
  function add(doc,module,{keepIdentity=false,parent=null}={}){
    const nodes=module.ir.nodes,edges=module.ir.edges,ids=new Map(),prefix='edit:'+ (++doc.serial)+':';
    for(const x of [...nodes,...edges])ids.set(x.id,keepIdentity?x.id:prefix+x.id);
    if(nodes.some(n=>doc.nodes.some(x=>x.id===ids.get(n.id))))throw Error('此构件已加入；复制请使用“复制模块”');
    const inserted=remap(nodes,ids),links=remap(edges,ids);for(const n of inserted)if(!n.parent)n.parent=parent;
    doc.nodes.push(...inserted);doc.edges.push(...links);
    for(const s of module.ir.sources||[])if(!doc.sources.some(v=>v.path===s.path))doc.sources.push(copy(s));
    const roots=inserted.filter(n=>!n.parent||n.parent===parent).map(n=>n.id);
    if(module.components)for(const [id,value]of Object.entries(remap(module.components,ids)))doc.modules[id]=value;
    for(const id of roots)doc.modules[id]={title:module.title,source:module.source||null,entry:module.entry||null,constructor:copy(module.constructor||{}),origin:module.ir.ir_digest||null,codeBinding:Object.fromEntries(ids),...(module.sourceLibrary?{sourceLibrary:copy(module.sourceLibrary)}:{})};
    if(keepIdentity&&doc.recipe){const present=new Set(doc.nodes.map(n=>n.id));for(const n of doc.nodes){const original=doc.recipe.parents[n.id];if(original&&present.has(original))n.parent=original;}}
    return {roots,ids:Object.fromEntries(ids)};
  }
  function erase(doc,ids){const gone=closure(doc,ids);doc.nodes=doc.nodes.filter(n=>!gone.has(n.id));doc.edges=doc.edges.filter(e=>!gone.has(e.source)&&!gone.has(e.target));doc.open=doc.open.filter(id=>!gone.has(id));for(const id of gone){delete doc.modules[id];delete doc.offsets[id];}return gone;}
  function portIndex(doc){
    const nodes=new Map(doc.nodes.map(n=>[n.id,n])),children=new Map(),incoming=new Map(),outgoing=new Map(),order=new Map(),cache=new Map();
    for(const n of doc.nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n);}
    doc.edges.forEach((e,i)=>{order.set(e,i);for(const [map,id]of [[incoming,e.target],[outgoing,e.source]]){if(!map.has(id))map.set(id,[]);map.get(id).push(e);}});
    return {nodes,children,incoming,outgoing,order,cache};
  }
  function ports(doc,id,index=portIndex(doc)){
    if(index.cache.has(id))return index.cache.get(id);
    const n=index.nodes.get(id);if(!n)throw Error('模块不存在');const children=index.children.get(id)||[],inputs=[],outputs=[];
    function put(list,node,port,label){if(!list.some(p=>p.node===node&&p.port===String(port)))list.push({node,port:String(port),label:label||String(port)});}
    if(n.kind!=='composite'){
      const ins=index.incoming.get(id)||[];for(const e of ins)put(inputs,id,e.target_port,e.target_port);
      if(!inputs.length&&!['parameter','state','buffer'].includes(n.kind))put(inputs,id,'in','输入');
      const out=index.outgoing.get(id)||[];for(const e of out)put(outputs,id,e.source_port,e.source_port);
      if(!outputs.length)put(outputs,id,'out','输出');const result={inputs,outputs};index.cache.set(id,result);return result;
    }
    for(const c of children){if(c.kind==='interface'&&c.role==='input')put(inputs,c.id,'in',c.label);if(c.kind==='interface'&&c.role==='output')put(outputs,c.id,'out',c.label);}
    const inside=new Set([id]),todo=[id];for(let i=0;i<todo.length;i++)for(const c of index.children.get(todo[i])||[])if(!inside.has(c.id)){inside.add(c.id);todo.push(c.id);}
    const boundaryLabel=(node,port)=>{const child=index.nodes.get(node),owner=index.nodes.get(child?.parent);return (owner&&owner.id!==id?owner.label+' · ':'')+(child?.kind==='interface'?child.label:String(port));};
    const incident=new Set();for(const child of inside)for(const e of [...index.incoming.get(child)||[],...index.outgoing.get(child)||[]])incident.add(e);
    for(const e of [...incident].sort((a,b)=>index.order.get(a)-index.order.get(b))){if(!inside.has(e.source)&&inside.has(e.target))put(inputs,e.target,e.target_port,boundaryLabel(e.target,e.target_port));if(inside.has(e.source)&&!inside.has(e.target))put(outputs,e.source,e.source_port,boundaryLabel(e.source,e.source_port));}
    const needInputs=!inputs.length,needOutputs=!outputs.length;if(needInputs||needOutputs)for(const child of children.filter(n=>n.kind==='composite')){const p=ports(doc,child.id,index);if(needInputs)for(const v of p.inputs)if(!(index.incoming.get(v.node)||[]).some(e=>String(e.target_port)===v.port))put(inputs,v.node,v.port,child.label+' · '+v.label);if(needOutputs)for(const v of p.outputs)if(!(index.outgoing.get(v.node)||[]).some(e=>inside.has(e.target)))put(outputs,v.node,v.port,child.label+' · '+v.label);}
    const result={inputs,outputs};index.cache.set(id,result);return result;
  }
  function connect(doc,source,target,{kind='data',condition=null,id=null,replace=false}={}){
    if(!doc.nodes.some(n=>n.id===source.node)||!doc.nodes.some(n=>n.id===target.node))throw Error('连接端点不存在');
    if(source.node===target.node)throw Error('请连接不同节点；状态反馈需使用显式状态接口');
    if(source.port==null||target.port==null)throw Error('请选择确切的输出和输入端口');
    const drivers=doc.edges.filter(e=>e.target===target.node&&String(e.target_port)===String(target.port));
    if(drivers.length&&!replace)throw Error('输入已有连接，请先删除或选择替换连接');
    if(replace)doc.edges=doc.edges.filter(e=>!drivers.includes(e));
    const edge={id:id||'edit:edge:'+(++doc.serial),source:source.node,target:target.node,source_port:String(source.port),target_port:String(target.port),kind,evidence:'authored-dependency',condition,authoring:{status:'user-authored',validated_execution:false}};
    doc.edges.push(edge);return edge;
  }
  function group(doc,ids,title){
    const by=new Map(doc.nodes.map(n=>[n.id,n])),picked=[...new Set(ids)];if(!picked.length||picked.some(id=>!by.has(id)))throw Error('请选择要组合的节点');
    const parents=new Set(picked.map(id=>by.get(id).parent));if(parents.size!==1)throw Error('请在同一级选择模块进行组合');
    const id='edit:group:'+(++doc.serial),parent=[...parents][0];
    doc.nodes.push({id,parent,source_parent:null,kind:'composite',label:title||'自定义组合',source:[],evidence_status:'user-authored',authoring:{status:'user-authored'}});
    for(const key of picked)by.get(key).parent=id;doc.modules[id]={title:title||'自定义组合',composition:true};return id;
  }
  function replaceModule(doc,id,module){
    const old=ports(doc,id),inside=closure(doc,[id]),incoming=doc.edges.filter(e=>!inside.has(e.source)&&inside.has(e.target)),outgoing=doc.edges.filter(e=>inside.has(e.source)&&!inside.has(e.target)),parent=doc.nodes.find(n=>n.id===id).parent,label=doc.nodes.find(n=>n.id===id).label;
    // Check port compatibility before touching the working transaction.
    const trial=copy(doc);erase(trial,[id]);const inserted=add(trial,module,{parent}),rootId=inserted.roots[0];if(inserted.roots.length!==1)throw Error('替换模块需要唯一根节点');
    const next=ports(trial,rootId),mapping=new Map();for(const direction of ['inputs','outputs'])for(const p of old[direction]){const match=next[direction].filter(v=>v.label===p.label);if(match.length===1)mapping.set(p.node+'|'+p.port,match[0]);}
    for(const e of incoming){const p=mapping.get(e.target+'|'+e.target_port);if(!p)throw Error('新源码移除了已连接输入：请先调整连接');trial.edges.push({...copy(e),target:p.node,target_port:p.port});}
    for(const e of outgoing){const p=mapping.get(e.source+'|'+e.source_port);if(!p)throw Error('新源码移除了已连接输出：请先调整连接');trial.edges.push({...copy(e),source:p.node,source_port:p.port});}
    trial.nodes.find(n=>n.id===rootId).label=label;validate(trial);Object.assign(doc,trial);return rootId;
  }
  function recipe(ir,{atomic=false}={}){
    const by=new Map(ir.nodes.map(n=>[n.id,n])),roots=ir.nodes.filter(n=>!n.parent),parts=[];
    if(atomic){for(const n of ir.nodes)parts.push(fragment({...ir,nodes:[n],edges:[]},[n.id],n.label+' · '+n.kind));}
    for(const r of atomic?[]:roots){const children=ir.nodes.filter(n=>n.parent===r.id);if(!children.length){parts.push(fragment(ir,[r.id],r.label));continue;}
      parts.push(fragment({...ir,nodes:[r],edges:[]},[r.id],r.label+' · 外框'));
      for(const child of children)parts.push(fragment(ir,[child.id],child.label));
    }
    const owner=new Map(parts.flatMap((p,i)=>p.ir.nodes.map(n=>[n.id,i])));
    return {title:ir.title,parts,connections:copy(ir.edges.filter(e=>owner.get(e.source)!==owner.get(e.target))),parents:Object.fromEntries(ir.nodes.map(n=>[n.id,n.parent])),baseline:copy(ir)};
  }
  function restoreConnection(doc,edge){if(!doc.nodes.some(n=>n.id===edge.source)||!doc.nodes.some(n=>n.id===edge.target))throw Error('请先加入此连接的两个端点构件');if(doc.edges.some(e=>e.id===edge.id))throw Error('此连接已存在');doc.edges.push(copy(edge));}
  function sourceIR(doc){
    validate(doc);const base=doc.baseline||doc.recipe?.baseline;
    if(base&&JSON.stringify(doc.nodes)===JSON.stringify(base.nodes)&&JSON.stringify(doc.edges)===JSON.stringify(base.edges))return {...copy(base),title:doc.title};
    // Array insertion order need not match a recipe's extraction order.
    if(base){const stable=rows=>rows.map(x=>JSON.stringify(x)).sort();if(JSON.stringify(stable(doc.nodes))===JSON.stringify(stable(base.nodes))&&JSON.stringify(stable(doc.edges))===JSON.stringify(stable(base.edges)))return {...copy(base),title:doc.title};}
    const nodes=copy(doc.nodes),baseNodes=new Map((base?.nodes||[]).map(n=>[n.id,n]));
    for(const n of nodes){
      const unchangedScope=n.repeat_contract&&base&&[...closure(doc,[n.id])].every(id=>JSON.stringify(doc.nodes.find(n=>n.id===id))===JSON.stringify(baseNodes.get(id)));
      const keys=[...(unchangedScope?[]:['repeat_contract']),'semantic_contracts','contract_roles','module_identity','module_binding','module_resource_binding','symbolic_value','motif','runtime_evidence'];
      const facts={};for(const key of keys)if(n[key]!=null){facts[key]=n[key];delete n[key];}
      if(Object.keys(facts).length)n.source_provenance={...n.source_provenance,original_facts:facts,scope:'Before user assembly; not a certificate of the edited program'};
      n.runtime_evidence=[];if(n.return_selection&&!doc.edges.some(e=>e.target===n.id&&e.source===n.return_selection.selected&&e.kind==='interface-binding'))delete n.return_selection;
    }
    // A model has one explicit enclosure, even when assembled from unrelated
    // modules. This makes the ordinary publication focus include every branch.
    if(!base||nodes.filter(n=>!n.parent).length!==1||!nodes.some(n=>!n.parent&&n.kind==='composite')){
      let id='edit:model';while(nodes.some(n=>n.id===id))id+=':root';
      for(const n of nodes)if(!n.parent)n.parent=id;
      nodes.unshift({id,parent:null,kind:'composite',label:doc.title,source:[],runtime_evidence:[],evidence_status:'user-authored'});
    }
    return {schema:'archcanvas-source-semantic/2',title:doc.title,entry:{class:doc.title,constructor:{}},nodes,edges:copy(doc.edges),sources:copy(doc.sources),motifs:[],branches:[],semantic_contracts:[],
      ir_digest:draftKey({title:doc.title,nodes,edges:doc.edges,sources:doc.sources,modules:doc.modules}),
      coverage:{status:'not-verified',scope:'user-authored-assembly',complete:false,reason:'编辑连接尚未由执行或完整程序验证；原始事实见来源。'},runtime:{status:'not-requested',model_executed:false},
      limitations:['用户编辑文档；保留模块源码及原始绑定。组合后的全程序执行与形状兼容尚未验证。'],authoring:{schema,modules:copy(doc.modules),edited:true}};
  }
  function addInterface(doc,role,label,parent=null){
    if(!['input','output'].includes(role))throw Error('接口类型无效');const id='edit:interface:'+(++doc.serial);
    doc.nodes.push({id,parent,kind:'interface',role,label:label||role,source:[],runtime_evidence:[],evidence_status:'user-authored',authoring:{status:'user-authored'}});return id;
  }
  function editNode(doc,id,fields){
    const n=doc.nodes.find(n=>n.id===id);if(!n)throw Error('节点不存在');
    n.source_provenance={...n.source_provenance,original_source:n.source_provenance?.original_source||copy(n.source||[])};
    for(const key of ['label','constructor','arguments'])if(Object.hasOwn(fields,key))n[key]=copy(fields[key]);
    const expression=fields.expression||JSON.stringify({operator:n.operator,constructor:n.constructor,arguments:n.arguments});
    n.source=[{file:'authoring://draft',line:1,end_line:1,column:0,end_column:expression.length,symbol:n.label,expression}];
    if(!doc.sources.some(s=>s.path==='authoring://draft'))doc.sources.push({path:'authoring://draft',physical:null,unit_sha256:null,sha256:null});
    n.evidence_status='user-authored';n.authoring={status:'user-authored',requires_source_review:true};return n;
  }
  function template(doc,ids,title){const m=fragment({nodes:doc.nodes,edges:doc.edges,sources:doc.sources},ids,title);m.components=copy(Object.fromEntries(Object.entries(doc.modules).filter(([id])=>m.ir.nodes.some(n=>n.id===id))));return m;}
  function parameterValue(value,previous){if(typeof previous==='boolean')return !!value;if(typeof previous==='number'){if(!String(value).trim()||!Number.isFinite(Number(value)))throw Error('数值参数必须是有限数字');return Number(value);}return typeof previous==='object'?JSON.parse(value):String(value);}
  const api={schema,empty,validate,fromIR,closure,fragment,add,erase,ports,portIndex,connect,group,replaceModule,recipe,restoreConnection,sourceIR,addInterface,editNode,template,parameterValue,copy};root.SemanticAuthoring=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
