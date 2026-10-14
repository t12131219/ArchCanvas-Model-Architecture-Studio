"""Reviewed split/retention and same-input/downsample ShuffleNetV2 blocks."""
from module_adapters._vision_common import Author,shape,validate_declaration
from module_adapters.support import ref
SOURCE='torchvision-v0.9.0-modules/torchvision/models/shufflenetv2.py'
def build_variant(key,stride):
 a=Author(key,SOURCE,'InvertedResidual');cin=24;cout=24 if stride==1 else 48;half=cout//2;h=16;oh=h if stride==1 else 8
 refs=a.refs+[ref(SOURCE,'InvertedResidual.depthwise_conv')]
 def conv(s,scope,ci,co,k=1,st=1,p=0,g=1,size=16):
  n=a.conv(s,scope,ci,co,k,st,p,g=g,bias=False,out=shape(co,size));n['source']=refs
  if g>1:n['label']=f'Depthwise Conv3 / C={ci}';n['detail']=[f'groups={g}; stride={st}; bias=False']
  return n
 second=a.chain('branch2','Learned branch2',[
  conv('b2.conv1','branch2.0',half if stride==1 else cin,half),a.bn('b2.bn1','branch2.1',half,shape(half,h)),a.relu('b2.relu1',shape(half,h),True),
  conv('b2.dw','branch2.3',half,half,3,stride,1,half,oh),a.bn('b2.bn2','branch2.4',half,shape(half,oh)),
  conv('b2.project','branch2.5',half,half,size=oh),a.bn('b2.bn3','branch2.6',half,shape(half,oh)),a.relu('b2.relu2',shape(half,oh),True),
 ],shape(half,oh),expand=2,source=refs,role='conv')
 items=[]
 if stride==1:
  items.append(a.node('chunk','Chunk channel dim1 into2','chunk','2 tensors [B,12,16,16]',chunks=2,dim=1,literal_tuple=True,learnable=False))
  first=a.node('retained','Retain x1 / no learned branch1','identity',shape(half,h),role='tensor',input_selector='item[0]',learnable=False)
  second['input_selector']='item[1]'
  branches=a.parallel('branches','Dispatch x1 / x2', [first,second],'x1 + transformed x2',expand=1,dispatch=True)
 else:
  first=a.chain('branch1','Learned branch1',[
   conv('b1.dw','branch1.0',cin,cin,3,stride,1,cin,oh),a.bn('b1.bn1','branch1.1',cin,shape(cin,oh)),
   conv('b1.project','branch1.2',cin,half,size=oh),a.bn('b1.bn2','branch1.3',half,shape(half,oh)),a.relu('b1.relu',shape(half,oh),True),
  ],shape(half,oh),expand=2,source=refs,role='conv')
  branches=a.parallel('branches','Same x to both downsample paths',[first,second],'2 learned paths',expand=1)
 branches.update(collection_type='tuple',literal_tuple=True)
 items.extend([branches,a.node('concat','Concat channel dim=1','concat',shape(cout,oh),role='concat',dim=1,ordered_branches=['x1','branch2(x2)'] if stride==1 else['branch1(x)','branch2(x)']),a.node('shuffle','channel_shuffle / groups=2','channel_shuffle',shape(cout,oh),source=[a.forward,ref(SOURCE,'channel_shuffle')],role='tensor',groups=2,learnable=False,reviewed_source_boundary=True)])
 body=a.chain('module','ShuffleNetV2 InvertedResidual',items,shape(cout,oh),expand=1,role='encoder')
 return a.model('ShuffleNetV2 '+('split/retain' if stride==1 else 'stride2/downsample'),'ShuffleIRStride1.md' if stride==1 else 'ShuffleIRStride2.md',body,shape(cin,h),shape(cout,oh),dict(scope='One ShuffleNetV2 InvertedResidual only',constructor=f'InvertedResidual(24,{cout},stride={stride})',inp=cin,oup=cout,stride=stride,branch_features=half,branch1_called=stride>1,split_called=stride==1),['stride1 splits channels: retained x1 and learned branch2(x2) are distinct operands.','stride>1 uses two independently learned paths on the same full x; no chunk operation.','Depthwise groups equal input channels, all Conv biasFalse, BN/ReLU preserve source Sequential indices.','Channel Concat precedes one groups2 shuffle call; shuffle has no weights and its internals are separately covered.'],['This is not MobileNet inverted residual: no residual Add or expansion-ratio skip.','An empty branch1 constructor at stride1 is never called; retain x1 directly.'],symbols=['InvertedResidual','InvertedResidual.__init__','InvertedResidual.depthwise_conv','InvertedResidual.forward','channel_shuffle'])
def validate_variant(ir,key,stride):return validate_declaration(ir,build_variant(key,stride))
