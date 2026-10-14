"""Reviewed Large v0.9.0 model, bound to the CIFAR caller and actual library."""
from spec import chain, op, ref

CALLER = 'deeplearning-models-batch4/pytorch_ipynb/cnn/cnn-mobilenet-v3-large-cifar10.py'
MODEL = 'torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv3.py'
CBA_SOURCE = 'torchvision-v0.9.0-mobilev3/torchvision/models/mobilenetv2.py'
# cin, kernel, expanded, cout, SE, activation, stride, dilation; width=1.
CONFIGS = [
    [16,3,16,16,False,'RE',1,1], [16,3,64,24,False,'RE',2,1],
    [24,3,72,24,False,'RE',1,1], [24,5,72,40,True,'RE',2,1],
    [40,5,120,40,True,'RE',1,1], [40,5,120,40,True,'RE',1,1],
    [40,3,240,80,False,'HS',2,1], [80,3,200,80,False,'HS',1,1],
    [80,3,184,80,False,'HS',1,1], [80,3,184,80,False,'HS',1,1],
    [80,3,480,112,True,'HS',1,1], [112,3,672,112,True,'HS',1,1],
    [112,5,672,160,True,'HS',2,1], [160,5,960,160,True,'HS',1,1],
    [160,5,960,160,True,'HS',1,1],
]
STAGES = [[1],[2,3],[4,5,6],[7,8,9,10],[11,12],[13,14,15]]
REPRESENTATIVES = [1,4,12]


