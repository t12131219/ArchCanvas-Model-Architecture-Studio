"""ASPP with three rates and a true global-pool/resize path."""
from module_adapters._vision_common import Author,shape,validate_declaration
from module_adapters.support import ref
SOURCE='torchvision-v0.9.0-vision-extended/torchvision/models/segmentation/deeplabv3.py'
def build():
 a=Author('aspp',SOURCE,'ASPP');branches=[]
 branches.append(a.conv_bn_relu('pointwise','convs.0',256,64,out=shape(64,32)))
 branches[-1]['label']='Pointwise Conv1 + BN + ReLU'
 for i,rate in enumerate([6,12,18],1):
  b=a.conv_bn_relu('rate'+str(rate),'convs.'+str(i),256,64,3,p=rate,d=rate,out=shape(64,32));b['source'] += [ref(SOURCE,'ASPPConv.__init__')]
  for child in b['items']:child['source'] += [ref(SOURCE,'ASPPConv.__init__')]
  b['label']=f'Atrous Conv3 / rate={rate}'
  b['items'][0]['detail']=[f'dilation={rate}; padding={rate}; bias=False']
  branches.append(b)
 pooled=a.chain('pool_path','Global pool + project + resize',[
  a.node('pool','Adaptive average pool1','pool',shape(256,1),pool_type='adaptive_average',output_size=1),
  a.conv('pool_conv','convs.4.1',256,64,bias=False,out=shape(64,1)),
  a.bn('pool_bn','convs.4.2',64,shape(64,1)),a.relu('pool_relu',shape(64,1)),
  a.node('resize','Bilinear resize to input H,W','interpolate',shape(64,32),role='tensor',mode_argument='bilinear',align_corners=False,size_from='aspp.module:input_shape',library_boundary=True),
 ],shape(64,32),expand=2,source=[a.init,a.forward,ref(SOURCE,'ASPPPooling.__init__'),ref(SOURCE,'ASPPPooling.forward')],role='pool')
 for child in pooled['items']:
  child['source'] += [ref(SOURCE,'ASPPPooling.forward' if child['id'].endswith('.resize') else 'ASPPPooling.__init__')]
 branches.append(pooled)
 fork=a.parallel('branches','Pointwise / rates / global context',branches,'5 x 64 channels',expand=1,branch_order=['pointwise','rate6','rate12','rate18','pool_path'])
 project=a.chain('project','Project + BN + ReLU + Dropout',[
  a.conv('project.conv','project.0',320,64,bias=False,out=shape(64,32)),a.bn('project.bn','project.1',64,shape(64,32)),a.relu('project.relu',shape(64,32)),a.node('dropout','Dropout p=0.5','dropout',shape(64,32),role='control',p=.5,learnable=False),
 ],shape(64,32),expand=2,role='conv')
 body=a.chain('module','ASPP',[fork,a.node('concat','Concat all5 paths','concat',shape(320,32),role='concat',dim=1),project],shape(64,32),expand=1,role='encoder')
 return a.model('ASPP atrous context','ASPP.md',body,shape(256,32),shape(64,32),dict(scope='ASPP only; no DeepLabHead/backbone',constructor='ASPP(256,[6,12,18],out_channels=64)',atrous_rates=[6,12,18],out_channels=64,branch_channels=[64]*5),['Five paths receive the same feature input; three3x3 paths have distinct rates and independent parameters.','Global pooling path records adaptive pool1 and bilinear resize with align_corners=False.','Concat320 precedes Conv1x1/BN/ReLU/Dropout.5; caller mode controls BN/Dropout.'],['Rates6/12/18 and width64 are explicitly chosen; DeepLabHead uses12/24/36 and default width256.','A global-pool path is not a fourth dilated convolution.'],edges=[dict(src='aspp.input',dst='aspp.resize',src_port='shape',dst_port='size',role='shape_dependency',src_side='right',dst_side='right',dashed=True,label='input H,W')],symbols=['ASPP','ASPP.__init__','ASPP.forward','ASPPConv.__init__','ASPPPooling.__init__','ASPPPooling.forward'])
def validate_ir(ir):return validate_declaration(ir,build())
