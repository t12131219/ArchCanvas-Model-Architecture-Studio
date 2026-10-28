/* Evidence-backed local graph rules. This module never edits the canonical IR.
 * Source ownership, semantic findings and the presentation tree are independent.
 * Unknown operators are boundaries, not invitations to manufacture a template. */
(function(root){
  'use strict';
  const Relations=root.SemanticLocalRelations||(typeof require==='function'?require('./local-relations.js'):null);
  const VERSION='architecture-rules/5';
  const copy=x=>JSON.parse(JSON.stringify(x));
  const flow=e=>['data','alias','interface-binding'].includes(e.kind);
  const transparent=n=>n&&(n.kind==='interface'||n.kind==='value-alias')&&n.slot==null&&!n.operator;
  const hash=s=>{let h=2166136261;for(const c of s)h=Math.imul(h^c.charCodeAt(0),16777619);return(h>>>0).toString(16);};
  function operator(n){
    if(!n||n.kind==='opaque')return null;
    const activation=(n.function_target||n.framework_type||'').split('.').at(-1)?.toLowerCase();
    if(['sigmoid','tanh'].includes(activation))return activation;
    const op=n.operator||'';
    if(!op.startsWith('aten.'))return op;
    const name=op.split('.')[1];
    return ({mul:'mult',add:'add',sigmoid:'sigmoid',tanh:'tanh',relu:'activation',gelu:'activation',
      linear:'linear',convolution:'convolution',conv2d:'convolution',layer_norm:'normalization',
      native_layer_norm:'normalization',softmax:'softmax',_softmax:'softmax',dropout:'dropout'})[name]||op;
  }
  // Dependency edges also describe dtype/device/axis/allocation arguments.
  // They remain canonical facts, but cannot establish a residual value path.
  function valueOperands(n,edges){
    const name=n.operator?.startsWith('aten.')?n.operator.split('.')[1]:null;
    const op=({size:'shape',sym_size:'shape',zeros:'create',ones:'create',zeros_like:'create',ones_like:'create',
      rand:'random',randn:'random',rand_like:'random',randn_like:'random',_to_copy:'device-cast',to:'device-cast',
      view:'reshape',reshape:'reshape',_unsafe_view:'reshape',flatten:'reshape',squeeze:'reshape',unsqueeze:'reshape',
      transpose:'transpose',permute:'transpose',t:'transpose',clone:'copy',detach:'detach',expand:'expand',
      sum:'reduce',mean:'reduce',split:'split',split_with_sizes:'split',unbind:'split'})[name]||operator(n);
    if(['shape','attribute','scalar-cast','create','random','range','enumerate'].includes(op))return [];
    if(!['device-cast','dtype-cast','reshape','transpose','copy','detach','expand','softmax',
      'dropout','activation','pooling','interpolate','reduce','split','nan-guard'].includes(op))return edges;
    if(edges.some(e=>e.target_port==='receiver'))return edges.filter(e=>e.target_port==='receiver');
    const input=edges.filter(e=>['arg:0','kw:input'].includes(e.target_port));
    if(input.length)return input;
    // Runtime captures number flattened tensor inputs. For these unary value
    // operations the first tensor is the value, even when other tensors configure it.
    if(n.operator?.startsWith('aten.'))return edges.filter(e=>String(e.target_port)==='0');
    // Legacy single-input framework contracts have the generic port "in".
    return edges.length===1&&edges[0].target_port==='in'?edges:[];
  }
  function build(ir){
    const original=new Map(ir.nodes.map(n=>[n.id,n])),incoming=new Map(),outgoing=new Map();
    for(const e of ir.edges){
      if(!incoming.has(e.target))incoming.set(e.target,[]);incoming.get(e.target).push(e);
      if(!outgoing.has(e.source))outgoing.set(e.source,[]);outgoing.get(e.source).push(e);
    }
    // Resolve only unambiguous aliases/interfaces; tuple slots and conditional
    // joins retain their identity. No guessed tensor equivalence across slots.
    function value(id,port='out',seen=new Set()){
      const key=JSON.stringify([id,port]);if(seen.has(key))return {id,port};seen.add(key);
      const n=original.get(id),es=(incoming.get(id)||[]).filter(flow);
      if(transparent(n)&&es.length===1&&!es[0].condition)return value(es[0].source,es[0].source_port,seen);
      return {id,port};
    }
    const producer=id=>value(id).id;
    function inputs(id){return (incoming.get(id)||[]).filter(e=>flow(e)&&!e.condition).map(e=>({...value(e.source,e.source_port),edge:e}));}
    function compatible(a,b){return a.evidence===b.evidence||new Set([a.evidence,b.evidence]).size===2&&[a.evidence,b.evidence].every(e=>['source-dependency','framework-contract'].includes(e));}
    // Find a dependency path with a bounded search. A successful path says only
    // that one value feeds a substructure; it is not an all-input equivalence proof.
    function path(from,to,evidence,valueOnly=true){
      const queue=[[to,[]]],seen=new Set();
      for(let i=0;i<queue.length&&i<2048;i++){
        const [at,tail]=queue[i],{id,port}=at;if(id===from.id&&port===from.port)return tail;
        const key=JSON.stringify([id,port]);if(seen.has(key)||tail.length>=48)continue;seen.add(key);
        const n=original.get(id);
        if(!n||!['compute','interface','value-alias'].includes(n.kind)||n.mutable||n.condition||n.operator==='phi')continue;
        const edges=(incoming.get(id)||[]).filter(flow);
        for(const e of valueOnly?valueOperands(n,edges):edges)if(!e.condition&&compatible(e,{evidence}))queue.push([value(e.source,e.source_port),[id,...tail]]);
      }
      return null;
    }
    function support(at,stop){
      const queue=[at],seen=new Set(),members=[];
      for(let i=0;i<queue.length&&i<2048;i++){
        const current=queue[i],key=JSON.stringify([current.id,current.port]);
        if(seen.has(key)||current.id===stop.id&&current.port===stop.port)continue;seen.add(key);
        const n=original.get(current.id);if(!n||['parameter','buffer','state','control','composite'].includes(n.kind))continue;
        const es=(incoming.get(current.id)||[]).filter(flow);
        if(n.kind==='interface'&&!es.length)continue;
        members.push(current.id);
        if(n.kind==='opaque'||n.operator==='phi')continue;
        for(const e of es)if(!e.condition)queue.push(value(e.source,e.source_port));
      }
      return members;
    }
    const findings=[];
    function finding(rule,label,members,roles,proof,excluded=[]){
      members=[...new Set(members)];
      const sorted=members.slice().sort(),base='architecture:'+rule+':'+hash(sorted.join('|'));
      if(findings.some(f=>f.rule===rule&&JSON.stringify(f.members.slice().sort())===JSON.stringify(sorted)))return;
      let id=base;for(let suffix=1;findings.some(f=>f.id===id);suffix++)id=base+':'+suffix;
      findings.push({id,rule,label,members,roles,proof,excluded,rule_version:VERSION,
        evidence_scope:members.some(id=>original.get(id)?.evidence_status==='runtime-only')?'observed-run':'source-dependencies'});
    }
    function consumers(id){
      // Consumers through explicit bindings, including local helper interfaces.
      const todo=[id],seen=new Set(),result=[];
      for(let i=0;i<todo.length&&i<2048;i++){
        const at=todo[i];if(seen.has(at))continue;seen.add(at);
        for(const e of outgoing.get(at)||[]){
          if(!flow(e)||e.condition)continue;
          if(transparent(original.get(e.target)))todo.push(e.target);else result.push(e.target);
        }
      }
      return [...new Set(result)];
    }
    const scalarOutput=p=>p.port==='out'||p.port==='0'&&original.get(p.id)?.outputs?.length===1;
    function gateTerm(id){
      const n=original.get(id),ins=inputs(id);
      const clean=n=>n&&n.kind==='compute'&&!n.mutable&&!n.condition&&!(incoming.get(n.id)||[]).some(e=>flow(e)&&e.condition);
      if(!clean(n)||!['mult','mul'].includes(operator(n))||ins.length!==2||!compatible(ins[0].edge,ins[1].edge))return null;
      const gate=ins.find(p=>scalarOutput(p)&&operator(original.get(p.id))==='sigmoid'&&clean(original.get(p.id)));
      const signal=ins.find(p=>p!==gate);
      if(!gate||gate.id===signal.id)return null;
      const members=[gate.id,id];
      if(scalarOutput(signal)&&operator(original.get(signal.id))==='tanh'&&clean(original.get(signal.id)))members.push(signal.id);
      return {gate:gate.id,value:signal.id,output:id,gate_port:gate.port,value_port:signal.port,
        gate_edge:gate.edge.id,value_edge:signal.edge.id,members,edges:ins.map(p=>p.edge)};
    }
    for(const n of ir.nodes){
      if(n.kind!=='compute')continue;
      const op=operator(n),ins=inputs(n.id);
      const term=gateTerm(n.id);
      if(term){
        finding('gate','Sigmoid gate',term.members,{gate:term.gate,value:term.value,output:n.id},['sigmoid output is an explicit operand of multiplication; no LSTM claim']);
      }
      if(op==='matmul'||/^aten\.(bmm|mm|matmul)\./.test(op||'')){
        for(const operand of ins){
          let at=operand.id,chain=[],scaled=false,softmax=null,score=null;
          for(let step=0;step<12;step++){
            const current=original.get(at),kind=operator(current);
            if(!current||current.kind==='opaque'||current.mutable)break;
            if(kind==='softmax')softmax=at;
            if(['div','mult','mul'].includes(kind)||/^aten\.(div|mul)\./.test(kind||''))scaled=true;
            if(softmax&&(kind==='matmul'||/^aten\.(bmm|mm|matmul)\./.test(kind||''))){score=at;break;}
            // Follow a single data input; scale constants have no producer in
            // the static IR. Multiple tensor inputs must not be guessed away.
            const prev=inputs(at).filter(p=>kind!=='softmax'||!['kw:dim','arg:1'].includes(p.edge.target_port));if(prev.length!==1)break;
            chain.push(at);at=prev[0].id;
          }
          if(score&&softmax&&scaled){const other=ins.find(p=>p!==operand);
            if(other)finding('scaled-attention-like','Scaled attention-like',[score,...chain,n.id],
              {scores:score,normalization:softmax,values:other.id,output:n.id},
              ['matmul → scale → softmax → matmul operand path; Q/K/V and head identities are not asserted']);
          }
        }
      }
      if(op==='linear'||op==='convolution'){
        const direct=consumers(n.id),normalizations=op==='convolution'?direct.filter(id=>operator(original.get(id))==='normalization'&&inputs(id).length===1):[];
        const activations=[...new Set([...direct,...normalizations.flatMap(consumers)])].filter(id=>operator(original.get(id))==='activation');
        for(const act of activations){
          const next=consumers(act);
          if(op==='linear'){
            for(const end of next.filter(id=>operator(original.get(id))==='linear'))
              finding('feed-forward','Feed-forward',[n.id,act,end],{input:n.id,activation:act,output:end},['Linear → activation → Linear operand dependency path']);
          }else{
            const pool=next.find(id=>operator(original.get(id))==='pooling');
            const norm=normalizations.find(id=>consumers(id).includes(act));
            finding('convolution-block','Convolution block',[n.id,...(norm?[norm]:[]),act,...(pool?[pool]:[])],{convolution:n.id,...(norm?{normalization:norm}:{}),activation:act,...(pool?{pooling:pool}:{})},['convolution'+(norm?' → normalization':'')+' → activation'+(pool?' → pooling':'')+' operand dependency path']);
          }
        }
      }
      if(op!=='add'||ins.length!==2||n.mutable||!compatible(ins[0].edge,ins[1].edge))continue;
      for(let side=0;side<2;side++){
        const skip=ins[side].id,branch=ins[1-side].id;
        if(skip===branch)continue;
        const branchPath=path(ins[side],ins[1-side],ins[side].edge.evidence);
        if(!branchPath?.length)continue;
        const norm=consumers(n.id).find(id=>operator(original.get(id))==='normalization'&&inputs(id).length===1);
        // A normalization *somewhere* in a branch is not sufficient for Pre-LN.
        const prenorm=branchPath.find(id=>operator(original.get(id))==='normalization'&&inputs(id).length===1&&inputs(id)[0].id===skip&&inputs(id)[0].port===ins[side].port);
        const rule=norm?'residual-postnorm':prenorm?'residual-prenorm':'residual';
        finding(rule,norm?'Residual · Post-Norm':prenorm?'Residual · Pre-Norm':'Residual',
          [...support(ins[1-side],ins[side]),n.id,...(norm?[norm]:[])],{skip,branch,add:n.id,...(norm?{normalization:norm}:prenorm?{normalization:prenorm}:{})},
          ['skip value is an actual producer of both the branch path and addition',norm?'normalization consumes the addition output':prenorm?'normalization directly consumes the skip value':'normalization order not asserted'],[skip]);
        break;
      }
    }
    // A dependency through configuration still forms a real local expression.
    // Preserve a compact, reversible structural form without calling it a
    // residual or generating a bypass constraint. This applies to ordinary
    // binary algebra, independently of source module or model names.
    const expressionLabels={add:'Add expression',sub:'Subtract expression',mult:'Multiply expression',div:'Divide expression',matmul:'Matmul expression'};
    for(const n of ir.nodes){
      const op=operator(n),ins=inputs(n.id);
      if(n.kind!=='compute'||!Object.hasOwn(expressionLabels,op)||ins.length!==2||n.mutable||n.condition||
        !compatible(ins[0].edge,ins[1].edge)||findings.some(f=>f.rule.startsWith('residual')&&f.roles.add===n.id))continue;
      for(let side=0;side<2;side++){
        const input=ins[side],branch=ins[1-side];
        if(input.id===branch.id||path(input,branch,input.edge.evidence)?.length||
          !path(input,branch,input.edge.evidence,false)?.length)continue;
        const members=[...support(branch,input),n.id];
        if(members.some(id=>{const m=original.get(id);return !m||m.mutable||m.condition||m.operator==='phi'||
          ['opaque','control'].includes(m.kind)||m.identity_display||m.observed_calls||m.iteration||m.repeat_contract||
          m.evidence_status==='runtime-only'||m.runtime_evidence?.length;}))continue;
        finding('operand-expression',expressionLabels[op],members,
          {operator:op,output:n.id,operands:ins.map(p=>({node:p.id,slot:p.port,edge:p.edge.id,target_port:p.edge.target_port}))},
          ['exact binary operands have a source dependency without a proved tensor-value branch path',
            'structural expression only; no residual, value equivalence, purity or model-family claim'],[input.id]);
        break;
      }
    }
    // Compose proved local products by their exact sum operands. This describes
    // the algebra even for unfamiliar cells, without asserting state, experts,
    // complementary/normalized weights, independent paths or a model family.
    for(const n of ir.nodes){
      if(n.kind!=='compute'||operator(n)!=='add'||n.mutable||n.condition)continue;
      const alpha=n.arguments?.kwargs?.alpha??n.arguments?.args?.[2]??1;
      if(alpha!==1)continue;
      const raw=(incoming.get(n.id)||[]).filter(flow),ins=inputs(n.id);
      if(raw.some(e=>e.condition)||ins.length!==2||ins[0].id===ins[1].id||!ins.every(scalarOutput)||!compatible(ins[0].edge,ins[1].edge))continue;
      const terms=ins.map(p=>gateTerm(p.id));
      if(terms.some(t=>!t)||terms.some((t,i)=>t.edges.some(e=>!compatible(e,ins[i].edge))))continue;
      finding('gated-sum','Gated sum',[...terms.flatMap(t=>t.members),n.id],
        {terms:terms.map((t,i)=>({gate:t.gate,value:t.value,product:t.output,gate_port:t.gate_port,value_port:t.value_port,
          gate_edge:t.gate_edge,value_edge:t.value_edge,sum_edge:ins[i].edge.id,sum_port:ins[i].edge.target_port})),
        output:n.id,weight_normalization:'not-asserted',state_update:'not-asserted',model_family:'not-asserted'},
        ['two explicit sigmoid-gated products are the distinct operands of addition',
          'each product and sum operand retains its original edge, slot and evidence; no state-update or model-family claim']);
    }
    // Serial invocations of the same local definition and configuration can be
    // summarized without substituting one instance for another. All instances
    // and parameter paths remain inside the summary; sharing is not guessed.
    const scopes=new Map();
    const unresolved=x=>x&&typeof x==='object'&&('unresolved' in x||Object.values(x).some(unresolved));
    for(const n of ir.nodes)if(n.kind==='composite'&&['source-module','source-function'].includes(n.semantic_type)&&n.source?.length&&Object.hasOwn(n,'constructor')&&n.constructor!==undefined&&!unresolved(n.constructor)){
      if(!scopes.has(n.parent))scopes.set(n.parent,[]);scopes.get(n.parent).push(n);
    }
    function originalOwner(id,parent){while(id!=null&&original.get(id)?.parent!==parent)id=original.get(id)?.parent;return id;}
    for(const [parent,calls]of scopes){
      if(calls.length<2)continue;
      const ids=new Set(calls.map(n=>n.id)),adj=new Map(calls.map(n=>[n.id,new Set()])),prev=new Map(calls.map(n=>[n.id,new Set()]));
      for(const e of ir.edges)if(flow(e)&&!e.condition){
        const a=originalOwner(producer(e.source),parent),b=originalOwner(e.target,parent);
        if(ids.has(a)&&ids.has(b)&&a!==b){adj.get(a).add(b);prev.get(b).add(a);}
      }
      const signature=n=>JSON.stringify([(n.source||[]).map(s=>[s.file,s.symbol,s.line,s.column]),n.constructor]);
      const same=(a,b)=>signature(original.get(a))===signature(original.get(b));
      const next=id=>[...adj.get(id)].filter(b=>same(id,b));
      for(const n of calls){
        if([...prev.get(n.id)].some(a=>same(a,n.id)))continue;
        const members=[n.id],seen=new Set(members);let at=n.id;
        while(next(at).length===1){const b=next(at)[0];if(seen.has(b)||[...prev.get(b)].filter(a=>same(a,b)).length!==1)break;members.push(b);seen.add(b);at=b;}
        if(members.length>1)finding('repeated-source',`Repeated structure × ${members.length}`,members,
          {instances:members,parameter_scopes:members.map(id=>original.get(id).module_path),parameter_sharing:'unresolved'},
          ['serial dependency between invocations of the same local source definition and constructor configuration',
            'every invocation is retained; equivalent outputs and independent/shared parameters are not asserted']);
      }
    }
    const nodes=ir.nodes.map(n=>({...copy(n),source_parent:n.source_parent===undefined?n.parent:n.source_parent}));
    const by=new Map(nodes.map(n=>[n.id,n]));
    const descendants=id=>{const result=[];for(const n of nodes)if(n.parent===id)result.push(n.id,...descendants(n.id));return result;};
    function ancestry(id){const result=[];while(id!=null){result.push(id);id=by.get(id)?.parent;}result.push(null);return result;}
    function direct(id,parent){while(by.get(id)?.parent!==parent){id=by.get(id)?.parent;if(id==null)return null;}return id;}
    // Findings can overlap. Materialize compatible, nested groups only; retain
    // every incompatible finding as evidence rather than forcing a false tree.
    for(const f of findings.slice().sort((a,b)=>a.members.length-b.members.length||a.id.localeCompare(b.id))){
      const chains=f.members.map(ancestry),parent=chains[0].slice(1).find(p=>chains.every(c=>c.includes(p)));
      const members=[...new Set(f.members.map(id=>direct(id,parent)))];
      if(members.includes(null)||members.length<2){f.presentation='annotation';continue;}
      const closure=new Set(members.flatMap(id=>[id,...descendants(id)]));
      if(f.excluded.some(id=>closure.has(id))||members.some(id=>by.get(id)?.kind==='opaque')){f.presentation='annotation';continue;}
      // A source-backed motif may already own this exact computation set.
      // Attach the stronger finding to that container instead of nesting an
      // identical semantic enclosure inside it. Canonical ownership survives.
      const existing=by.get(parent),prior=ir.motifs?.find(m=>m.id===existing?.motif);
      const computations=ids=>new Set(ids.filter(id=>['compute','opaque'].includes(original.get(id)?.kind)));
      if(prior){const expected=computations(prior.members),actual=computations(f.members);
        if(expected.size&&expected.size===actual.size&&[...expected].every(id=>actual.has(id))){
          existing.source_label=existing.label;existing.label=f.label;existing.semantic_type=f.rule;existing.finding=f.id;
          f.presentation='annotation';f.presentation_node=parent;f.presentation_reason='Existing source motif owns the same computation set';continue;
        }
      }
      const partialOverlap=members.some(id=>{
        const grouped=findings.find(other=>other.id===by.get(id)?.finding);
        return grouped&&!grouped.members.every(id=>f.members.includes(id));
      });
      if(partialOverlap){f.presentation='annotation';f.presentation_reason='overlapping findings cannot form a nested presentation tree';continue;}
      // Move dependent aliases and exclusively owned resources with the group.
      let changed=true;
      while(changed){changed=false;for(const n of nodes){
        if(n.parent!==parent||closure.has(n.id))continue;
        const es=(incoming.get(n.id)||[]).filter(flow),uses=outgoing.get(n.id)||[];
        const binding=n.kind==='value-alias'&&!n.operator&&es.length===1&&closure.has(es[0].source);
        const resource=['parameter','buffer'].includes(n.kind)&&uses.length&&uses.every(e=>closure.has(e.target));
        if(binding||resource){members.push(n.id);closure.add(n.id);changed=true;}
      }}
      const sources=members.flatMap(id=>by.get(id).source||[]),runtime=members.flatMap(id=>by.get(id).runtime_evidence||[]);
      const group={id:f.id,kind:'composite',label:f.label,parent,source:sources,runtime_evidence:runtime,
        semantic_type:f.rule,granularity:'composite',evidence_status:f.evidence_scope==='observed-run'?'runtime-only':'static-only',
        glyph:{shape:'frame',fill:'#e9f1ff'},presentation_only:true,finding:f.id};
      nodes.push(group);by.set(group.id,group);for(const id of members)by.get(id).parent=group.id;
      f.presentation='group';f.parent=parent;
    }
    // Each original node and edge survives. Boundary ports identify the exact
    // cut, even when two tensors connect the same pair of collapsed modules.
    for(const n of nodes)if(n.presentation_only){
      const inside=new Set(descendants(n.id));
      n.canonical_members=[...inside].filter(id=>original.has(id));
      n.boundary_ports=ir.edges.filter(e=>inside.has(e.source)!==inside.has(e.target)).map(e=>({
        id:e.id,direction:inside.has(e.target)?'input':'output',source:e.source,source_port:e.source_port,
        target:e.target,target_port:e.target_port,evidence:e.evidence,...(e.condition?{condition:copy(e.condition)}:{})
      }));
    }
    // Reviewed source contracts annotate existing nodes. They do not replace
    // canonical topology or select a whole-model template.
    const contracts=copy(ir.semantic_contracts||[]),design=[];
    for(const c of contracts){
      const n=by.get(c.node);if(!n||c.rule_version!=='source-contracts/1'||!c.members.every(id=>original.has(id)))continue;
      n.semantic_contracts=[...(n.semantic_contracts||[]),c.id];
      n.contract_evidence=[...(n.contract_evidence||[]),{id:c.id,rule:c.rule,proof:c.proof,scope:c.scope,not_asserted:c.not_asserted}];
      if(['multihead-attention','scaled-dot-product-attention','feed-forward'].includes(c.rule)){
        n.source_label=n.label;n.semantic_type=c.rule;
        n.label=c.rule==='feed-forward'?'Feed-forward':c.rule==='multihead-attention'?'Multi-head attention':'Scaled dot-product attention';
        n.contract_roles=copy(c.roles);
      }
      if(c.rule.startsWith('residual-'))design.push({kind:'bypass',certificate:c.id,...copy(c.roles)});
      if(c.roles.projections)design.push({kind:'parallel-projections',certificate:c.id,parent:c.node,members:Object.values(c.roles.projections),roles:copy(c.roles.projections)});
      findings.push({id:c.id,rule:c.rule,label:c.rule,members:c.members,roles:c.roles,proof:c.proof,excluded:[],
        rule_version:c.rule_version,evidence_scope:'source-contract',presentation:'annotation',certificate:c.id});
    }
    for(const n of nodes)if(n.repeat_contract)design.push({kind:'serial-sequence',node:n.id,...copy(n.repeat_contract)});
    for(const a of ir.observation_index?.module_associations||[]){const n=by.get(a.node);if(n)n.observed_calls=copy(a);}
    for(const g of ir.observation_index?.trace_groups||[]){
      if(!g.complete_trace||g.runs.length<2||!g.runs.every(r=>by.has(r.node)))continue;
      const roots=g.runs.map(r=>by.get(r.node)),parent=roots[0].parent;
      if(!roots.every(n=>n.parent===parent))continue;
      const members=roots.flatMap(n=>[n.id,...descendants(n.id)]),id=g.id;
      const group={id,parent,kind:'composite',label:`Observed variant · ${g.runs.length} runs`,semantic_type:'observed-variant',
        presentation_only:true,finding:id,source:[],runtime_evidence:roots.flatMap(n=>n.runtime_evidence||[]),evidence_status:'runtime-only',
        canonical_members:members,boundary_ports:[],observation_group:copy(g),glyph:{shape:'frame',fill:'#e9f4ee'}};
      nodes.push(group);by.set(id,group);for(const n of roots)n.parent=id;
      findings.push({id,rule:'observed-trace-structure',label:group.label,members,roles:{representative:g.representative},
        proof:[g.scope],excluded:[],evidence_scope:'observed-runs',presentation:'group',rule_version:'observation-index/1'});
    }
    const relationGraph=Relations.build(ir,operator);
    let objectLabel=0;
    for(const r of relationGraph.relations){
      if(r.type==='same-object-calls')for(const [i,id]of r.members.entries()){
        const n=by.get(id);if(n)n.identity_display={relation:r.id,reference:r.properties.reference,
          label:'Object '+(objectLabel+1),invocation:i+1,count:r.members.length,kind:r.type};
      }
      if(r.type==='same-object-calls')objectLabel++;
      if(r.type==='observed-parameter-aliases'){
        const n=by.get(r.node);if(n)n.identity_display={relation:r.id,kind:r.type,aliases:copy(r.properties.aliases),run:r.properties.run};
      }
    }
    for(const r of relationGraph.relations){const n=by.get(r.node);if(n)n.local_relations=[...(n.local_relations||[]),r.id];}
    return {schema:'archcanvas-architecture/1',rule_version:VERSION,canonical_digest:ir.ir_digest,nodes,edges:ir.edges.map(copy),findings,relation_graph:relationGraph,
      semantic_contracts:contracts,design_constraints:design,
      limitations:['Local dependency patterns do not certify arbitrary-input behavior.',
        'Unknown operations, tuple slots, conditional joins and loop templates remain explicit.',
        'No Q/K/V, complete LSTM, MoE or model-family identity is inferred from names.']};
  }
  const api={VERSION,build,operator};root.SemanticArchitecture=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
