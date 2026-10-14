"""Declaration helpers for the reviewed extended vision modules.

No upstream model is imported. Declaration equality guards protect serialized IR;
the separate checks/vision_extended.py establishes independent source contracts.
"""
from module_adapters.support import chain, op, parallel, graph, ref, finish
from evidence import semantic_ir, walk
import json


def shape(c, h, w=None):
    return f"[B,{c},{h},{h if w is None else w}]"


class Author:
    def __init__(self, key, source, symbol):
        self.key, self.source, self.symbol = key, source, symbol
        self.init = ref(source, symbol + ".__init__")
        self.forward = ref(source, symbol + ".forward")
        self.refs = [self.init, self.forward]
        self.roles = {key+'.root':'root',key+'.input':'input',key+'.output':'output',key+'.module':'encoder'}

    def node(self, suffix, label, kind, out='', source=None, role=None, **attrs):
        identity=self.key+'.'+suffix
        self.roles[identity]=role or kind
        sources=source or self.refs
        return op(identity,label,kind,list(sources) if isinstance(sources,list) else sources,out,width=300,**attrs)

    def chain(self,suffix,label,items,out='',expand=1,source=None,role='group',**attrs):
        identity=self.key+'.'+suffix;self.roles[identity]=role
        sources=source or self.refs
        return chain(identity,label,items,list(sources) if isinstance(sources,list) else sources,out,expand=expand,**attrs)

    def parallel(self,suffix,label,items,out='',expand=1,source=None,dispatch=False,**attrs):
        identity=self.key+'.'+suffix;self.roles[identity]='inner'
        sources=source or self.refs
        return parallel(identity,label,items,list(sources) if isinstance(sources,list) else sources,out,expand=expand,
                        collection_type='list',literal_tuple=False,dispatch=dispatch,**attrs)

    def conv(self,suffix,parameter,cin,cout,k=1,s=1,p=0,d=1,g=1,bias=True,out=''):
        return self.node(suffix,f'Conv {k} / {cin}→{cout}','conv',out,role='conv',
                         parameter=parameter,instance_identity=self.key+'.'+parameter,learnable=True,
                         in_channels=cin,out_channels=cout,kernel_size=k,stride=s,padding=p,
                         dilation=d,groups=g,bias=bias,source_operation='nn.Conv2d')

    def bn(self,suffix,parameter,c,out='',eps=1e-5):
        return self.node(suffix,'BatchNorm','batch_norm2d',out,role='norm',
                         parameter=parameter,instance_identity=self.key+'.'+parameter,learnable=True,
                         num_features=c,eps=eps,momentum=.1,affine=True,track_running_stats=True)

    def relu(self,suffix,out='',inplace=False):
        return self.node(suffix,'ReLU','relu',out,role='activation',inplace=inplace,learnable=False)

    def conv_bn_relu(self,suffix,scope,cin,cout,k=1,s=1,p=0,d=1,g=1,out='',eps=1e-5,expand=2,inplace=False):
        return self.chain(suffix,f'Conv {k} + BN + ReLU',[
            self.conv(suffix+'.conv',scope+'.0',cin,cout,k,s,p,d,g,False,out),
            self.bn(suffix+'.bn',scope+'.1',cout,out,eps),self.relu(suffix+'.relu',out,inplace),
        ],out,expand=expand,role='conv',parameter_scope=scope)

    def model(self,name,doc,body,input_shape,output_shape,profile,facts,corrections=None,
              aux=None,edges=None,symbols=None,legend=None,root=None):
        if root is None:
            root=self.chain('root',name+' / module',[
                self.node('input','Module input','input',input_shape,learnable=False),body,
                self.node('output','Module output','output',output_shape,learnable=False),
            ],output_shape,expand=0,role='root')
        profile=dict(profile,input_shape=input_shape,output_shape=output_shape,
                     shape_origin='explicit static module profile; not observed',mode=profile.get('mode','caller train/eval; not executed'))
        return finish(dict(key=self.key,name=name,doc=doc,module_scope=profile['scope'],
            source_project=self.source.split('/')[0],entry=ref(self.source,self.symbol),
            profile=profile,profile_label=profile.get('constructor',profile['scope']),tree=root,
            visual_roles=self.roles,fill_width=[],aux_inputs=aux or [],extra_edges=edges or [],
            config_files=[self.source],symbols={self.source:symbols or [self.symbol,self.symbol+'.__init__',self.symbol+'.forward']},
            facts=facts,corrections=corrections or [],
            color_legend=legend or [(r,l) for r,l in [('input','Input'),('conv','Conv'),('norm','BN'),('concat','Concat'),('pool','Pool'),('linear','Learned parameter'),('tensor','Tensor'),('activation','Activation'),('control','Control'),('output','Output')] if r in self.roles.values()],
            legend=['Declared module scope; source code and kernels are not executed.',
                    'Different parameter paths own independent weights; colors express operation roles.']))


def validate_declaration(ir,model):
    """Protect all declared semantic attributes and exact reviewed endpoints.

    This consistency check is deliberately separate from independent AST/source
    contracts. It does not claim automatic model semantics extraction.
    """
    references={s for n in walk(model['tree']) for s in n['source']}
    references.update(s for aux in model.get('aux_inputs',[]) for n in walk(aux) for s in n['source'])
    evidence=dict(symbols={s:dict(evidence_id=s) for s in references},repository='',commit='',source_snapshot_sha256='')
    expected=semantic_ir(model,evidence)
    canonical=lambda value:json.loads(json.dumps(value))
    if ir.get('artifact_scope')!='module' or canonical(ir['profile'])!=canonical(expected['profile']):
        raise ValueError(model['key']+': selected module configuration differs')
    actual={n['id']:n for n in ir['nodes']};wanted={n['id']:n for n in expected['nodes']}
    if len(actual)!=len(ir['nodes']) or set(actual)!=set(wanted):
        raise ValueError(model['key']+': missing, duplicate or invented node')
    checked=[]
    for identity,node in wanted.items():
        a={k:v for k,v in actual[identity].items() if k!='source_evidence'}
        b={k:v for k,v in node.items() if k!='source_evidence'}
        if canonical(a)!=canonical(b):raise ValueError(model['key']+': operator/configuration/parameter identity differs: '+identity)
        checked.append(identity+': exact declared operator and source identity')
    if ir['edges']!=expected['edges']:
        raise ValueError(model['key']+': reviewed tensor/operand endpoint or port differs')
    return checked+['exact source-grounded dependency endpoints','module scope and explicit profile']
