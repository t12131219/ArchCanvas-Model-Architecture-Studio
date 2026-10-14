"""Only the Conv4 + PixelShuffle tail of the super-resolution example."""
from module_adapters.support import chain, op, parallel, graph, ref, finish

SOURCE = 'pytorch-examples-superres/super_resolution/model.py'
MAPPING = 'Y[b,c,3*h+i,3*w+j] = X[b,9*c+3*i+j,h,w]; 0<=i,j<3'


def build():
    init=ref(SOURCE,'Net.__init__'); forward=ref(SOURCE,'Net.forward')
    initialization=ref(SOURCE,'Net._initialize_weights')
    projection=chain('pixelshuffle.projection','Channel projection',[
        op('pixelshuffle.conv4','Conv3x3: 32 -> 9','conv2d',[init,forward,initialization],'[B,9,8,8]',
           ['out_channels=r^2=9; stride1; padding1; bias=True',
            'conv4 weight: orthogonal initialization; no following ReLU'],
           module_identity='conv4',parameters=['conv4.weight','conv4.bias'],
           in_channels=32,out_channels=9,kernel_size=[3,3],stride=[1,1],padding=[1,1],
           bias=True,weight_initialization='orthogonal',activation_after=False),
    ],[init,forward],'[B,9,8,8]',expand=2,
        parameter_scope='conv4',detail=['learned low-resolution channels for r=3 spatial offsets'])
    shuffle=op('pixelshuffle.shuffle','PixelShuffle r=3 / library','tensor',[init,forward],'[B,1,24,24]',
        ['channel-to-space rearrangement; no learned parameters',
         'library implementation is not expanded; formula is standard API context'],
        module_identity='pixel_shuffle',runtime_dependency='torch.nn.PixelShuffle',
        opaque_runtime_boundary=True,learnable=False,parameters=[],
        upscale_factor=3,input_shape=['B',9,8,8],output_shape=['B',1,24,24],
        operation='channel_to_spatial_rearrangement',
        standard_api_mapping=MAPPING,mapping_provenance='standard PixelShuffle mathematical/API contract; not source AST operators')
    head=chain('pixelshuffle.head','Conv4 + PixelShuffle head',[
        projection,shuffle,
    ],[init,forward],'[B,32,8,8] -> [B,1,24,24]',expand=1,
        detail=['tail submodule of Net.forward; explicit example upscale_factor=3'])
    tree=chain('pixelshuffle.root','PixelShuffle tail / r=3',[
        op('pixelshuffle.input','Input after omitted Conv1-3 + ReLU','input',forward,'[B,32,8,8]',
           ['scope boundary: previous feature extractor is not drawn'],
           scope_boundary='after self.relu(self.conv3(x))',tensor_shape=['B',32,8,8]),
        head,
        op('pixelshuffle.output','Upscaled single-channel output','output',forward,'[B,1,24,24]',
           return_value='tail output of Net.forward'),
    ],forward,'[B,1,24,24]',expand=0)
    return finish(dict(key='pixelshuffle',name='Conv4 + PixelShuffle head',doc='PixelShuffle.md',
        module_scope='Only self.pixel_shuffle(self.conv4(x)) tail; Conv1-3 and their ReLU calls excluded',
        source_project='pytorch-examples-superres',entry=forward,
        profile=dict(task='super-resolution tail module',mode='static explicit example',upscale_factor=3,
                     input_shape=['B',32,8,8],conv4_shape=['B',9,8,8],output_shape=['B',1,24,24],
                     input_boundary='output of self.relu(self.conv3(x)); conv1-3 omitted',
                     excluded_modules=['conv1','conv2','conv3','relu'],
                     drawing_scope='only self.pixel_shuffle(self.conv4(x))',
                     kernel_implementation_frozen=False,mapping_provenance='standard API contract',
                     example_configuration='upscale_factor=3 chosen explicitly; constructor supports other r'),
        profile_label='Conv4+PixelShuffle tail / explicit r=3 / [B,32,8,8] -> [B,1,24,24] / static',
        tree=tree,
        visual_roles={'pixelshuffle.root':'root','pixelshuffle.input':'input',
                      'pixelshuffle.head':'attention','pixelshuffle.projection':'ffn',
                      'pixelshuffle.conv4':'conv','pixelshuffle.shuffle':'tensor','pixelshuffle.output':'output'},
        color_legend=[('input', 'Feature input'), ('attention', 'Upsampling head'), ('conv', 'Learned Conv4'), ('tensor', 'PixelShuffle / library'), ('output', 'Image output')],
        fill_width=['pixelshuffle.head','pixelshuffle.projection'],
        facts=[
            'The frozen Net supports a constructor argument upscale_factor. This module example explicitly chooses r=3 and input features[B,32,8,8].',
            'Only conv4 and pixel_shuffle are drawn. conv1, conv2, conv3 and their ReLU calls produce the omitted upstream feature boundary.',
            'conv4 is Conv2d32->r^2 with kernel3, stride1, padding1 and default bias=True, so r=3 produces[B,9,8,8].',
            'Net.forward calls pixel_shuffle(conv4(x)) directly; no ReLU, normalization or interpolation is inserted after conv4.',
            'PixelShuffle is a real nn.PixelShuffle(r) instance with no learned parameters. It rearranges[B,C*r^2,H,W] into[B,C,H*r,W*r].',
            'For r=3, nine channel offsets map to a3x3 spatial neighborhood and yield[B,1,24,24]. The formula is a standard API/mathematical explanation, not four AST-derived reshape operators.',
            'The PixelShuffle library implementation is not frozen or expanded. Its single source-bound glyph is explicitly marked opaque_runtime_boundary.',
            'The example initializes conv4.weight orthogonally but does not explicitly reinitialize conv4.bias; initialization is constructor context, not an extra forward layer.',
            'All shapes are statically inferred under the explicit example profile. No source model, initializer, pixel rearrangement, training or image data was executed.',
        ],
        corrections=[
            'Do not label the entire super-resolution Net as this module; keep the omitted Conv1-3 feature boundary visible.',
            'Do not replace PixelShuffle with interpolation or ConvTranspose, and do not give it learned weights.',
            'Do not present reshape/permute/reshape or a3x3 offset diagram as implementation nodes extracted from this file; the source contains one nn.PixelShuffle call.',
        ],symbols={SOURCE:['Net.__init__','Net.forward','Net._initialize_weights']},
        legend=['B: batch; r=3 explicitly selected; channels9 = output_channels1 * r^2',
                'Conv4 has learned weight/bias; PixelShuffle only rearranges tensor entries',
                'Standard API mapping explanation is separate from the frozen source call boundary']))


