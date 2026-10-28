/* A local role frontier consumes existing certificates. It neither recognizes
 * model families nor substitutes computations for their internal paths. */
(function(root){
  'use strict';
  const VERSION='role-frontier/3',PATH_VERSION='role-paths/2';
  function references(value,by,path=[]){
    if(typeof value==='string'&&by.has(value))return [{path:path.join('.'),keys:path,node:value}];
    if(value&&typeof value==='object')return Object.entries(value).flatMap(([key,v])=>references(v,by,[...path,key]));
    return [];
  }
  function compile({plan,focus,details=[],paths=[]}){
    const nodes=plan.nodes.map(n=>({...n})),by=new Map(nodes.map(n=>[n.id,n])),certs=new Map((plan.semantic_contracts||[]).map(c=>[c.id,c]));
    const within=(id,owner)=>{const seen=new Set();while(id&&!seen.has(id)){if(id===owner)return true;seen.add(id);id=by.get(id)?.parent;}return false;};
    const attached=n=>(n.semantic_contracts||[]).map(id=>certs.get(id)).filter(c=>c?.node===n.id);
    const candidates=new Set(nodes.filter(n=>n.kind==='composite'&&within(n.id,focus)&&attached(n).length).map(n=>n.id));
    const owners=new Set([...candidates].filter(id=>{let at=by.get(id)?.parent;while(at&&within(at,focus)){if(candidates.has(at))return false;at=by.get(at)?.parent;}return true;}));
    const open=new Set(),records=[],modules=[];
    const protectedFrame=n=>n.contract_stage||n.kind==='opaque'||n.kind==='control'||n.condition||n.mutable||n.identity_display||n.observed_calls||n.evidence_status==='runtime-only'||n.runtime_evidence?.length||
      ['conditional-region','conditional-collection','loop-template','iteration-region','observed-variant','serial-repeat','repeat-instance','serial-remainder'].includes(n.semantic_type);
    const ownerOf=id=>{while(id){if(owners.has(id))return id;id=by.get(id)?.parent;}return null;};
    // An explicit local refinement may cross ordinary source helpers, but
    // never a control/effect/identity boundary or an unselected certificate.
    // Ancestors are processed first so selecting two nested boundaries works
    // independently of the order stored in the document.
    const depth=id=>{let d=0;while(by.get(id)?.parent){d++;id=by.get(id).parent;}return d;};
    const detailRequests=[],pathRequests=[],partial=new Map();
    const full=new Set(Array.isArray(details)?details.filter(id=>typeof id==='string'):[]);
    const signatures=new Set();
    for(const request of Array.isArray(paths)?paths:[]){
      if(!request||typeof request.node!=='string'||typeof request.certificate!=='string'||
        !Array.isArray(request.role)||!request.role.length||request.role.some(k=>typeof k!=='string'))continue;
      const signature=JSON.stringify([request.node,request.certificate,request.role]);if(signatures.has(signature))continue;signatures.add(signature);
      const c=certs.get(request.certificate),r=c&&references(c.roles,by).find(r=>JSON.stringify(r.keys)===JSON.stringify(request.role));
      const record={node:request.node,certificate:request.certificate,role:request.role.slice(),target:r?.node??null,selection:'deferred',reason:null};
      pathRequests.push(record);
      if(!c||c.node!==request.node||!attached(by.get(request.node)||{}).some(x=>x.id===c.id)||!r){
        record.reason='No exact attached certificate role reference matches this path.';continue;
      }
      if(r.node===request.node||!within(r.node,request.node)){record.reason='The role reference is self or external, not a local internal path.';continue;}
      if(!partial.has(request.node))partial.set(request.node,[]);partial.get(request.node).push(record);
    }
    const requests=[...new Set([...full,...partial.keys()])].sort((a,b)=>depth(a)-depth(b)||a.localeCompare(b));
    for(const node of requests){
      const n=by.get(node),record={node,selection:'deferred',reason:null};
      if(full.has(node))detailRequests.push(record);
      const finish=()=>{for(const r of partial.get(node)||[])Object.assign(r,{selection:record.selection,reason:record.reason,...(record.boundary?{boundary:record.boundary}:{})});};
      if(!candidates.has(node)){record.reason='No attached composite certificate in the current focus.';finish();continue;}
      if(protectedFrame(n)){record.reason='A control, effect, identity, observation or repetition boundary remains protected.';finish();continue;}
      if(owners.has(node)){record.selection='selected';record.reason='Already a local role owner.';finish();continue;}
      const chain=[];let at=node;
      while(at&&!owners.has(at)){chain.unshift(at);at=by.get(at)?.parent;}
      if(!at){record.reason='No reachable local role owner.';finish();continue;}
      if(protectedFrame(by.get(at))){record.boundary=at;record.reason='The enclosing local role owner is protected.';finish();continue;}
      const stop=chain.find(id=>protectedFrame(by.get(id))||(id!==node&&attached(by.get(id)).length));
      if(stop){record.boundary=stop;record.reason='An intervening protected or unselected certified boundary limits this request.';finish();continue;}
      owners.add(node);for(const id of chain.slice(0,-1))open.add(id);open.add(at);
      record.selection='selected';record.reason='Explicit local role refinement; independent certificate scope retained.';finish();
    }
    for(const owner of owners){
      const n=by.get(owner),local=[];
      for(const c of attached(n))for(const r of references(c.roles,by)){
        if(!full.has(owner)&&(partial.get(owner)||[]).some(p=>p.selection==='selected')&&!(partial.get(owner)||[]).some(p=>p.selection==='selected'&&p.certificate===c.id&&JSON.stringify(p.role)===JSON.stringify(r.keys)))continue;
        const record={owner,certificate:c.id,role:r.path,role_keys:r.keys.slice(),node:r.node,scope:c.scope,not_asserted:c.not_asserted||[]};
        if(r.node===owner||!within(r.node,owner)){records.push({...record,location:r.node===owner?'self':'external',frontier_node:r.node});continue;}
        // Stop before the next certified, conditional, unknown or mutable
        // boundary. Its own detail remains available through manual expansion.
        const chain=[];let at=r.node;while(at&&at!==owner){chain.unshift(at);at=by.get(at)?.parent;}
        let target=r.node;
        for(const id of chain){const child=by.get(id);if(protectedFrame(child)||attached(child).length){target=id;break;}}
        const row={...record,location:'internal',frontier_node:target};records.push(row);local.push(row);
        let parent=by.get(target)?.parent;while(parent&&parent!==owner){open.add(parent);parent=by.get(parent)?.parent;}
        const child=by.get(target);child.role_annotations=[...(child.role_annotations||[]),row];
      }
      if(local.length&&!protectedFrame(n))open.add(owner);
      modules.push({node:owner,certificates:attached(n).map(c=>c.id),roles:local.length,scope:'one local role layer; nested certified/control/unknown boundaries retain independent detail'});
    }
    return {plan:{...plan,nodes},open,owners,ownerOf,records,modules,detailRequests,pathRequests};
  }
  function receipt(frontier,graph){
    const attached=new Set(graph.node_accounting.attached),contracted=new Set(graph.node_accounting.contracted);
    const roleRows=frontier.records.map(r=>{
      const visible=graph.positions.has(r.frontier_node),representative=graph.representatives[r.frontier_node]||null;
      return {...r,visible_node:visible?r.frontier_node:representative,status:visible?(r.node===r.frontier_node?'exposed':'boundary'):
        attached.has(r.frontier_node)?'attached':contracted.has(r.frontier_node)?'contracted':representative?'folded':'outside'};
    });
    return {rule_version:VERSION,...(frontier.pathRequests.length?{path_rule_version:PATH_VERSION,path_requests:frontier.pathRequests.map(r=>{
      const role=roleRows.find(x=>x.owner===r.node&&x.certificate===r.certificate&&JSON.stringify(x.role_keys)===JSON.stringify(r.role)&&x.node===r.target);
      return {...r,status:r.selection!=='selected'?'deferred':role?.status||'deferred',frontier_node:role?.frontier_node??null,visible_node:role?.visible_node??null};
    })}:{}),detail_requests:frontier.detailRequests.map(r=>({...r,status:r.selection==='selected'&&graph.positions.get(r.node)?.expanded?'expanded':'deferred',
      ...(r.selection==='selected'&&!graph.positions.get(r.node)?.expanded?{reason:'The selected role detail remains folded by visibility, explicit open state or local budget.'}:{})})),
      modules:frontier.modules.map(m=>({...m,expanded:!!graph.positions.get(m.node)?.expanded})),roles:roleRows,scope:'Existing certificate role references only; no equivalence, missing role, causality or execution-count claim is added.'};
  }
  const api={VERSION,PATH_VERSION,references,compile,receipt};root.SemanticRoleFrontier=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
