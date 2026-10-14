"""Independent source/IR/view endpoint contracts; never import upstream models.

The renderer declares traces. This checker reconstructs expected visible
operators from flat IR parentage and audited source contracts, not routing code.
"""
import ast
import textwrap


def require(ok,message):
    if not ok:raise ValueError('Arrow semantics: '+message)


def source_endpoint_contracts(ir,evidence=None):
    nodes={n['id']:n for n in ir['nodes']};edges=ir['edges'];checks=[]
    def has(src,dst,sp,dp,role):
        require(any((e['src'],e['dst'],e['src_port'],e['dst_port'],e['role'])==(src,dst,sp,dp,role) for e in edges),f'actual operand {src}:{sp} -> {dst}:{dp} ({role})')
        checks.append(f'{src}:{sp}->{dst}:{dp}:{role}')
    key=ir['model'];expressions=[]
    if key=='autoformer':
        has('af_memory','af_dec_cross_qkv','out','memory_KV','memory')
        require(nodes['af_dec_cross_qkv'].get('main_input_operand')=='Q','cross main input must supply Q')
        require(nodes['af_dec_cross_qkv'].get('auxiliary_input_operands')=={'memory_KV':['K','V']},'memory supplies K,V only')
        for i in (1,2,3):
            has(f'af_dec_decomp{i}', 'af_trend_update','trend',f'trend{i}','trend')
            require(nodes[f'af_dec_decomp{i}'].get('output_bindings',{}).get('trend')==f'af_dec_decomp{i}_mean','trend must come from moving average, not seasonal subtraction')
            has(f'af_dec_decomp{i}_mean',f'af_dec_decomp{i}','out','trend','output_binding')
        expressions=[('DecoderLayer.forward','self.cross_attention(x, cross, cross, attn_mask=cross_mask)'),('series_decomp.forward','self.moving_avg(x)'),('series_decomp.forward','(res, moving_mean)'),('my_Layernorm.forward','x_hat - bias')]
    elif key=='itransformer':
        has('it.normalize','it.denormalize','mean_std','mean_std','statistics')
        has('it.marks','it.concat','out','side','covariate')
        expressions=[('Model.forecast','x_enc.mean(1, keepdim=True).detach()'),('Model.forecast','stdev[:, 0, :].unsqueeze(1).repeat(1, self.pred_len, 1)'),('Model.forecast','means[:, 0, :].unsqueeze(1).repeat(1, self.pred_len, 1)')]
    elif key=='patchtst':
        has('patch_layer1_raw_scores','patch_layer2_raw_scores','scores','prev','scores')
        has('patch_revin_norm','patch_revin_denorm','stats','side','normalization')
        require(nodes['patch_layer1_raw_scores'].get('pre_softmax') is True,'prev source is before Softmax')
        expressions=[('_ScaledDotProductAttention.forward','attn_scores + prev'),('_ScaledDotProductAttention.forward','F.softmax(attn_scores, dim=-1)'),('_ScaledDotProductAttention.forward','(output, attn_weights, attn_scores)')]
    elif key=='timemixer':
        has('tm.norm0','tm.denorm','statistics','statistics','statistics')
        for block in (1,2):
            for kind in ('season','trend'):
                indices=list(range(4)) if kind=='season' else list(reversed(range(4)))
                p=f'tm.pdm{block}.{kind}'
                for step,scale in enumerate(indices[1:]):has(f'tm.pdm{block}.decomp',p+f'.step{step}.add',f'{kind}[{scale}]','original_scale','component')
                for source,scale in zip([p+'.initial',p+'.step0',p+'.step1'],indices[:-1]):has(source,p+'.list','out',f'scale[{scale}]','retained_scale')
                require(nodes[p+'.list'].get('ordered_output_scales')==[0,1,2,3],'collection restores all original scale positions')
                require(nodes[p+'.list'].get('main_input_operand')==f'scale[{indices[-1]}]','final recurrence input must name its actual scale')
        expressions=[('MultiScaleSeasonMixing.forward','out_season_list.append(out_high.permute(0, 2, 1))'),('MultiScaleTrendMixing.forward','out_trend_list.append(out_low.permute(0, 2, 1))'),('MultiScaleTrendMixing.forward','out_trend_list.reverse()')]
    else:raise ValueError('No reviewed model endpoint contracts: '+key)
    for edge in edges:
        if edge['role']=='dispatch' and nodes[edge['dst']].get('input_selector'):
            require(edge['src_port']==nodes[edge['dst']]['input_selector'],'source tuple field must match declared operand selector')
    if evidence:
        for symbol,expression in expressions:
            snippets=[v['snippet'] for v in evidence['symbols'].values() if v['symbol']==symbol]
            require(len(snippets)==1,'unambiguous source symbol '+symbol)
            tree=ast.parse(textwrap.dedent(snippets[0]));expected=ast.dump(ast.parse(expression,mode='eval').body,include_attributes=False)
            require(any(ast.dump(n,include_attributes=False)==expected for n in ast.walk(tree)),f'real source expression {symbol}: {expression}')
            checks.append(symbol+': '+expression)
    return checks


