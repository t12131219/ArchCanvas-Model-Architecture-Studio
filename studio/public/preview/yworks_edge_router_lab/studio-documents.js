/* Summary document formats share the native authority, without claiming a
 * verified Python source binding for user-supplied IR or authored drafts. */
(function(root){
  'use strict';
  const G=root.SummaryNativeSemantic,copy=value=>JSON.parse(JSON.stringify(value));
  const schemas=new Set([G.SCHEMA,'semantic-canvas/1','archcanvas-architecture-document/1','semantic-authoring/1','archcanvas-source-semantic/2']);
  const limits=Object.freeze({bytes:64000000,fileBytes:128000000,nodes:4000,edges:5000,depth:128,objects:400000});
  const supports=value=>!!value&&typeof value==='object'&&schemas.has(value.schema);
  const localScope='local operand structure of the declared user assembly; not equivalence to original source or execution coverage';
  const sha=async text=>Array.from(new Uint8Array(await root.crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))).map(n=>n.toString(16).padStart(2,'0')).join('');
  function declaredFacts(ir){const value=copy(ir);delete value.ir_digest;delete value.semantic_contract_basis;value.semantic_contracts=[];if(value.authoring)delete value.authoring.local_contracts_recomputed;return G.stable(value);}
  async function localResult(base,analysis,digest){
    bounded(analysis);
    if(analysis?.schema!=='archcanvas-summary-local-assembly/1'||analysis.baseDocumentSha256!==digest||typeof analysis.irText!=='string'||await sha(analysis.irText)!==analysis.resultSha256)throw Error('局部结构结果与当前组装稿或内容摘要不一致。');
    const ir=JSON.parse(analysis.irText),status=analysis.analysis;bounded(ir);
    if(!base.authoring?.edited||ir.authoring?.local_contracts_recomputed!==true||status?.scope!==localScope||status.modelExecuted!==false||status.sourceTransactionBinding!==false||status.staticStructureOnly!==true||!Array.isArray(ir.semantic_contracts)||status.contracts!==ir.semantic_contracts.length||declaredFacts(ir)!==declaredFacts(base))throw Error('局部复核不能改变组装事实或授予执行、源码权限。');
    for(const cert of ir.semantic_contracts)if(cert.scope!==localScope||!['assembled-program execution','shape compatibility','unchanged original source'].every(text=>cert.not_asserted?.includes(text)))throw Error('局部契约缺少限定范围。');
    root.SemanticEngine.validate(ir);return ir;
  }
  function bounded(value){
    const stack=[[value,0]],seen=new Set();let count=0;
    while(stack.length){const [item,depth]=stack.pop();if(!item||typeof item!=='object')continue;
      if(seen.has(item))throw Error('文档包含重复对象引用或循环；请导入 JSON 文档。');
      seen.add(item);if(depth>limits.depth||++count>limits.objects)throw Error('文档超过结构预算。');
      if(Array.isArray(item.nodes)&&item.nodes.length>limits.nodes||Array.isArray(item.edges)&&item.edges.length>limits.edges)throw Error(`文档超过当前 ${limits.nodes} 节点 / ${limits.edges} 依赖预算。`);
      for(const key of Object.keys(item)){if(key==='__proto__')throw Error('文档包含无效对象字段。');stack.push([item[key],depth+1]);}
    }
    const text=JSON.stringify(value);if(new TextEncoder().encode(text).length>limits.bytes)throw Error('文档超过 64 MB。');
    return text;
  }
  async function read(value){
    if(!supports(value))throw Error('不支持的 Summary 文档格式。');
    const original=JSON.parse(bounded(value)),parsed=G.read(copy(original));
    if(parsed.ir.nodes.length>limits.nodes||parsed.ir.edges.length>limits.edges)throw Error('文档超过当前原生图预算。');
    const text=G.stable(original),digest=Array.from(new Uint8Array(await root.crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))).map(n=>n.toString(16).padStart(2,'0')).join('');
    return {record:{schema:'archcanvas-summary-import/1',id:'summary-document-'+digest,title:String(parsed.ir.title||original.title||'Summary 文档').slice(0,240),documentSha256:digest,document:original},parsed};
  }
  async function restore(record){
    if(record?.schema==='archcanvas-summary-authoring/1'){
      if(!/^summary-authoring-[a-f0-9-]{36}$/.test(record.id)||record.document?.schema!=='semantic-authoring/1')throw Error('Summary 编辑副本身份无效。');
      const result=await workspace(record.document,record.id,record.origin,record.localAnalysis);
      if(record.documentSha256!==result.record.documentSha256)throw Error('编辑副本摘要与内容不一致。');
      return result;
    }
    if(record?.schema!=='archcanvas-summary-import/1')throw Error('导入文档记录无效。');
    const result=await read(record.document);
    if(record.id!==result.record.id||record.documentSha256!==result.record.documentSha256)throw Error('导入文档身份与内容不一致。');
    return result;
  }
  async function workspace(document,id='summary-authoring-'+root.crypto.randomUUID(),origin=null,localAnalysis=null){
    if(!/^summary-authoring-[a-f0-9-]{36}$/.test(id)||document?.schema!=='semantic-authoring/1')throw Error('Summary 编辑副本格式无效。');
    if(origin)bounded(origin);
    const result=await read(document);
    result.record={...result.record,schema:'archcanvas-summary-authoring/1',id,origin:copy(origin)};
    if(localAnalysis){result.parsed.ir=await localResult(result.parsed.ir,localAnalysis,result.record.documentSha256);result.record.localAnalysis=copy(localAnalysis);}
    // Match Summary authoring-app.viewState: open the model enclosure and
    // current scope's ancestors, keeping inserted child modules selectable.
    const by=new Map(result.parsed.ir.nodes.map(n=>[n.id,n])),open=new Set(document.open);
    for(const n of result.parsed.ir.nodes)if(!n.parent&&n.kind==='composite')open.add(n.id);
    let at=document.editorScope;while(at&&by.has(at)){open.add(at);at=by.get(at).parent;}
    result.parsed.state={...result.parsed.state,paperGranularity:'detailed',paperAuto:false,details:true,open:[...open]};
    return result;
  }
  function attach(graph,record){
    graph.caseId=record.id;delete graph.sourceAdapter;
    if(record.schema!=='archcanvas-summary-authoring/1')delete graph.authoringWorkspace;
    graph.importedDocument={schema:record.document.schema,documentSha256:record.documentSha256,sourceVerified:false,modelExecuted:false};
    graph.sourceProfile={analysis:'Summary document import',sourceVerified:false,modelExecuted:false,evidenceOrigin:'imported-document'};
    return graph;
  }
  function matches(graph,parsed){return !!graph?.generic&&G.stable(graph.generic.ir)===G.stable(parsed.ir)&&G.stable(graph.generic.authoring||null)===G.stable(parsed.authoring||null);}
  function checkRendering(graph){
    // Native documents store data and layout. Only Summary's generator may
    // supply SVG markup, including when an edited wrapper comes from storage.
    if(graph.definitions||graph.extras||graph.attachments?.length||graph.routeLabels?.length)throw Error('原生文档不能携带外部 SVG 图元。');
    const generated=G.build(graph.generic.ir,graph.generic.state,{authoring:graph.generic.authoring}),by=new Map(generated.nodes.map(n=>[n.id,n]));
    if(graph.nodes.some(n=>!by.has(n.id)||n.html!==by.get(n.id).html||G.stable(n.base)!==G.stable(by.get(n.id).base)))throw Error('原生文档图元不是 Summary 生成的内容。');
    return true;
  }
  root.ArchCanvasSummaryDocuments={supports,read,restore,workspace,attach,matches,checkRendering,limits};
})(typeof window!=='undefined'?window:globalThis);
