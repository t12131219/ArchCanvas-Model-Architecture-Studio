"""Presentation/validation helpers for explicit reviewed graph-module adapters."""
from module_adapters.support import op,chain,graph,finish


class Diagram:
    def __init__(self,key,name,source,symbol,scope,profile):
        self.key,self.name,self.source,self.entry,self.scope,self.profile=key,name,source,source+'::'+symbol,scope,profile
        self.inputs=[];self.ops=[];self.ranks={};self.edges=[];self.roles={};self.symbols={source:{symbol}}
    def ref(self,symbol,path=None):
        path=path or self.source;self.symbols.setdefault(path,set()).add(symbol);return path+'::'+symbol
    def input(self,name,label,shape,kind='input',source=None,**fields):
        identity=self.key+'.'+name
        node=op(identity,label,kind,source or self.entry,shape,width=250,**fields)
        self.inputs.append(node);self.roles[identity]='linear' if kind=='parameter' else kind
        return identity
    def node(self,name,label,kind,shape,rank,source=None,**fields):
        identity=self.key+'.'+name
        node=op(identity,label,kind,source or self.entry,shape,width=270,**fields)
        self.ops.append(node);self.ranks.setdefault(rank,[]).append(identity)
        self.roles[identity]={'multiply':'tensor','add':'norm','subtract':'tensor','sigmoid':'softmax','tanh':'softmax',
                              'relu':'activation','einsum':'mixing','bmm':'mixing','matmul':'mixing','spmm':'mixing',
                              'mean':'pool','sum':'pool','cat':'concat','normalize':'norm','dropout':'control',
                              'scatter':'mixing','softmax':'softmax','squash':'activation','linear':'linear'}.get(kind,kind)
        return identity
    def stage(self,name,label,shape,rank,steps,source=None,**fields):
        identity=self.key+'.'+name;children=[]
        for suffix,title,kind,childshape,kw in steps:
            child_fields=dict(kw)
            child_source=child_fields.pop('source',source or self.entry)
            child=op(identity+'.'+suffix,title,kind,child_source,childshape,width=270,**child_fields)
            children.append(child);self.roles[child['id']]={'relu':'activation','tanh':'softmax','sigmoid':'softmax',
                'multiply':'tensor','add':'norm','mean':'pool','cat':'concat','matmul':'mixing','bmm':'mixing','einsum':'mixing',
                'spmm':'mixing','dropout':'control','softmax':'softmax'}.get(kind,kind)
        node=chain(identity,label,children,source or self.entry,shape,expand=2,**fields)
        self.ops.append(node);self.ranks.setdefault(rank,[]).append(identity);self.roles[identity]='inner'
        return identity
    def edge(self,src,dst,port='in',role='tensor',sp='out',ss='out',ds='in',label=''):
        full=lambda s:s if s.startswith(self.key+'.') else self.key+'.'+s
        self.edges.append(dict(src=full(src),dst=full(dst),src_port=sp,dst_port=port,role=role,
                               src_side=ss,dst_side=ds,dashed=role not in ('tensor','retained_value'),label=label))
    def build(self,output_source,output_shape,doc,facts,corrections,**fields):
        output=op(self.key+'.output','Selected module output','output',output_source,output_shape,width=270)
        module=graph(self.key+'.module',self.name+' / operators',self.ops,self.entry,output_shape,
                     ranks=[self.ranks[r] for r in sorted(self.ranks)],expand=1,rank_gap=72,column_gap=64)
        root=graph(self.key+'.root',self.name+' / module only',self.inputs+[module,output],self.entry,output_shape,
                   ranks=[[n['id'] for n in self.inputs],[module['id']],[output['id']]],expand=0,rank_gap=72,column_gap=48)
        self.roles.update({self.key+'.root':'root',self.key+'.module':'encoder',self.key+'.output':'output'})
        self.profile.setdefault('selected_configuration','explicit static module profile; not a runtime observation')
        return finish(dict(key=self.key,name=self.name,doc=doc,module_scope=self.scope,source_project=self.source.split('/')[0],
            entry=self.entry,tree=root,profile=self.profile,extra_edges=self.edges,visual_roles=self.roles,
            symbols={path:sorted(names) for path,names in self.symbols.items()},
            profile_label=self.profile.get('display','module only / reviewed fixed source / independent operands'),
            facts=facts+['Graph ranks only allocate space. Explicit edges supply real operands; no upstream code is imported or executed.'],
            corrections=corrections,legend=['Read bottom to top; all module internals follow the same direction.',
                 'Same operator color does not imply shared weights; instance/parameter identities are preserved in IR.',
                 'Solid edges carry values; dashed edges carry topology, shape or loop state. Library kernels stay opaque.'],
            color_legend=[('input','Inputs'),('mixing','Propagation'),('linear','Parameters'),('norm','Add / norm'),
                          ('tensor','Tensor ops'),('softmax','Gates'),('control','Topology'),('output','Output')],**fields))


def validate(ir,key,required,links,profile=None,source_ports=None):
    n={node['id']:node for node in ir['nodes']};checks=[]
    def check(ok,label):
        if not ok:raise ValueError(key+': '+label)
        checks.append(label)
    check(ir.get('artifact_scope')==ir['profile'].get('artifact_scope')=='module'
          and ir['profile']['model_executed'] is False,'static module-only scope')
    for identity,fields in required.items():
        identity=key+'.'+identity
        check(identity in n and all(n[identity].get(k)==v for k,v in fields.items()),'node contract '+identity)
    for src,dst,port,*role in links:
        check(any(e['src']==key+'.'+src and e['dst']==key+'.'+dst and e['dst_port']==port
                  and (not role or e['role']==role[0]) for e in ir['edges']),f'actual operand {src} -> {dst}:{port}')
    for field,value in (profile or {}).items():check(ir['profile'].get(field)==value,'profile '+field)
    for src,dst,port,source_port in source_ports or []:
        check(any(e['src']==key+'.'+src and e['dst']==key+'.'+dst and e['dst_port']==port
                  and e['src_port']==source_port for e in ir['edges']),
              f'typed source port {src}:{source_port} -> {dst}:{port}')
    check(not any(e['role'] in ('fork','dispatch') for e in ir['edges']),'no artificial shared input fork')
    return checks