def view_endpoint_checks(layout,ir):
    """Reconstruct expanded-chain output/input aliases without renderer imports."""
    nodes={n['id']:n for n in ir['nodes']};edges={e['id']:e for e in ir['edges']};boxes={b['id']:b for b in layout['boxes']};visible=set(boxes);counts={}
    # Reconstruct interfaces from real IR edges, independently of both the
    # renderer and its materialized port_bindings metadata.
    interfaces={}
    for e in edges.values():
        if e['role']=='boundary' and e['src_port']=='in':interfaces[(e['src'],'in','dst')]=(e['dst'],e['dst_port'],e['id'])
        elif e['role']=='boundary' and e['dst_port']=='out':interfaces[(e['dst'],'out','src')]=(e['src'],e['src_port'],e['id'])
        elif e['role']=='output_binding':interfaces[(e['dst'],e['dst_port'],'src')]=(e['src'],e['src_port'],e['id'])
    for (identity,field,end),(child,port,edge_id) in interfaces.items():
        require(nodes[identity].get('port_bindings',{}).get('outputs' if end=='src' else 'inputs',{}).get(field)==dict(node=child,port=port,edge=edge_id),'interface metadata disagrees with real boundary edge')
    def expected(identity,field,end):
        current=identity;seen=set()
        while current in visible and boxes[current]['expanded']:
            require(current not in seen,'cyclic endpoint alias');seen.add(current);node=nodes[current]
            binding=interfaces.get((current,field,end))
            if binding is None:break
            current,field,_=binding
            require(current in nodes,'alias references unknown source node')
            while current not in visible and nodes[current].get('fold_inline'):
                candidates=[e for e in edges.values() if e['role'] in ('tensor','seasonal') and (e['dst']==current if end=='src' else e['src']==current)]
                require(len(candidates)==1,'ambiguous folded source operand')
                edge=candidates[0];current=edge['src' if end=='src' else 'dst'];field=edge['src_port' if end=='src' else 'dst_port']
        while current not in visible:
            current=nodes[current].get('parent');require(current is not None,'missing visible ancestor')
        return current
    covered=set();branch_covered={}
    for route in layout['routes']:
        trace=route.get('semantic_trace');require(isinstance(trace,list) and trace,'every rendered arrow/bus must have source IR trace: '+route['id'])
        require(all(x in edges for x in trace),'unknown route trace edge: '+route['id']);actual=[edges[x] for x in trace];covered.update(trace)
        rep=route.get('representation');counts[rep]=counts.get(rep,0)+1
        if rep=='typed_auxiliary':
            require(len(actual)==1,'typed auxiliary represents exactly one real operand');edge=actual[0]
            for end in ('src','dst'):
                require(route.get('semantic_'+end)==edge[end] and route.get('semantic_'+end+'_port')==edge[end+'_port'],'typed operand identity/field mismatch '+route['id'])
                projected=expected(edge[end],edge[end+'_port'],end)
                require(route.get('projected_'+end)==projected,'wrong expanded/folded operator '+route['id']+' '+end+' expected '+projected)
                ref=route.get(end);require(ref and ref.rsplit(':',1)[0]==projected,'physical endpoint is wrong operator '+route['id'])
        elif rep=='dependency':
            for left,right in zip(actual,actual[1:]):
                require(left['dst']==right['src'],'disconnected contracted trace')
                require(left['dst'] not in visible,'cannot contract away an exposed operator')
            for end,edge in [('src',actual[0]),('dst',actual[-1])]:
                ref=route.get(end);require(ref is not None,'dependency needs both physical endpoint identities')
                name,port=ref.rsplit(':',1);require(name==edge[end],'ordinary arrow lands on wrong source/target operator')
                if port not in ('left','right'):require(port==edge[end+'_port'],'ordinary arrow field mismatch')
                else:require(edge[end+'_port']=='side','side Add must consume declared side operand')
        elif rep in ('fork_branch','collection_branch'):
            require(len(actual)==1,'each branch selects one source field');edge=actual[0]
            end='dst' if rep=='fork_branch' else 'src';ref=route.get(end);require(ref and ref.rsplit(':',1)[0]==edge[end],'branch connects wrong nested child')
            require(edge['role'] in (('fork','dispatch') if rep=='fork_branch' else ('tuple_collection',)),'branch selector role mismatch')
            if edge['role']=='dispatch':
                selector=nodes[edge['dst']].get('input_selector')
                if selector:require(edge['src_port']==selector,'wrong tuple field dispatched to nested child')
            branch_covered[edge['id']]=branch_covered.get(edge['id'],0)+1
        elif rep in ('fork_bus','collection_bus'):
            group_field='src' if rep=='fork_bus' else 'dst';require(len({e[group_field] for e in actual})==1,'unrelated branches share a tuple bus')
            require(all(e['role'] in (('fork','dispatch') if rep=='fork_bus' else ('tuple_collection',)) for e in actual),'collection/fork is not implicit arithmetic')
        else:raise ValueError('Arrow semantics: unknown route representation '+str(rep))
    suppressed=set()
    for row in layout.get('suppressed_edges',[]):
        require(row.get('reason')=='internal_to_collapsed_boundary','unjustified omitted operand edge')
        for identity in row['semantic_trace']:
            edge=edges[identity];require(expected(edge['src'],edge['src_port'],'src')==expected(edge['dst'],edge['dst_port'],'dst')==row['projected_node'],'suppression must remain within exactly one folded boundary');suppressed.add(identity)
    auxiliary={e['id'] for e in ir['edges'] if e['role'] not in ('tensor','boundary','seasonal','fork','dispatch','tuple_collection','residual','retained_input','output_binding')}
    require(auxiliary <= covered|suppressed,'missing true auxiliary operands: '+repr(sorted(auxiliary-(covered|suppressed))))
    exposed_branches={e['id'] for e in edges.values() if e['role'] in ('fork','dispatch','tuple_collection') and e['src'] in visible and e['dst'] in visible}
    require(all(branch_covered.get(e)==1 for e in exposed_branches),'each exposed tuple branch needs exactly one physical operand path')
    return {'passed':True,'routes_checked':len(layout['routes']),'representation_counts':counts,'traced_ir_edges':len(covered),'suppressed_internal_edges':len(suppressed),'all_true_auxiliary_operands_accounted_for':True,'method':'actual IR boundary/output_binding edges + parentage + typed selectors; independent of renderer port metadata'}
