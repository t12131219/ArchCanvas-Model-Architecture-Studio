"""Independent AST contracts, frozen-source integrity and adversarial endpoints.

The contract tables below are independent of adapter build declarations. No
upstream Python module, model, PyTorch operator or checkpoint is executed.
"""
from __future__ import annotations
import ast,copy,hashlib,importlib,json,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
import bootstrap
if str(bootstrap.SHARED) in sys.path:sys.path.remove(str(bootstrap.SHARED))
sys.path.insert(0,str(bootstrap.SHARED))
from evidence import collect,semantic_ir
from verify import source_checks

KEYS=['fire','aspp','pyramid_pooling','inception_reduction','inception_factorized',
      'inception_reduction_factorized','inception_split','roi_align','deformable_conv',
      'deformable_conv_unmodulated','shuffle_ir_stride1','shuffle_ir_stride2','fpn','fpn_extra_levels','psp_upsample']

class Contract:
 def __init__(self,text,ir):self.tree=ast.parse(text);self.ir=ir;self.n={n['id']:n for n in ir['nodes']};self.checks=[]
 def check(self,condition,label):
  if not condition:raise ValueError('independent source contract: '+label)
  self.checks.append(label)
 def method(self,cls,method):
  c=next(n for n in self.tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
  return next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name==method)
 def function(self,name):return next(n for n in self.tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
 def expr(self,scope,code,label=None):
  expected=ast.dump(ast.parse(code,mode='eval').body)
  self.check(any(ast.dump(n)==expected for n in ast.walk(scope)),label or 'AST expression '+code)
 def stmt(self,scope,code,label=None):
  expected=ast.dump(ast.parse(code).body[0])
  self.check(any(ast.dump(n)==expected for n in ast.walk(scope)),label or 'AST statement '+code)
 def edge(self,s,d,dp='in',role='tensor',sp='out'):
  self.check(any(e['src']==s and e['dst']==d and e['src_port']==sp and e['dst_port']==dp and e['role']==role for e in self.ir['edges']),f'IR operand {s}:{sp} → {d}:{dp} / {role}')
 def node(self,k,**fields):
  canon=lambda v:json.loads(json.dumps(v))
  self.check(all(canon(self.n[k].get(f))==canon(v) for f,v in fields.items()),'IR source fields '+k+' / '+','.join(fields))

def source_contract(key,text,ir):
 c=Contract(text,ir);n=c.n;p=ir['profile'];prefix=key+'.'
 c.check(ir['artifact_scope']=='module' and p['model_executed'] is False,'selected module only; no execution claim')
 if key=='fire':
  init=c.method('Fire','__init__');f=c.method('Fire','forward')
  for code in ['nn.Conv2d(inplanes,squeeze_planes,kernel_size=1)','nn.Conv2d(squeeze_planes,expand1x1_planes,kernel_size=1)','nn.Conv2d(squeeze_planes,expand3x3_planes,kernel_size=3,padding=1)']:c.expr(init,code)
  c.stmt(f,'x = self.squeeze_activation(self.squeeze(x))')
  c.expr(f,'torch.cat([self.expand1x1_activation(self.expand1x1(x)),self.expand3x3_activation(self.expand3x3(x))],1)')
  relus=[x for x in ast.walk(init) if isinstance(x,ast.Call) and ast.unparse(x.func)=='nn.ReLU']
  c.check(len(relus)==3 and all(ast.unparse(x)=='nn.ReLU(inplace=True)' for x in relus),'three source inplace activations')
  c.node('fire.squeeze.conv',in_channels=64,out_channels=16,bias=True,kernel_size=1)
  c.node('fire.expand1x1.conv',in_channels=16,out_channels=64,bias=True,kernel_size=1)
  c.node('fire.expand3x3.conv',in_channels=16,out_channels=64,bias=True,kernel_size=3,padding=1)
  c.edge('fire.squeeze','fire.expand');c.edge('fire.expand','fire.expand1x1',role='fork',sp='in');c.edge('fire.expand','fire.expand3x3',role='fork',sp='in')
  c.node('fire.concat',kind='concat',dim=1,shape='[B,128,32,32]')
  c.check(not any(x['kind'] in ('batch_norm2d','add','pool') for x in n.values()),'no invented BN, residual or pool')
 elif key=='aspp':
  init=c.method('ASPP','__init__');f=c.method('ASPP','forward');ac=c.method('ASPPConv','__init__');ap=c.method('ASPPPooling','__init__');af=c.method('ASPPPooling','forward')
  c.expr(init,'modules.append(nn.Sequential(nn.Conv2d(in_channels,out_channels,1,bias=False),nn.BatchNorm2d(out_channels),nn.ReLU()))')
  c.expr(init,'modules.append(ASPPConv(in_channels,out_channels,rate))');c.expr(init,'modules.append(ASPPPooling(in_channels,out_channels))')
  c.expr(init,'nn.Sequential(nn.Conv2d(len(self.convs)*out_channels,out_channels,1,bias=False),nn.BatchNorm2d(out_channels),nn.ReLU(),nn.Dropout(0.5))')
  c.expr(ac,'[nn.Conv2d(in_channels,out_channels,3,padding=dilation,dilation=dilation,bias=False),nn.BatchNorm2d(out_channels),nn.ReLU()]')
  for code in ['nn.AdaptiveAvgPool2d(1)','nn.Conv2d(in_channels,out_channels,1,bias=False)','nn.BatchNorm2d(out_channels)','nn.ReLU()']:c.expr(ap,code)
  c.stmt(af,'size = x.shape[-2:]');c.expr(af,"F.interpolate(x,size=size,mode='bilinear',align_corners=False)")
  c.expr(f,'res.append(conv(x))');c.expr(f,'torch.cat(res,dim=1)');c.expr(f,'self.project(res)')
  c.check(p['atrous_rates']==[6,12,18] and p['out_channels']==64,'explicit selected rates/width, no DeepLabHead default claim')
  for i,r in enumerate([6,12,18],1):
   c.node(prefix+f'rate{r}.conv',dilation=r,padding=r,kernel_size=3,in_channels=256,out_channels=64,bias=False,parameter='convs.'+str(i)+'.0')
   c.edge(prefix+'branches',prefix+'rate'+str(r),role='fork',sp='in')
  c.node(prefix+'resize',mode_argument='bilinear',align_corners=False,shape='[B,64,32,32]')
  c.edge(prefix+'input',prefix+'resize','size','shape_dependency','shape')
  c.node(prefix+'project.conv',in_channels=320,out_channels=64,bias=False);c.node(prefix+'dropout',p=.5)
 elif key=='pyramid_pooling':
  init=c.method('PSPModule','__init__');stage=c.method('PSPModule','_make_stage');f=c.method('PSPModule','forward')
  c.expr(init,'nn.ModuleList([self._make_stage(features,size) for size in sizes])')
  c.expr(init,'nn.Conv2d(features*(len(sizes)+1),out_features,kernel_size=1)')
  c.expr(stage,'nn.AdaptiveAvgPool2d(output_size=(size,size))');c.expr(stage,'nn.Conv2d(features,features,kernel_size=1,bias=False)');c.expr(stage,'nn.Sequential(prior,conv)')
  c.expr(f,"[F.upsample(input=stage(feats),size=(h,w),mode='bilinear') for stage in self.stages]+[feats]")
  c.expr(f,'self.bottleneck(torch.cat(priors,1))');c.expr(f,'self.relu(bottle)')
  for i,s in enumerate([1,2,3,6]):
   c.node(prefix+'pool'+str(i),output_size=[s,s]);c.node(prefix+'conv'+str(i),in_channels=64,out_channels=64,bias=False,parameter=f'stages.{i}.1')
   c.node(prefix+'resize'+str(i),align_corners_argument='omitted',shape='[B,64,24,24]')
   c.edge(prefix+'input',prefix+'resize'+str(i),'size','shape_dependency','shape')
   c.edge(prefix+'branches',prefix+'bin'+str(s),role='fork',sp='in')
  c.node(prefix+'branches',branch_order=[1,2,3,6,'feats']);c.node(prefix+'bottleneck',in_channels=320,out_channels=128,bias=True)
  c.check(not any(x['kind']=='batch_norm2d' for x in n.values()),'source PSPModule has no BN')
 elif key=='psp_upsample':
  init=c.method('PSPUpsample','__init__');f=c.method('PSPUpsample','forward')
  c.expr(init,'nn.Sequential(nn.Conv2d(in_channels,out_channels,3,padding=1),nn.BatchNorm2d(out_channels),nn.PReLU())')
  c.stmt(f,'h,w = 2*x.size(2),2*x.size(3)');c.stmt(f,"p = F.upsample(input=x,size=(h,w),mode='bilinear')")
  c.expr(f,'self.conv(p)')
  c.node(prefix+'resize',mode_argument='bilinear',shape='[B,64,16,16]',align_corners_argument='omitted')
  c.edge(prefix+'input',prefix+'resize','size','shape_dependency','shape')
  c.node(prefix+'conv_op',in_channels=64,out_channels=32,kernel_size=3,padding=1,bias=True,parameter='conv.0')
  c.node(prefix+'bn',num_features=32,parameter='conv.1')
  c.node(prefix+'prelu',learnable=True,num_parameters=1,initial_slope=.25,parameter='conv.2',parameter_shape=[1])
  c.edge(prefix+'resize',prefix+'conv');c.edge(prefix+'bn',prefix+'prelu')
 elif key.startswith('inception_'):
  cls={'inception_reduction':'InceptionB','inception_factorized':'InceptionC','inception_reduction_factorized':'InceptionD','inception_split':'InceptionE'}[key]
  init=c.method(cls,'__init__');f=c.method(cls,'_forward')
  configs={
   'InceptionB':{'branch3x3':(288,384,3,2,0),'branch3x3dbl_1':(288,64,1,1,0),'branch3x3dbl_2':(64,96,3,1,1),'branch3x3dbl_3':(96,96,3,2,0)},
   'InceptionC':{'branch1x1':(768,192,1,1,0),'branch7x7_1':(768,128,1,1,0),'branch7x7_2':(128,128,(1,7),1,(0,3)),'branch7x7_3':(128,192,(7,1),1,(3,0)),
    'branch7x7dbl_1':(768,128,1,1,0),'branch7x7dbl_2':(128,128,(7,1),1,(3,0)),'branch7x7dbl_3':(128,128,(1,7),1,(0,3)),'branch7x7dbl_4':(128,128,(7,1),1,(3,0)),'branch7x7dbl_5':(128,192,(1,7),1,(0,3)),'branch_pool':(768,192,1,1,0)},
   'InceptionD':{'branch3x3_1':(768,192,1,1,0),'branch3x3_2':(192,320,3,2,0),'branch7x7x3_1':(768,192,1,1,0),'branch7x7x3_2':(192,192,(1,7),1,(0,3)),'branch7x7x3_3':(192,192,(7,1),1,(3,0)),'branch7x7x3_4':(192,192,3,2,0)},
   'InceptionE':{'branch1x1':(1280,320,1,1,0),'branch3x3_1':(1280,384,1,1,0),'branch3x3_2a':(384,384,(1,3),1,(0,1)),'branch3x3_2b':(384,384,(3,1),1,(1,0)),
    'branch3x3dbl_1':(1280,448,1,1,0),'branch3x3dbl_2':(448,384,3,1,1),'branch3x3dbl_3a':(384,384,(1,3),1,(0,1)),'branch3x3dbl_3b':(384,384,(3,1),1,(1,0)),'branch_pool':(1280,192,1,1,0)},
  }[cls]
  literal_env={'in_channels':p['in_channels'],'c7':128}
  def value(x):return literal_env[x.id] if isinstance(x,ast.Name) else ast.literal_eval(x)
  assigns=[x for x in init.body if isinstance(x,ast.Assign) and isinstance(x.targets[0],ast.Attribute) and isinstance(x.value,ast.Call) and ast.unparse(x.value.func)=='conv_block']
  c.check([x.targets[0].attr for x in assigns]==list(configs),'independent table of actual BasicConv attribute order')
  for x in assigns:
   attr=x.targets[0].attr;kw={z.arg:value(z.value) for z in x.value.keywords};found=(value(x.value.args[0]),value(x.value.args[1]),kw['kernel_size'],kw.get('stride',1),kw.get('padding',0))
   c.check(found==configs[attr],'AST exact constructor '+attr)
   ci,co,k,s,pad=found;c.node(prefix+attr+'.conv',in_channels=ci,out_channels=co,kernel_size=k,stride=s,padding=pad,bias=False,parameter=attr+'.conv')
   c.node(prefix+attr+'.bn',eps=.001,parameter=attr+'.bn');c.node(prefix+attr+'.relu',inplace=True)
  bi=c.method('BasicConv2d','__init__');bf=c.method('BasicConv2d','forward')
  c.expr(bi,'nn.Conv2d(in_channels,out_channels,bias=False,**kwargs)');c.expr(bi,'nn.BatchNorm2d(out_channels,eps=0.001)')
  c.check([ast.unparse(x.value.func) for x in bf.body]==['self.conv','self.bn','F.relu'],'AST actual Conv → BN → ReLU order')
  c.expr(bf,'F.relu(x,inplace=True)')
  branches={'InceptionB':['branch3x3','branch3x3dbl','branch_pool'],'InceptionC':['branch1x1','branch7x7','branch7x7dbl','branch_pool'],'InceptionD':['branch3x3','branch7x7x3','branch_pool'],'InceptionE':['branch1x1','branch3x3','branch3x3dbl','branch_pool']}[cls]
  c.stmt(f,'outputs = ['+','.join(branches)+']');c.expr(c.method(cls,'forward'),'torch.cat(outputs,1)')
  mode='max' if cls in ['InceptionB','InceptionD'] else 'avg'
  c.expr(f,'F.'+mode+'_pool2d(x,kernel_size=3,stride='+('2)' if mode=='max' else '1,padding=1)'))
  c.node(prefix+'branches',branch_order=branches);c.node(prefix+'concat',kind='concat',dim=1)
  for branch in branches:c.edge(prefix+'branches',prefix+'path.'+branch,role='fork',sp='in')
  if cls=='InceptionE':
   c.stmt(f,'branch3x3 = [self.branch3x3_2a(branch3x3),self.branch3x3_2b(branch3x3)]')
   c.stmt(f,'branch3x3dbl = [self.branch3x3dbl_3a(branch3x3dbl),self.branch3x3dbl_3b(branch3x3dbl)]')
   c.check(sum(x['kind']=='concat' for x in n.values())==3,'two inner cats plus final cat; split kernels not serial')
   c.edge(prefix+'branch3x3.split',prefix+'branch3x3_2a',role='fork',sp='in')
   c.edge(prefix+'branch3x3.split',prefix+'branch3x3_2b',role='fork',sp='in')
 elif key=='roi_align':
  f=c.function('roi_align');mf=c.method('RoIAlign','forward')
  c.expr(mf,'roi_align(input,rois,self.output_size,self.spatial_scale,self.sampling_ratio,self.aligned)')
  c.stmt(f,'rois = boxes');c.expr(f,'_pair(output_size)');c.stmt(f,'if not isinstance(rois,torch.Tensor):\n rois = convert_boxes_to_roi_format(rois)')
  c.expr(f,'torch.ops.torchvision.roi_align(input,rois,spatial_scale,output_size[0],output_size[1],sampling_ratio,aligned)')
  c.node(prefix+'kernel',opaque_runtime_boundary=True,runtime_dependency='torch.ops.torchvision.roi_align',output_size=[7,7],spatial_scale=.25,sampling_ratio=2,aligned=True,learnable=False)
  c.edge(prefix+'boxes',prefix+'kernel','rois','roi_coordinates');c.check(not any('parameter' in x for x in n.values()),'wrapper has no learned parameter family')
 elif key in ['deformable_conv','deformable_conv_unmodulated']:
  f=c.function('deform_conv2d');init=c.method('DeformConv2d','__init__');mf=c.method('DeformConv2d','forward')
  c.expr(init,'Parameter(torch.empty(out_channels,in_channels//groups,self.kernel_size[0],self.kernel_size[1]))')
  c.expr(init,"self.register_parameter('bias',None)")
  c.expr(c.method('DeformConv2d','reset_parameters'),'init.kaiming_uniform_(self.weight,a=math.sqrt(5))')
  c.expr(mf,'deform_conv2d(input,offset,self.weight,self.bias,stride=self.stride,padding=self.padding,dilation=self.dilation,mask=mask)')
  c.stmt(f,'use_mask = mask is not None')
  c.stmt(f,'if mask is None:\n mask = torch.zeros((input.shape[0],0),device=input.device,dtype=input.dtype)')
  c.stmt(f,'if bias is None:\n bias = torch.zeros(out_channels,device=input.device,dtype=input.dtype)')
  c.expr(f,'offset.shape[1] // (2*weights_h*weights_w)');c.expr(f,'n_in_channels // weight.shape[1]')
  c.expr(f,'torch.ops.torchvision.deform_conv2d(input,weight,offset,mask,bias,stride_h,stride_w,pad_h,pad_w,dil_h,dil_w,n_weight_grps,n_offset_grps,use_mask)')
  present=key=='deformable_conv';c.node(prefix+'kernel',use_mask=present,bias=False,offset_groups=1,groups=1,opaque_runtime_boundary=True)
  c.node(prefix+'offset',shape='[B,18,16,16]',origin='caller',learnable=False);c.node(prefix+'weight',shape='[16,8,3,3]',parameter='weight',learnable=True)
  c.edge(prefix+'offset',prefix+'kernel','offset','sampling_offsets');c.edge(prefix+'weight',prefix+'kernel','weight','parameter_operand')
  if present:c.node(prefix+'mask',shape='[B,9,16,16]',origin='caller');c.edge(prefix+'mask',prefix+'kernel','mask','modulation_mask')
  else:c.check(prefix+'mask' not in n,'no invented mask operand for None profile')
  c.check(sum(x['kind']=='deform_conv2d' for x in n.values())==1 and not any(x['kind']=='conv' for x in n.values()),'no invented offset/mask prediction Conv')
 elif key in ['shuffle_ir_stride1','shuffle_ir_stride2']:
  init=c.method('InvertedResidual','__init__');f=c.method('InvertedResidual','forward');dw=c.method('InvertedResidual','depthwise_conv')
  c.stmt(init,'branch_features = oup // 2')
  c.expr(dw,'nn.Conv2d(i,o,kernel_size,stride,padding,bias=bias,groups=i)')
  c.expr(init,'nn.Sequential(self.depthwise_conv(inp,inp,kernel_size=3,stride=self.stride,padding=1),nn.BatchNorm2d(inp),nn.Conv2d(inp,branch_features,kernel_size=1,stride=1,padding=0,bias=False),nn.BatchNorm2d(branch_features),nn.ReLU(inplace=True))')
  c.expr(init,'nn.Sequential(nn.Conv2d(inp if self.stride > 1 else branch_features,branch_features,kernel_size=1,stride=1,padding=0,bias=False),nn.BatchNorm2d(branch_features),nn.ReLU(inplace=True),self.depthwise_conv(branch_features,branch_features,kernel_size=3,stride=self.stride,padding=1),nn.BatchNorm2d(branch_features),nn.Conv2d(branch_features,branch_features,kernel_size=1,stride=1,padding=0,bias=False),nn.BatchNorm2d(branch_features),nn.ReLU(inplace=True))')
  c.stmt(f,'if self.stride == 1:\n x1,x2 = x.chunk(2,dim=1)\n out = torch.cat((x1,self.branch2(x2)),dim=1)\nelse:\n out = torch.cat((self.branch1(x),self.branch2(x)),dim=1)')
  c.stmt(f,'out = channel_shuffle(out,2)')
  split=key.endswith('stride1');c.check(p['split_called']==split and p['branch1_called']!=split,'selected Python branch matches explicit stride')
  c.node(prefix+'b2.dw',groups=12 if split else 24,stride=1 if split else 2,bias=False)
  if split:
   c.node(prefix+'chunk',chunks=2,dim=1);c.edge(prefix+'branches',prefix+'branch2',role='dispatch',sp='item[1]');c.edge(prefix+'branches',prefix+'retained',role='dispatch',sp='item[0]')
   c.check(prefix+'branch1' not in n,'no learned branch1 call at stride1')
  else:
   c.check(prefix+'chunk' not in n,'no channel chunk at stride2');c.node(prefix+'b1.dw',groups=24,stride=2)
   c.edge(prefix+'branches',prefix+'branch1',role='fork',sp='in');c.edge(prefix+'branches',prefix+'branch2',role='fork',sp='in')
  c.check(not any(x['kind']=='add' for x in n.values()),'Shuffle block has no MobileNet residual Add')
 elif key=='fpn':
  init=c.method('FeaturePyramidNetwork','__init__');f=c.method('FeaturePyramidNetwork','forward')
  c.expr(init,'nn.Conv2d(in_channels,out_channels,1)');c.expr(init,'nn.Conv2d(out_channels,out_channels,3,padding=1)')
  c.expr(init,'nn.init.kaiming_uniform_(m.weight,a=1)');c.expr(init,'nn.init.constant_(m.bias,0)')
  c.stmt(f,'names = list(x.keys())');c.stmt(f,'x = list(x.values())')
  c.stmt(f,'last_inner = self.get_result_from_inner_blocks(x[-1],-1)')
  c.expr(f,'results.append(self.get_result_from_layer_blocks(last_inner,-1))')
  c.stmt(f,'inner_lateral = self.get_result_from_inner_blocks(x[idx],idx)');c.stmt(f,'feat_shape = inner_lateral.shape[-2:]')
  c.stmt(f,"inner_top_down = F.interpolate(last_inner,size=feat_shape,mode='nearest')")
  c.stmt(f,'last_inner = inner_lateral + inner_top_down');c.expr(f,'results.insert(0,self.get_result_from_layer_blocks(last_inner,idx))')
  c.expr(f,'OrderedDict([(k,v) for k,v in zip(names,results)])')
  for method,attr in [('get_result_from_inner_blocks','inner_blocks'),('get_result_from_layer_blocks','layer_blocks')]:
   c.stmt(c.method('FeaturePyramidNetwork',method),'if i == idx:\n out = module(x)')
   c.check(any(isinstance(x,ast.For) and ast.unparse(x.iter)=='self.'+attr for x in ast.walk(c.method('FeaturePyramidNetwork',method))),'helper selects correct ModuleList '+attr)
  c.edge('fpn.lateral2','fpn.up1');c.edge('fpn.add1','fpn.up0');c.edge('fpn.lateral1','fpn.add1','lateral');c.edge('fpn.lateral0','fpn.add0','lateral')
  c.check(not any(e['src'] in ['fpn.output_conv2','fpn.output_conv1'] and e['dst'] in ['fpn.up1','fpn.up0'] for e in ir['edges']),'top-down never consumes smoothed output Conv')
  c.node('fpn.output',ordered_keys=['feat0','feat1','feat2']);c.check(p['extra_blocks'] is None,'no extra pyramid levels in base profile')
  for i,ci in enumerate([64,128,256]):
   c.node('fpn.lateral'+str(i),in_channels=ci,out_channels=128,kernel_size=1,bias=True,parameter=f'inner_blocks.{i}')
   c.node('fpn.output_conv'+str(i),kernel_size=3,padding=1,bias=True,parameter=f'layer_blocks.{i}')
 elif key=='fpn_extra_levels':
  init=c.method('LastLevelP6P7','__init__');f=c.method('LastLevelP6P7','forward')
  c.stmt(init,'self.p6 = nn.Conv2d(in_channels,out_channels,3,2,1)');c.stmt(init,'self.p7 = nn.Conv2d(out_channels,out_channels,3,2,1)')
  c.expr(init,'nn.init.kaiming_uniform_(module.weight,a=1)');c.expr(init,'nn.init.constant_(module.bias,0)')
  c.stmt(init,'self.use_P5 = in_channels == out_channels');c.stmt(f,'p5,c5 = p[-1],c[-1]')
  c.stmt(f,'x = p5 if self.use_P5 else c5');c.stmt(f,'p6 = self.p6(x)');c.stmt(f,'p7 = self.p7(F.relu(p6))')
  c.expr(f,'p.extend([p6,p7])');c.expr(f,"names.extend(['p6','p7'])")
  c.check(p['use_P5'] is False and p['in_channels']!=p['out_channels'],'declared C5 selection, not equal-channel P5 branch')
  c.edge(prefix+'c5',prefix+'p6');c.edge(prefix+'p6',prefix+'relu');c.edge(prefix+'relu',prefix+'p7');c.edge(prefix+'p6',prefix+'extend','P6');c.edge(prefix+'p7',prefix+'extend','P7')
  c.node(prefix+'p6',in_channels=256,out_channels=128,stride=2,shape='[B,128,4,4]',bias=True)
  c.node(prefix+'p7',in_channels=128,out_channels=128,stride=2,shape='[B,128,2,2]',bias=True)
 else:raise ValueError('unregistered independent vision contract '+key)
 # Parameter identity and frozen AST grounding are audited for every learned node.
 learned=[x for x in n.values() if 'parameter' in x]
 c.check(len({x['instance_identity'] for x in learned})==len(learned),'all distinct learned attribute identities remain independent')
 return c.checks

def negative_tests(key,adapter,ir,text):
 """Reject deliberate graph errors through both contracts and IR consistency."""
 edge_targets={
  'fire':('fire.expand','fire.expand1x1'),
  'aspp':('aspp.branches','aspp.rate6'),
  'pyramid_pooling':('pyramid_pooling.branches','pyramid_pooling.bin1'),
  'inception_reduction':('inception_reduction.branches','inception_reduction.path.branch3x3'),
  'inception_factorized':('inception_factorized.branches','inception_factorized.path.branch7x7'),
  'inception_reduction_factorized':('inception_reduction_factorized.branches','inception_reduction_factorized.path.branch7x7x3'),
  'inception_split':('inception_split.branch3x3.split','inception_split.branch3x3_2a'),
  'roi_align':('roi_align.boxes','roi_align.kernel'),
  'deformable_conv':('deformable_conv.offset','deformable_conv.kernel'),
  'deformable_conv_unmodulated':('deformable_conv_unmodulated.offset','deformable_conv_unmodulated.kernel'),
  'shuffle_ir_stride1':('shuffle_ir_stride1.branches','shuffle_ir_stride1.branch2'),
  'shuffle_ir_stride2':('shuffle_ir_stride2.branches','shuffle_ir_stride2.branch1'),
  'fpn':('fpn.lateral2','fpn.up1'),
  'fpn_extra_levels':('fpn_extra_levels.p6','fpn_extra_levels.extend'),
  'psp_upsample':('psp_upsample.resize','psp_upsample.conv'),
 }
 src,dst=edge_targets[key]
 def selected(d):return next(e for e in d['edges'] if e['src']==src and e['dst']==dst)
 def remove(d):d['edges'].remove(selected(d))
 def swap(d):
  e=selected(d)
  if key=='fpn':e['src']='fpn.output_conv2'
  elif key=='shuffle_ir_stride1':e['src_port']='item[0]'
  else:e['dst_port']='wrong_operand'
 def wrong_shape(d):next(n for n in d['nodes'] if n['id']==dst)['shape']='[B,999,1,1]'
 def wrong_kind(d):next(n for n in d['nodes'] if n['id']==dst)['kind']='invented_add'
 mutations=[('remove required dependency endpoint',remove),('swap operand producer/port',swap),('wrong selected tensor shape',wrong_shape),('wrong selected operator',wrong_kind)]
 if key in ['aspp','pyramid_pooling','psp_upsample']:
  def missing_size(d):d['edges'].__setitem__(slice(None),[e for e in d['edges'] if not(e['src']==key+'.input' and e['dst_port']=='size' and e['role']=='shape_dependency')])
  mutations.append(('remove original input H/W dependency',missing_size))
 learned=next((n for n in ir['nodes'] if 'parameter' in n),None)
 if learned:
  def conflate(d):next(n for n in d['nodes'] if n['id']==learned['id'])['instance_identity']='shared.invented.weight'
  mutations.append(('invent parameter sharing identity',conflate))
 cases=[]
 for label,mutation in mutations:
  wrong=copy.deepcopy(ir);mutation(wrong);contracts_rejected=False;declaration_rejected=False
  try:source_contract(key,text,wrong)
  except (ValueError,KeyError,AssertionError):contracts_rejected=True
  try:adapter.validate_ir(wrong)
  except (ValueError,KeyError):declaration_rejected=True
  cases.append(dict(case=label,rejected=declaration_rejected,independent_contract_rejected=contracts_rejected))
 return cases

def run():
 manifest=json.loads((HERE/'source_manifest.json').read_text())
 for slug,project in json.loads((HERE/'staging/vision_source_manifest.json').read_text()).items():
  if slug in manifest and manifest[slug]!=project:raise ValueError('extended source slug must not mutate original snapshots')
  manifest[slug]=project
 reports=[]
 with tempfile.TemporaryDirectory(prefix='archcanvas-vision-extended-') as scratch:
  tmp=Path(scratch);mp=tmp/'manifest.json';mp.write_text(json.dumps(manifest))
  for key in KEYS:
   result=dict(module=key,passed=False,model_executed=False)
   try:
    a=importlib.import_module('module_adapters.'+key);model=a.build();folder=tmp/key;folder.mkdir()
    ev=collect(model,HERE/'sources',folder,manifest_path=mp);ir=semantic_ir(model,ev)
    result['source_integrity']=source_checks(folder,ev,ir,manifest_path=mp,source_root=HERE/'sources')
    result['git_blob_checks']=[]
    for path in ev['files']:
     slug,inner=path.split('/',1);record=manifest[slug]['files'][inner];data=(HERE/'sources'/path).read_bytes()
     blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
     if blob!=record['git_blob_sha']:raise ValueError('Git tree blob mismatch '+path)
     result['git_blob_checks'].append(path)
    source_path=model['entry'].split('::')[0];text=(HERE/'sources'/source_path).read_text()
    result['source_contract']=source_contract(key,text,ir)
    result['semantic_checks']=a.validate_ir(ir)
    # Also validate the portable JSON form, where literal tuples become lists.
    portable=json.loads(json.dumps(ir));a.validate_ir(portable);source_contract(key,text,portable)
    result['json_roundtrip_passed']=True
    result['negative_cases']=negative_tests(key,a,ir,text)
    result['source_sha256']=hashlib.sha256(text.encode()).hexdigest()
    result['adapter_sha256']=hashlib.sha256(Path(a.__file__).read_bytes()).hexdigest()
    result['passed']=all(x['rejected'] for x in result['negative_cases'])
   except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
   reports.append(result)
 return dict(schema='module-vision-extended-checks/1',passed=all(x['passed'] for x in reports),source_executed=False,
  modules=reports,negative_case_count=sum(len(x.get('negative_cases',[])) for x in reports),
  limitation='Independent contracts cover these pinned modules/profiles; declaration guard alone is not general source extraction.')

if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