def validate_ir(ir):
    nodes={n['id']:n for n in ir['nodes']};edges=ir['edges'];p=ir['profile'];checks=[]
    def check(condition,label):
        if not condition:raise ValueError('pixelshuffle: '+label)
        checks.append(label)
    def has(src,dst,role='tensor'):
        return any(e['src']==src and e['dst']==dst and e['role']==role for e in edges)
    check(ir.get('artifact_scope')=='module' and p['artifact_scope']=='module'
          and p['model_executed'] is False and p['drawing_scope']=='only self.pixel_shuffle(self.conv4(x))',
          'module-only static tail scope')
    check(p['upscale_factor']==3 and p['input_shape']==['B',32,8,8]
          and p['conv4_shape']==['B',9,8,8] and p['output_shape']==['B',1,24,24],
          'explicit r3 input, channel-expanded intermediate and24x24 output')
    conv=nodes['pixelshuffle.conv4'];shuffle=nodes['pixelshuffle.shuffle']
    check(conv['in_channels']==32 and conv['out_channels']==p['upscale_factor']**2
          and conv['kernel_size']==[3,3] and conv['stride']==[1,1] and conv['padding']==[1,1]
          and conv['bias'] is True and conv['shape']=='[B,9,8,8]',
          'actual conv4 channel count and3x3 stride1 padding1 geometry')
    check(conv['parameters']==['conv4.weight','conv4.bias'] and conv['weight_initialization']=='orthogonal'
          and conv['activation_after'] is False,
          'learned conv4 parameters and no post-convolution activation')
    check(shuffle['module_identity']=='pixel_shuffle' and shuffle['upscale_factor']==3
          and shuffle['runtime_dependency']=='torch.nn.PixelShuffle'
          and shuffle['opaque_runtime_boundary'] is True and p['kernel_implementation_frozen'] is False,
          'actual nn.PixelShuffle opaque library boundary')
    check(shuffle['learnable'] is False and shuffle['parameters']==[]
          and shuffle['operation']=='channel_to_spatial_rearrangement',
          'parameter-free rearrangement, not interpolation or learned convolution')
    check(shuffle['input_shape']==['B',9,8,8] and shuffle['output_shape']==['B',1,24,24]
          and shuffle['standard_api_mapping']==MAPPING
          and shuffle['mapping_provenance']=='standard PixelShuffle mathematical/API contract; not source AST operators',
          'channel-offset mapping attributed to API contract rather than source operators')
    check(has('pixelshuffle.projection','pixelshuffle.shuffle')
          and has('pixelshuffle.conv4','pixelshuffle.projection','boundary'),
          'Conv4 projection feeds PixelShuffle in source order')
    check(nodes['pixelshuffle.input']['scope_boundary']=='after self.relu(self.conv3(x))'
          and p['excluded_modules']==['conv1','conv2','conv3','relu']
          and not any(n.get('module_identity') in p['excluded_modules'] for n in nodes.values()),
          'omitted feature extractor remains explicit input scope boundary')
    check(len([n for n in nodes.values() if n.get('runtime_dependency')=='torch.nn.PixelShuffle'])==1
          and not any(n['kind'] in ['relu','interpolate','conv_transpose2d','reshape','permute'] for n in nodes.values())
          and not any(n.get('parent')=='pixelshuffle.shuffle' for n in nodes.values()),
          'no invented PixelShuffle implementation graph or extra activation')
    return checks
