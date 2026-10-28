/* Studio panels dispatch declared edits to Summary's original authoring model.
 * This module never executes Python or confers a formal source binding. */
(function(root){
  'use strict';
  const A=root.SemanticAuthoring,D=root.ArchCanvasSummaryDocuments,copy=A.copy;
  const selected=(doc,ids)=>{if(!Array.isArray(ids)||!ids.length||ids.some(id=>!doc.nodes.some(n=>n.id===id)))throw Error('请选择原始编辑节点；合并图元需要先展开。');return ids;};
  const title=value=>{if(typeof value!=='string'||!value.trim()||value.length>240)throw Error('名称需为 1–240 字符。');return value.trim();};
  function scopeOf(doc,value=doc.editorScope){if(value!=null&&!doc.nodes.some(n=>n.id===value&&n.kind==='composite'))throw Error('编辑层级不存在或不是容器。');return value||null;}
  function endpoint(doc,value,direction){
    if(!value||typeof value.node!=='string'||typeof value.port!=='string')throw Error('请选择确切的端口槽位。');
    const ports=A.ports(doc,value.node)[direction];
    if(!ports.some(p=>p.node===value.node&&p.port===value.port))throw Error('端口槽位不属于当前编辑节点。');
    return {node:value.node,port:value.port};
  }
  function retainView(result,graph,rebindings={}){
    const cuts=(graph?.generic?.state.moduleCuts||[]).flatMap(c=>{
      const id=rebindings[c.id]||c.id;
      if(!result.parsed.ir.nodes.some(n=>n.id===id&&n.kind==='composite'))return [];
      // Recompile edited structures; old synthetic role openings are receipts
      // of a different IR and must never be replayed as new certificates.
      return [{id,level:c.level,...(c.depth!==undefined?{depth:c.depth}:{})}];
    });
    if(cuts.length)result.parsed.state={...result.parsed.state,moduleCuts:cuts};
    return result;
  }
  async function begin(graph,{blank=false,title:name}={}){
    if(!blank&&!graph?.generic)throw Error('当前案例还没有 Summary 原生语义，请先导入 Python 或 Summary 文档。');
    const doc=blank?A.empty(name?title(name):'未命名模型'):copy(graph.generic.authoring||A.fromIR(graph.generic.ir));
    A.validate(doc);
    const origin=blank?null:{caseId:graph.caseId,irDigest:graph.generic.ir.ir_digest||null,sourceSha256:graph.sourceAdapter?.sourceSha256||null,scope:'provenance-only; edited assembly is not verified Python'};
    return retainView(await D.workspace(doc,undefined,origin),blank?null:graph);
  }
  async function apply(graph,op,presets=[]){
    const previous=graph?.authoringWorkspace;
    if(previous?.schema!=='archcanvas-summary-authoring/1'||!graph.generic?.authoring)throw Error('请先进入 Summary 编辑副本。');
    if(op.workspaceId!==undefined&&op.workspaceId!==previous.id||op.baseDocumentSha256!==undefined&&op.baseDocumentSha256!==previous.documentSha256)throw Error('源码解析期间编辑文档已变化；原稿保留，请重新解析。');
    if(op.action==='certify')return retainView(await D.workspace(graph.generic.authoring,previous.id,previous.origin,{...copy(op.result),baseDocumentSha256:op.baseDocumentSha256}),graph);
    const doc=copy(graph.generic.authoring),scope=scopeOf(doc);let selection=[],rebindings={};
    switch(op.action){
      case 'title': doc.title=title(op.title);break;
      case 'interface': selection=[A.addInterface(doc,op.role,title(op.label||op.role),scope)];break;
      case 'add': {
        let module;
        if(op.preset!==undefined){if(!Number.isInteger(op.preset)||!presets[op.preset])throw Error('构件不存在。');module=presets[op.preset];}
        else if(op.library!==undefined){if(!Number.isInteger(op.library)||!doc.library[op.library])throw Error('组合库条目不存在。');module=doc.library[op.library];}
        else {const base=doc.baseline||doc.recipe?.baseline;if(!base?.nodes.some(n=>n.id===op.sourceNode))throw Error('原始源码构件不存在。');module=A.fragment(base,[op.sourceNode]);}
        selection=A.add(doc,module,{parent:scope}).roots;break;
      }
      case 'duplicate': selection=A.add(doc,A.template(doc,selected(doc,op.ids),'副本'),{parent:scope}).roots;break;
      case 'add-source': case 'replace-module': {
        const module=op.module;
        if(module?.schema!=='semantic-module/1'||typeof module.source!=='string'||!module.source.trim()||typeof module.entry!=='string')throw Error('源码模块格式无效。');
        root.SemanticEngine.validate(module.ir);
        if(op.action==='add-source')selection=A.add(doc,module,{parent:scope}).roots;
        else {
          selected(doc,[op.id]);const next=A.replaceModule(doc,op.id,module);selection=[next];rebindings[op.id]=next;
          if(doc.editorScope&&!doc.nodes.some(n=>n.id===doc.editorScope))doc.editorScope=next;
        }
        break;
      }
      case 'erase': A.erase(doc,selected(doc,op.ids));if(doc.editorScope&&!doc.nodes.some(n=>n.id===doc.editorScope))doc.editorScope=null;break;
      case 'group': selection=[A.group(doc,selected(doc,op.ids),title(op.title))];break;
      case 'library': doc.library.push(A.template(doc,selected(doc,op.ids),title(op.title)));selection=op.ids;break;
      case 'edit': {
        selected(doc,[op.id]);const fields=op.fields;
        if(!fields||typeof fields!=='object'||Array.isArray(fields)||Object.keys(fields).some(k=>!['label','constructor','arguments','expression'].includes(k)))throw Error('编辑字段无效。');
        if(fields.label!==undefined)title(fields.label);
        A.editNode(doc,op.id,fields);selection=[op.id];break;
      }
      case 'connect': case 'rewire': {
        const from=endpoint(doc,op.source,'outputs'),to=endpoint(doc,op.target,'inputs');
        if(op.replace!==undefined&&typeof op.replace!=='boolean')throw Error('替换标志无效。');
        if(op.action==='rewire'){if(!doc.edges.some(e=>e.id===op.id))throw Error('原始连接不存在，请展开合并线。');doc.edges=doc.edges.filter(e=>e.id!==op.id);}
        A.connect(doc,from,to,{replace:op.replace===true});break;
      }
      case 'remove-edge': if(!doc.edges.some(e=>e.id===op.id))throw Error('原始连接不存在，请展开合并线。');doc.edges=doc.edges.filter(e=>e.id!==op.id);break;
      case 'recipe-start': {
        const baseline=doc.baseline||doc.recipe?.baseline;if(!baseline)throw Error('当前编辑稿没有原始参考 IR。');
        if(op.atomic!==undefined&&typeof op.atomic!=='boolean')throw Error('参考粒度无效。');
        const plan=A.recipe(baseline,{atomic:!!op.atomic}),next=A.empty(plan.title);next.library=copy(doc.library);next.recipe={parents:plan.parents,baseline:plan.baseline};next.recipeLevel=op.atomic?'atomic':'modules';
        for(const key of Object.keys(doc))delete doc[key];Object.assign(doc,next);break;
      }
      case 'recipe-add': {
        if(!doc.recipe?.baseline)throw Error('请先开始参考构件重建。');
        const plan=A.recipe(doc.recipe.baseline,{atomic:doc.recipeLevel==='atomic'});
        if(!Number.isInteger(op.part)||!plan.parts[op.part])throw Error('参考构件不存在。');
        selection=A.add(doc,plan.parts[op.part],{keepIdentity:true}).roots;break;
      }
      case 'recipe-wires': {
        if(!doc.recipe?.baseline)throw Error('请先开始参考构件重建。');
        const plan=A.recipe(doc.recipe.baseline,{atomic:doc.recipeLevel==='atomic'}),ids=new Set(doc.nodes.map(n=>n.id)),baseline=new Map(doc.recipe.baseline.edges.map(e=>[e.id,root.SummaryNativeSemantic.stable(e)]));let count=0;
        for(const e of plan.connections)if(ids.has(e.source)&&ids.has(e.target)&&!doc.edges.some(x=>x.id===e.id)){
          if(doc.edges.some(x=>x.target===e.target&&String(x.target_port)===String(e.target_port)&&baseline.get(x.id)!==root.SummaryNativeSemantic.stable(x)))throw Error('参考输入已有编辑连接，请先删除或调整该连接。');
          A.restoreConnection(doc,e);count++;
        }
        if(!count)throw Error('没有可恢复连接，请先加入更多端点构件。');break;
      }
      case 'scope': doc.editorScope=scopeOf(doc,op.id);if(doc.editorScope)doc.open=[...new Set([...doc.open,doc.editorScope])];break;
      default: throw Error('不支持的 Summary 编辑操作：'+op.action);
    }
    doc.serial++;delete doc.canvasPlacement;doc.offsets={};A.validate(doc);
    const result=await D.workspace(doc,previous.id,previous.origin);
    return {...retainView(result,graph,rebindings),selection,rebindings};
  }
  function record(graph){return graph?.authoringWorkspace?{...copy(graph.authoringWorkspace),document:copy(graph.generic.authoring)}:null;}
  function attach(graph,value){D.attach(graph,value);graph.authoringWorkspace=copy(value);delete graph.authoringWorkspace.document;return graph;}
  function inspector(graph){
    if(!graph?.authoringWorkspace)return null;
    const doc=graph.generic.authoring,index=A.portIndex(doc),scope=doc.editorScope||null;
    const nodes=doc.nodes.map(n=>({id:n.id,label:n.label,parent:n.parent||null,kind:n.kind,...(Object.hasOwn(n,'constructor')?{constructor:copy(n.constructor)}:{}),...(Object.hasOwn(n,'arguments')?{arguments:copy(n.arguments)}:{}),...(doc.modules[n.id]?.source?{module:copy(doc.modules[n.id])}:{}),ports:A.ports(doc,n.id,index)}));
    let recipe=null;
    if(doc.recipe?.baseline){
      const plan=A.recipe(doc.recipe.baseline,{atomic:doc.recipeLevel==='atomic'}),ids=new Set(doc.nodes.map(n=>n.id)),edges=new Set(doc.edges.map(e=>e.id)),pending=plan.connections.filter(e=>!edges.has(e.id));
      const rows=value=>root.SummaryNativeSemantic.stable(value.map(root.SummaryNativeSemantic.stable).sort());
      recipe={level:doc.recipeLevel||'modules',parts:plan.parts.map((p,index)=>({index,title:p.title,nodes:p.ir.nodes.length,present:p.ir.nodes.every(n=>ids.has(n.id))})),pendingConnections:pending.length,readyConnections:pending.filter(e=>ids.has(e.source)&&ids.has(e.target)).length,exact:rows(doc.nodes)===rows(plan.baseline.nodes)&&rows(doc.edges)===rows(plan.baseline.edges)};
    }
    return {workspaceId:graph.authoringWorkspace.id,title:doc.title,scope,nodes,edges:copy(doc.edges),library:doc.library.map(m=>({title:m.title})),sourceNodes:(doc.baseline?.nodes||doc.recipe?.baseline?.nodes||[]).map(n=>({id:n.id,label:n.label,kind:n.kind})),recipe,edited:!!graph.generic.ir.authoring?.edited,localAnalysis:graph.authoringWorkspace.localAnalysis?copy(graph.authoringWorkspace.localAnalysis.analysis):null,sourceVerified:false,modelExecuted:false};
  }
  root.ArchCanvasSummaryAuthoring={begin,apply,record,attach,inspector};
})(typeof window!=='undefined'?window:globalThis);
