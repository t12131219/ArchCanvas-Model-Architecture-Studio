/* Independent local facts, not a family recognizer or a containment tree.
 * Every binding retains its canonical edge and operand/output slot. */
(function(root){
  'use strict';
  const VERSION='local-relations/1',copy=x=>JSON.parse(JSON.stringify(x));
  const flow=e=>['data','alias','interface-binding'].includes(e.kind);
  const key=p=>JSON.stringify([p.id,p.port]);
  function build(ir,operator){
    const by=new Map(ir.nodes.map(n=>[n.id,n])),ins=new Map(),outs=new Map(),relations=[];
    for(const e of ir.edges){if(!ins.has(e.target))ins.set(e.target,[]);ins.get(e.target).push(e);if(!outs.has(e.source))outs.set(e.source,[]);outs.get(e.source).push(e);}
    const compose=(outer,inner)=>outer==='out'?inner:inner==='out'?outer:outer+'.'+inner;
    function conditionScope(id){const result=[];while(id){const n=by.get(id);if(n?.condition)result.push(copy(n.condition));id=n?.parent;}return result;}
    function resolve(id,port='out'){
      const via=[],seen=new Set();
      while(!seen.has(key({id,port}))){
        seen.add(key({id,port}));const n=by.get(id),es=(ins.get(id)||[]).filter(flow),e=es[0];
        // Tuple extraction is resolved only when its explicit incoming slot
        // matches. Conditional joins, opaque calls and mutations never unwrap.
        if(!n||n.operator||n.mutable||n.condition||!['interface','value-alias'].includes(n.kind)||es.length!==1||e.condition)break;
        if(n.kind==='value-alias'&&n.slot!=null&&String(n.slot)!==String(e.source_port))break;
        via.push(e.id);id=e.source;port=compose(e.source_port??'out',port);
      }
      return {id,port,via};
    }
    function binding(e,role){const p=resolve(e.source,e.source_port??'out');return {role,edge:e.id,source:e.source,source_port:e.source_port??'out',target:e.target,target_port:e.target_port??'in',producer:p.id,producer_port:p.port,via:p.via,condition_scope:conditionScope(e.target),...(e.condition?{condition:copy(e.condition)}:{})};}
    const input=(n,role='input')=>(ins.get(n.id)||[]).filter(flow).map(e=>binding(e,role));
    const compatible=bs=>{const evidence=new Set(bs.map(b=>(ins.get(b.target)||[]).find(e=>e.id===b.edge)?.evidence));return evidence.size<=1||[...evidence].every(e=>['source-dependency','framework-contract'].includes(e));};
    const clean=n=>n&&n.kind==='compute'&&!n.mutable&&!n.condition&&!(ins.get(n.id)||[]).some(e=>flow(e)&&e.condition);
    function add(type,node,members,bindings,properties={},notAsserted=[]){
      const unique=[...new Set(members)],base='relation:'+type+':'+node;let id=base;
      for(let suffix=1;relations.some(r=>r.id===id);suffix++)id=base+':'+suffix;
      const edges=[...new Set(bindings.flatMap(b=>[...b.via,b.edge]))];
      relations.push({id,type,node,members:unique,bindings,edges,properties,not_asserted:notAsserted,
        rule_version:VERSION,evidence_scope:unique.some(id=>by.get(id)?.evidence_status==='runtime-only')?'observed-run':'source-local',
        source_scope:by.get(node)?.parent??null,condition_scope:conditionScope(node)});
    }
    const edgeBy=new Map(ir.edges.map(e=>[e.id,e]));
    function inside(id,frame){const seen=new Set();while(by.has(id)&&!seen.has(id)){if(id===frame)return true;seen.add(id);id=by.get(id).parent;}return false;}
    function iterationBindings(loop){
      const c=loop.iteration_contract,guard=edgeBy.get(c?.guard_edge);
      if(c?.rule_version!=='iteration-bindings/1'||c.scope!=='source-name-bindings; normal-completion; zero-or-more-iterations'||
        by.get(c.body)?.semantic_type!=='loop-template'||by.get(c.region)?.semantic_type!=='iteration-region'||loop.parent!==c.region||guard?.target!==loop.id||guard.kind!=='control')return;
      if(ir.nodes.some(n=>inside(n.id,c.body)&&(n.kind==='opaque'||n.mutable)))return;
      for(const row of c.bindings||[]){
        const entry=by.get(row.entry),exit=by.get(row.exit),initial=edgeBy.get(row.initial_edge),back=edgeBy.get(row.backedge),result=edgeBy.get(row.exit_edge),completion=edgeBy.get(row.completion_edge);
        const exact=(e,s,t,p)=>e&&e.source===s&&e.target===t&&e.source_port==='out'&&e.target_port===p&&e.iteration?.loop===loop.id;
        if(entry?.role!=='iteration-entry'||entry.operator!=='iteration-phi'||exit?.role!=='iteration-exit'||exit.operator!=='iteration-result'||
          entry.parent!==c.region||entry.iteration?.loop!==loop.id||exit.iteration?.loop!==loop.id||!inside(row.body_value,c.body)||
          !exact(initial,row.initial,row.entry,'initial')||!exact(back,row.body_value,row.entry,'backedge')||!exact(result,row.entry,row.exit,'value'))continue;
        if(completion?.source!==loop.id||completion.target!==row.exit||completion.kind!=='control'||completion.target_port!=='completion')continue;
        const reads=ir.edges.filter(e=>e.source===row.entry&&(inside(e.target,c.body)||(c.guard_nodes||[]).includes(e.target)||e.id===c.guard_edge));
        if(reads.length!==(row.read_edges||[]).length||reads.some(e=>!row.read_edges.includes(e.id)))continue;
        const bs=[binding(initial,'iteration-initial'),binding(back,'iteration-feedback'),binding(result,'iteration-result'),binding(completion,'iteration-completion'),
          ...reads.map(e=>binding(e,'iteration-read')),binding(guard,'iteration-control'),
          ...(outs.get(row.exit)||[]).filter(flow).map(e=>binding(e,'iteration-output'))];
        const update=resolve(row.body_value).id;
        add('iteration-binding',row.entry,[loop.id,c.body,row.entry,row.exit,...c.guard_nodes||[]],bs,
          {name:row.name,loop:loop.id,loop_kind:c.loop_kind,entry:row.entry,exit:row.exit,body:c.body,
            scope:c.scope,backedge:row.backedge,guard_edge:c.guard_edge,
            required_nodes:[loop.id,row.entry,row.exit,...(inside(update,c.body)?[update]:[])]},
          ['time recurrence','fixed count','termination','storage identity','purity','complete recurrent cell']);
      }
    }
    const terms=new Map();
    // A registered single-step interface is independent of any enclosing
    // model or time loop. Require the actual source call shape and every
    // dynamic operand, rather than inferring omitted state from missing edges.
    function cellInterface(n,bs){
      const operators={'torch.nn.RNNCell':'rnn-cell','torch.nn.GRUCell':'gru-cell','torch.nn.LSTMCell':'lstm-cell'};
      if(!Object.hasOwn(operators,n.framework_type)||n.operator!==operators[n.framework_type]||
        n.source_framework_module!==n.framework_type||n.evidence_status!=='static-only'||n.runtime_evidence?.length||n.observed_calls||!clean(n)||n.syntax?.type!=='Call')return null;
      const args=n.syntax.fields?.args,keywords=n.syntax.fields?.keywords;
      if(!Array.isArray(args)||!Array.isArray(keywords)||args.length>2||keywords.length>2)return null;
      const call=n.cell_call;
      if(call?.rule_version!=='source-cell-call/1'||call.positional_count!==args.length||
        JSON.stringify(call.keyword_names)!==JSON.stringify(keywords.map(k=>k?.fields?.arg))||
        call.positional_expansion!==false||call.keyword_expansion!==false)return null;
      const slots=new Map();
      for(const [i,a]of args.entries())slots.set(i===0?'input':'hx',{port:'arg:'+i,syntax:a,path:'.args:'+i});
      for(const [i,k]of keywords.entries()){
        const name=k?.fields?.arg;
        if(k?.type!=='keyword'||!['input','hx'].includes(name)||slots.has(name))return null;
        slots.set(name,{port:'kw:'+name,syntax:k.fields.value,path:'.keywords:'+i+'.value'});
      }
      if(!slots.has('input'))return null;
      const expected=[];
      for(const [name,s]of slots){
        if(s.syntax?.operand===s.path&&Object.keys(s.syntax).length===1){expected.push(s.port);continue;}
        if(name==='hx'&&s.syntax?.literal_type==='NoneType'&&s.syntax.literal==='None'&&Object.keys(s.syntax).length===2)continue;
        return null;
      }
      const incoming=ins.get(n.id)||[];
      if(incoming.length!==expected.length||incoming.some(e=>!flow(e)||e.evidence!=='source-dependency'||e.condition||e.iteration)||
        expected.some(port=>incoming.filter(e=>e.target_port===port).length!==1))return null;
      const state=slots.get('hx'),explicit=state&&expected.includes(state.port),pair=n.framework_type==='torch.nn.LSTMCell';
      const inputs=bs.map(b=>({...b,role:b.target_port===slots.get('input').port?'step-input':'initial-state'}));
      const results=(outs.get(n.id)||[]).filter(flow).map(e=>binding(e,
        (e.source_port??'out')==='out'?(pair?'final-state-pair':'final-state'):
        pair&&['0','1'].includes(e.source_port)?'final-state':'result'));
      return {bindings:inputs.concat(results),properties:{framework_type:n.framework_type,interface_kind:'single-step',
        input_port:slots.get('input').port,state_input_port:explicit?state.port:null,
        initial_state:explicit?'explicit':state?'explicit-none':'framework-default',
        state_return_slot:'out',state_components:pair?{'0':'hidden','1':'cell'}:{out:'hidden'},
        scope:'Registered framework single-step input/output contract; no temporal index or recurrence inferred.'}};
    }
    for(const n of ir.nodes){
      const op=operator(n),bs=input(n);
      if(clean(n)&&['mult','mul'].includes(op)&&bs.length===2&&compatible(bs)){
        const gates=bs.filter(b=>b.producer_port==='out'&&operator(by.get(b.producer))==='sigmoid'&&clean(by.get(b.producer)));
        if(gates.length===1){const gate=gates[0],signal=bs.find(b=>b!==gate);
          if(key({id:gate.producer,port:gate.producer_port})!==key({id:signal.producer,port:signal.producer_port})){
            const bindings=[{...gate,role:'gate'},{...signal,role:'signal'}];
            add('gated-product',n.id,[gate.producer,signal.producer,n.id],bindings,{operation:'elementwise-product'},['cell family','state update','normalized or complementary weights']);terms.set(n.id,bindings);
          }
        }
      }
      if(clean(n)&&op==='linear')add('linear-transform',n.id,[n.id],bs,{framework_type:n.framework_type??null},['projection role in a larger module']);
      if(clean(n)&&['reshape','transpose','permute','flatten','squeeze','unsqueeze'].includes(op))add('axis-transform',n.id,[n.id],bs,{operation:op,arguments:copy(n.arguments||{})},['axis equivalence or invertibility','head identities']);
      if(clean(n)&&op==='softmax')add('axis-normalization',n.id,[n.id],bs,{operation:op,arguments:copy(n.arguments||{})},['routing','attention','normalization across different calls']);
      if(clean(n)&&['div','mult','mul'].includes(op))add('arithmetic',n.id,[n.id],bs,{operation:op},['scalar scaling unless operand type is independently known']);
      if(clean(n)&&['add','concat','stack'].includes(op)&&bs.length>1)add('join',n.id,[n.id],bs.map((b,i)=>({...b,role:'operand:'+i})),{operation:op},['independent branches','parallel execution']);
      if(clean(n)&&op==='top-k'){
        const result=(outs.get(n.id)||[]).filter(flow).map(e=>binding(e,e.source_port==='0'?'selected-values':e.source_port==='1'?'selection-indices':'result'));
        add('selection',n.id,[n.id],bs.concat(result),{operation:'top-k',arguments:copy(n.arguments||{})},['conditional dispatch','expert routing','weight-to-branch correspondence']);
      }
      // The framework type is an interface contract, never a source label.
      if(clean(n)&&['torch.nn.RNN','torch.nn.GRU','torch.nn.LSTM'].includes(n.framework_type)){
        const recurrent=n.framework_type==='torch.nn.LSTM',inputs=bs.map(b=>({...b,role:['arg:0','kw:input'].includes(b.target_port)?'sequence-input':['arg:1','kw:hx'].includes(b.target_port)?'initial-state':'configuration'}));
        const results=(outs.get(n.id)||[]).filter(flow).map(e=>binding(e,e.source_port==='0'?'sequence-output':e.source_port==='1'?(recurrent?'final-state-pair':'final-state'):'result'));
        add('state-interface',n.id,[n.id],inputs.concat(results),{framework_type:n.framework_type,initial_state:inputs.some(b=>b.role==='initial-state')?'explicit':'framework-default',state_return_slot:'1'},['custom loop recurrence','internal gates','identity of sequence and final state']);
      }
      const cell=cellInterface(n,bs);
      if(cell)add('state-interface',n.id,[n.id],cell.bindings,cell.properties,
        ['time recurrence','internal gates','storage identity','input/output equality','fixed call count']);
      if(n.kind==='opaque'||n.mutable){
        const bindings=[...bs,...(outs.get(n.id)||[]).filter(flow).map(e=>binding(e,'result'))];
        add('unknown-boundary',n.id,[n.id],bindings,{reason:n.reason||'mutable-operation',effects:n.effect_scope||'unresolved; inputs and external state may be affected'},['purity','transparency','storage alias stability']);
      }
      if(n.operator==='phi'){
        const branches=bs.filter(b=>b.condition&&by.get(b.condition.branch)?.kind==='control');
        if(branches.length)add('conditional-join',n.id,[n.id,...branches.map(b=>b.condition.branch)],branches.map(b=>({...b,role:'alternative:'+b.condition.outcome})),{},['all branches execute','expert routing']);
      }
      if(n.kind==='composite'&&n.condition?.branch&&by.has(n.condition.branch)){
        const control=(ins.get(n.id)||[]).filter(e=>e.kind==='control').map(e=>binding(e,'condition'));
        add('conditional-region',n.id,[n.id,n.condition.branch],control,{condition:copy(n.condition)},['parallel execution','unconditional invocation']);
      }
      if(n.kind==='control'&&op==='loop'){
        add('iteration-template',n.id,[n.id],(ins.get(n.id)||[]).map(e=>binding(e,'iteration-control')),{loop_semantics:n.loop_semantics||'unresolved'},['fixed count','time recurrence','state update']);
        iterationBindings(n);
      }
    }
    for(const n of ir.nodes){
      const bs=input(n);if(!clean(n)||operator(n)!=='add'||bs.length!==2||bs.some(b=>b.producer_port!=='out')||bs[0].producer===bs[1].producer)continue;
      if((n.arguments?.kwargs?.alpha??n.arguments?.args?.[2]??1)!==1||!compatible(bs)||!bs.every(b=>terms.has(b.producer)&&compatible([b,...terms.get(b.producer)])))continue;
      add('gated-join',n.id,[n.id,...bs.flatMap(b=>[b.producer,...terms.get(b.producer).map(b=>b.producer)])],bs.flatMap((b,i)=>[{...b,role:'sum:'+i},...terms.get(b.producer).map(b=>({...b,role:i+':'+b.role}))]),{operation:'sum-of-gated-products'},['complete cell','state update','normalized weights','expert routing']);
    }
    // Source usage groups compare exact resolved slots. They describe binding
    // identity, not storage equality across potentially effectful calls.
    const uses=new Map();
    for(const n of ir.nodes)if(['compute','opaque'].includes(n.kind))for(const b of input(n)){
      const scope=JSON.stringify([b.producer,b.producer_port,by.get(n.id)?.evidence_status,b.condition||null,b.condition_scope]);if(!uses.has(scope))uses.set(scope,[]);uses.get(scope).push(b);
    }
    for(const bs of uses.values())if(new Set(bs.map(b=>b.target)).size>1){
      const first=bs[0];add('source-uses',first.producer,[first.producer,...bs.map(b=>b.target)],bs,{identity:'explicit value binding and result slot'},['parallel execution','storage equality after side effects']);
    }
    // Identity is independent of invocation and tensor equality. A source
    // binding is accepted only inside the extractor's modeled prefix; paths,
    // class labels, equal shapes and constructor similarity are insufficient.
    const objects=new Map(),writes=new Set(ir.edges.filter(e=>e.kind==='state-write').map(e=>e.target));let barrier=null;
    for(const n of ir.nodes){
      if(n.evidence_status==='runtime-only'||n.id.startsWith('runtime:'))continue;
      const c=n.module_binding;
      if(!barrier&&c?.rule_version==='source-module-binding/1'&&c.status==='proved'&&c.invocation===n.id&&
        c.reference===n.module_identity&&c.reference&&c.construction_evidence?.length&&c.parameter_identity==='unresolved'&&
        c.allocation_distinctness==='not-asserted'&&['compute','composite'].includes(n.kind)){
        if(!objects.has(c.reference))objects.set(c.reference,[]);objects.get(c.reference).push(n);
      }
      if(n.kind==='opaque'||n.mutable||writes.has(n.id)||n.kind==='control'&&n.operator==='loop')barrier=barrier||n.id;
    }
    for(const [reference,calls]of objects)if(calls.length>1){
      const bs=calls.flatMap(n=>ir.edges.filter(e=>flow(e)&&inside(e.source,n.id)!==inside(e.target,n.id))
        .map(e=>binding(e,inside(e.target,n.id)?'invocation-input':'invocation-result')));
      add('same-object-calls',calls[0].id,calls.map(n=>n.id),bs,
        {reference,invocations:calls.map(n=>({node:n.id,condition_scope:conditionScope(n.id)})),required_nodes:calls.map(n=>n.id),
          scope:'source call sites selecting the same constructor binding in a modeled effect-free prefix'},
        ['parameter stability','parameter equality','output equality','fixed runtime call count','unconditional execution']);
    }
    // These aliases are measured at enumeration time, before forward. They do
    // not establish parameter identity after a mutation or between runs.
    for(const n of ir.nodes)if(n.kind==='parameter'&&n.evidence_status==='runtime-only'&&n.aliases?.length>1){
      const match=/^runtime:(\d+):parameter:/.exec(n.id),run=match&&ir.runtime?.runs?.[Number(match[1])];
      const p=run?.parameters?.find(p=>p.aliases?.[0]===n.parameter_identity&&JSON.stringify(p.aliases)===JSON.stringify(n.aliases));
      if(p)add('observed-parameter-aliases',n.id,[n.id],[],
        {aliases:copy(n.aliases),run:Number(match[1]),case:run.case,mode:run.mode,required_nodes:[n.id],scope:'parameter object aliases enumerated at the start of this run'},
        ['storage aliasing between distinct parameters','identity after mutation','identity between runs','equal invocation outputs']);
    }
    return {schema:VERSION,relations,canonical_nodes:ir.nodes.length,canonical_edges:ir.edges.length,
      limitations:['Local relationships may overlap; no family label selects a rule.','Unknown effects are unresolved; no identity proof crosses their computation.']};
  }
  const api={VERSION,build};root.SemanticLocalRelations=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
