"""Source FilterResponseNormalization: per-instance second moment + learned TLU."""
from module_adapters.support import chain,op,graph,ref,finish
SOURCE='rasbt-modules/pytorch_ipynb/cnn/nin-cifar10_filter-response-norm.py'

def build():
    init=ref(SOURCE,'FilterResponseNormalization.__init__');fwd=ref(SOURCE,'FilterResponseNormalization.forward')
    shape='[B,192,32,32]';stat='[B,192,1,1]';p='frn'
    norm=chain(p+'.norm','Response normalization',[
        op(p+'.square','Elementwise x^2','power',fwd,shape,exponent=2),
        op(p+'.mean','Mean over H,W','reduce_mean',fwd,stat,
           ['torch.mean(x.pow(2),(2,3),keepdims=True); no batch reduction'],dims=[2,3],keepdims=True,
           statistic='uncentered second moment'),
        op(p+'.eps_add','nu2 + abs(eps)','add',fwd,stat,expression='nu2 + torch.abs(self.eps)'),
        op(p+'.rsqrt','Reciprocal square root','rsqrt',fwd,stat,expression='torch.rsqrt(nu2 + abs(eps))'),
        op(p+'.scale','Retained x * rsqrt','multiply',fwd,shape,
           ['same original x; per-B/per-channel spatial broadcast'],broadcast_axes=[2,3]),
    ],fwd,shape,expand=2,retained_input=True)
    affine=chain(p+'.affine','Affine + learned threshold',[
        op(p+'.gamma_mul','gamma * normalized x','multiply',[init,fwd],shape,parameter='gamma',broadcast_axes=[0,2,3]),
        op(p+'.beta_add','Add beta','add',[init,fwd],shape,parameter='beta',broadcast_axes=[0,2,3]),
        op(p+'.threshold','Elementwise max(y,tau)','maximum',[init,fwd],shape,
           ['torch.max(tensor,tensor); learned per-channel threshold, not max reduction or ReLU'],
           parameter='tau',operation='elementwise_maximum',reduction=False),
    ],[init,fwd],shape,expand=2)
    body=chain(p+'.module','FRN / learned TLU', [norm,affine],[init,fwd],shape,expand=1)
    params=[]
    for key in ['gamma','beta','tau']:
        params.append(op(p+'.'+key,key+' / channel Parameter','parameter',init,'[1,192,1,1]',
                         ['torch.empty(...).normal_(); separate learnable channel entries'],
                         parameter=key,learnable=True,initialization='normal_'))
    params.append(op(p+'.epsilon','eps / ordinary tensor','constant',[init,fwd],'[1]',
                     ['eps=1e-6; neither Parameter nor registered buffer; to(tau.device) in forward'],
                     attribute_identity='eps',value=1e-6,learnable=False,registered_buffer=False,
                     device_assignment='self.eps = self.eps.to(self.tau.device)'))
    state=graph(p+'.state','Parameters / constant',params,[init,fwd],'module-owned state',expand=2,
                ranks=[[n['id']] for n in params],rank_gap=48)
    edges=[dict(src=p+'.epsilon',dst=p+'.eps_add',role='constant_operand',src_port='out',dst_port='epsilon',label='abs(eps)')]
    for key,target in [('gamma','gamma_mul'),('beta','beta_add'),('tau','threshold')]:
        edges.append(dict(src=p+'.'+key,dst=p+'.'+target,role='parameter_operand',src_port='out',dst_port=key,label=key))
    tree=chain(p+'.root','FRN + TLU module',[
        op(p+'.input','Feature map x','input',fwd,shape),body,
        op(p+'.output','Normalized / thresholded x','output',fwd,shape),
    ],ref(SOURCE,'FilterResponseNormalization'),shape,expand=0)
    roles={p+'.root':'root',p+'.input':'input',p+'.output':'output',p+'.module':'encoder',p+'.norm':'norm',p+'.affine':'ffn',p+'.state':'control',
           p+'.square':'tensor',p+'.mean':'pool',p+'.eps_add':'norm',p+'.rsqrt':'norm',p+'.scale':'tensor',
           p+'.gamma_mul':'linear',p+'.beta_add':'norm',p+'.threshold':'activation',p+'.epsilon':'control'}
    roles.update({p+'.'+key:'linear' for key in ['gamma','beta','tau']})
    return finish(dict(key='frn_tlu',name='FRN + learned TLU',doc='FRN_TLU.md',
        module_scope='仅 FilterResponseNormalization 类；不画 NiN 的卷积与分类头',source_project='rasbt-modules',
        entry=ref(SOURCE,'FilterResponseNormalization'),tree=tree,aux_inputs=[state],extra_edges=edges,
        profile=dict(num_features=192,input_shape=shape,eps=1e-6,mode='train/eval same formula',
                     selected_configuration='192-channel32x32 example; FRN class direct module scope',
                     statistic='mean(x^2) over H,W only',mean_centered=False,running_statistics=False,
                     learnable_parameters=['gamma','beta','tau'],parameter_shape=[1,192,1,1],initialization='normal_ for all3',
                     eps_registered_buffer=False,threshold='maximum(gamma*x_hat+beta,tau)',
                     notebook_redefinition_boundary='NiN is redefined later as BN; selected module is the unique FRN class, not final NiN binding'),
        profile_label='192 channels / H,W second moment / gamma,beta,tau / eps1e-6 / shape-preserving',
        visual_roles=roles,fill_width=[p+'.module',p+'.norm',p+'.affine'],config_files=[SOURCE],
        color_legend=[('input','Input'),('norm','Normalize / Add'),('pool','Spatial mean'),
                      ('tensor','Square / Scale'),('linear','Channel params'),('activation','Learned TLU'),
                      ('control','Plain eps'),('output','Output')],
        facts=[
            'Unique FilterResponseNormalization class computes mean(x.pow(2),(2,3),keepdims=True); no subtraction of mean, batch reduction or running statistics.',
            'Original x multiplies rsqrt(nu2+abs(eps)); this retained input is a different value from the squared/statistic branch.',
            'gamma,beta,tau are three registered Parameters of shape[1,C,1,1], each initialized with normal_ rather than usual FRN ones/zeros.',
            'Threshold is torch.max(gamma*x_hat+beta,tau), an elementwise learned TLU; not a max-pool, scalar reduction or fixedzeroReLU.',
            'eps is a plain Tensor attribute, not registered buffer/Parameter; forward explicitly moves it to tau.device.',
            'Notebook later redefines NiN as a BN model. This example scopes the unique FRN class directly and does not claim the final NiN binding uses FRN.',
        ],corrections=[
            'Do not reuse BatchNorm/LayerNorm statistics: source normalizes uncentered second moment over H,W separately for each B,C.',
            'Do not set gamma=1/beta=tau=0 merely from the usual paper defaults; this source initializes all3 with normal_.',
            'Do not draw eps as a learned parameter or registered buffer; its source storage identity differs.',
            'Do not silently bind the duplicated NiN symbol; only the unique FilterResponseNormalization class is selected.',
        ],symbols={SOURCE:['FilterResponseNormalization','FilterResponseNormalization.__init__','FilterResponseNormalization.forward']},
        legend=['B=batch; C=192; no mixing across batch or channels; shape unchanged.',
                'Retained x enters normalization Multiply; independent gamma,beta,tau enter their own operators.',
                'Parameter panel is containment only, no fake sequence between gamma/beta/tau/eps.']))