def squeeze_channels(expanded):
    # Pure static arithmetic matching the imported _make_divisible; no model import.
    channels = expanded // 4
    result = max(8, int(channels + 4) // 8 * 8)
    return result + 8 if result < .9 * channels else result


def build():
    caller = ref(CALLER, '__module__')
    init, fwd = ref(MODEL,'MobileNetV3.__init__'), ref(MODEL,'MobileNetV3._forward_impl')
    bi, bf = ref(MODEL,'InvertedResidual.__init__'), ref(MODEL,'InvertedResidual.forward')
    conf = ref(MODEL,'_mobilenet_v3_conf')
    cba = ref(CBA_SOURCE,'ConvBNActivation.__init__')
    si, ss, sf = [ref(MODEL,'SqueezeExcitation.'+n) for n in ('__init__','_scale','forward')]
    roles, fill = {}, []
    def cba_group(p,label,cin,cout,k,s,groups,side,scope,activation,owner,expand=2):
        shape = f'[B,{cout},{side},{side}]'
        roles.update({p:'conv',p+'.conv':'conv',p+'.bn':'norm',p+'.act':'activation'})
        return chain(p,label,[
            op(p+'.conv',f'Conv{k}x{k} {cin} -> {cout}','conv2d',[cba,owner],shape,
               [f'stride={s}; groups={groups}; bias=False; padding={(k-1)//2}'],
               parameter=scope+'.0',in_channels=cin,out_channels=cout,kernel_size=k,
               stride=s,groups=groups,padding=(k-1)//2,bias=False),
            op(p+'.bn','BatchNorm2d','batch_norm2d',[cba,init],shape,
               ['eval: running statistics; eps=0.001; momentum=0.01'],
               parameter=scope+'.1',eps=.001,momentum=.01),
            op(p+'.act',activation,activation.lower(),[cba,owner],shape,
               ['Identity: no nonlinear activation' if activation=='Identity' else 'inplace=True'],
               instance_identity=scope+'.2',learnable=False),
        ],[cba,owner],shape,expand=expand,activation=activation)
    def se_group(p,expanded,side,scope):
        small=squeeze_channels(expanded); scale=f'[B,{expanded},1,1]';shape=f'[B,{expanded},{side},{side}]'
        roles.update({p:'attention',p+'.pool':'pool',p+'.fc1':'linear',p+'.relu':'activation',
                      p+'.fc2':'linear',p+'.gate':'softmax',p+'.multiply':'tensor'})
        fill.append(p)
        return chain(p,'Squeeze / excitation',[
            op(p+'.pool','Adaptive average pool 1x1','adaptive_avg_pool2d',ss,scale),
            op(p+'.fc1',f'Conv1x1 {expanded} -> {small}','conv2d',[si,ss],f'[B,{small},1,1]',
               ['squeeze = _make_divisible(expanded//4,8); bias=True'],
               parameter=scope+'.fc1',in_channels=expanded,out_channels=small,kernel_size=1,bias=True),
            op(p+'.relu','ReLU','relu',[si,ss],f'[B,{small},1,1]',learnable=False),
            op(p+'.fc2',f'Conv1x1 {small} -> {expanded}','conv2d',[si,ss],scale,
               ['bias=True; restores expanded channel count'],parameter=scope+'.fc2',
               in_channels=small,out_channels=expanded,kernel_size=1,bias=True),
            op(p+'.gate','Hardsigmoid channel gate','hardsigmoid',ss,scale,learnable=False),
            op(p+'.multiply','Scale * retained input','multiply',sf,shape,
               ['[B,C,1,1] gate broadcasts across H,W; original depthwise features retained'],
               broadcast=True,learnable=False),
        ],[si,ss,sf],shape,expand=2,retained_input=True,
           squeeze_channels=small,expanded_channels=expanded,parameter_scope=scope)
    blocks=[];side=32
    for i,c in enumerate(CONFIGS,1):
        cin,k,expanded,cout,se,act,s,d=c;input_side=side;side=(side+s-1)//s
        p=f'm3.block{i}';scope=f'features.{i}.block';activation='Hardswish' if act=='HS' else 'ReLU'
        parts=[];idx=0
        if expanded!=cin:
            parts.append(cba_group(p+'.expand','Pointwise expansion',cin,expanded,1,1,1,input_side,
                                   scope+f'.{idx}',activation,bi));idx+=1
        parts.append(cba_group(p+'.depthwise','Depthwise spatial convolution',expanded,expanded,k,s,expanded,
                               side,scope+f'.{idx}',activation,bi));idx+=1
        if se:
            parts.append(se_group(p+'.se',expanded,side,scope+f'.{idx}'));idx+=1
        parts.append(cba_group(p+'.project','Linear pointwise projection',expanded,cout,1,1,1,
                               side,scope+f'.{idx}','Identity',bi))
        residual=s==1 and cin==cout;shape=f'[B,{cout},{side},{side}]'
        if residual:
            parts.append(op(p+'.add','Add identity input','add',bf,shape,
                            ['result += input; no activation after Add'],learnable=False));roles[p+'.add']='norm'
        roles[p]='conv';fill.append(p)
        blocks.append(chain(p,f'IR {i} / '+('SE / ' if se else '')+activation+(' / skip' if residual else ' / no skip'),
                            parts,[conf,bi,bf],shape,
                            [f'{cin}->{expanded}->{cout}; k{k}; s{s}; '+('expansion omitted' if cin==expanded else 'expand1x1'),
                             'Depthwise -> SE -> project-BN-Identity' if se else 'Depthwise -> project-BN-Identity'],
                            expand=2 if i in REPRESENTATIVES else 3,residual=residual,
                            parameter_scope=scope,feature_index=i,configuration=c,
                            expansion_present=expanded!=cin,use_se=se,use_res_connect=residual,
                            input_side=input_side,output_side=side,project_index=idx))
    stem=cba_group('m3.stem','Stem / Hardswish',3,16,3,2,1,32,'features.0','Hardswish',init,expand=1)
    stages=[]
    for i,indices in enumerate(STAGES,1):
        p=f'm3.stage{i}';last=blocks[indices[-1]-1]
        roles[p]='encoder';fill.append(p)
        stages.append(chain(p,f'Stage {i} / IR '+','.join(map(str,indices)),[blocks[j-1] for j in indices],
                            [init,conf],last['shape'],
                            ['logical grouping by output channels; actual features is one Sequential'],expand=1,
                            feature_indices=indices))
    last=cba_group('m3.last','Final pointwise / Hardswish',160,960,1,1,1,2,'features.16','Hardswish',init,expand=1)
    head=chain('m3.head','CIFAR-10 classifier',[
        op('m3.pool','Adaptive average pool 1x1','adaptive_avg_pool2d',[init,fwd],'[B,960,1,1]',
           instance_identity='avgpool',learnable=False),
        op('m3.flatten','Flatten from dimension 1','flatten',fwd,'[B,960]',
           ['torch.flatten(x,1); preserves B=1 batch axis'],start_dim=1,learnable=False),
        op('m3.fc1','Linear 960 -> 1280','linear',[init,fwd],'[B,1280]',parameter='classifier.0'),
        op('m3.head_act','Hardswish','hardswish',[init,fwd],'[B,1280]',instance_identity='classifier.1',learnable=False),
        op('m3.dropout','Dropout 0.2 / eval identity','dropout',[init,fwd,caller],'[B,1280]',
           ['inplace=True; inactive in selected eval profile'],instance_identity='classifier.2',p=.2,learnable=False),
        op('m3.fc2','Replaced Linear 1280 -> 10','linear',[init,fwd,caller],'logits: [B,10]',
           ['caller replaces classifier[-1]; new nn.Linear default initialization'],parameter='classifier.3',
           in_features=1280,out_features=10,replaced_by_caller=True),
    ],[init,fwd,caller],'logits: [B,10]',expand=1)
    tree=chain('m3.model','MobileNetV3-Large / CIFAR-10',[
        op('m3.input','CIFAR-10 image','input',[caller,fwd],'[B,3,64,64]',
           ['test: Resize70 -> CenterCrop64 -> tensor -> Normalize(mean=std=.5)']),
        stem,*stages,last,head,
        op('m3.output','Returned logits','output',[fwd,ref(MODEL,'MobileNetV3.forward')],'[B,10]',
           ['no model-forward Softmax']),
    ],[caller,ref(MODEL,'mobilenet_v3_large'),init],'[B,10]',expand=0)
    roles.update({'m3.model':'root','m3.input':'input','m3.output':'output','m3.head':'ffn',
                  'm3.pool':'pool','m3.flatten':'tensor','m3.fc1':'linear','m3.head_act':'activation',
                  'm3.dropout':'control','m3.fc2':'linear'})
    return dict(key='mobilenetv3',name='MobileNetV3-Large (CIFAR-10)',
                source_project='deeplearning-models-batch4',source_projects=['torchvision-v0.9.0-mobilev3'],
                entry=ref(MODEL,'MobileNetV3'),tree=tree,aux_inputs=[],extra_edges=[],
                profile=dict(task='CIFAR-10 classification',mode='eval',input_channels=3,input_size=[64,64],
                             constructor="torch.hub.load('pytorch/vision:v0.9.0','mobilenet_v3_large',pretrained=False)",
                             pretrained=False,width_mult=1.,reduced_tail=False,dilated=False,
                             configs=CONFIGS,stages=STAGES,total_blocks=15,se_blocks=[4,5,6,11,12,13,14,15],
                             residual_blocks=[1,3,5,6,8,9,10,12,14,15],representative_blocks=REPRESENTATIVES,
                             stage_channels=[16,24,40,80,112,160],stage_spatial=[32,16,8,4,4,2],
                             final_feature_channels=960,classifier_hidden=1280,num_classes=10,
                             dropout=.2,output='logits',forward_softmax=False,symbolic_shapes=True,model_executed=False),
                profile_label='CIFAR-10 / Crop64 / Large v0.9.0 / width1 / replaced head / eval',
                visual_roles=roles,fill_width=fill+['m3.stem','m3.last','m3.head'],
                config_files=[CALLER],symbols={CALLER:['__module__'],
                    MODEL:['MobileNetV3','InvertedResidualConfig.__init__','InvertedResidualConfig.adjust_channels',
                           '_mobilenet_v3_conf','_mobilenet_v3_model','mobilenet_v3_large'],
                    CBA_SOURCE:['_make_divisible','ConvBNActivation.__init__']},
                facts=[
                    'Notebook cell12 chooses torchvision v0.9.0 Large, pretrained=False, then replaces classifier[-1] with Linear(1280,10); cell14 explicitly selects eval.',
                    'Independent snapshots preserve the Notebook caller and the exact imported library implementation; the caller checkpoint filename mentions v2 but its construction is V3.',
                    'The 15 InvertedResidual configs are [cin,kernel,expanded,cout,se,activation,stride,dilation], with width1, no reduced tail and dilation1.',
                    'Stem is3->16, Hardswish, stride2; logical output-channel stages are16,24,40,80,112,160 with64-crop spatial sizes32,16,8,4,4,2.',
                    'Expansion is omitted only when expanded==cin (IR1); depthwise groups equals expanded channels.',
                    'RE means ReLU; HS means Hardswish. Each project is Conv1x1+BN+Identity, followed by identity Add only for stride1 with equal input/output channels.',
                    'Eight SE blocks use rounded squeeze width, pool->Conv1x1->ReLU->Conv1x1->Hardsigmoid->broadcast scale*retained depthwise features, before projection.',
                    'Ten original-input residual Adds have no following activation; all blocks have independent feature-index parameter scopes.',
                    'Final Conv160->960 precedes pool1, flatten fromdim1, Linear960->1280, Hardswish, Dropout.2 and replacement Linear1280->10; model returns logits only.',
                    'Every block and operator remains in semantic IR. Detailed rendering expands IR1(no expansion), IR4(SE/ReLU/no skip), IR12(SE/Hardswish/skip); other blocks retain exact config and parameter identities in folded boxes.',
                ],corrections=[
                    'Do not substitute modern torchvision source or MobileNetV2 merely because the checkpoint filename contains v2.',
                    'Do not copy224 input or1000-class output: selected Notebook uses64x64 CIFAR images and a replaced10-class head.',
                    'The final feature width is960, not1280;1280 is the hidden classifier width in this Large configuration.',
                    'SE gate is Hardsigmoid, not Sigmoid/Softmax, and its reduction uses _make_divisible rather than an unrounded C/4.',
                    'Project has Identity rather than ReLU/Hardswish; do not add a projection shortcut to stride2/channel-changing blocks.',
                    'SE multiplication retains depthwise features while the residual Add retains the block input; these two routes refer to different tensors.',
                ],legend=[
                    'B=batch; [B,C,H,W]; all module internals follow bottom-to-top flow.',
                    'Blue Conv / orange SE / yellow BN or Add / purple Linear / green Hardsigmoid gate.',
                    'SE retained-feature route and block identity shortcut have different source endpoints; color never implies shared weights.',
                    'IR1,4,12 expand; all15 configs and parameter scopes remain in the source-bound IR.',
                ])


def validate_ir(ir):
    nodes={n['id']:n for n in ir['nodes']};p=ir['profile'];edges=ir['edges'];checks=[]
    def check(condition,label):
        if not condition:raise ValueError('MobileNetV3: '+label)
        checks.append(label)
    def has(a,b,role='tensor'):
        return any(e['src']==a and e['dst']==b and e['role']==role for e in edges)
    check(p['configs']==CONFIGS and p['total_blocks']==15,'exact v0.9.0 Large configs;15 independent blocks')
    check(p['mode']=='eval' and p['input_size']==[64,64] and p['num_classes']==10,'caller64-crop replaced10-class eval profile')
    for i,c in enumerate(CONFIGS,1):
        cin,k,expanded,cout,se,act,s,d=c;n=nodes[f'm3.block{i}'];prefix=n['id'];scope=f'features.{i}.block'
        check(n['configuration']==c and n['feature_index']==i and n['parameter_scope']==scope,f'IR{i} config and parameter scope')
        check(n['expansion_present']==(expanded!=cin) and ((prefix+'.expand') in nodes)==(expanded!=cin),f'IR{i} conditional expansion')
        dw=nodes[prefix+'.depthwise.conv']
        check(dw['groups']==expanded and dw['in_channels']==expanded and dw['out_channels']==expanded and dw['kernel_size']==k and dw['stride']==s,f'IR{i} depthwise channel groups and spatial kernel')
        activation='hardswish' if act=='HS' else 'relu'
        check(nodes[prefix+'.depthwise.act']['kind']==activation and nodes[prefix+'.project.act']['kind']=='identity',f'IR{i} selected activation and linear projection')
        residual=s==1 and cin==cout
        check(n['use_res_connect']==residual and n['residual']==residual and ((prefix+'.add') in nodes)==residual,f'IR{i} conditional identity Add')
        if residual:
            check(has(prefix,prefix+'.add','residual') and has(prefix+'.project',prefix+'.add'),f'IR{i} retained block input enters final Add')
        check(n['use_se']==se and ((prefix+'.se') in nodes)==se,f'IR{i} SE presence')
        if se:
            sn=nodes[prefix+'.se'];sq=squeeze_channels(expanded)
            check(sn['squeeze_channels']==sq and nodes[prefix+'.se.fc1']['out_channels']==sq and nodes[prefix+'.se.fc2']['out_channels']==expanded,f'IR{i} rounded SE channels')
            check(nodes[prefix+'.se.gate']['kind']=='hardsigmoid' and has(prefix+'.se',prefix+'.se.multiply','retained_input') and has(prefix+'.se.gate',prefix+'.se.multiply') and has(prefix+'.depthwise',prefix+'.se') and has(prefix+'.se',prefix+'.project'),f'IR{i} gate multiplies retained depthwise tensor before project')
            check(nodes[prefix+'.se.fc1']['bias'] is True and nodes[prefix+'.se.fc2']['bias'] is True,f'IR{i} SE conv bias')
    check(sum(n['kind']=='add' for n in nodes.values())==10 and sum(n['kind']=='multiply' for n in nodes.values())==8,'ten residual Adds and eight SE multiplications')
    check(nodes['m3.last.conv']['in_channels']==160 and nodes['m3.last.conv']['out_channels']==960 and nodes['m3.flatten']['shape']=='[B,960]' and nodes['m3.flatten']['start_dim']==1,'960 final features; batch-preserving flatten')
    check(nodes['m3.fc1']['parameter']=='classifier.0' and nodes['m3.fc2']['parameter']=='classifier.3' and nodes['m3.fc2']['in_features']==1280 and nodes['m3.fc2']['out_features']==10 and nodes['m3.fc2']['replaced_by_caller'],'original hidden Linear and exact caller replacement identity')
    check(has('m3.fc1','m3.head_act') and has('m3.head_act','m3.dropout') and has('m3.dropout','m3.fc2') and p['forward_softmax'] is False and not any(n['kind']=='softmax' for n in nodes.values()),'classifier order; logits-only return')
    check(all(n['eps']==.001 and n['momentum']==.01 for n in nodes.values() if n['kind']=='batch_norm2d'),'V3 BatchNorm eps and momentum')
    return checks
