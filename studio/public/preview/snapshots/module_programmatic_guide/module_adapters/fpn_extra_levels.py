"""LastLevelP6P7 preserves P6 as an output while P7 consumes ReLU(P6)."""
from module_adapters._vision_common import Author,shape,validate_declaration
from module_adapters.support import graph
SOURCE='torchvision-v0.9.0-vision-extended/torchvision/ops/feature_pyramid_network.py'

def build():
 a=Author('fpn_extra_levels',SOURCE,'LastLevelP6P7');edges=[]
 def edge(s,t,dp='in',**kw):
  style=dict(src_side='out',dst_side='in',dashed=False);style.update(kw)
  edges.append(dict(src=a.key+'.'+s,dst=a.key+'.'+t,src_port='out',dst_port=dp,role='tensor',**style))
 c5=a.node('c5','Caller c[-1] / C5','input',shape(256,8),learnable=False,value='c[-1]')
 existing=a.node('existing','Existing p + names / retain','input','p contains P5[128,8,8]; names match p',learnable=False,value='p,names',p5_selected=False)
 p6=a.conv('p6','p6',256,128,3,2,1,out=shape(128,4));p6['initialization']='kaiming_uniform_(a=1); bias=0'
 p6['label']='P6 / Conv3 stride2'
 relu=a.relu('relu',shape(128,4))
 p7=a.conv('p7','p7',128,128,3,2,1,out=shape(128,2));p7['initialization']='kaiming_uniform_(a=1); bias=0'
 p7['label']='P7 / Conv3 stride2'
 append=a.node('extend','Extend p and names / P6 + P7','tensor','p + P6[128,4,4] + P7[128,2,2]',role='control',
  ordered_values=['fpn_extra_levels.p6','fpn_extra_levels.p7'],appended_names=['p6','p7'],mutates_caller_lists=True,learnable=False)
 body=graph(a.key+'.module','LastLevelP6P7 / C5 branch',[p6,relu,p7,append],a.refs,
  'P6 and P7 / both retained',expand=1,ranks=[[p6['id']],[relu['id']],[p7['id']],[append['id']]],rank_gap=80,column_gap=64)
 output=a.node('output','Return extended p, names','output','(existing p + [P6,P7], names + [p6,p7])',literal_tuple=True,learnable=False)
 root=graph(a.key+'.root','FPN extra levels / module',[c5,existing,body,output],a.refs,
  'C5 → P6 + P7',expand=0,ranks=[[c5['id'],existing['id']],[body['id']],[output['id']]],rank_gap=80,column_gap=76)
 edge('c5','p6');edge('p6','relu');edge('relu','p7');edge('p6','extend','P6',src_side='left',dst_side='left')
 edge('p7','extend','P7');edge('existing','extend','retained_lists',src_side='right',dst_side='right');edge('extend','output')
 return a.model('FPN extra P6/P7 levels','FPNExtraLevels.md',body,
  'c[-1][B,256,8,8]; existing p[-1][B,128,8,8]; names',
  '(extended p including P6[B,128,4,4],P7[B,128,2,2], extended names)',
  dict(scope='LastLevelP6P7 only; excludes backbone and base FPN',constructor='LastLevelP6P7(256,128)',in_channels=256,out_channels=128,use_P5=False),
  ['in_channels != out_channels selects C5, even though the caller p list contains P5.',
   'P6=Conv3 stride2(C5); P7=Conv3 stride2(ReLU(P6)); ReLU is not applied before P6 or to returned P6.',
   'Both P6 and P7 are appended to the existing p list, and matching names append in the same order.',
   'p6 and p7 are independent default-bias Conv families initialized with Kaiming(a=1), bias0.'],
  ['Do not show only P7 at the output; P6 is independently retained.',
   'An equal-channel construction selects P5 and needs a separately reviewed profile.'],edges=edges,root=root,
  symbols=['LastLevelP6P7','LastLevelP6P7.__init__','LastLevelP6P7.forward'],
  legend=[('input','C5 / retained lists'),('conv','Conv3 stride2'),('activation','ReLU'),('control','List extension'),('output','P6 and P7')])

def validate_ir(ir):return validate_declaration(ir,build())