def validate_ir(ir):
    n={v['id']:v for v in ir['nodes']};p=ir['profile'];e=ir['edges'];checks=[]
    def check(c,s):
        if not c:raise ValueError('FRN: '+s)
        checks.append(s)
    def has(a,b,r=None):return any(x['src']==a and x['dst']==b and (r is None or x['role']==r) for x in e)
    check(p['num_features']==192 and p['mean_centered'] is False and p['running_statistics'] is False,'selected C; no centered or running statistics')
    check(n['frn.mean']['dims']==[2,3] and n['frn.mean']['keepdims'] and n['frn.square']['exponent']==2,'perB,C H,W second moment')
    check(has('frn.norm','frn.scale','retained_input') and has('frn.rsqrt','frn.scale'),'original x and rsqrt both enter normalization Multiply')
    check(n['frn.epsilon']['value']==1e-6 and n['frn.epsilon']['registered_buffer'] is False and n['frn.epsilon']['learnable'] is False,'plain eps tensor attribute, abs epsilon')
    check(has('frn.epsilon','frn.eps_add','constant_operand') and has('frn.mean','frn.eps_add'),'epsilon and second-moment add')
    check(p['learnable_parameters']==['gamma','beta','tau'] and all(n['frn.'+k]['initialization']=='normal_' for k in p['learnable_parameters']),'three distinct normal-initialized Parameters')
    check(n['frn.threshold']['operation']=='elementwise_maximum' and n['frn.threshold']['reduction'] is False,'learned TLU elementwise max')
    check(has('frn.gamma','frn.gamma_mul','parameter_operand') and has('frn.beta','frn.beta_add','parameter_operand') and has('frn.tau','frn.threshold','parameter_operand'),'parameter identity and operand endpoints')
    check(not any(x['src'] in ['frn.gamma','frn.beta','frn.tau'] and x['dst'] in ['frn.gamma','frn.beta','frn.tau','frn.epsilon'] for x in e),'state panel introduces no tensor chain')
    return checks
