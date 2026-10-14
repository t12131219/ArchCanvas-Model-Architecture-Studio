"""Bilinear upsample before Conv/BN/PReLU; PReLU owns one learned scalar."""
from module_adapters._vision_common import Author,shape,validate_declaration
SOURCE='pspnet-vision-extended/pspnet.py'
def build():
 a=Author('psp_upsample',SOURCE,'PSPUpsample')
 resize=a.node('resize','Bilinear resize / 2x H,W','interpolate',shape(64,16),role='tensor',
  source_operation='F.upsample',mode_argument='bilinear',align_corners_argument='omitted',
  size_expression='(2*x.size(2),2*x.size(3))',library_boundary=True,learnable=False)
 prelu=a.node('prelu','PReLU / one learned slope','prelu',shape(32,16),role='activation',
  parameter='conv.2',instance_identity='psp_upsample.conv.2',learnable=True,num_parameters=1,
  parameter_tensors=['conv.2.weight'],parameter_shape=[1],initial_slope=.25,shared_across='all output channels',source_operation='nn.PReLU()')
 conv=a.chain('conv','Conv3 + BN + PReLU',[
  a.conv('conv_op','conv.0',64,32,3,p=1,bias=True,out=shape(32,16)),
  a.bn('bn','conv.1',32,shape(32,16)),prelu,
 ],shape(32,16),expand=2,role='conv')
 body=a.chain('module','PSPUpsample',[resize,conv],shape(32,16),expand=1,role='encoder')
 return a.model('PSP resize/convolution upsample','PSPUpsample.md',body,shape(64,8),shape(32,16),
  dict(scope='PSPUpsample only; PSP pooling, enclosing decoder and classifier excluded',constructor='PSPUpsample(64,32)',in_channels=64,out_channels=32,spatial_scale=2,prelu_num_parameters=1),
  ['Bilinear F.upsample doubles input H and W before the convolution, rather than applying pixel channel rearrangement.',
   'Conv3 padding1 retains enlarged16x16 and has default biasTrue; BN32 follows it.',
   'nn.PReLU() owns exactly one learned slope initialized0.25, shared across all32 channels; it is not a fixed ReLU.',
   'align_corners is omitted in this historical API call; drawing does not invent a default or execute the library.'],
  ['Do not replace bilinear upsample with ConvTranspose or PixelShuffle.',
   'The PReLU parameter is separate from Conv/BN parameter paths and does not have32 independent slopes.'],
  edges=[dict(src='psp_upsample.input',dst='psp_upsample.resize',src_port='shape',dst_port='size',role='shape_dependency',src_side='right',dst_side='right',dashed=True,label='2x input H,W')])
def validate_ir(ir):return validate_declaration(ir,build())
