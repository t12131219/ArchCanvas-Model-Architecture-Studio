"""Two-layer Highway module with source's learned linear carry, not identity."""
from module_adapters.support import chain,op,graph,ref,finish
SOURCE='pytorch-highway/highway/highway.py'

def build():
    init=ref(SOURCE,'Highway.__init__');fwd=ref(SOURCE,'Highway.forward');shape='[B,16]';edges=[];roles={}
    def edge(a,b,role='tensor',sp='out',dp='in',label=''):
        edges.append(dict(src=a,dst=b,role=role,src_port=sp,dst_port=dp,label=label,dashed=False,
                          src_side='out',dst_side='in'))
    layers=[]
    for i in range(2):
        p=f'highway.layer{i}';producer='highway.input' if i==0 else 'highway.layer0.add'
        gate=chain(p+'.gate','Transform gate',[
            op(p+'.gate_linear','Linear 16 -> 16','linear',init,shape,parameter=f'gate.{i}',bias=True),
            op(p+'.sigmoid','Sigmoid gate g','sigmoid',fwd,shape,expression=f'F.sigmoid(self.gate[{i}](x))'),
        ],[init,fwd],shape,expand=2)
        nonlinear=chain(p+'.nonlinear','Nonlinear transform',[
            op(p+'.nonlinear_linear','Linear 16 -> 16','linear',init,shape,parameter=f'nonlinear.{i}',bias=True),
            op(p+'.relu','Selected f = ReLU','relu',fwd,shape,
               ['callable f supplied explicitly in this example; source does not fix activation'],configuration='f=F.relu'),
        ],[init,fwd],shape,expand=2)
        linear=chain(p+'.carry','Learned linear carry',[
            op(p+'.carry_linear','Linear 16 -> 16','linear',[init,fwd],shape,
               ['source self.linear[layer](x); this branch is not identity x'],parameter=f'linear.{i}',bias=True),
        ],[init,fwd],shape,expand=2)
        complement=op(p+'.complement','1 - g','subtract',fwd,shape,expression='1 - gate')
        left=op(p+'.nonlinear_product','g * nonlinear','multiply',fwd,shape,operands=['gate','nonlinear'])
        right=op(p+'.carry_product','(1-g) * linear','multiply',fwd,shape,operands=['complement','linear'])
        add=op(p+'.add','Add gated branches','add',fwd,shape,
               ['x = gate * nonlinear + (1-gate) * linear'],expression='gate * nonlinear + (1 - gate) * linear')
        layer=graph(p,f'Highway layer {i} / independent weights',
                    [gate,nonlinear,linear,complement,left,right,add],[init,fwd],shape,expand=1 if i==0 else 3,
                    ranks=[[gate['id'],nonlinear['id'],linear['id']],[complement['id']],
                           [left['id'],right['id']],[add['id']]],rank_gap=72,column_gap=56,
                    layer_index=i,parameter_scopes=[f'gate.{i}',f'nonlinear.{i}',f'linear.{i}'],independent_parameters=True)
        layers.append(layer)
        for dst,name in [(gate['id'],'gate x'),(nonlinear['id'],'transform x'),(linear['id'],'carry x')]:
            edge(producer,dst,dp='in',label=name)
        edge(p+'.sigmoid',p+'.complement',label='g')
        edge(p+'.sigmoid',left['id'],dp='gate',label='g')
        edge(p+'.relu',left['id'],dp='value',label='nonlinear')
        edge(p+'.complement',right['id'],dp='gate',label='1-g')
        edge(p+'.carry_linear',right['id'],dp='value',label='linear')
        edge(left['id'],add['id'],dp='nonlinear',label='gated transform')
        edge(right['id'],add['id'],dp='carry',label='gated linear')
        roles.update({p:'encoder',gate['id']:'attention',nonlinear['id']:'ffn',linear['id']:'ffn',
                      p+'.gate_linear':'linear',p+'.sigmoid':'softmax',p+'.nonlinear_linear':'linear',p+'.relu':'activation',
                      p+'.carry_linear':'linear',complement['id']:'tensor',left['id']:'tensor',right['id']:'tensor',add['id']:'norm'})
    edge('highway.layer1.add','highway.output',label='x after layer1')
    items=[op('highway.input','Input features x','input',fwd,shape),*layers,op('highway.output','Highway output x','output',fwd,shape)]
    root=graph('highway.root','Highway module / two layers',items,[init,fwd],shape,expand=0,
               ranks=[[n['id']] for n in items],rank_gap=72)
    roles.update({'highway.root':'root','highway.input':'input','highway.output':'output'})
    return finish(dict(key='highway',name='Highway gated fusion',doc='Highway.md',
        module_scope='Highway(size=16,num_layers=2,f=F.relu) 模块；不包含任何任务头',
        source_project='pytorch-highway',entry=ref(SOURCE,'Highway'),tree=root,extra_edges=edges,
        profile=dict(size=16,num_layers=2,f='F.relu',configuration_origin='explicit module example; f and size are constructor arguments',
                     input_shape=shape,output_shape=shape,carry_is_identity=False,
                     formula='sigmoid(gate_i(x))*relu(nonlinear_i(x)) + (1-sigmoid(gate_i(x)))*linear_i(x)',
                     learned_linears=6,independent_parameters=True,shared_across_depth=False,mode='same train/eval formula'),
        profile_label='size16 / layers2 / supplied f=ReLU / learned linear carry / 6 independent Linear modules',
        visual_roles=roles,fill_width=[],config_files=[SOURCE],
        color_legend=[('input','Input'),('attention','Gate branch'),('ffn','Transforms'),
                      ('linear','Linear / Out'),('softmax','Sigmoid'),('norm','Add'),
                      ('tensor','Products / 1-g'),('activation','Selected f')],
        symbols={SOURCE:['Highway','Highway.__init__','Highway.forward']},
        facts=[
            'Three separate ModuleLists independently construct gate, nonlinear and linear transforms for each layer; six Linear modules for this2layer example.',
            'All3 paths consume the same current layer input; nonlinear is f(self.nonlinear[layer](x)); gate is F.sigmoid(self.gate[layer](x)).',
            'Source carry path is self.linear[layer](x), a learned affine transform, not original x.',
            'Two gated products use complementary g and1-g, then Add; next layer reads updated x and uses its own weights.',
            'Source accepts callable f without fixing it; f=F.relu,size16,layers2 are explicitly selected module example values.',
            'Graph ranks allocate space only; every branch input, product operand and inter-layer dependency is an explicit edge, no fake tuple.',
        ],corrections=[
            'Do not substitute textbook identity carry: source includes a learned linear branch.',
            'Do not use three independent gates: the complement uses exactly1-g from the same gate tensor.',
            'Do not share weights across Highway layers: the ModuleLists construct distinct Linear modules.',
            'Do not claim activation was recovered asReLU from source; it is the selected f callable.',
        ],legend=['B=batch; size16; first layer expands; layer1 keeps exact independent parameter scopes in IR.',
                'Orange gate / blue transforms / purple Linear / green Sigmoid / yellow Add.',
                'Three branch inputs are the same current x; carry is a learned Linear, not a skip identity.']))

