"""RoIAlign with named feature/box operands and a genuine opaque kernel."""
from module_adapters._vision_common import Author,shape,validate_declaration
from module_adapters.support import ref
SOURCE='torchvision-v0.9.0-vision-extended/torchvision/ops/roi_align.py'
def build():
 a=Author('roi_align',SOURCE,'RoIAlign')
 rois=a.node('boxes','RoIs / batch index + xyxy','input','[K,5]',source=ref(SOURCE,'roi_align'),learnable=False,coordinate_format='batch_index,x1,y1,x2,y2',origin='caller')
 call=a.node('kernel','RoIAlign / torchvision kernel','roi_align','[K,64,7,7]',source=a.refs+[ref(SOURCE,'roi_align')],role='pool',learnable=False,opaque_runtime_boundary=True,runtime_dependency='torch.ops.torchvision.roi_align',output_size=[7,7],spatial_scale=.25,sampling_ratio=2,aligned=True,boxes_representation='Tensor[K,5]',input_ports=['in','rois'])
 body=a.chain('module','RoIAlign module',[call],'[K,64,7,7]',expand=1,role='encoder')
 return a.model('RoIAlign region sampling','RoIAlign.md',body,shape(64,32),'[K,64,7,7]',dict(scope='RoIAlign wrapper and actual kernel call only',constructor='RoIAlign((7,7),spatial_scale=.25,sampling_ratio=2,aligned=True)',rois_shape=['K',5],boxes_type='Tensor',aligned=True,sampling_ratio=2,spatial_scale=.25,kernel_frozen=False),['Features and coordinates are different operands; each box first column selects a batch image.','Tensor RoIs bypass convert_boxes_to_roi_format; output size is pair7x7.','Source kernel call is opaque; interpolation/bin details are API context rather than invented AST nodes.','No learning parameters; alignedTrue and fixed2x2 bin sampling are explicitly selected.'],['This is torchvision RoIAlign, not longcw crop_and_resize.','Do not pool the whole image or replace coordinates with feature values.'],aux=[rois],edges=[dict(src=rois['id'],dst=call['id'],role='roi_coordinates',src_port='out',dst_port='rois',label='RoIs')],symbols=['RoIAlign','RoIAlign.__init__','RoIAlign.forward','roi_align'])
def validate_ir(ir):return validate_declaration(ir,build())
