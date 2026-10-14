"""Actual Lextal PSPModule; source has no repository LICENSE file."""
from module_adapters._vision_common import Author,shape,validate_declaration
from module_adapters.support import ref
SOURCE='pspnet-vision-extended/pspnet.py'
def build():
 a=Author('pyramid_pooling',SOURCE,'PSPModule');branches=[]
 for i,size in enumerate([1,2,3,6]):
  branches.append(a.chain('bin'+str(size),f'Pool bins {size}x{size}',[
   a.node(f'pool{i}',f'AdaptiveAvgPool {size}x{size}','pool',shape(64,size),output_size=[size,size],pool_type='adaptive_average'),
   a.conv(f'conv{i}',f'stages.{i}.1',64,64,bias=False,out=shape(64,size)),
   a.node(f'resize{i}','Bilinear upsample to H,W','interpolate',shape(64,24),role='tensor',source_operation='F.upsample',mode_argument='bilinear',align_corners_argument='omitted',size_from='input.shape[-2:]'),
  ],shape(64,24),expand=2,source=a.refs+[ref(SOURCE,'PSPModule._make_stage')],role='pool'))
  for child in branches[-1]['items'][:2]:child['source'] += [ref(SOURCE,'PSPModule._make_stage')]
 branches.append(a.node('retained','Retain original feats','identity',shape(64,24),role='tensor',learnable=False))
 fork=a.parallel('branches','Four pyramid bins + original feats',branches,'5 x 64 channels',expand=1,branch_order=[1,2,3,6,'feats'])
 body=a.chain('module','PSPModule',[fork,a.node('concat','Concat priors then original','concat',shape(320,24),role='concat',dim=1),a.conv('bottleneck','bottleneck',320,128,out=shape(128,24)),a.relu('relu',shape(128,24))],shape(128,24),expand=1,role='encoder')
 edges=[dict(src='pyramid_pooling.input',dst='pyramid_pooling.resize'+str(i),src_port='shape',dst_port='size',role='shape_dependency',src_side='left' if i<2 else 'right',dst_side='left' if i<2 else 'right',dashed=True,label='input H,W') for i in range(4)]
 return a.model('Pyramid pooling / PSPModule','PyramidPooling.md',body,shape(64,24),shape(128,24),dict(scope='PSPModule only',constructor='PSPModule(features=64,out_features=128,sizes=(1,2,3,6))',sizes=[1,2,3,6],features=64,out_features=128,license_status='upstream tree contains no LICENSE; recorded rather than fabricated'),['Four adaptive pools independently project64->64, resize to24x24, then concatenate before original feats.','Stage Conv biasFalse; bottleneck bias defaultsTrue; no BN inside this PSPModule.','F.upsample has omitted align_corners; no API default is invented.','Upstream repository contains no LICENSE file; its absence is explicitly retained in provenance.'],['This literal implementation retainsC channels per bin rather than C/4.','Original feats is the last list entry, not the first.','Do not use ASPP dilation rates or add absent BN.'],edges=edges,symbols=['PSPModule','PSPModule.__init__','PSPModule._make_stage','PSPModule.forward'])
def validate_ir(ir):return validate_declaration(ir,build())
