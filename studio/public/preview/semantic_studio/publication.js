/* Publication is a derived, reversible presentation. Structural regions carry
 * no model-family claim. Exact canonical cuts, slots and unknowns survive. */
(function(root){
  'use strict';
  const A=root.SemanticArchitecture||(typeof require==='function'?require('./architecture.js'):null);
  const L=root.SemanticLayout||(typeof require==='function'?require('./architecture-layout.js'):null);
  const B=root.SemanticBranchRegions||(typeof require==='function'?require('./branch-regions.js'):null);
  const Regions=root.SemanticPresentationRegions||(typeof require==='function'?require('./presentation-regions.js'):null);
  const plans=new WeakMap(),copy=x=>JSON.parse(JSON.stringify(x));
  const flow=e=>['data','alias','interface-binding'].includes(e.kind);
  const hash=s=>{let h=2166136261;for(const c of s)h=Math.imul(h^c.charCodeAt(0),16777619);return (h>>>0).toString(16);};
  function unique(base,used){let id=base;for(let i=1;used.has(id);i++)id=base+':'+i;return id;}
  const textWidths=new Map();
  function width(s,font=16){
    const text=String(s),key=JSON.stringify([text,font]);
    if(textWidths.has(key))return textWidths.get(key);
    const value=Array.from(text).reduce((a,c)=>a+font*(/[^\u0000-\u024f]/u.test(c)?1:/[ilI.,:;'!|]/.test(c)?.29:/[MW@#%]/.test(c)?.85:.57),0);
    if(textWidths.size>=8192)textWidths.delete(textWidths.keys().next().value);
    textWidths.set(key,value);return value;
  }
  const wrappedTexts=new Map();
  function wrap(text,limit,font=16){
    const key=JSON.stringify([String(text),String(limit),String(font)]);
    if(wrappedTexts.has(key))return wrappedTexts.get(key).slice();
    const lines=[];let line='';
    // Use identifier word boundaries before falling back to character cuts.
    // Keep every character: this changes wrapping, never the source label.
    for(const token of String(text).split(/(\s+|(?<=[_.\/·→])|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z]))/u).filter(Boolean)){
      if(line&&width(line+token,font)>limit){lines.push(line.trim());line='';}
      for(const c of token){if(line&&width(line+c,font)>limit){lines.push(line.trim());line='';}line+=c;}
    }
    if(line.trim())lines.push(line.trim());const result=lines.length?lines:[''];
    if(wrappedTexts.size>=4096)wrappedTexts.delete(wrappedTexts.keys().next().value);
    wrappedTexts.set(key,result);return result.slice();
  }
  function index(plan){const nodes=new Map(plan.nodes.map(n=>[n.id,n])),children=new Map();for(const n of plan.nodes){if(!children.has(n.parent||null))children.set(n.parent||null,[]);children.get(n.parent||null).push(n.id);}return {nodes,children};}
  function relations(ir){const ins=new Map(),uses=new Map();for(const e of ir.edges){if(!ins.has(e.target))ins.set(e.target,[]);ins.get(e.target).push(e);if(!uses.has(e.source))uses.set(e.source,[]);uses.get(e.source).push(e);}return {ins,uses};}
  function literalArithmetic(n){
    // A bounded syntax recognizer, never eval: only integer literals, numeric
    // operators and parentheses. No names, calls, attributes or tensor reads.
    if(n.kind!=='compute'||n.evidence_status!=='static-only'||n.mutable||n.condition||n.runtime_evidence?.length||
      !['add','sub','mult','mul','div','floordiv','mod','pow'].includes(n.operator)||n.source?.length!==1)return false;
    const text=n.source[0].expression;if(typeof text!=='string'||text.length>160)return false;
    const tokens=text.match(/\d(?:_?\d)*|\/\/|\*\*|[()+*\/%\-]/g)||[];
    if(tokens.join('')!==text.replace(/\s/g,''))return false;
    let at=0,operations=0;
    function atom(depth){
      if(depth>16)return false;
      if(['+','-'].includes(tokens[at])){at++;return atom(depth+1);}
      if(/^\d(?:_?\d)*$/.test(tokens[at]||'')){at++;return true;}
      if(tokens[at]==='('){at++;if(!expression(depth+1)||tokens[at]!==')')return false;at++;return true;}
      return false;
    }
    function expression(depth){if(!atom(depth))return false;while(['+','-','*','/','//','%','**'].includes(tokens[at])){at++;operations++;if(!atom(depth))return false;}return true;}
    return expression(0)&&at===tokens.length&&operations>0;
  }
  function policy(ir,focus=null,inside=null,dimensionPaths=false,directOperands=new Set()){
    const {ins,uses}=relations(ir),by=new Map(ir.nodes.map(n=>[n.id,n])),bindings=new Map(),metadata=new Set();
    function configUse(e){
      const n=by.get(e.target),name=(n?.function_target||'').split('.').at(-1),port=e.target_port;
      if(n?.kind!=='compute')return false;
      if(['kw:dim','kw:keepdim','kw:keepdims','kw:size','kw:device','kw:dtype','kw:p','kw:negative_slope','kw:eps','kw:training','kw:align_corners'].includes(port))return true;
      if(['view','expand','transpose','permute','squeeze','unsqueeze'].includes(name))return port.startsWith('arg:');
      if(name==='reshape')return port!=='receiver'&&port!=='arg:0'||
        dimensionPaths?.unconsumedBindings===true&&port==='arg:0'&&(ins.get(n.id)||[]).some(e=>e.target_port==='receiver');
      if(['zeros','ones','rand','randn'].includes(name))return port.startsWith('arg:');
      return false;
    }
    for(const n of ir.nodes){const es=ins.get(n.id)||[],out=uses.get(n.id)||[];
      const one=es.length===1&&!es[0].condition&&flow(es[0]);
      const boundary=inside&&es.some(e=>!inside.has(e.source));
      // A focused alias fed from outside is a real local binding. Contracting
      // it to the out-of-scope producer strands both synthetic boundary ports.
      if(n.kind==='value-alias'&&!n.operator&&one&&!boundary)bindings.set(n.id,{...es[0],source_port:n.slot??es[0].source_port});
      if(n.kind==='interface'&&one&&!boundary&&n.parent!==focus&&(n.role==='input'||out.length))bindings.set(n.id,es[0]);
      const literalValue=Object.hasOwn(n,'value')&&n.value!==undefined&&!(n.value&&typeof n.value==='object'&&!Array.isArray(n.value));
      if(n.role==='module-reference'||n.operator==='shape'||(['state','buffer'].includes(n.kind)&&(literalValue||out.length&&out.every(configUse))))metadata.add(n.id);
    }
    let changed=true;while(changed){changed=false;for(const [id,e]of bindings)if(metadata.has(e.source)&&!metadata.has(id)){metadata.add(id);changed=true;}}
    // Prove a closed literal-only dependency subgraph first. A plausible source
    // string cannot override an incoming tensor, state, condition or runtime edge.
    const pure=new Set(),staticEdge=e=>flow(e)&&e.source_port==='out'&&!e.condition&&['source-dependency','static-source'].includes(e.evidence);
    changed=true;while(changed){changed=false;for(const n of ir.nodes){
      if(pure.has(n.id)||n.evidence_status!=='static-only'||n.mutable||n.condition||n.runtime_evidence?.length)continue;
      const incoming=ins.get(n.id)||[],alias=n.kind==='value-alias'&&!n.operator&&n.slot==null&&incoming.length===1;
      if((literalArithmetic(n)||alias)&&incoming.every(e=>staticEdge(e)&&pure.has(e.source))){pure.add(n.id);changed=true;}
    }}
    // Only configuration consumers justify attachment. A returned scalar or a
    // coefficient in feature arithmetic keeps the entire value chain visible.
    const configurationOnly=new Set();changed=true;
    while(changed){changed=false;for(const id of pure){const out=uses.get(id)||[];
      if(!configurationOnly.has(id)&&out.length&&out.every(e=>staticEdge(e)&&(configUse(e)||configurationOnly.has(e.target)))){configurationOnly.add(id);changed=true;}
    }}
    const configurationArithmetic=[];
    for(const id of configurationOnly){metadata.add(id);const n=by.get(id);
      configurationArithmetic.push({node:id,kind:n.kind==='compute'?'literal-arithmetic':'literal-binding',
        proof_scope:'full-extracted-graph',basis:'integer-literal-syntax-and-configuration-only-uses',
        expression:n.source?.[0]?.expression||n.label,dependencies:(ins.get(id)||[]).map(copy),uses:(uses.get(id)||[]).map(copy),
        value_evaluation:'not-performed',source:copy(n.source||[])});
    }
    if(dimensionPaths){
      const engine=root.SemanticDimensionPaths||(typeof require==='function'?require('./dimension-paths.js'):null);
      const derived=engine.compile({ir,configurationUse:configUse,...dimensionPaths});
      for(const id of derived.metadata)metadata.add(id);
      const existing=new Set(configurationArithmetic.map(row=>row.node));
      configurationArithmetic.push(...derived.rows.filter(row=>!existing.has(row.node)));
    }
    // An explicitly selected atomic operation must expose its real incoming
    // cuts, including shape/configuration values normally attached as notes.
    // External producers stay outside the detail; no behavior is inferred.
    const directValues=new Set(directOperands);
    for(const e of ir.edges)if(directOperands.has(e.target)&&flow(e))directValues.add(e.source);
    for(const id of directValues)metadata.delete(id);
    return {bindings,metadata,ins,uses,configurationArithmetic:configurationArithmetic.filter(r=>!directValues.has(r.node)),configurationUses:new Set(ir.edges.filter(configUse).map(e=>e.id))};
  }
  function value(id,port='out',bindings){const seen=new Set();while(bindings.has(id)&&!seen.has(id)){seen.add(id);const e=bindings.get(id);id=e.source;const outer=e.source_port??'out';port=outer==='out'?port:port==='out'?outer:outer+'.'+port;}return {id,port};}
  function descendants(id,children){const all=[],todo=[...(children.get(id)||[])];for(let i=0;i<todo.length;i++){all.push(todo[i]);todo.push(...children.get(todo[i])||[]);}return all;}
  function category(n){
    const op=A.operator(n)||'',type=n.semantic_type||'';
    if(n.kind==='opaque')return 'unknown';
    if(n.kind==='interface')return 'interface';
    if(n.kind==='control'||['conditional-region','loop-template','iteration-region'].includes(type))return 'control';
    if(type.startsWith('residual')||['add','mult','mul'].includes(op)||['gate','gated-sum'].includes(type))return 'algebra';
    if(['lstm','gru','rnn','lstm-cell','gru-cell','rnn-cell'].includes(op))return 'recurrent';
    if(op.includes('attention')||type.includes('attention'))return 'attention';
    if(op==='convolution'||type.includes('convolution')||type==='CNN block')return 'convolution';
    if(['parameter','buffer','state'].includes(n.kind))return 'resource';
    if(n.kind==='composite')return 'module';return 'operation';
  }
  const palette={module:['#f1f4fa','#62748c'],operation:['#edf4fc','#456c96'],convolution:['#e9f4ee','#4d7e67'],attention:['#eeedfa','#72659b'],recurrent:['#fff1e2','#a17b41'],algebra:['#f7eef7','#90678e'],control:['#fff7dc','#a48c3d'],unknown:['#fff4f0','#ac6857'],interface:['#ffffff','#7e8b9b'],resource:['#f7f6f2','#8a8474']};
  function configuration(n){
    if(n.kind==='compute'&&n.operator==='reshape'&&!n.mutable){
      const name=n.function_target?.split('.').at(-1),a=n.arguments?.args||[],k=n.arguments?.kwargs||{};
      let dims=['view','reshape'].includes(name)?k.shape:undefined;
      if(dims===undefined&&['view','reshape'].includes(name))dims=n.function_target?.startsWith('torch.')?a[1]:a.length===1&&Array.isArray(a[0])?a[0]:a;
      if(Array.isArray(dims)&&dims.length&&dims.length<=8&&dims.every(d=>Number.isSafeInteger(d)&&d>=-1))return 'shape '+dims.join(' × ');
    }
    if(!Object.hasOwn(n,'constructor'))return '';
    const c=n.constructor||{},a=c.args||[],k=c.kwargs||c,known=x=>x!==undefined&&!(x&&typeof x==='object'&&!Array.isArray(x)),fmt=x=>Array.isArray(x)?x.join('×'):String(x);
    if(['linear','convolution'].includes(n.operator)){
      const first=a[0]??k[n.operator==='linear'?'in_features':'in_channels'],last=a[1]??k[n.operator==='linear'?'out_features':'out_channels'];
      const kernel=a[2]??k.kernel_size;return [known(first)&&known(last)?`${fmt(first)} → ${fmt(last)}`:null,n.operator==='convolution'&&known(kernel)?`k=${fmt(kernel)}`:null].filter(Boolean).join(' · ');
    }
    if(['rnn','lstm','gru'].includes(n.operator)){
      const size=a[1]??k.hidden_size,layers=k.num_layers??a[2];return [known(size)?`hidden ${fmt(size)}`:null,known(layers)?`${fmt(layers)} layers`:null,k.bidirectional===true?'bidirectional':null].filter(Boolean).join(' · ');
    }
    if(['rnn-cell','lstm-cell','gru-cell'].includes(n.operator)){
      const size=a[1]??k.hidden_size;return ['Single step',known(size)?`hidden ${fmt(size)}`:null].filter(Boolean).join(' · ');
    }
    return '';
  }
  function inventory(units,idx){
    const names={linear:'Linear',convolution:'Convolution',normalization:'Normalization',activation:'Activation',
      sigmoid:'Sigmoid',tanh:'Tanh',add:'Add',mult:'Multiply',mul:'Multiply',matmul:'MatMul',
      softmax:'Softmax',pooling:'Pooling',dropout:'Dropout',embedding:'Embedding',concat:'Concat',
      rnn:'RNN',lstm:'LSTM',gru:'GRU','rnn-cell':'RNNCell','lstm-cell':'LSTMCell','gru-cell':'GRUCell',structure:'Pack values',transpose:'Transpose',reshape:'Reshape'};
    const rules={'feed-forward':'Feed-forward',gate:'Sigmoid gate','gated-sum':'Gated sum','convolution-block':'Convolution block',
      residual:'Residual','residual-prenorm':'Residual · Pre-Norm','residual-postnorm':'Residual · Post-Norm',
      'scaled-attention-like':'Scaled attention-like'};
    const items=[...new Set(units)].map(id=>{
      const n=idx.nodes.get(id),op=A.operator(n);let term,origin;
      if(n.kind==='opaque'){term='Unresolved';origin='unresolved';}
      else if(n.presentation_only&&Object.hasOwn(rules,n.semantic_type)){term=rules[n.semantic_type];origin='local-rule';}
      else if(n.kind==='compute'&&Object.hasOwn(names,op)){
        term=names[op];origin='operator';
        // A known framework operation may retain its more specific registered
        // class name. Source/module labels never select an algorithm meaning.
        if(n.framework_type?.startsWith('torch.nn.'))term=n.framework_type.split('.').at(-1);
        else if(op==='activation'){
          const fn=n.function_target?.split('.').at(-1)?.toLowerCase();
          if(['relu','gelu','silu','elu','leaky_relu'].includes(fn))term=({relu:'ReLU',gelu:'GELU',silu:'SiLU',elu:'ELU',leaky_relu:'LeakyReLU'})[fn];
        }
      }else{term=n.kind==='composite'?'Module':n.kind==='control'?'Control':'Other operation';origin='structure';}
      if(n.mutable)term+=' (in-place)';
      return {id,label:n.label,term,origin,kind:n.kind,operator:op,mutable:!!n.mutable,evidence_status:n.evidence_status||'unspecified'};
    });
    const terms=[];
    for(const item of items){let term=terms.find(t=>t.label===item.term&&t.origin===item.origin);
      if(!term){term={label:item.term,origin:item.origin,count:0,units:[]};terms.push(term);}term.count++;term.units.push(item.id);
    }
    return {schema:'publication-unit-inventory/1',basis:'direct-semantic-units',multiplicity:'extracted-units',
      execution_order:'not-asserted',parameter_sharing:'not-asserted',tensor_equality:'not-asserted',units:items,terms};
  }
  function inventoryCaption(contents,opaque,budget,limit){
    const terms=contents.terms.filter(t=>t.origin!=='unresolved');
    if(!terms.some(t=>['operator','local-rule'].includes(t.origin)))return null;
    // Keep the existing text envelope and node dimensions. This is a selected
    // contents summary; the complete inventory and topology caption survive.
    for(let count=terms.length;count>0;count--){
      const shown=terms.slice(0,count);
      if(!shown.some(t=>['operator','local-rule'].includes(t.origin)))continue;
      const text=[...shown.map(t=>t.label+(t.count>1?' × '+t.count:'')),count<terms.length?'+'+(terms.length-count)+' kinds':null,opaque?opaque+' unresolved':null].filter(Boolean).join(' · ');
      const lines=wrap(text,limit,13);
      if(lines.length<=budget)return {text,lines,shown_terms:shown.map(t=>({label:t.label,origin:t.origin})),omitted_kinds:terms.length-count};
    }
    return null;
  }
  function decorate(n,idx){
    const ds=descendants(n.id,idx.children).map(id=>idx.nodes.get(id)),opaque=(n.kind==='opaque'?1:0)+ds.filter(n=>n.kind==='opaque').length;
    const cat=category(n),[fill,stroke]=palette[cat],type=n.semantic_type||n.operator||n.kind;
    const captionsByType={'source-module':'Module','source-function':'Function','sequential':'Sequential','structural-region':'Dependency region','interface':'','value-alias':'Value','structure':'','rnn':'RNN','lstm':'LSTM','gru':'GRU','gated-sum':'2 sigmoid-gated products','residual':'Residual path','residual-prenorm':'Residual · Pre-Norm','residual-postnorm':'Residual · Post-Norm'};
    let title=n.label,caption=configuration(n)||(Object.hasOwn(captionsByType,type)?captionsByType[type]:type);
    if(n.role==='iteration-entry'){title=n.iteration.name;caption='Current binding';}
    if(n.role==='iteration-exit'){title=n.iteration.name;caption='Loop result';}
    if(type==='iteration-region')caption='Source bindings · count unproved';
    // An extractor's scope-wide pattern annotation is not a certificate that
    // every computation in the source module implements that pattern. Exact
    // local findings and contracts supply their own labels below.
    if(n.kind==='composite'&&n.source_class&&!n.presentation_only&&!n.finding&&!n.contract_roles&&n.module_path!=null)caption='Source module';
    if(type==='relation-panel')caption='Local relationship · exact interfaces';
    if(type==='serial-remainder')caption=n.region_summary;
    if(n.contract_roles){
      const r=n.contract_roles;
      caption=type==='multihead-attention'?`${r.heads} heads · ${r.mode==='self'?'same source':r.mode==='cross'?'two sources':'role-bound inputs'}`:type==='feed-forward'?'Linear → activation → Linear':'Operand and axis contract';
    }
    if(n.repeat_contract){const r=n.repeat_contract,s=r.structure,unknown=s?.groups.filter(g=>g.status!=='proved').length||0;
      const summary=s?.rule_version!=='local-structure/1'?'Structure unverified':s.homogeneous?'Same modeled structure':unknown?`${s.groups.length-unknown} modeled groups · ${unknown} unclassified elements`:s.groups.length+' structural groups';
      caption=`${summary} · ${r.count} source calls · parameters ${r.parameter_sharing}`;}
    if(n.semantic_type==='repeat-instance'){
      const parent=idx.nodes.get(n.parent),repeat=parent?.repeat_contract||idx.nodes.get(parent?.sequence_remainder?.sequence)?.repeat_contract;
      if(repeat)caption=`Instance ${n.repeat_index+1} of ${repeat.count} · parameters ${repeat.parameter_sharing}`;
      if(n.structure_representative)caption+=` · source positions ${n.structure_representative.indices.map(i=>i+1).join(', ')} · structure only`;
    }
    if(n.observation_group)caption='Same observed structure · individual executions retained';
    const sourceOwner=n.frame_ownership?.find(r=>r.kind==='source-owner');
    if(sourceOwner)title=sourceOwner.label+' · '+title;
    const sequenceSample=n.frame_ownership?.find(r=>r.kind==='sequence-sample');
    if(sequenceSample)caption='Detail: source call '+(sequenceSample.sequence_sample.index+1)+' · '+caption;
    const sourceClass=n.module_path&&(n.source_class||n.source?.find(s=>s.symbol?.endsWith('.forward')&&s.expression?.startsWith('def forward('))?.symbol.slice(0,-8));
    if(sourceClass&&sourceClass!==title&&!n.contract_roles)caption=sourceClass+(caption&&caption!=='Module'?' · '+caption:'');
    if(n.operator==='structure')title=n.structure_kind==='dict'?'Pack mapping':'Pack values';
    if(n.kind==='compute'&&n.framework_type){const short=n.framework_type.split('.').at(-1);title=n.label.includes(' · ')?n.label.split(' · ')[0]+' · '+short:n.label;}
    if(['structural-region','computation-region','conditional-collection','branch-region','branch-path','branch-panel','dependency-band','dependency-panel','boundary-interface-group'].includes(n.semantic_type))caption=n.region_summary;
    if(n.boundary_caption)caption=n.boundary_caption;
    if(opaque&&n.kind!=='opaque')caption+=(caption?' · ':'')+opaque+' unresolved';
    if(n.kind==='opaque')caption='Unresolved operation';
    if(n.state_interface?.initial_state==='framework-default'||n.state_interface?.initial_state==='explicit-none')
      caption+=(caption?' · ':'')+'zero state default';
    if(n.mutable)caption+=(caption?' · ':'')+'In-place update';
    if(n.observed_calls){const observations=n.observed_calls.observations;caption+=(caption?' · ':'')+`${new Set(observations.map(o=>o.run)).size} observed runs`;}
    if(n.identity_display){const d=n.identity_display;caption+=(caption?' · ':'')+(d.kind==='same-object-calls'?
      `${d.label} · source call ${d.invocation}/${d.count}`:`Run ${d.run+1} start aliases: ${d.aliases.join(' = ')}`);}
    const literalOperands=n.syntax?.type==='BinOp'?['left','right'].filter(side=>Object.hasOwn(n.syntax.fields[side]||{},'literal')).map(side=>side+' operand: '+n.syntax.fields[side].literal):[];
    if(literalOperands.length)caption=literalOperands.join(' · ');
    const symbol=n.kind==='compute'&&!n.mutable&&!literalOperands.length&&(['add','mult','mul'].includes(n.operator)||/^aten\.(add|mul)\./.test(n.operator||''))?(n.operator==='add'||n.operator.startsWith('aten.add.')?'+':'×'):null;
    if(n.role_annotations?.length&&!['opaque','control'].includes(n.kind)&&!n.mutable&&!n.condition&&!n.identity_display&&!n.observed_calls){
      const roles=[...new Map(n.role_annotations.map(r=>[JSON.stringify(r.role_keys||[r.role]),r.role_keys||[r.role]])).values()],specific=roles.filter(keys=>keys.length!==1||keys[0]!=='output');
      const names=(specific.length?specific:roles).map(keys=>{
        // Keep the containing field for numeric members. A dotted object key
        // is a single key, never an inferred nesting separator or array index.
        const numeric=keys.findLastIndex(k=>/^\d+$/.test(k));
        const parts=keys.slice(numeric<0?-1:Math.max(0,numeric-1));
        return (numeric===0?'Role · ':'')+parts.map(k=>k.replaceAll('_',' ')).join(' · ');
      });
      const role=[...new Set(names)].slice(0,2).join(' / ');
      const operation=n.framework_type?.split('.').at(-1)||n.operator;
      title=role;if(operation)caption=operation+(caption?' · '+caption:'');
      else if(n.contract_roles)caption=n.label;
    }
    if(n.condition_predicate){title='If '+n.condition_predicate.label;caption='Conditional alternatives · exact interfaces';}
    if(n.role_operation_stage){const r=n.role_operation_stage;const role=r.roles[0].role_keys||r.roles[0].role.split('.');title=role.at(-1).replaceAll('_',' ');caption=r.operations.map(o=>o.label).join(' → ');}
    if(n.role_path_stage){title=n.role_path_stage.role_title;caption=n.role_path_stage.operations.map(o=>o.label).join(' → ');}
    if(n.return_region){title='Return alternatives';caption='If '+n.return_region.predicate+' · '+n.return_region.return_sites.length+' source returns';}
    if(n.normal_return){title='Normal return';caption='Other source path retained';}
    if(n.contract_stage){title='Add & Norm';caption=(n.contract_stage.branch_tail?n.contract_stage.branch_tail.label+' → ':'')+n.contract_stage.normalization_type.split('.').at(-1)+' · Post-Norm';}
    if(n.local_pipeline&&!n.local_pipeline_expanded){
      const p=n.local_pipeline,labels=new Map(p.operations.map(o=>[o.node,o.label]));
      const expression=t=>labels.get(t.node)+(t.inputs.length?' ← {'+t.inputs.map(i=>expression(i.expression)).join('; ')+'}':'');
      const pathTitle=p.path_display?p.path_display.runs.map(r=>r.label+(r.operations.length>1?' · '+r.operations.length+' calls':'')).join(' → '):p.operations.map(o=>o.label).join(' → ');
      const rows=n.local_pipeline_binding_rows;
      title=rows?rows.title:p.dependency_dag?'Result '+p.dependency_dag.result:p.dependency_tree?expression(p.dependency_tree):pathTitle;
      caption=p.dependency_dag?'Dependency DAG':p.dependency_tree?'Dependency tree':'Dependency path';
      if(rows)caption+=' · operand uses';
      else if(p.source_reads?.length)caption+=' · Reads '+p.source_reads.map(r=>r.expression).join(', ');
      if(p.owner_identity){const d=p.owner_identity;caption+=` · ${d.label} · source call ${d.invocation}/${d.count}`;}
    }
    // A source name identifies the call; the result and every operand use
    // remain printed below it. It never certifies a semantic family.
    const sourceHeading=n.local_pipeline_source_heading&&n.local_pipeline?.dependency_dag&&
      n.local_pipeline_binding_rows&&!n.local_pipeline_expanded&&n.local_pipeline_source_label?
      {schema:'source-summary-heading/1',node:n.id,label:n.local_pipeline_source_label,result_title:title}:null;
    if(sourceHeading){caption=title+' · '+caption.replace(' · operand uses','');title='Source: '+sourceHeading.label;}
    if(n.invocation_binding){title=n.invocation_binding.label;caption='Fixed call argument';}
    const dagSummary=n.local_pipeline?.dependency_dag&&!n.local_pipeline_expanded;
    const maxWidth=dagSummary?292:n.kind==='interface'?126:184,font=n.kind==='interface'?15:16;
    const lines=wrap(title,n.kind==='composite'?maxWidth-20:maxWidth,font),captions=caption?wrap(caption,maxWidth,13):[];
    if(dagSummary&&n.local_pipeline_binding_rows){
      for(const row of n.local_pipeline_binding_rows.rows)captions.push(...wrap(row.text,maxWidth,13));
    }else if(dagSummary){
      const labels=new Map(n.local_pipeline.operations.map(o=>[o.node,o.label]));
      for(const step of n.local_pipeline.dependency_dag.nodes){
        const inputs=step.inputs.slice().sort((a,b)=>String(a.target_port).localeCompare(String(b.target_port))||a.edge.localeCompare(b.edge));
        const ref=input=>input.reference+(input.source_port==='out'?'':'['+input.source_port+']');
        captions.push(...wrap(step.reference+' '+labels.get(step.node)+(inputs.length?' ← '+inputs.map(i=>i.target_port+'='+ref(i)).join('; '):''),maxWidth,13));
      }
      for(const r of n.local_pipeline.source_reads||[])for(const e of r.edges){
        const ref=n.local_pipeline.dependency_dag.nodes.find(s=>s.node===e.target)?.reference;
        captions.push(...wrap(`Reads ${r.expression} → ${ref}[${e.target_port}]`,maxWidth,13));
      }
      for(const b of n.local_pipeline.external_inputs||[])captions.push(...wrap(`Input ${b.label} → ${b.reference}[${b.target_port}]`,maxWidth,13));
    }
    n.paper={title,caption,lines,captions,font,fill,stroke,category:cat,unknown_count:opaque,symbol,
      w:symbol?48:dagSummary?320:n.kind==='interface'?154:212,h:symbol?48:Math.max(n.kind==='interface'?44:64,22+lines.length*20+captions.length*16)};
    if(dagSummary&&n.local_pipeline_binding_rows)n.paper.read_binding_rows=n.local_pipeline_binding_rows;
    if(sourceHeading)n.paper.source_heading=sourceHeading;
    if(n.local_pipeline_call_boundary&&!n.local_pipeline_expanded){
      const boundary=n.local_pipeline_call_boundary;
      const lines=wrap(boundary.printed_title,212,16),captions=boundary.printed_captions.flatMap(s=>wrap(s,212,13));
      n.paper={...n.paper,title:boundary.printed_title,caption:boundary.printed_captions.join(' · '),lines,captions,
        w:240,h:22+lines.length*20+captions.length*16,call_boundary:boundary};
      delete n.paper.read_binding_rows;delete n.paper.source_heading;
    }
    if(n.invocation_binding){
      const compact=wrap(title,176,13);n.paper={...n.paper,lines:compact,captions:[],font:13,
        w:Math.max(110,Math.ceil(Math.max(...compact.map(s=>width(s,13)))+28)),h:Math.max(40,16+compact.length*20),fill:'#fff8e9',stroke:'#a18b5e'};
    }
    if(n.content_inventory&&!n.identity_display&&!n.role_annotations?.length&&!dagSummary){
      const summary=inventoryCaption(n.content_inventory,opaque,captions.length,maxWidth);
      if(summary){n.paper.caption=summary.text;n.paper.captions=summary.lines;n.paper.caption_scope='unit-inventory';n.paper.layout_caption_rows=captions.length;
        n.paper.inventory_summary={shown_terms:summary.shown_terms,omitted_kinds:summary.omitted_kinds};}
    }
    if(n.module_arguments?.length){
      const extra=n.module_arguments.flatMap(r=>wrap(r.label,maxWidth,13));
      n.paper.captions.push(...extra);n.paper.caption+=(n.paper.caption?' · ':'')+n.module_arguments.map(r=>r.label).join(' · ');
      if(n.paper.layout_caption_rows!=null)n.paper.layout_caption_rows+=extra.length;
      n.paper.h=Math.max(n.paper.h,22+n.paper.lines.length*20+n.paper.captions.length*16);
    }
    if(n.transform_configurations?.length){
      const extra=n.transform_configurations.flatMap(r=>wrap(r.display_text,maxWidth,13));
      n.paper.captions.push(...extra);
      n.paper.caption+=(n.paper.caption?' · ':'')+n.transform_configurations.map(r=>r.display_text).join(' · ');
      if(n.paper.layout_caption_rows!=null)n.paper.layout_caption_rows+=extra.length;
      n.paper.h=Math.max(n.paper.h,22+n.paper.lines.length*20+n.paper.captions.length*16);
    }
    return n.paper;
  }
  function build(ir){
    const plan=A.build(ir);
    // A large residual enclosure can hide an entire hybrid network behind one
    // label. Keep its named source stages on the main frontier; the finding,
    // operand identity and actual skip edge remain, without an extra frame.
    for(const n of plan.nodes.slice())if(n.presentation_only&&n.semantic_type.startsWith('residual')&&plan.nodes.some(c=>c.parent===n.id&&c.kind==='composite'&&!c.presentation_only&&c.module_path)){
      for(const child of plan.nodes)if(child.parent===n.id)child.parent=n.parent;
      plan.nodes=plan.nodes.filter(c=>c.id!==n.id);
      const f=plan.findings.find(f=>f.id===n.finding);if(f){f.presentation='annotation';f.presentation_reason='Publication keeps named source stages visible; residual operand and skip edge are retained.';}
    }
    const idx=index(plan),by=idx.nodes,children=idx.children,pol=policy(ir),findings=plan.findings;
    function owner(id,parent){while(id!=null&&by.get(id)?.parent!==parent)id=by.get(id)?.parent;return id;}
    const original=new Set(ir.nodes.map(n=>n.id));
    function region(parent,members,type,label,summary,roles,proof){
      const id=unique('paper:'+type+':'+hash(parent+'|'+members.join('|')),by),closure=new Set(members.flatMap(id=>[id,...descendants(id,children)]));
      // Whole-value output aliases belong to the region producing them. Keep
      // their original slots and source records rather than exposing false
      // boundary inputs when a focused panel is later expanded.
      let changed=true;while(changed){changed=false;for(const child of children.get(parent)||[]){
        const binding=pol.bindings.get(child);
        if(!closure.has(child)&&by.get(child).kind==='value-alias'&&binding&&closure.has(binding.source)){
          members.push(child);closure.add(child);changed=true;
        }
      }}
      const canonical=[...closure].filter(id=>original.has(id)),inside=new Set(canonical);
      const group={id,kind:'composite',label,parent,source:members.flatMap(id=>by.get(id).source||[]).slice(0,32),source_parent:null,runtime_evidence:[],
        semantic_type:type,presentation_only:true,granularity:'composite',evidence_status:'static-only',canonical_members:canonical,
        boundary_ports:ir.edges.filter(e=>inside.has(e.source)!==inside.has(e.target)).map(copy),region_summary:summary,finding:id};
      findings.push({id,rule:type,label,members:members.slice(),roles,proof:proof||['Fork/join boundaries and separate paths in the extracted dependency graph. No execution concurrency or model-family semantics is inferred.'],evidence_scope:'presentation',presentation:'group',rule_version:'publication/2'});
      plan.nodes.push(group);by.set(id,group);children.set(id,members);
      for(const member of members)by.get(member).parent=id;
      children.set(parent,[...(children.get(parent)||[]).filter(id=>!closure.has(id)),id]);
      return id;
    }
    const scopes=plan.nodes.filter(n=>n.kind==='composite').map(n=>n.id);
    const regionPlans=[];
    for(const parent of scopes){
      if(['loop-template','iteration-region','conditional-region'].includes(by.get(parent)?.semantic_type))continue;
      const selected=Regions.candidates({nodes:plan.nodes,children,parent,edges:ir.edges,relations:plan.relation_graph?.relations||[],
        resolve:(id,port)=>value(id,port,pol.bindings).id,
        eligible:id=>!pol.metadata.has(id)&&!pol.bindings.has(id)&&!['interface','parameter'].includes(by.get(id).kind)});
      if(!selected?.proposals.length)continue;
      // Existing depth bands remain useful for interwoven computation. Replace
      // them early when a condition, state, selection or effect boundary needs
      // protection that a depth rank alone cannot provide. Unknown-only scopes
      // keep that established topology fallback and their explicit detail goals.
      if(!selected.proposals.some(c=>c.kind==='conditional-collection')&&!selected.protected.some(p=>p.reasons.some(r=>['state-interface','selection-interface','control','condition','iteration','effects'].includes(r))))continue;
      for(const candidate of selected.proposals){
        const conditional=candidate.kind==='conditional-collection',label=conditional?'Conditional alternatives':'Computation region';
        candidate.id=region(parent,candidate.members.slice(),candidate.kind,label,
          conditional?'Condition-bound alternatives · exact interfaces':candidate.members.length+' connected units · exact interfaces',
          {units:candidate.members.slice(),boundary_selection:candidate},
          ['Presentation boundary selected from local condition, state, effect and dependency facts. All canonical cuts and escaping results remain; no family or purity claim.']);
        const group=by.get(candidate.id),inside=new Set(group.canonical_members);
        candidate.canonical_members=group.canonical_members.slice();candidate.boundary_edges=group.boundary_ports.map(e=>e.id);
        candidate.input_edges=group.boundary_ports.filter(e=>inside.has(e.target)).map(e=>e.id);
        candidate.output_edges=group.boundary_ports.filter(e=>inside.has(e.source)).map(e=>e.id);
        candidate.escaping_results=[...new Set(group.boundary_ports.filter(e=>inside.has(e.source)).map(e=>JSON.stringify([e.source,e.source_port])))].map(s=>JSON.parse(s));
        candidate.internal_edges=ir.edges.filter(e=>inside.has(e.source)&&inside.has(e.target)).length;
        candidate.cut_edges=group.boundary_ports.length;candidate.cohesion=candidate.internal_edges/Math.max(1,candidate.internal_edges+candidate.cut_edges);
        group.boundary_selection=candidate;
        group.content_inventory=inventory(candidate.members,{nodes:by,children});
      }
      regionPlans.push(selected);
    }
    const protectedScopes=new Set(regionPlans.map(p=>p.parent));
    // Find inner diamonds first, then revisit the enclosing scope so nested
    // diamonds can compose. Input interfaces stay local during this analysis.
    // All existing module boundaries, canonical cuts and unknowns are retained.
    for(const parent of scopes)for(let iteration=0;iteration<32;iteration++){
      const kids=(children.get(parent)||[]).filter(id=>!pol.metadata.has(id)&&!pol.bindings.has(id)&&by.get(id).kind!=='parameter');
      // The general policy contracts local interfaces; restore them as real
      // fork/join anchors while considering this particular source scope.
      for(const id of children.get(parent)||[])if(by.get(id).kind==='interface'&&!kids.includes(id))kids.push(id);
      const active=new Set(kids),bindings=new Map(pol.bindings),adj=new Map(kids.map(id=>[id,new Set()])),barriers=new Set(),externalBoundary=new Set();
      for(const id of kids)if(by.get(id).kind==='interface')bindings.delete(id);
      for(const e of ir.edges){
        const resolved=value(e.source,e.source_port,bindings).id,a=owner(resolved,parent),b=owner(e.target,parent);
        if(e.condition||['control','state-write'].includes(e.kind)){if(active.has(a))barriers.add(a);if(active.has(b))barriers.add(b);}
        if(flow(e)&&!e.condition&&active.has(a)&&active.has(b)&&a!==b)adj.get(a).add(b);
        if(flow(e)&&!pol.metadata.has(resolved)&&by.get(resolved)?.kind!=='parameter'){
          if(a==null&&active.has(b))externalBoundary.add(b);
          if(b==null&&active.has(a))externalBoundary.add(a);
        }
      }
      const forbidden=id=>barriers.has(id)||[id,...descendants(id,children)].some(child=>{const n=by.get(child);return n.mutable||n.kind==='control'||n.condition||['conditional-region','loop-template'].includes(n.semantic_type);});
      const candidates=B.discover(kids,adj).filter(c=>![c.entry,c.exit,...c.members].some(forbidden)&&!c.members.some(id=>externalBoundary.has(id)));
      const candidate=candidates[0];if(!candidate)break;
      const paths=candidate.branches.map((members,i)=>region(parent,members.slice(),'branch-path','Path '+(i+1),members.slice(0,3).map(id=>by.get(id).label).join(' → ')+(members.length>3?' → …':''),{entry:candidate.entry,exit:candidate.exit,path_index:i}));
      // A wide fanout must not force all paths into a single unprintable row.
      // Build a reversible tree of at most three independent path summaries
      // per panel. The hierarchy is presentation only, with exact cuts at
      // every level; it adds no dependency between adjacent summaries.
      let panels=paths.map((id,i)=>({id,first:i+1,last:i+1,paths:[id]}));
      while(panels.length>3){
        const next=[],size=Math.min(3,Math.ceil(panels.length/Math.ceil(panels.length/3)));
        for(let i=0;i<panels.length;i+=size){
          const chunk=panels.slice(i,i+size);if(chunk.length===1){next.push(chunk[0]);continue;}
          const first=chunk[0].first,last=chunk.at(-1).last,members=chunk.flatMap(p=>p.paths);
          const id=region(parent,chunk.map(p=>p.id),'branch-panel',`Paths ${first}–${last}`,members.length+' separate dependency paths',
            {entry:candidate.entry,exit:candidate.exit,paths:members,path_range:[first,last],execution_parallelism:'not-asserted'});
          next.push({id,first,last,paths:members});
        }
        panels=next;
      }
      region(parent,panels.map(p=>p.id),'branch-region','Branches × '+paths.length,paths.length+' dependency paths',
        {entry:candidate.entry,exit:candidate.exit,paths,execution_parallelism:'not-asserted'});
    }
    // Interwoven DAGs have shared intermediate values and cross-links, so
    // they cannot be called separate branch paths. Partition broad frontiers
    // by longest dependency depth instead. Exact cross-band and skip edges
    // remain in the canonical cut; no serial algorithm or concurrency claim.
    for(const parent of scopes){
      // A loop body is a source template with carried values across its
      // boundary, not a closed feed-forward scope for depth grouping.
      if(protectedScopes.has(parent)||['loop-template','iteration-region'].includes(by.get(parent).semantic_type))continue;
      const core=(children.get(parent)||[]).filter(id=>!pol.metadata.has(id)&&!pol.bindings.has(id)&&!['interface','parameter'].includes(by.get(id).kind));
      if(core.length<9)continue;
      const active=new Set(core),adj=new Map(core.map(id=>[id,new Set()])),degree=new Map(core.map(id=>[id,0])),depth=new Map(core.map(id=>[id,0]));
      for(const edge of ir.edges){
        const a=owner(value(edge.source,edge.source_port,pol.bindings).id,parent),b=owner(edge.target,parent);
        if(active.has(a)&&active.has(b)&&a!==b&&!adj.get(a).has(b)){adj.get(a).add(b);degree.set(b,degree.get(b)+1);}
      }
      const ready=core.filter(id=>!degree.get(id));
      for(let at=0;at<ready.length;at++)for(const to of adj.get(ready[at])){
        depth.set(to,Math.max(depth.get(to),depth.get(ready[at])+1));degree.set(to,degree.get(to)-1);if(!degree.get(to))ready.push(to);
      }
      if(ready.length!==core.length)continue; // Feedback keeps the SCC view.
      const bands=new Map();for(const id of core){const rank=depth.get(id);if(!bands.has(rank))bands.set(rank,[]);bands.get(rank).push(id);}
      if([...bands.values()].filter(ids=>ids.length>=3).length<2)continue;
      const proof=['Presentation grouping at the same longest dependency depth in an acyclic scope. All canonical cross-links, values and operands remain; no independent-path or model-family claim.'];
      for(const [rank,units]of [...bands].sort((a,b)=>a[0]-b[0])){
        if(units.length<2)continue;
        let panels=units.map((id,i)=>({id,first:i+1,last:i+1,units:[id]}));
        while(panels.length>3){
          const next=[];for(let i=0;i<panels.length;i+=3){
            const chunk=panels.slice(i,i+3);
            const first=chunk[0].first,last=chunk.at(-1).last,members=chunk.flatMap(p=>p.units);
            const id=region(parent,chunk.map(p=>p.id),'dependency-panel',first===last?`Unit ${first}`:`Units ${first}–${last}`,members.length+' units · dependency depth '+rank,
              {dependency_depth:rank,units:members,execution_parallelism:'not-asserted'},proof);
            next.push({id,first,last,units:members});
          }panels=next;
        }
        region(parent,panels.map(p=>p.id),'dependency-band','Dependency band '+(rank+1),units.length+' units · dependency depth '+rank,
          {dependency_depth:rank,units:units.slice(),execution_parallelism:'not-asserted'},proof);
      }
    }
    const queue=plan.nodes.filter(n=>n.kind==='composite').map(n=>n.id);
    for(let at=0;at<queue.length;at++){
      const parent=queue[at],core=(children.get(parent)||[]).filter(id=>{const n=by.get(id);return !pol.metadata.has(id)&&!pol.bindings.has(id)&&!['interface','parameter'].includes(n.kind);});
      if(protectedScopes.has(parent)||core.length<=10)continue;
      const coreSet=new Set(core),adj=new Map(core.map(id=>[id,new Set()]));
      for(const e of ir.edges)if(flow(e)||e.kind==='control'){
        const a=owner(value(e.source,e.source_port,pol.bindings).id,parent),b=owner(e.target,parent);
        if(coreSet.has(a)&&coreSet.has(b)&&a!==b)adj.get(a).add(b);
      }
      const scc=L.components(core,adj),unit=new Map();scc.forEach((ids,i)=>ids.forEach(id=>unit.set(id,i)));
      const next=scc.map(()=>new Set()),degree=scc.map(()=>0),order=new Map(core.map((id,i)=>[id,i]));
      for(const [a,targets]of adj)for(const b of targets){const x=unit.get(a),y=unit.get(b);if(x!==y&&!next[x].has(y)){next[x].add(y);degree[y]++;}}
      const ready=scc.map((_,i)=>i).filter(i=>!degree[i]),sorted=[];
      while(ready.length){ready.sort((a,b)=>Math.min(...scc[a].map(id=>order.get(id)))-Math.min(...scc[b].map(id=>order.get(id))));const i=ready.shift();sorted.push(scc[i]);for(const j of next[i])if(!--degree[j])ready.push(j);}
      // Large SCCs can be split for presentation, retaining all feedback edges.
      // Acyclic units are contiguous in topological order, so their partition
      // cannot manufacture a cycle. Regions never assert a serial algorithm.
      for(let j=sorted.length-1;j>=0;j--)if(sorted[j].length>10){const ids=sorted[j],size=Math.ceil(ids.length/7);sorted.splice(j,1,...Array.from({length:Math.ceil(ids.length/size)},(_,i)=>ids.slice(i*size,(i+1)*size)));}
      const chunk=Math.max(2,Math.ceil(sorted.length/7));
      for(let i=0;i<sorted.length;i+=chunk){
        const members=sorted.slice(i,i+chunk).flat();if(members.length<2)continue;
        const id=unique('paper:region:'+hash(parent+'|'+members.join('|')),by),inside=members.flatMap(id=>[id,...descendants(id,children)]),canonical=inside.filter(id=>ir.nodes.some(n=>n.id===id));
        const names=members.slice(0,3).map(id=>by.get(id).label),label='Stage '+String(Math.floor(i/chunk)+1).padStart(2,'0');
        const sources=members.flatMap(id=>by.get(id).source||[]).slice(0,32);
        const memberSet=new Set(canonical);
        const group={id,kind:'composite',label,parent,source:sources,source_parent:null,runtime_evidence:[],semantic_type:'structural-region',presentation_only:true,granularity:'composite',evidence_status:'static-only',canonical_members:canonical,
          boundary_ports:ir.edges.filter(e=>memberSet.has(e.source)!==memberSet.has(e.target)).map(e=>copy(e)),region_summary:members.length+' units · '+names.join(' · ')+(members.length>3?' · +'+(members.length-3):''),finding:id};
        findings.push({id,rule:'structural-region',label,members,roles:{},proof:['Presentation partition of contiguous dependency-order units. No algorithm or model-family semantics is inferred.'],evidence_scope:'presentation',presentation:'group',rule_version:'publication/1'});
        plan.nodes.push(group);by.set(id,group);children.set(id,members);queue.push(id);
        for(const member of members)by.get(member).parent=id;
        children.set(parent,[...(children.get(parent)||[]).filter(id=>!members.includes(id)),id]);
      }
    }
    for(const r of plan.relation_graph?.relations||[])if(r.type==='state-interface'&&r.properties.interface_kind==='single-step'){
      const n=by.get(r.node);if(n)n.state_interface={relation:r.id,...copy(r.properties)};
    }
    const final=index(plan);
    for(const n of plan.nodes)if(['dependency-band','dependency-panel'].includes(n.semantic_type)){
      const f=findings.find(f=>f.id===n.finding);
      if(f?.roles.units)n.content_inventory=inventory(f.roles.units,final);
    }
    for(const n of plan.nodes)decorate(n,final);
    plan.publication={schema:'archcanvas-publication-plan/1',structural_regions:plan.nodes.filter(n=>n.semantic_type==='structural-region').length,boundary_plans:regionPlans};
    return plan;
  }
  function plan(ir){if(!plans.has(ir))plans.set(ir,build(ir));return plans.get(ir);}
  function relationPanel(ir,base,relationId){
    let relation=base.relation_graph?.relations.find(r=>r.id===relationId);
    if(!relation&&relationId.startsWith('node:')){const node=ir.nodes.find(n=>n.id===relationId.slice(5));if(node)relation={id:relationId,type:'computation',members:[node.id],edges:ir.edges.filter(e=>e.source===node.id||e.target===node.id).map(e=>e.id),evidence_scope:node.evidence_status==='runtime-only'?'observed-run':'source-local'};}
    if(!relation)return null;
    const canonical=new Map(ir.nodes.map(n=>[n.id,n])),members=new Set(relation.members),edges=new Map(ir.edges.map(e=>[e.id,e]));
    // A cross-branch relationship must retain the original control enclosure.
    // Reparenting its calls directly into a detail panel would imply that both
    // alternatives execute without a condition.
    for(const id of [...members]){let at=canonical.get(id)?.parent;while(at){const n=canonical.get(at);
      if(n?.condition?.branch){members.add(at);members.add(n.condition.branch);}at=n?.parent;
    }}
    // Include the binding path only when both its producer and consumer are
    // internal roles. External provenance belongs on exact boundary ports;
    // pulling its entire chain into this panel obscures the selected relation.
    for(const b of relation.bindings||[])if(members.has(b.producer)&&members.has(b.target)){
      members.add(b.source);for(const id of b.via){const e=edges.get(id);if(e){members.add(e.source);members.add(e.target);}}
    }
    if(relation.type==='conditional-join')for(const b of relation.bindings){
      let at=b.source;while(at){const n=canonical.get(at);if(n?.kind==='composite'&&n.condition?.branch===b.condition?.branch&&n.condition?.outcome===b.condition?.outcome){members.add(at);break;}at=n?.parent;}
    }
    // A conditional container retains its governed body; selecting it cannot
    // turn conditional calls into unconditional peer computations.
    const children=new Map();for(const n of ir.nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
    for(const id of [...members])if(canonical.get(id)?.kind==='composite')for(const child of descendants(id,children))members.add(child);
    const used=new Set(base.nodes.map(n=>n.id)),id=unique((relation.evidence_scope==='observed-run'?'runtime:paper:relation:':'paper:relation:')+hash(relationId),used),nodes=base.nodes.map(copy);
    const cuts=ir.edges.filter(e=>members.has(e.source)!==members.has(e.target));
    for(const n of nodes)if(members.has(n.id))n.parent=members.has(n.parent)?n.parent:id;
    const frame={id,parent:null,kind:'composite',semantic_type:'relation-panel',label:relation.type.replaceAll('-',' '),source:[],runtime_evidence:[],
      presentation_only:true,finding:id,canonical_members:[...members],boundary_ports:cuts.map(copy),evidence_status:relation.evidence_scope==='observed-run'?'runtime-only':'static-only',
      relation:relationId,region_summary:'Local relationship · exact boundary ports'};
    nodes.push(frame);
    const p={...base,nodes,findings:[...base.findings,{id,rule:'relation-panel',members:[...members],presentation:'group',evidence_scope:'presentation',proof:['One local relationship; external canonical cuts remain explicit.']}]},idx=index(p);
    for(const n of nodes.filter(n=>members.has(n.id)||n.id===id))decorate(n,idx);
    const required=relation.properties?.required_nodes,minimal=new Set([id]);
    if(required)for(const node of required){let at=idx.nodes.get(node)?.parent;while(at&&at!==id){minimal.add(at);at=idx.nodes.get(at)?.parent;}}
    return {plan:p,id,open:[id,...nodes.filter(n=>members.has(n.id)&&n.kind==='composite').map(n=>n.id)],
      minimal_open:required?[...minimal]:null};
  }
  const wireLabel=edge=>edge.bundle_members.length+(edge.bundle_values===1?' uses':edge.bundle_values===edge.bundle_members.length?' values':' links');
  function presentEdges(edges,idx){
    const groups=new Map(),used=new Set(edges.map(e=>e.id));
    for(const edge of edges){
      const a=idx.nodes.get(edge.source),b=idx.nodes.get(edge.target);
      // Closed presentation panels and repeated uses of one boundary result
      // may use ribbons. Each operand and canonical edge remains a member.
      // A folded serial sequence also owns the repeated uses of a context
      // value. Retain every invocation/operand instead of drawing N copies
      // across the same closed boundary. Conditional/state edges stay explicit.
      const sharedOutput=b?.boundary_value&&b.boundary_uses?.length>1;
      if(edge.condition||edge.semantic_bindings?.some(b=>['initial-state','final-state','final-state-pair','sequence-input'].includes(b.role))||!flow(edge)||!sharedOutput&&![a,b].some(n=>['computation-region','conditional-collection','branch-panel','branch-region','dependency-band','dependency-panel','serial-repeat','serial-remainder'].includes(n?.semantic_type)))continue;
      const sequence=edge.semantic_bindings?.some(b=>b.role==='sequence-output');
      const key=JSON.stringify([edge.source,edge.target,edge.kind,edge.evidence,sequence?[edge.resolved_source,edge.source_port,'sequence-output']:null]);
      if(!groups.has(key))groups.set(key,[]);groups.get(key).push(edge);
    }
    const ribbons=new Map();
    for(const [key,members]of groups)if(members.length>1){
      const id=unique('paper:wire:'+hash(key+'|'+members.map(e=>e.id).join('|')),used);used.add(id);
      const values=new Set(members.map(e=>JSON.stringify([e.resolved_source,e.source_port]))).size,first=members[0];
      const ribbon={id,source:first.source,target:first.target,kind:'data-bundle',evidence:first.evidence,
        source_port:'bundle',target_port:'bundle',resolved_source:id,
        originals:members.flatMap(e=>e.originals),bundle_members:members.map(copy),
        bundle_values:values,sequence_output:members.every(m=>m.semantic_bindings?.some(b=>b.role==='sequence-output')),tensor_equality:'not-asserted'};
      for(const member of members)ribbons.set(member.id,ribbon);
    }
    const emitted=new Set();return edges.flatMap(edge=>{const ribbon=ribbons.get(edge.id);if(!ribbon)return [edge];if(emitted.has(ribbon.id))return [];emitted.add(ribbon.id);return [ribbon];});
  }
  function focusPlan(ir,base,focus,dimensionPaths=false,directOperands=new Set()){
    const p={...base,nodes:base.nodes.slice(),findings:base.findings.slice()},idx=index(p),used=new Set(idx.nodes.keys()),inside=new Set([focus,...descendants(focus,idx.children)]),boundaryReps=new Map(),boundary=[],inputValues=new Map(),outputValues=new Map(),rels=relations(ir);
    const {metadata,bindings}=policy(ir,focus,inside,dimensionPaths,directOperands);
    for(const e of ir.edges){const input=!inside.has(e.source)&&inside.has(e.target),output=inside.has(e.source)&&!inside.has(e.target);if(!input&&!output)continue;
      // An interface inside a closed child is not a panel-level terminal.
      // Reusing it leaves an edge pointing at a node with no visible geometry.
      const local=idx.nodes.get(input?e.target:e.source),external=idx.nodes.get(input?e.source:e.target),existing=local?.kind==='interface'&&local.parent===focus&&local.role===(input?'input':'output');
      if(metadata.has(e.source)||metadata.has(e.target)){
        boundary.push({...copy(e),direction:input?'input':'output',port_node:local.id,presentation:'attached-metadata'});continue;
      }
      // Match the compact projection's resource policy. These cuts are
      // attached to the consumer, never orphan synthetic data inputs.
      if(input&&!directOperands.has(e.target)&&external?.kind==='parameter'&&!(rels.ins.get(external.id)||[]).length&&(rels.uses.get(external.id)||[]).every(edge=>['data','parameter-read'].includes(edge.kind))){
        boundary.push({...copy(e),direction:'input',port_node:local.id,presentation:'attached-resource'});continue;
      }
      // Interface binding and data use can read the exact same value. The
      // value identity is shared; every original cut and use remains distinct.
      const resolved=value(e.source,e.source_port,bindings);
      const valueKey=input?JSON.stringify([e.source,e.source_port,flow(e)?'value':e.kind]):
        flow(e)&&!e.condition?JSON.stringify([resolved.id,resolved.port,e.kind,e.evidence]):null;
      const shared=!existing&&(input?inputValues.get(valueKey):valueKey&&outputValues.get(valueKey));
      let id=existing?local.id:shared||unique('paper:port:'+hash(focus+'|'+e.id),used);used.add(id);
      if(!existing&&!shared){const localBinding=input&&local?.kind==='value-alias'&&!local.operator;
        const n={id,parent:focus,kind:'interface',role:input?'input':'output',label:localBinding?local.label:!input&&external?.operator==='structure'?'slot '+e.target_port:external?.label||e.source_port,source:(localBinding?local.source:external?.source)||local?.source||[],evidence_status:external?.evidence_status||'static-only',runtime_evidence:[],boundary_edge:e.id,canonical_endpoint:input?e.source:e.target};
        if(!input&&valueKey)n.boundary_value={source:resolved.id,source_port:resolved.port,identity_scope:'extracted-graph',tensor_equality:'not-asserted'};
        if(!input)n.boundary_uses=[];
        decorate(n,index(p));p.nodes.push(n);
      }
      if(input&&!existing)inputValues.set(valueKey,id);
      if(!input&&!existing){
        const port=p.nodes.find(n=>n.id===id);port.boundary_uses.push(copy(e));
        if(valueKey)outputValues.set(valueKey,id);
      }
      boundaryReps.set(e.id,input?{source:id}:{target:id});boundary.push({...copy(e),direction:input?'input':'output',port_node:id});
    }
    // One extracted result can have several external consumers. Represent that
    // result once; all uses retain their targets and slots in the port and cuts.
    // Conditions, state edges, evidence and producer output slots never mix.
    for(const port of p.nodes.filter(n=>n.parent===focus&&n.boundary_uses?.length>1)){
      const source=idx.nodes.get(port.boundary_uses[0].source),origin=idx.nodes.get(port.boundary_value.source);
      port.label=source?.label||origin?.label||'Output';
      if(port.boundary_value.source_port!=='out')port.label+=' ['+port.boundary_value.source_port+']';
      port.boundary_caption=port.boundary_uses.length+' external uses';
      port.source=source?.source||origin?.source||port.source;
      delete port.canonical_endpoint;
      decorate(port,index(p));
    }
    // Repeated external operation names otherwise look like unrelated outputs.
    // A panel-local target reference and its exact operand distinguish
    // unshared terminals. Shared terminals retain every use in their cut list.
    const outputNames=new Map();
    for(const n of p.nodes.filter(n=>n.parent===focus&&n.boundary_edge&&n.role==='output'&&n.boundary_uses?.length<=1)){
      if(!outputNames.has(n.label))outputNames.set(n.label,[]);outputNames.get(n.label).push(n);
    }
    for(const ports of outputNames.values())if(ports.length>1){
      const targets=[...new Set(ports.map(n=>n.canonical_endpoint))];
      for(const port of ports){
        const cut=boundary.find(e=>e.id===port.boundary_edge);
        port.boundary_base_label=port.label;
        port.label+=' ['+(targets.indexOf(port.canonical_endpoint)+1)+']';
        port.boundary_caption='to '+cut.target_port;
        decorate(port,index(p));
      }
    }
    for(const direction of ['input','output']){
      const ports=p.nodes.filter(n=>n.parent===focus&&n.boundary_edge&&n.role===direction);
      if(ports.length<=6)continue;
      const id=unique('paper:ports:'+hash(focus+'|'+direction),used);used.add(id);
      const ids=new Set(ports.map(n=>n.id)),cuts=boundary.filter(e=>ids.has(e.port_node));
      const group={id,parent:focus,kind:'composite',label:direction==='input'?'External inputs':'External outputs',semantic_type:'boundary-interface-group',presentation_only:true,
        source:[],runtime_evidence:[],canonical_members:[],boundary_ports:cuts.map(e=>copy(e)),boundary_members:ports.map(n=>n.id),finding:id,evidence_status:'static-only'};
      // Bundle only the presentation of a large boundary. Every value keeps
      // its own synthetic node, canonical cut record and physical terminal.
      for(const port of ports)port.parent=id;
      const bindings=policy(ir).bindings;
      const values=new Set(cuts.map(e=>{const source=value(e.source,e.source_port,bindings);return JSON.stringify([source.id,source.port,flow(e)?'value':e.kind]);})).size;
      group.boundary_value_count=values;group.boundary_use_count=cuts.length;
      group.region_summary=values===cuts.length?values+' distinct values':values+' values · '+cuts.length+' uses';
      p.nodes.push(group);decorate(group,index(p));
      p.findings.push({id,rule:'boundary-interface-group',presentation:'group',evidence_scope:'presentation',members:ports.map(n=>n.id),proof:['Boundary values are grouped by direction only; all canonical edges and individual ports remain in the document.']});
    }
    return {plan:p,inside,boundaryReps,boundary};
  }
  const inlinePlans=new WeakMap();
  function inlinePlan(ir,base){if(!inlinePlans.has(ir)){const engine=root.SemanticSequenceFrontier||(typeof require==='function'?require('./sequence-frontier.js'):null);inlinePlans.set(ir,engine.build(ir,base));}return inlinePlans.get(ir);}
  function project(ir,state,E){
    const canvas=state.paperMedium==='canvas';
    if(canvas&&['stages','roles'].includes(state.paperGranularity)&&state.paperCompact==null)state={...state,paperCompact:true};
    const mode=state.mode||'source',originalPlan=plan(ir),originalIdx=index(originalPlan);
    const relationNode=state.paperRelation?.startsWith('node:')?state.paperRelation.slice(5):originalPlan.relation_graph?.relations.find(r=>r.id===state.paperRelation)?.node;
    const observed=id=>{while(id){if(id==='runtime-observations'||id.startsWith('runtime:'))return true;id=originalIdx.nodes.get(id)?.parent;}return false;};
    const local=relationNode&&(mode==='merged'||(mode==='runtime')===observed(relationNode))?relationPanel(ir,originalPlan,state.paperRelation):null;
    const inline=canvas&&state.paperSequenceView!=='summary'&&!local;
    // Cache the expensive source analysis, but decorate a private working
    // plan. Native receipts may freeze records reachable from a prior cut;
    // another granularity must neither mutate that cut nor inherit its glyphs.
    const base=copy(inline?inlinePlan(ir,originalPlan):local?.plan||originalPlan),baseIdx=index(base);
    if(inline){const all=index(base);for(const n of base.nodes)decorate(n,all);}
    if(mode==='runtime'&&!baseIdx.nodes.has('runtime-observations'))throw Error('当前 IR 没有 CPU 执行轨迹');
    const runtimeNode=id=>{while(id){if(id==='runtime-observations'||id.startsWith('runtime:'))return true;id=baseIdx.nodes.get(id)?.parent;}return false;};
    const allowed=id=>mode==='source'?!runtimeNode(id):mode==='runtime'?runtimeNode(id):true;
    const defaultRoots=mode==='runtime'&&baseIdx.nodes.has('runtime-observations')?['runtime-observations']:baseIdx.children.get(null)||[];
    let focus=local?.id||(baseIdx.nodes.has(state.paperFocus)&&allowed(state.paperFocus)?state.paperFocus:defaultRoots.find(allowed));
    const requestedFocus=focus;
    const requestedSequence=baseIdx.nodes.get(focus)?.repeat_contract,structure=requestedSequence?.structure;
    let structuralGroup=null;
    if(state.paperRepresentative&&structure?.rule_version==='local-structure/1'){
      const requestedGroup=Number.isInteger(state.paperRepresentativeGroup)?state.paperRepresentativeGroup:structure.homogeneous?0:null;
      const group=requestedGroup==null?null:structure.groups[requestedGroup];
      if(group&&group.status==='proved'&&baseIdx.nodes.get(group.representative)?.parent===focus){
        structuralGroup={...copy(group),group:requestedGroup};focus=group.representative;
      }
    }
    const representativeNode=baseIdx.nodes.get(focus),representativeSequence=baseIdx.nodes.get(ir.nodes.find(n=>n.id===focus)?.parent),repeat=representativeSequence?.repeat_contract;
    const representative=repeat?{sequence:representativeSequence.id,instance:focus,index:representativeNode.repeat_index,count:repeat.count,
      homogeneous:repeat.homogeneous,parameter_sharing:repeat.parameter_sharing,
      structural_group:structuralGroup,
      scope:'one concrete instance; other instances remain in the canonical IR; output equality not asserted'}:null;
    const granularity=['overview','modules','stages','semantic','roles','detailed'].includes(state.paperGranularity)?state.paperGranularity:'overview';
    const invocationEngine=canvas&&granularity==='roles'&&state.paperInvocationInputs!==false?
      root.SemanticInvocationInputs||(typeof require==='function'?require('./invocation-inputs.js'):null):null;
    const invocationInputs=invocationEngine?.compile(ir);
    const dimensionPaths=canvas&&granularity==='roles'&&state.paperDimensionPaths!==false?
      {unconsumedBindings:state.paperUnconsumedDimensions!==false}:false;
    const directOperands=new Set(local&&state.paperRelation?.startsWith('node:')?[state.paperRelation.slice(5)]:[]);
    const focused=focusPlan(ir,base,focus,dimensionPaths,directOperands);
    if(structuralGroup)focused.plan.nodes=focused.plan.nodes.map(n=>n.id===focus?{...copy(n),structure_representative:structuralGroup}:n);
    // Coarser certified boundaries still need their local operation summaries.
    // Role exposure and presentation folding are independent choices.
    const summaryFrontier=canvas&&['stages','roles'].includes(granularity);
    const stageEngine=summaryFrontier&&state.paperContractStages!==false?(root.SemanticContractStages||(typeof require==='function'?require('./contract-stages.js'):null)):null;
    const roleEngine=canvas&&granularity==='roles'&&!local?(root.SemanticRoleFrontier||(typeof require==='function'?require('./role-frontier.js'):null)):null;
    const roleFrontier=roleEngine?.compile({plan:focused.plan,focus,details:state.paperRoleDetails,paths:state.paperRolePaths});
    if(roleFrontier){focused.plan=roleFrontier.plan;const all=index(focused.plan);for(const n of focused.plan.nodes)decorate(n,all);}
    const expressionEngine=roleFrontier?(root.SemanticLocalExpressions||(typeof require==='function'?require('./local-expressions.js'):null)):null;
    const expressions=expressionEngine?.compile({plan:focused.plan,focus,details:state.paperExpressionDetails});
    const frontierScopes=new Set(roleFrontier?.owners||[]);
    const pol=policy(ir,focus,focused.inside,dimensionPaths,directOperands),pipelineEngine=summaryFrontier&&state.paperPipelineSummaries!==false?(root.SemanticLocalPipelines||(typeof require==='function'?require('./local-pipelines.js'):null)):null;
    const pipelines=pipelineEngine?.compile({ir,plan:focused.plan,...pol,sourceReads:granularity==='stages'});
    if(pipelines)focused.plan.nodes=focused.plan.nodes.map(n=>pipelines.has(n.id)?{...n,local_pipeline:pipelines.get(n.id),
      ...(granularity==='stages'&&state.paperSourceHeadings===true?
        {local_pipeline_source_heading:true,local_pipeline_source_label:ir.nodes.find(s=>s.id===n.id)?.label}:{}),
      ...(granularity==='stages'&&state.paperReadBindingRows===true&&pipelineEngine.bindingRows(pipelines.get(n.id))?
        {local_pipeline_binding_rows:pipelineEngine.bindingRows(pipelines.get(n.id))}:{})}:n);
    let idx=index(focused.plan);
    if(invocationInputs){focused.plan.nodes=focused.plan.nodes.map(n=>invocationInputs.has(n.id)?{...n,invocation_binding:copy(invocationInputs.get(n.id))}:n);idx=index(focused.plan);for(const n of focused.plan.nodes)decorate(n,idx);}
    const budget=Math.max(4,Math.min(28,Number(state.paperBudget)||({overview:12,modules:20,stages:20,semantic:20,roles:20,detailed:28})[granularity]));
    if(structuralGroup)decorate(idx.nodes.get(focus),idx);
    // Input/output interfaces of a focused panel are real, named boundaries.
    for(const port of focused.boundary)if(!port.presentation)pol.bindings.delete(port.port_node);
    for(const cut of focused.boundary.filter(c=>c.direction==='input'&&!c.presentation)){
      const target=idx.nodes.get(cut.target),incoming=pol.ins.get(cut.target)||[];
      // Contract a proven local alias to this panel's input terminal, never
      // to the hidden external producer. Even a pure pass-through stays wired.
      if(target?.kind==='value-alias'&&!target.operator&&incoming.length===1&&!cut.condition&&flow(cut))
        pol.bindings.set(target.id,{...copy(cut),source:cut.port_node,source_port:target.slot??cut.source_port});
    }
    const exposedResources=new Set(local?originalPlan.relation_graph.relations.find(r=>r.id===state.paperRelation)?.properties.required_nodes?.filter(id=>idx.nodes.get(id)?.kind==='parameter')||[]:[]);
    for(const e of ir.edges)if(directOperands.has(e.target)&&flow(e)&&idx.nodes.get(e.source)?.kind==='parameter')exposedResources.add(e.source);
    const eligible=id=>{const n=idx.nodes.get(id);return allowed(id)&&!pol.bindings.has(id)&&!pol.metadata.has(id)&&(n.kind!=='parameter'||exposedResources.has(id));};
    const options={roots:focus?[focus]:[],bindings:pol.bindings,metadata:pol.metadata,boundaryReps:focused.boundaryReps,presentEdges,exposedResources,
      layout:{contextSourceFacing:state.paperContextSourceFacing===true,semanticLanes:true,inputDocks:canvas&&granularity==='roles'&&state.paperInputDocks===true&&!Object.keys(state.offsets||{}).length,compoundStarts:canvas&&state.paperFlowAlignment==='entries',compoundInputBand:canvas&&state.paperEntryBand===true,branchColumns:canvas&&granularity==='roles'&&state.paperBranchColumns===true,contextLanes:canvas&&granularity==='roles'&&['left','right'].includes(state.paperContextLanes)&&state.paperContextLanes,contextEdges:state.paperContextEdges,alignForks:true,compoundPorts:inline,rankStrategy:state.paperRankStrategy==='consumer'?'consumer':'earliest',foldSerial:state.paperCompact?false:state.foldSerial!==false,nodeSize:n=>({...n.paper,w:n.paper.w,h:n.paper.h}),rankColumns:3,rankColumnsFor:n=>['branch-region','branch-panel','dependency-band','dependency-panel'].includes(n?.semantic_type)?3:null,gapX:28,gapY:state.paperCompact?28:60,foldGapX:36,framePadding:state.paperCompact?16:24,headerClearance:state.paperCompact?12:20,frameHeader:n=>Math.max(state.paperCompact?56:66,24+n.paper.lines.length*20+(n.paper.layout_caption_rows??n.paper.captions.length)*16),maxWidth:700}};
    options.layout.protectFrameTitles=state.paperProtectFrameTitles===true;
    options.layout.sourceForkWidths=canvas&&granularity==='roles'&&state.paperSourceForkWidths!==false;
    if(state.paperCompact)options.layout.nodeSize=n=>{
      const a=n.paper,size={...a,w:a.w,h:a.h};
      if(!a.symbol&&['compute','opaque'].includes(n.kind))size.w=Math.max(180,Math.ceil(Math.max(...a.lines.map(s=>width(s,a.font)),...a.captions.map(s=>width(s,13)))+28));
      return size;
    };
    if(invocationInputs&&state.paperInvocationInputDocks===true&&!Object.keys(state.offsets||{}).length)options.layout.fixedInputIds=new Set(invocationInputs.keys());
    if(base.publication?.boundary_plans?.some(p=>p.parent===focus))options.layout.inputPlacement='consumer';
    if(canvas&&state.paperFrameView!=='source'){
      const engine=root.SemanticFrameOwnership||(typeof require==='function'?require('./frame-ownership.js'):null);
      options.frameOwnership=args=>engine.select({...args,flattenDependencyBands:canvas&&granularity==='roles',flattenSequenceSamples:canvas&&['stages','roles'].includes(granularity)&&state.paperSampleFrame===true,
        roleSources:canvas&&granularity==='roles'&&state.paperRoleSourceFrames===true?roleFrontier?.records||[]:[]});options.decorateFrameOwner=decorate;
    }
    // A proved source path already has a meaningful intermediate expression.
    // Keep it folded unless a role or local relationship requests its detail.
    const contextEdges=ir.edges.filter(e=>flow(e)&&!pol.bindings.has(e.target)&&!pol.metadata.has(e.source)&&!pol.metadata.has(e.target)&&!pol.configurationUses.has(e.id))
      .map(e=>({...e,source:value(e.source,e.source_port,pol.bindings).id}));
    const contextByEdge=new Map(contextEdges.map(e=>[e.id,e]));
    const contextSources=new Set(pipelines?.size?L.contextEntries(idx,new Set(idx.nodes.keys()),contextEdges).map(r=>contextByEdge.get(r.edge).source):[]);
    const summarized=id=>{
      const path=pipelines?.get(id);if(!path||roleFrontier?.open.has(id)||expressions?.open.has(id))return false;
      // A source result can feed several later context/skip entries without
      // exposing its producer's implementation. Only an exact single-result
      // cut map permits this; intermediate context sources remain explicit.
      const result=path.output_bindings?.length&&path.output_bindings.every(b=>b.producer===path.operations.at(-1).node)?path.operations.at(-1).node:null;
      if(path.canonical_members.some(id=>contextSources.has(id)&&id!==result))return false;
      const operations=new Set(path.operations.map(o=>o.node));
      // A later external value is a meaningful context/skip entry. Keep its
      // exact consumer visible rather than reducing it to a helper interface.
      const entries=new Set(path.entry_operations||[path.operations[0].node]);
      return !path.bindings.some(b=>b.kind==='value'&&!operations.has(b.producer)&&!entries.has(b.target)&&
        !path.external_inputs?.some(input=>input.edge===b.edge));
    };
    let open=state.paperAuto===false?(state.open||[]):focus?[focus]:[];
    const coherentChoices=[];
    if(state.paperAuto!==false&&focus){
      // Unwrap a single source wrapper when it improves the actual overview.
      for(let i=0;i<4;i++){
        const visible=[],todo=[focus];for(let j=0;j<todo.length;j++){const id=todo[j];if(!eligible(id))continue;visible.push(id);if(open.includes(id))todo.push(...idx.children.get(id)||[]);}
        const leaves=visible.filter(id=>!open.includes(id)),containers=leaves.filter(id=>(idx.children.get(id)||[]).some(eligible));
        const wrapper=id=>{const n=idx.nodes.get(id);return n.presentation_only&&n.semantic_type.startsWith('residual')&&descendants(id,idx.children).some(child=>idx.nodes.get(child)?.module_path);};
        const sourceWrapper=id=>{const n=idx.nodes.get(id),kids=(idx.children.get(id)||[]).filter(eligible).map(id=>idx.nodes.get(id));return ['source-function','source-module'].includes(n.semantic_type)&&!n.semantic_contracts?.length&&kids.some(n=>n.kind==='composite')&&kids.every(n=>['interface','composite','state','buffer'].includes(n.kind));};
        const cost=id=>idx.nodes.get(id).kind==='interface'?.25:1;
        const used=leaves.reduce((s,id)=>s+cost(id),0);
        const candidate=containers.filter(id=>{if(idx.nodes.get(id).contract_stage)return false;if(roleFrontier?.ownerOf(id)&&!roleFrontier.open.has(id))return false;const n=idx.nodes.get(id),kids=(idx.children.get(id)||[]).filter(eligible);return !['boundary-interface-group','dependency-band','dependency-panel','serial-repeat'].includes(n.semantic_type)&&(containers.length===1||wrapper(id)||sourceWrapper(id))&&used+kids.reduce((s,id)=>s+cost(id),0)-cost(id)<=budget;}).sort((a,b)=>{
          const score=id=>{const n=idx.nodes.get(id);return (n.semantic_type==='sequential'?10:0)+(n.semantic_type==='structural-region'?-10:0)-(idx.children.get(id)||[]).filter(eligible).length;};return score(b)-score(a);
        })[0];
        if(!candidate)break;
        // Keep named modules closed in the overview unless they are merely a
        // wrapper around the main pipeline or contain at most one operation.
        const n=idx.nodes.get(candidate),kids=(idx.children.get(candidate)||[]).filter(eligible);
        if(['boundary-interface-group','dependency-band','dependency-panel','serial-repeat'].includes(n.semantic_type)||n.paper.unknown_count&&!wrapper(candidate)||n.semantic_type!=='sequential'&&!wrapper(candidate)&&!sourceWrapper(candidate)&&kids.length>2)break;
        open=[...open,candidate];
      }
      // Presets select a semantic frontier within the same canonical graph.
      // Repeated instances, control templates and observed executions have
      // their own panels; a denser preset never silently unrolls them.
      if(granularity!=='overview'){
        const frontier=()=>{const leaves=[],todo=[focus];for(let i=0;i<todo.length;i++){const id=todo[i];if(!eligible(id))continue;if(open.includes(id))todo.push(...idx.children.get(id)||[]);else leaves.push(id);}return leaves;};
        const cost=id=>idx.nodes.get(id).kind==='interface'?.25:1;
        const blocked=n=>n.contract_stage||(roleFrontier?.ownerOf(n.id)?!roleFrontier.open.has(n.id):['stages','semantic','roles'].includes(granularity)&&n.semantic_contracts?.length)||(['serial-repeat','repeat-instance','serial-remainder'].includes(n.semantic_type)?!(n.sequence_frontier||n.sequence_sample):['loop-template','iteration-region','conditional-region','observed-variant','boundary-interface-group'].includes(n.semantic_type)||n.id==='runtime-observations'||n.semantic_type==='observed-module-call');
        const scopeOf=id=>{let at=idx.nodes.get(id)?.parent;while(at){if(idx.nodes.get(at)?.sequence_frontier||frontierScopes.has(at))return at;at=idx.nodes.get(at)?.parent;}return null;};
        const usedIn=scope=>{const seen=new Set();return frontier().reduce((total,id)=>{const localScope=scopeOf(id);if(scope)return total+(localScope===scope?cost(id):0);if(localScope){if(seen.has(localScope))return total;seen.add(localScope);return total+1;}return total+cost(id);},0);};
        const localUsed=scope=>{
          if(!roleFrontier)return usedIn(scope);
          const seen=new Set();return frontier().reduce((total,id)=>{
            let localScope=scopeOf(id);if(localScope===scope)return total+cost(id);
            while(localScope&&scopeOf(localScope)!==scope)localScope=scopeOf(localScope);
            if(!localScope||seen.has(localScope))return total;seen.add(localScope);return total+1;
          },0);
        };
        const candidates=frontier().filter(id=>!blocked(idx.nodes.get(id))&&(idx.children.get(id)||[]).some(eligible));
        const queue=candidates.slice(),decided=new Set();
        // Match presentation detail profiles, not values or module identities.
        // Spending a shared budget on just the first of several comparable
        // local regions gives source order an accidental visual meaning.
        // Protected boundaries and explicit detail requests remain independent.
        const profileCache=new Map(),profile=id=>{
          if(profileCache.has(id))return profileCache.get(id);
          const n=idx.nodes.get(id);
          // Arbitrary topological chunks are temporary layout partitions;
          // matching their sizes is not meaningful expression consistency.
          if(!canvas||granularity!=='roles'||state.paperCoherentFrontier===false||!n.presentation_only||n.semantic_type==='structural-region'){profileCache.set(id,null);return null;}
          const members=[n,...descendants(id,idx.children).map(id=>idx.nodes.get(id))];
          const memberIds=new Set(members.map(n=>n.id));
          const protectedNode=n=>['opaque','control'].includes(n.kind)||n.mutable||n.condition||n.identity_display||n.observed_calls||n.runtime_evidence?.length||
            n.evidence_status==='runtime-only'||n.kind==='composite'&&n.semantic_contracts?.length||n.repeat_contract||n.iteration||roleFrontier?.open.has(n.id)||expressions?.open.has(n.id);
          const protectedEdge=ir.edges.some(e=>(memberIds.has(e.source)||memberIds.has(e.target))&&
            (e.condition||e.iteration||e.design_route||!flow(e)&&e.kind!=='parameter-read'));
          const signature=!protectedEdge&&!members.some(protectedNode)?JSON.stringify([n.semantic_type,(idx.children.get(id)||[]).filter(eligible).map(id=>{
              const c=idx.nodes.get(id);return [c.kind,c.semantic_type||null,c.operator||null,c.framework_type||null,(idx.children.get(id)||[]).filter(eligible).length];
            }).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)))]):null;
          profileCache.set(id,signature);return signature;
        };
        const deltaFor=id=>idx.nodes.get(id).sequence_frontier||frontierScopes.has(id)?0:
          (idx.children.get(id)||[]).filter(eligible).reduce((s,id)=>s+cost(id),0)-cost(id);
        for(let i=0;i<queue.length&&i<256;i++){
          const id=queue[i];if(decided.has(id))continue;
          const scope=scopeOf(id),used=localUsed(scope),signature=profile(id);
          const peers=signature?queue.slice(i).filter(other=>!decided.has(other)&&scopeOf(other)===scope&&profile(other)===signature):[id];
          // A proved sequence is one unit in its parent's frontier, with its
          // own bounded local detail budget. Concrete suffixes stay folded.
          const delta=peers.reduce((s,id)=>s+deltaFor(id),0),accepted=used+delta<=budget&&
            !peers.some(id=>frontierScopes.has(id)&&(idx.children.get(id)||[]).filter(eligible).reduce((s,id)=>s+cost(id),0)>budget);
          for(const peer of peers)decided.add(peer);
          if(peers.length>1)coherentChoices.push({nodes:peers,scope,profile:JSON.parse(signature),used,delta,budget,status:accepted?'expanded':'deferred',
            scope_of_claim:'Comparable local presentation detail only; no computational, parameter, value or object equivalence is asserted.'});
          if(!accepted)continue;
          open.push(...peers);
          if(['detailed','stages','semantic','roles'].includes(granularity))for(const peer of peers)queue.push(...(idx.children.get(peer)||[]).filter(id=>!blocked(idx.nodes.get(id))&&(idx.children.get(id)||[]).some(eligible)));
        }
      }
      if(expressions)open=expressionEngine.select(expressions,{plan:focused.plan,focus,open,budget,eligible,budgetScopes:frontierScopes});
    }
    // Choose the logical frontier before lowering a proved helper to its
    // smaller presentation. Otherwise a new summary silently spends its
    // released node budget opening unrelated computations. Role/relation
    // requests still veto a summary; measured adaptive trials may explicitly
    // reinvest the actual space later. Manual open states bypass this step.
    let reservations=null;
    if(pipelines&&state.paperAuto!==false&&!local){
      const planned=open.slice(),selected=[...pipelines.values()].filter(p=>open.includes(p.node)&&summarized(p.node));
      const outer=selected.filter(p=>!selected.some(other=>other!==p&&other.canonical_members.includes(p.node)));
      const reserved=new Set(),rows=outer.map(p=>{
        const members=new Set([p.node,...descendants(p.node,idx.children)]),reservedOpen=planned.filter(id=>members.has(id));
        for(const id of reservedOpen)reserved.add(id);
        return {node:p.node,reserved_open:reservedOpen,canonical_members:p.canonical_members};
      });
      open=open.filter(id=>!reserved.has(id));
      if(rows.length)reservations={rule_version:'frontier-reservations/1',planned_open:planned,selected_open:open.slice(),summaries:rows,
        scope:'Logical detail allocation precedes summary lowering. Released display space does not automatically open unrelated regions; explicit role/relation requests and manual expansion retain their own contracts.'};
    }
    if(local)open=state.paperCompact&&local.minimal_open?local.minimal_open:local.open;
    // Select evidence detail before presentation subregions change container
    // counts. A local summary must not consume an unrelated region's budget.
    const stages=stageEngine?.compile({ir,plan:focused.plan,branchTails:state.paperStageTails!==false,open:new Set(open)});
    if(stages){focused.plan=stages.plan;idx=index(focused.plan);for(const n of focused.plan.nodes)decorate(n,idx);}
    const roleStageEngine=canvas&&granularity==='roles'&&state.paperRoleOperationStages===true?(root.SemanticRoleOperationStages||(typeof require==='function'?require('./role-operation-stages.js'):null)):null;
    const explicitRoles=new Set([...(roleFrontier?.records||[]).filter(r=>(state.paperRoleDetails||[]).includes(r.owner)||(state.paperRolePaths||[]).some(p=>p.node===r.owner&&p.certificate===r.certificate&&JSON.stringify(p.role)===JSON.stringify(r.role_keys))).map(r=>r.node)]);
    const roleStages=roleStageEngine?.compile({ir,plan:focused.plan,open:new Set(open),requested:[...explicitRoles]});
    if(roleStages){focused.plan=roleStages.plan;idx=index(focused.plan);for(const n of focused.plan.nodes)decorate(n,idx);}
    const rolePathEngine=canvas&&granularity==='roles'&&state.paperRolePathStages===true?(root.SemanticRolePathStages||(typeof require==='function'?require('./role-path-stages.js'):null)):null;
    const rolePaths=rolePathEngine?.compile({ir,plan:focused.plan,open:new Set(open),requested:[...explicitRoles],owners:state.paperRolePathStageOwners});
    if(rolePaths){focused.plan=rolePaths.plan;idx=index(focused.plan);for(const n of focused.plan.nodes)decorate(n,idx);}
    const predicateStages=canvas&&granularity==='roles'&&state.paperConditionPredicates!==false?Regions.predicates({ir,plan:focused.plan}):null;
    if(predicateStages){focused.plan=predicateStages.plan;idx=index(focused.plan);for(const r of predicateStages.rows)idx.nodes.get(r.group).content_inventory=inventory(idx.children.get(r.group)||[],idx);for(const n of focused.plan.nodes)decorate(n,idx);}
    const returnStages=canvas&&granularity==='roles'&&state.paperReturnRegions!==false?Regions.returns({ir,plan:focused.plan}):null;
    if(returnStages){focused.plan=returnStages.plan;idx=index(focused.plan);for(const r of returnStages.rows)idx.nodes.get(r.group).content_inventory=inventory(idx.children.get(r.group)||[],idx);for(const n of focused.plan.nodes)decorate(n,idx);}
    // A closed module owns its interface. Contracting that interface would
    // expose each internal consumer as another, misleading boundary arrow.
    for(const n of ir.nodes)if(n.kind==='interface'&&!open.includes(n.parent))pol.bindings.delete(n.id);
    // A return-region's source return sites are inspectable interfaces, not
    // transparent aliases. Their parent branches still control visibility.
    for(const r of returnStages?.rows||[])for(const site of r.return_sites)pol.bindings.delete(site.node);
    const normalReturns=returnStages&&state.paperNormalReturns!==false&&!local&&!state.paperFocus?
      Regions.normalReturns({ir,plan:focused.plan,open:new Set(open),inputs:invocationInputs,requested:[...explicitRoles,...(state.paperExpressionDetails||[])]}):null;
    if(normalReturns){focused.plan=normalReturns.plan;idx=index(focused.plan);options.edgeAttachments=normalReturns.attachments;for(const row of normalReturns.rows)decorate(idx.nodes.get(row.group),idx);}
    const summaryEngine=canvas&&granularity==='stages'&&state.paperReadSummary==='boundary'?
      (root.SemanticSummaryGoals||(typeof require==='function'?require('./summary-goals.js'):null)):null;
    const callBoundaries=new Map(summaryEngine?summaryEngine.build(ir,focused.plan).goals.flatMap(goal=>{
      const boundary=summaryEngine.callBoundary(goal,ir);return boundary?[[goal.node,boundary]]:[];
    }):[]);
    if(pipelines)for(const id of pipelines.keys()){const n=idx.nodes.get(id);n.local_pipeline_expanded=open.includes(id);
      if(callBoundaries.has(id))n.local_pipeline_call_boundary=callBoundaries.get(id);decorate(n,idx);}
    // Lower module-reference arguments only after selecting the logical
    // frontier. Released space must not implicitly open unrelated regions.
    const moduleArgumentEngine=canvas&&granularity==='roles'&&!local&&state.paperModuleArguments!==false?
      (root.SemanticModuleArguments||(typeof require==='function'?require('./module-arguments.js'):null)):null;
    const moduleArguments=moduleArgumentEngine?.compile({ir,plan:focused.plan,open:new Set(open),focus,requested:[...explicitRoles]});
    if(moduleArguments){
      options.metadataTargets=new Map();options.metadataKinds=new Map();
      for(const row of moduleArguments.rows.filter(r=>r.status==='attached')){
        pol.metadata.add(row.node);options.metadataTargets.set(row.node,row.consumer);options.metadataKinds.set(row.node,'module-reference-argument');
        const consumer=idx.nodes.get(row.consumer);consumer.module_arguments=[...(consumer.module_arguments||[]),copy(row)];
      }
      for(const row of moduleArguments.rows.filter(r=>r.status==='source-detail'))pol.bindings.delete(row.input);
      for(const n of focused.plan.nodes.filter(n=>n.module_arguments?.length))decorate(n,idx);
    }
    // Keep source call configurations separate from dependency summaries:
    // neither label alone proves tensor rank, valid shapes or axis meanings.
    const transformEngine=canvas&&granularity==='roles'&&state.paperTransformConfigurations!==false?
      (root.SemanticTransformConfigurations||(typeof require==='function'?require('./transform-configurations.js'):null)):null;
    const transformConfigurations=transformEngine?.compile(ir,{operands:state.paperTransformOperands!==false,sequences:state.paperTransformSequences!==false});
    if(transformConfigurations){
      focused.plan.nodes=focused.plan.nodes.map(n=>{
        const operations=n.role_path_stage?.operations||(!n.local_pipeline_expanded?n.local_pipeline?.operations:null)||[{node:n.id}];
        const rows=operations.flatMap((o,i)=>transformConfigurations.has(o.node)?[{...copy(transformConfigurations.get(o.node)),
          display_text:(operations.length>1?'#'+(i+1)+' ':'')+transformConfigurations.get(o.node).text}]:[]);
        const updated={...n};delete updated.transform_configurations;
        if(rows.length)updated.transform_configurations=rows;
        return updated;
      });
      idx=index(focused.plan);for(const n of focused.plan.nodes)decorate(n,idx);
    }
    let projected=E.project(ir,{...state,view:'architecture',details:false,open},focused.plan,options);
    let labelGapY=0,baseLabelGapY=0,clearanceRegions=[],rankClearance=false,localClearance=false;
    if(!E.semanticOnly){
    const edgePairs=new Map(),labeledPairs=new Set();
    for(const e of projected.edges){const key=JSON.stringify([e.source,e.target]);edgePairs.set(key,(edgePairs.get(key)||0)+1);if(e.condition||e.bundle_members)labeledPairs.add(key);}
    const requestedLabelGap=Number(state.paperLabelGapY)||0;
    labelGapY=Math.max(Math.min(160,Math.max(0,requestedLabelGap)),...[...labeledPairs].map(key=>edgePairs.get(key)>1?32+28*edgePairs.get(key):0));
    baseLabelGapY=Math.max(options.layout.gapY,Math.min(160,Math.max(0,requestedLabelGap)));
    clearanceRegions=L.labelClearances(projected.positions.context.idx,projected.edges);
    rankClearance=canvas&&state.paperLabelSpacing==='rank'&&!Object.keys(state.offsets||{}).length;
    localClearance=canvas&&(state.paperLabelSpacing==='local'||rankClearance)&&!Object.keys(state.offsets||{}).length;
    const globalRankFallback=rankClearance&&state.paperLabelRankFallback==='global';
    if(localClearance){
      const gaps=new Map(clearanceRegions.map(r=>[r.parent,r.gap_y]));
      options.layout.gapYForParent=parent=>gaps.get(parent)||0;
      if(rankClearance){
        options.layout.rankBaseGapY=baseLabelGapY;
        options.layout.rankLabelClearances=Array.isArray(state.paperLabelRankParents)?clearanceRegions.filter(r=>state.paperLabelRankParents.includes(r.parent)):clearanceRegions;
      }
    }
    const wireGapX=Math.max(36,...projected.edges.filter(e=>e.bundle_members).map(e=>Math.ceil(width(wireLabel(e),13)+28)));
    if(labelGapY>options.layout.gapY||wireGapX>options.layout.foldGapX){options.layout.gapY=localClearance&&!globalRankFallback?baseLabelGapY:Math.max(labelGapY,options.layout.gapY);options.layout.foldGapX=wireGapX;projected=E.project(ir,{...state,view:'architecture',details:false,open},focused.plan,options);}
    const widthMm=Math.max(80,Math.min(400,Number(state.paperWidthMm)||180));
    // Compare a bounded set of topology layouts at the requested print size.
    // The objective is readable physical scale, independent of module names.
    const fit=g=>{const ps=[...g.positions.values()];if(!ps.length)return 0;const w=Math.max(...ps.map(p=>p.x+p.w))-Math.min(...ps.map(p=>p.x))+56,h=Math.max(...ps.map(p=>p.y+p.h))-Math.min(...ps.map(p=>p.y))+56;return Math.min(widthMm/w,(state.paperFitPage===false?Infinity:240)/h);};
    let best=fit(projected);
    if(!canvas&&state.paperAuto!==false&&best*13*72/25.4<8.5&&!Object.keys(state.offsets||{}).length){
      const baseline=options.layout;
      for(const alternative of [
        {rankColumns:3,gapY:44,maxWidth:700,foldMinRanks:4,foldGain:.98,foldMaxColumns:2},
        {rankColumns:2,gapY:44,maxWidth:850,foldMinRanks:4,foldGain:.98,foldMaxParallel:2},
        {rankColumns:3,gapY:44,maxWidth:1000,foldMinRanks:4,foldGain:.98,foldMaxParallel:3},
        {rankColumns:3,gapY:44,maxWidth:800,foldMinRanks:4,foldGain:.98,foldMaxParallel:2,foldBoundaryRanks:true},
        {rankColumns:2,gapY:40,maxWidth:700,foldSerial:false},
        {rankColumns:3,gapY:32,maxWidth:700,foldSerial:false}
      ]){
        const candidate=E.project(ir,{...state,view:'architecture',details:false,open},focused.plan,{...options,layout:{...baseline,...alternative,gapY:Math.max(labelGapY,alternative.gapY)}}),score=fit(candidate);
        if(score>best*1.01){projected=candidate;best=score;}
      }
    }
    } // Native host consumes the same semantic cut without old geometry trials.
    const ps=[...projected.positions.values()];
    if(ps.length){const x=Math.min(...ps.map(p=>p.x))-28,y=Math.min(...ps.map(p=>p.y))-28;projected.bounds={x,y,w:Math.max(...ps.map(p=>p.x+p.w))+28-x,h:Math.max(...ps.map(p=>p.y+p.h))+28-y};}
    projected.publication={schema:'archcanvas-publication/1',focus,requested_focus:requestedFocus,relation:local?state.paperRelation:null,representative,granularity,auto:state.paperAuto!==false,open,budget,boundary:focused.boundary,
      wire_bundles:projected.edges.filter(e=>e.bundle_members).map(e=>({id:e.id,members:e.bundle_members.map(m=>m.id),values:e.bundle_values,tensor_equality:'not-asserted'})),
      configuration_arithmetic:pol.configurationArithmetic.filter(row=>allowed(row.node)),
      paper_width_mm:Math.max(80,Math.min(400,Number(state.paperWidthMm)||180)),fit_page:state.paperFitPage!==false,min_font_pt:8,unknowns:projected.nodes.filter(n=>!projected.positions.get(n.id).expanded).reduce((s,n)=>s+n.paper.unknown_count,0)};
    if(reservations)projected.publication.frontier_reservations=reservations;
    if(transformConfigurations)projected.publication.transform_configurations={rule_version:transformEngine.VERSION,
      rows:projected.nodes.filter(n=>n.transform_configurations?.length).map(n=>({node:n.id,operations:copy(n.transform_configurations)}))};
    if(coherentChoices.length)projected.publication.coherent_frontier={rule_version:'coherent-frontier/1',phase:'logical-frontier-before-summary-and-stage-lowering',choices:coherentChoices};
    if(moduleArguments?.rows.length)projected.publication.module_arguments=copy(moduleArguments);
    if(invocationInputs)projected.publication.invocation_inputs={rule_version:'invocation-inputs/1',rows:[...invocationInputs.values()].map(r=>({...copy(r),
      status:projected.positions.get(r.node)?.arrangement==='fixed-call-argument'?'docked':projected.positions.has(r.node)?'visible':projected.representatives[r.node]?'folded':'outside',
      visible_node:projected.representatives[r.node]||null})),docks:projected.positions.context.fixedInputs||[]};
    if(canvas){
      const input=state.paperCanvasLimits||{},limit=(key,fallback,min,max)=>Number.isFinite(input[key])?Math.max(min,Math.min(max,input[key])):fallback;
      projected.publication.medium='canvas';
      if(labelGapY>baseLabelGapY)projected.publication.label_clearance={mode:rankClearance?'rank':localClearance?'local':'global',base_gap_y:baseLabelGapY,global_gap_y:labelGapY,regions:clearanceRegions,
        ...(rankClearance?{rank_layout:projected.positions.context.rankClearances}: {})};
      projected.publication.inline_sequences=base.publication?.inline_sequences||null;
      projected.publication.frame_ownership=projected.frame_ownership||[];
      if(roleFrontier)projected.publication.role_frontier=roleEngine.receipt(roleFrontier,projected);
      if(roleStages)projected.publication.role_operation_stages=roleStageEngine.receipt(roleStages,projected);
      if(rolePaths)projected.publication.role_path_stages=rolePathEngine.receipt(rolePaths,projected);
      if(stages)projected.publication.contract_stages=stageEngine.receipt(stages,projected);
      if(predicateStages)projected.publication.condition_predicates={rule_version:'condition-predicates/1',rows:predicateStages.rows.map(r=>({...r,
        canonical_members:idx.nodes.get(r.group).canonical_members,cuts:idx.nodes.get(r.group).boundary_ports,
        status:projected.positions.has(r.group)?projected.positions.get(r.group).expanded?'expanded':'summary':'folded'}))};
      if(returnStages)projected.publication.return_regions={rule_version:'return-regions/1',rows:returnStages.rows.map(r=>({...r,
        status:projected.positions.has(r.group)?projected.positions.get(r.group).expanded?'expanded':'summary':'folded'}))};
      if(normalReturns?.rows.length)projected.publication.normal_returns={rule_version:'normal-returns/1',rows:normalReturns.rows.map(r=>({...copy(r),
        status:projected.positions.has(r.group)&&!projected.positions.get(r.group).expanded?'summary':'folded',
        attached_edges:r.alternative_inputs.filter(e=>projected.edge_accounting.attached.includes(e.id)).map(e=>e.id)}))};
      if(pipelines)projected.publication.local_pipelines=pipelineEngine.receipt(pipelines,projected);
      if(expressions)projected.publication.local_expressions=expressionEngine.receipt(expressions,projected);
      projected.publication.canvas_limits={width_px:limit('width_px',8192,512,16384),height_px:limit('height_px',16384,512,32768),
        area_px2:limit('area_px2',16777216,262144,67108864),nodes:limit('nodes',512,16,2048),edges:limit('edges',2048,16,8192)};
    }
    for(const cut of focused.boundary){let id=cut.port_node;while(id&&!projected.positions.has(id))id=idx.nodes.get(id)?.parent;cut.visible_node=id||null;}
    for(const cut of focused.boundary.filter(c=>c.presentation==='attached-metadata'&&c.visible_node)){
      if([...projected.annotations.values()].some(notes=>notes.some(note=>note.edge.id===cut.id)))continue;
      const id=cut.visible_node;if(!projected.annotations.has(id))projected.annotations.set(id,[]);
      projected.annotations.get(id).push({edge:copy(cut),resource:idx.nodes.get(pol.metadata.has(cut.source)?cut.source:cut.target),annotation_kind:'configuration-boundary'});
    }
    const original=new Map(ir.nodes.map(n=>[n.id,n]));
    const cellInterfaces=new Map((base.relation_graph?.relations||[]).filter(r=>r.type==='state-interface'&&r.properties.interface_kind==='single-step').map(r=>[r.node,r.properties]));
    const portRoles=(node,port,input)=>{
      if(!node||node.kind==='opaque')return null;
      const cell=cellInterfaces.get(node.id);
      if(cell){
        const pair=Object.hasOwn(cell.state_components,'1');
        if(input)return port===cell.input_port?'input':port===cell.state_input_port?(pair?'(h, c) in':'h in'):null;
        return pair?({out:'(h, c) out','0':'h out','1':'c out'})[port]:port==='out'?'h out':null;
      }
      const op=A.operator(node);
      if(['rnn','gru','lstm'].includes(op)){
        if(input)return port==='arg:0'?'xₜ':port==='arg:1'||port==='kw:hx'?(op==='lstm'?'(h₀, c₀)':'h₀'):null;
        return op==='lstm'?({'0':'sequence','1':'(hₙ, cₙ)','1.0':'hₙ','1.1':'cₙ'})[port]:({'0':'sequence','1':'hₙ'})[port];
      }
      if(op==='top-k'&&!input)return ({'0':'values','1':'indices'})[port];
      return null;
    };
    for(const edge of projected.edges){
      edge.paper_labels=[];
      if(edge.bundle_members){
        const uses=idx.nodes.get(edge.target)?.boundary_uses;
        // The shared result terminal already states this exact use count.
        // Avoid a duplicate label in its short input channel.
        if(!uses||uses.length!==edge.bundle_members.length||!uses.every(use=>edge.bundle_members.some(m=>m.id===use.id)))
          edge.paper_labels.push({text:(edge.sequence_output?'sequence · ':'')+wireLabel(edge),evidence:'Presentation bundle; individual canonical dependencies are retained in bundle_members.'});
        continue;
      }
      const from=portRoles(original.get(edge.resolved_source),edge.source_port,false),to=portRoles(original.get(edge.canonical_target),edge.target_port,true);
      if(from||to)edge.paper_labels.push({text:[from,to].filter(Boolean).join(' → '),evidence:'torch.nn / torch.topk interface contract'});
      if(edge.condition)edge.paper_labels.push({text:String(edge.condition.outcome),evidence:'source branch condition'});
      if(edge.target===edge.canonical_target)for(const b of edge.semantic_bindings||[])if(['gate','signal'].includes(b.role))
        edge.paper_labels.push({text:b.role,evidence:'local sigmoid operand binding',constraint:b.constraint});
      const iterationRole=edge.semantic_bindings?.find(b=>['iteration-initial','iteration-feedback','iteration-result','iteration-completion'].includes(b.role));
      if(iterationRole)edge.paper_labels.push({text:({'iteration-initial':'initial binding','iteration-feedback':'next iteration','iteration-result':'loop exit','iteration-completion':'complete'})[iterationRole.role],
        evidence:'source name binding on normal loop completion; time axis unproved',constraint:iterationRole.constraint});
    }
    for(const f of base.findings.filter(f=>f.rule==='scaled-attention-like')){
      const score=original.get(f.roles.scores),softmax=original.get(f.roles.normalization),operands=(pol.ins.get(score?.id)||[]).filter(flow),dim=softmax?.arguments?.kwargs?.dim??softmax?.arguments?.args?.[1];
      if(operands.length!==2||dim!==-1)continue;
      const left=value(operands.find(e=>e.target_port==='arg:0')?.source,'out',pol.bindings),right=value(operands.find(e=>e.target_port==='arg:1')?.source,'out',pol.bindings),transpose=original.get(right.id);
      const dims=transpose?.arguments?.args;
      if(A.operator(transpose)!=='transpose'||!transpose.function_target?.endsWith('.transpose')||!Array.isArray(dims)||dims.length!==2||!dims.includes(-1)||!dims.includes(-2))continue;
      for(const edge of projected.edges){
        let label=null;if(edge.canonical_target===score.id&&edge.target_port==='arg:0')label='Q';
        if(edge.canonical_target===transpose.id&&edge.target_port==='receiver')label='K';
        if(edge.canonical_target===f.roles.output&&edge.target_port==='arg:1')label='V';
        if(label)edge.paper_labels.push({text:label,evidence:'matmul operand order, final-axis key transpose and softmax(dim=-1)',finding:f.id});
      }
    }
    // An alias such as width must still expose the original arithmetic in the
    // consumer's inspector. Preserve the whole proven chain, not just its name.
    const proofs=new Map(pol.configurationArithmetic.map(row=>[row.node,row])),proofCache=new Map();
    function proofFor(id){if(!proofCache.has(id)){
      const rows=[],seen=new Set(),todo=[id];for(let i=0;i<todo.length;i++){const row=proofs.get(todo[i]);if(!row||seen.has(row.node))continue;seen.add(row.node);rows.push(row);todo.push(...row.dependencies.map(e=>e.source));}
      proofCache.set(id,rows);
    }return proofCache.get(id);}
    for(const notes of projected.annotations.values())for(const note of notes)if(proofs.has(note.resource?.id))note.configuration_proof=proofFor(note.resource.id);
    projected.architecture=focused.plan;return projected;
  }
  function fullyExpanded(ir,state,E){
    const next={...E.clone(state),paperCanonical:true,paperMedium:'canvas',paperGranularity:'detailed',paperAuto:false,paperAdaptive:false,details:true,
      open:[...E.index(ir).children.keys()].filter(Boolean),offsets:{}};
    for(const key of ['canvasPlacement','paperFocus','paperRelation','paperRepresentative','paperRepresentativeGroup','paperDiagramPlan','paperDiagramReturn'])delete next[key];
    return next;
  }
  function projectCanonical(ir,state,E){
    // Every source unit and binding gets its own expandable identity. The
    // semantic certificates remain available, but no summary/alias/metadata
    // policy may hide a canonical node in this explicit source-detail mode.
    const semantic=plan(ir),raw={...semantic,nodes:copy(ir.nodes),edges:ir.edges},idx=index(raw);
    for(const n of raw.nodes)decorate(n,idx);
    const graph=E.project(ir,{...state,view:'source',details:true},raw,{...(E.semanticOnly&&state.nativeSourceFocus&&idx.nodes.has(state.nativeSourceFocus)?{roots:[state.nativeSourceFocus]}:{}),layout:{foldSerial:false,gapX:28,gapY:44,framePadding:20,
      nodeSize:n=>({...n.paper}),frameHeader:n=>Math.max(66,24+n.paper.lines.length*20+n.paper.captions.length*16),alignForks:true}});
    graph.architecture=raw;
    for(const e of graph.edges)e.paper_labels=e.condition?[{text:String(e.condition.outcome),evidence:'source branch condition'}]:[];
    graph.publication={schema:'archcanvas-publication/1',canonical:true,focus:null,requested_focus:null,granularity:'detailed',auto:false,open:state.open,budget:null,boundary:[],wire_bundles:[],
      paper_width_mm:180,fit_page:false,medium:'canvas',canvas_limits:{width_px:8192,height_px:16384,area_px2:16777216,nodes:512,edges:2048},
      unknowns:graph.nodes.filter(n=>n.kind==='opaque').length,
      scope:'Explicit canonical source detail; no value, parameter, call, condition or state is summarized.'};
    return graph;
  }
  const api={plan,project,fullyExpanded,projectCanonical,relationPanel,wrap,width,decorate,configuration,category,palette};root.SemanticPublication=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
