"""Reviewed explicit DAG cases; layout ranks are not source data edges."""
from copy import deepcopy
from module_adapters.support import chain,op,graph,ref,finish

ROLE={'input':'input','output':'output','linear':'linear','conv2d':'conv','masked_linear':'linear',
      'tanh':'softmax','sigmoid':'softmax','softmax':'softmax','activation':'activation','multiply':'norm',
      'add':'norm','subtract':'norm','matmul':'linear','norm':'norm','tensor':'tensor','concat':'concat',
      'control':'control','statistics':'norm','density':'softmax'}

def build_case(key):
    from module_adapters.root_definitions import CASES
    c=deepcopy(CASES[key]);src=c['source'];symbols=c['symbols'];fwd=ref(src,c['entry'])
    prefix=key+'.';roles={prefix+'root':'root',prefix+'body':'encoder'};items=[];edges=[]
    def identity(v):return prefix+v
    def node(v):
        d=deepcopy(v);short=d.pop('id');label=d.pop('label');kind=d.pop('kind');shape=d.pop('shape','')
        syms=d.pop('symbols',[c['entry']]);detail=d.pop('detail',[])
        roles[identity(short)]=ROLE.get(kind,'tensor')
        return op(identity(short),label,kind,[ref(src,s) for s in syms],shape,detail,**d)
    for s in c['stages']:
        kids=[node(x) for x in s['ops']]
        roles[identity(s['id'])]=s.get('role','attention')
        items.append(chain(identity(s['id']),s['label'],kids,[ref(src,sym) for sym in s.get('symbols',[c['entry']])],
                           s.get('shape',''),s.get('detail',[]),expand=2,**{k:s[k] for k in ['suppress_input_boundary','flow_role'] if k in s}))
    body=graph(prefix+'body',c['body'],items,[ref(src,s) for s in symbols],c.get('output_shape',''),expand=1,
               ranks=[[identity(x) for x in row] for row in c['ranks']],rank_gap=76,column_gap=58)
    ins=[node(dict(x,kind='input')) for x in c['inputs']]
    outs=[node(dict(x,kind='output')) for x in c['outputs']]
    tree=graph(prefix+'root',c['name'],ins+[body]+outs,[ref(src,s) for s in symbols],
               expand=0,ranks=[[x['id'] for x in ins],[prefix+'body'],[x['id'] for x in outs]],rank_gap=76,column_gap=58)
    for x in c['edges']:
        a,b,*rest=x;options=rest[0] if rest else {}
        edges.append(dict(src=identity(a),dst=identity(b),src_port=options.get('src_port','out'),
                          dst_port=options.get('dst_port','in'),role=options.get('role','tensor'),dashed=options.get('role')=='shape_dependency',
                          src_side=options.get('src_side','out'),dst_side=options.get('dst_side','in')))
    legend=[]
    for role,label in [('input','Inputs'),('attention','Module'),('linear','Linear'),
                       ('conv','Convolution'),('norm','Norm / math'),('softmax','Prob. / act.'),
                       ('tensor','Reshape'),('concat','Concatenation'),('control','State'),('output','Outputs')]:
        if role in roles.values():legend.append((role,label))
    profile=c['profile']|dict(shape_origin='declared example; statically inferred, not observed',drawing_scope=c['scope'],
        source_contracts=c['contracts'])
    return finish(dict(key=key,name=c['name'],source_project=src.split('/')[0],entry=fwd,doc=key+'.md',
        module_scope=c['scope'],profile=profile,profile_label=c['profile_label'],tree=tree,extra_edges=edges,
        visual_roles=roles,color_legend=legend,fill_width=[],symbols={src:symbols},facts=c['facts'],
        corrections=c['corrections'],legend=['Bottom-to-top; independent outputs are parallel, never an implicit tensor chain',
          'Colors denote roles; Parameter / buffer / ordinary state are recorded separately in IR',
          'Fixed source symbols + explicit profile; library operators are call boundaries']))

def validate_case(key,ir):
    from module_adapters.root_definitions import CASES
    c=CASES[key];prefix=key+'.';n={x['id']:x for x in ir['nodes']};checks=[]
    def check(ok,label):
        if not ok:raise ValueError(key+': '+label)
        checks.append(label)
    check(ir.get('artifact_scope')=='module' and ir['profile']['artifact_scope']=='module' and
          ir['profile']['model_executed'] is False,'static module boundary')
    for k,v in c['profile'].items():check(ir['profile'].get(k)==v,'selected profile '+k)
    check(ir['profile']['drawing_scope']==c['scope'],'exact subgraph scope')
    for stage in c['stages']+[dict(ops=[dict(x,kind='input') for x in c['inputs']]+[dict(x,kind='output') for x in c['outputs']])]:
        for expected in stage['ops']:
            actual=n[prefix+expected['id']]
            for k,v in expected.items():
                if k in ('id','symbols','detail'):continue
                check(actual.get(k)==v,expected['id']+' '+k)
    for a,b,*r in c['edges']:
        o=r[0] if r else {}
        check(any(e['src']==prefix+a and e['dst']==prefix+b and e['src_port']==o.get('src_port','out')
                  and e['dst_port']==o.get('dst_port','in') and e['role']==o.get('role','tensor') for e in ir['edges']),
              'explicit dependency '+a+' -> '+b)
    # The final IR cannot acquire an invented classifier or cross-output chain.
    declared={prefix+x['id'] for s in c['stages'] for x in s['ops']}
    declared|={prefix+x['id'] for x in c['inputs']+c['outputs']}|{prefix+s['id'] for s in c['stages']}|{prefix+'root',prefix+'body'}
    check(set(n)==declared,'only declared module nodes')
    out={prefix+x['id'] for x in c['outputs']}
    check(not any(e['src'] in out and e['dst'] in out for e in ir['edges']),'independent tuple outputs')
    return checks
