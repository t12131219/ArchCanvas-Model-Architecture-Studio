"""Both source mask branches, with external offsets and optional modulation."""
from module_adapters._vision_common import Author,shape,validate_declaration
from module_adapters.support import ref
SOURCE='torchvision-v0.9.0-vision-extended/torchvision/ops/deform_conv.py'
def build_variant(key,mask_present):
 a=Author(key,SOURCE,'DeformConv2d');source=a.refs+[ref(SOURCE,'deform_conv2d')]
 offset=a.node('offset','External sampling offsets','input',shape(18,16),source=source,learnable=False,origin='caller',offset_groups=1)
 weight=a.node('weight','Learned convolution weight','parameter','[16,8,3,3]',source=source,role='linear',parameter='weight',instance_identity=key+'.weight',learnable=True,initialization='kaiming_uniform_(a=sqrt(5))')
 aux=[offset,weight]
 call=a.node('kernel','DeformConv / '+('modulated' if mask_present else 'no mask'),'deform_conv2d',shape(16,16),source=source,role='conv',learnable=False,opaque_runtime_boundary=True,runtime_dependency='torch.ops.torchvision.deform_conv2d',in_channels=8,out_channels=16,kernel_size=[3,3],stride=[1,1],padding=[1,1],dilation=[1,1],groups=1,offset_groups=1,use_mask=mask_present,bias=False,weight_identity='weight',offset_is_external=True)
 edges=[dict(src=offset['id'],dst=call['id'],role='sampling_offsets',src_port='out',dst_port='offset',label='offset'),dict(src=weight['id'],dst=call['id'],role='parameter_operand',src_port='out',dst_port='weight',label='weight')]
 if mask_present:
  mask=a.node('mask','External modulation mask','input',shape(9,16),source=source,learnable=False,origin='caller');aux.append(mask);edges.append(dict(src=mask['id'],dst=call['id'],role='modulation_mask',src_port='out',dst_port='mask',label='mask'))
 body=a.chain('module','DeformConv2d wrapper',[call],shape(16,16),expand=1,role='encoder')
 return a.model('DeformableConv '+('modulated' if mask_present else 'unmodulated'),'DeformableConv.md' if mask_present else 'DeformableConvUnmodulated.md',body,shape(8,16),shape(16,16),dict(scope='One DeformConv2d call; no offset/mask predictor network',constructor='DeformConv2d(8,16,3,padding=1,bias=False); '+('mask supplied' if mask_present else 'mask=None'),mask_present=mask_present,offset_channels=18,mask_channels=9 if mask_present else 0,weight_shape=[16,8,3,3],kernel_frozen=False),['Offsets are caller-supplied, not produced by an invented convolution.','Mask supplied selects DeformableConv v2; maskNone selects original nonmodulated deformation.','Weight is a true Parameter; groups1 and offset_groups1 are distinct source-derived quantities.','biasFalse passesNone and the wrapper creates zero bias; maskNone also creates an empty placeholder with use_maskFalse.','The C++/CUDA kernel is opaque; no fabricated interpolation subnodes.'],['Do not force modulation on the no-mask branch.','The offset input has18 channels for3x3, mask has9; neither is the convolution weight.'],aux=aux,edges=edges,symbols=['DeformConv2d','DeformConv2d.__init__','DeformConv2d.reset_parameters','DeformConv2d.forward','deform_conv2d'])
def validate_variant(ir,key,mask_present):return validate_declaration(ir,build_variant(key,mask_present))
