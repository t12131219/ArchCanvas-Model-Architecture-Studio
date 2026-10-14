"""Presentation helpers for reviewed explicit sequence-module adapters."""
from module_adapters.support import chain, op, graph, ref, finish


def link(src, dst, port='in', role='tensor', source_port='out', **kwargs):
    kwargs.setdefault('src_side','out')
    kwargs.setdefault('dst_side','in')
    return dict(src=src, dst=dst, src_port=source_port, dst_port=port,
                role=role, label='', dashed=role in ('mask', 'configuration', 'shape_dependency'), **kwargs)


def make(key, name, doc, scope, source, symbols, inputs, body, outputs, edges,
         profile, facts, corrections, roles=None, legend=None, additional_sources=None):
    refs=[ref(source,s) for s in symbols]
    items=inputs+[body]+outputs
    root=graph(key+'.root',name,items,refs,'',expand=0,
               ranks=[[x['id'] for x in inputs],[body['id']],[x['id'] for x in outputs]],
               rank_gap=64,column_gap=48)
    visual={}
    palette={'linear':'linear','conv1d':'conv','matmul':'tensor','bmm':'tensor',
             'einsum':'tensor','multiply':'tensor','subtract':'tensor','tensor':'tensor',
             'concat':'norm','add':'norm','layer_norm':'norm','softmax':'softmax',
             'sigmoid':'softmax','tanh':'softmax','relu':'activation','dropout':'control',
             'mask':'control','input':'input','output':'output','group':'ffn'}
    def visit(node):
        visual[node['id']]=palette.get(node['kind'],'control')
        for child in node.get('items',[]):visit(child)
    visit(root);visual[root['id']]='root';visual[body['id']]='encoder'
    visual.update(roles or {})
    used=set(visual.values())
    colors=[('input','Inputs')]
    for role,label,aliases in [
        ('attention','Gate / attention',{'attention','recurrent'}),
        ('conv','Conv / transforms',{'conv','ffn','encoder'}),
        ('norm','Add / norm / concat',{'norm','concat'}),
        ('softmax','Gates / Softmax',{'softmax','sampling'}),
        ('linear','Linear / outputs',{'linear','output'}),
        ('tensor','Tensor operations',{'tensor'}),
        ('control','ReLU / Dropout',{'control','activation'}),
    ]:
        if used & aliases:colors.append((role,label))
    model=finish(dict(key=key,name=name,doc=doc,module_scope=scope,
        source_project=source.split('/',1)[0],entry=refs[-1],tree=root,extra_edges=edges,
        profile=dict(profile,mode='reviewed static selected module profile'),
        profile_label=profile.get('label','Module only / static / explicit shapes'),
        symbols={source:symbols},config_files=[source],visual_roles=visual,fill_width=[],
        facts=facts,corrections=corrections,
        color_legend=colors,
        legend=legend or ['Declared shapes are static examples, not observed execution.',
                        'Bottom-to-top ranks express dependency levels; ports carry real source operands.',
                        'Parameter identities denote independent source instances, not shared colors.']))
    if additional_sources:
        for path,names in additional_sources.items():model['symbols'][path]=names
    return model


def verify(ir, key, node_fields, bindings):
    """Check source-reviewed fields and operand ports, including negative edges."""
    nodes={n['id']:n for n in ir['nodes']};p=ir['profile'];checks=[]
    def check(condition,label):
        if not condition:raise ValueError(key+': '+label)
        checks.append(label)
    check(ir['artifact_scope']=='module' and p['artifact_scope']=='module'
          and p['model_executed'] is False,'static module-only scope')
    for identity,fields in node_fields.items():
        check(identity in nodes,identity+' stable source-bound identity')
        for field,value in fields.items():
            check(nodes[identity].get(field)==value,identity+' source contract '+field)
    for src,dst,port in bindings:
        matches=[e for e in ir['edges'] if e['dst']==dst and e['dst_port']==port]
        check(any(e['src']==src for e in matches),src+' feeds '+dst+':'+port)
        if port not in ('in','out'):
            check(len(matches)==1,dst+':'+port+' has exactly one declared producer')
    return checks