def validate_ir(ir):
    n={v['id']:v for v in ir['nodes']};e=ir['edges'];p=ir['profile'];checks=[]
    def check(c,s):
        if not c:raise ValueError('Highway: '+s)
        checks.append(s)
    def has(a,b,dp=None):return any(x['src']==a and x['dst']==b and (dp is None or x['dst_port']==dp) for x in e)
    check(p['num_layers']==2 and p['size']==16 and p['f']=='F.relu','explicit module arguments')
    check(p['carry_is_identity'] is False and p['learned_linears']==6,'learned carry in six Linear modules')
    check({x['parameter'] for x in n.values() if x['kind']=='linear'}=={f'{k}.{i}' for k in ['gate','nonlinear','linear'] for i in range(2)},'six distinct source ModuleList parameter identities')
    for i in range(2):
        s=f'highway.layer{i}';x='highway.input' if i==0 else 'highway.layer0.add'
        check(all(has(x,s+'.'+b) for b in ['gate','nonlinear','carry']),'layer'+str(i)+' receives same current x at all3branches')
        check(has(s+'.sigmoid',s+'.complement') and n[s+'.complement']['expression']=='1 - gate','layer'+str(i)+' same complementary gate')
        check(has(s+'.sigmoid',s+'.nonlinear_product','gate') and has(s+'.relu',s+'.nonlinear_product','value'),'layer'+str(i)+' gate times nonlinear')
        check(has(s+'.complement',s+'.carry_product','gate') and has(s+'.carry_linear',s+'.carry_product','value'),'layer'+str(i)+' complement times learned carry')
        check(has(s+'.nonlinear_product',s+'.add','nonlinear') and has(s+'.carry_product',s+'.add','carry'),'layer'+str(i)+' explicit product sum')
    check(has('highway.layer1.add','highway.output'),'last layer output')
    return checks
