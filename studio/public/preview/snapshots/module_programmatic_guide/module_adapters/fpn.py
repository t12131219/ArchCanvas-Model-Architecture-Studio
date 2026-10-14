"""A three-input FPN DAG: last_inner carries top-down values, not output P."""
from module_adapters._vision_common import Author,shape,validate_declaration
from module_adapters.support import graph,ref
SOURCE='torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py'

def build():
 a=Author('fpn',SOURCE,'FeaturePyramidNetwork')
 refs=a.refs+[ref(SOURCE,'FeaturePyramidNetwork.get_result_from_inner_blocks'),ref(SOURCE,'FeaturePyramidNetwork.get_result_from_layer_blocks')]
 inputs=[];lateral=[];output_convs=[];edges=[]
 def edge(src,dst,dp='in',role='tensor',**kw):
  style=dict(src_side='out',dst_side='in',dashed=role!='tensor');style.update(kw)
  edges.append(dict(src='fpn.'+src,dst='fpn.'+dst,src_port='out',dst_port=dp,role=role,**style))
 for i,(ci,size) in enumerate([(64,32),(128,16),(256,8)]):
  inputs.append(a.node('input'+str(i),'feat'+str(i)+' / caller feature','input',shape(ci,size),feature_key='feat'+str(i),learnable=False))
  n=a.conv('lateral'+str(i),'inner_blocks.'+str(i),ci,128,out=shape(128,size));n['source']=refs
  n['label']='Lateral1x1 / feat'+str(i)
  n.update(initialization='kaiming_uniform_(a=1); bias=0',feature_key='feat'+str(i));lateral.append(n)
  n=a.conv('output_conv'+str(i),'layer_blocks.'+str(i),128,128,3,p=1,out=shape(128,size));n['source']=refs
  n['label']='Output3x3 / feat'+str(i)
  n.update(initialization='kaiming_uniform_(a=1); bias=0',feature_key='feat'+str(i));output_convs.append(n)
  edge('input'+str(i),'lateral'+str(i))
 up1=a.node('up1','Nearest resize / 8→16','interpolate',shape(128,16),role='tensor',mode_argument='nearest',size_from='fpn.lateral1.shape[-2:]',library_boundary=True)
 add1=a.node('add1','Add lateral1 + top-down','add',shape(128,16),role='norm',ordered_operands=['fpn.lateral1','fpn.up1'],learnable=False)
 up0=a.node('up0','Nearest resize / 16→32','interpolate',shape(128,32),role='tensor',mode_argument='nearest',size_from='fpn.lateral0.shape[-2:]',library_boundary=True)
 add0=a.node('add0','Add lateral0 + top-down','add',shape(128,32),role='norm',ordered_operands=['fpn.lateral0','fpn.up0'],learnable=False)
 body=graph('fpn.module','FPN / lateral and top-down',[*lateral,up1,add1,up0,add0,*output_convs],refs,
  'OrderedDict feat0/feat1/feat2',expand=1,rank_gap=76,column_gap=76,
  ranks=[['fpn.lateral0','fpn.lateral1','fpn.lateral2'],['fpn.up1','fpn.output_conv2'],['fpn.add1'],['fpn.up0','fpn.output_conv1'],['fpn.add0'],['fpn.output_conv0']],
  align_x={'fpn.up1':'fpn.lateral1','fpn.add1':'fpn.lateral1','fpn.output_conv2':'fpn.lateral2','fpn.up0':'fpn.lateral0','fpn.add0':'fpn.lateral0','fpn.output_conv1':'fpn.lateral1','fpn.output_conv0':'fpn.lateral0'})
 edge('lateral2','output_conv2');edge('lateral2','up1')
 edge('lateral1','up1','size','shape_dependency',src_side='left',dst_side='left')
 edge('lateral1','add1','lateral',src_side='left',dst_side='left');edge('up1','add1','top_down')
 edge('add1','output_conv1');edge('add1','up0')
 edge('lateral0','up0','size','shape_dependency',src_side='left',dst_side='left')
 edge('lateral0','add0','lateral',src_side='left',dst_side='left');edge('up0','add0','top_down');edge('add0','output_conv0')
 out=a.node('output','OrderedDict / high resolution first','output','feat0[128,32,32] / feat1[128,16,16] / feat2[128,8,8]',
  ordered_keys=['feat0','feat1','feat2'],ordered_values=['fpn.output_conv0','fpn.output_conv1','fpn.output_conv2'],learnable=False)
 for i in range(3):edge('output_conv'+str(i),'output','feat'+str(i))
 root=graph('fpn.root','FeaturePyramidNetwork / module',inputs+[body,out],refs,
  '3 scales → 3 scales',expand=0,ranks=[[n['id'] for n in inputs],['fpn.module'],['fpn.output']],rank_gap=76,column_gap=76)
 return a.model('Feature Pyramid Network','FPN.md',body,'OrderedDict(feat0[64,32,32],feat1[128,16,16],feat2[256,8,8])',
  'OrderedDict(feat0[128,32,32],feat1[128,16,16],feat2[128,8,8])',
  dict(scope='FeaturePyramidNetwork only; caller backbone and extra blocks excluded',constructor='FeaturePyramidNetwork([64,128,256],128,extra_blocks=None)',in_channels_list=[64,128,256],out_channels=128,extra_blocks=None,input_keys=['feat0','feat1','feat2'],loop_order=[1,0]),
  ['Three different dictionary features feed independent lateral1x1 Conv weights, not one same-input fork.',
   'Coarsest lateral2 produces output2 and the first top-down value. Later last_inner values are Add results, not layer_blocks outputs.',
   'Nearest resize reads target H/W from the current lateral feature; shape-only edges do not carry tensor values.',
   'Processing loop is low-resolution to high-resolution; results.insert(0,...) restores caller key order/highest resolution first.',
   'Six independent Conv families retain default biases, Kaiming(a=1) and zero bias initialization; no BN or ReLU is present.'],
  ['Do not send smoothed output2/output1 into top-down interpolation.',
   'Different input resolutions are explicit operands, not three visual copies of one tensor.',
   'extra_blocks=None excludes P6/P7 and MaxPool.'],edges=edges,root=root,
  symbols=['FeaturePyramidNetwork','FeaturePyramidNetwork.__init__','FeaturePyramidNetwork.get_result_from_inner_blocks','FeaturePyramidNetwork.get_result_from_layer_blocks','FeaturePyramidNetwork.forward'],
  legend=[('input','Feature inputs'),('conv','Independent Conv'),('norm','Add'),('tensor','Nearest resize'),('output','OrderedDict')])

def validate_ir(ir):return validate_declaration(ir,build())
