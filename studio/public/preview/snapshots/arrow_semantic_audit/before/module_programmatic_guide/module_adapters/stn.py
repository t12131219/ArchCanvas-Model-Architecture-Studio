"""The tutorial's Net.stn submodule, with separate image and size dependencies."""
from module_adapters.support import chain, op, parallel, graph, ref, finish

SOURCE = 'pytorch-tutorials-stn/intermediate_source/spatial_transformer_tutorial.py'


def build():
    init = ref(SOURCE, 'Net.__init__')
    forward = ref(SOURCE, 'Net.stn')
    localization = chain('stn.localization', 'Locate transform', [
        op('stn.loc.conv1', 'Conv7x7: 1 -> 8', 'conv2d', [init, forward], '[B,8,22,22]',
           ['stride=1; padding=0; bias=True'], module_identity='localization.0',
           parameters=['localization.0.weight', 'localization.0.bias'],
           in_channels=1, out_channels=8, kernel_size=7, stride=1, padding=0, bias=True),
        op('stn.loc.pool1', 'MaxPool2x2 / stride2', 'max_pool2d', [init, forward], '[B,8,11,11]',
           kernel_size=2, stride=2, module_identity='localization.1'),
        op('stn.loc.relu1', 'ReLU / inplace', 'relu', [init, forward], '[B,8,11,11]',
           inplace=True, module_identity='localization.2'),
        op('stn.loc.conv2', 'Conv5x5: 8 -> 10', 'conv2d', [init, forward], '[B,10,7,7]',
           ['stride=1; padding=0; bias=True'], module_identity='localization.3',
           parameters=['localization.3.weight', 'localization.3.bias'],
           in_channels=8, out_channels=10, kernel_size=5, stride=1, padding=0, bias=True),
        op('stn.loc.pool2', 'MaxPool2x2 / stride2', 'max_pool2d', [init, forward], '[B,10,3,3]',
           kernel_size=2, stride=2, module_identity='localization.4'),
        op('stn.loc.relu2', 'ReLU / inplace', 'relu', [init, forward], '[B,10,3,3]',
           inplace=True, module_identity='localization.5'),
    ], [init, forward], '[B,10,3,3]', expand=2,
        module_identity='localization', parameter_scope='localization')
    parameters = chain('stn.parameters', 'Affine parameter regressor', [
        op('stn.flatten', 'View localization features', 'tensor', forward, '[B,90]',
           expression='xs.view(-1, 10 * 3 * 3)', feature_width=90),
        op('stn.fc1', 'Linear 90 -> 32', 'linear', [init, forward], '[B,32]',
           module_identity='fc_loc.0', parameters=['fc_loc.0.weight', 'fc_loc.0.bias'],
           in_features=90, out_features=32, bias=True),
        op('stn.relu', 'ReLU / inplace', 'relu', [init, forward], '[B,32]',
           inplace=True, module_identity='fc_loc.1'),
        op('stn.fc2', 'Linear 32 -> 6', 'linear', [init, forward], '[B,6]',
           ['constructor: zero weight; bias=[1,0,0,0,1,0]',
            'learnable after initialization; not permanently fixed identity'],
           module_identity='fc_loc.2', parameters=['fc_loc.2.weight', 'fc_loc.2.bias'],
           in_features=32, out_features=6, bias=True,
           initial_weight='zeros', initial_bias=[1,0,0,0,1,0]),
        op('stn.theta', 'View affine matrix theta', 'tensor', forward, '[B,2,3]',
           expression='theta.view(-1, 2, 3)', affine_rows=2, affine_columns=3),
    ], [init, forward], 'theta: [B,2,3]', expand=2,
        parameter_scope='fc_loc', detail=['six learned affine coefficients; no classifier head'])
    resampling = chain('stn.resampling', 'Grid + image resampling', [
        op('stn.grid', 'F.affine_grid(theta, size)', 'tensor', forward, '[B,28,28,2]',
           ['size=x.size(); consumes image shape, not image pixel values',
            'normalized sampling coordinates (x,y); functional library boundary'],
           expression='F.affine_grid(theta, x.size())', input_ports=['theta', 'size'],
           main_input='theta', ordered_operands=['stn.theta', 'stn.input:shape'],
           grid_coordinate_order=['x','y'], coordinate_domain='normalized input coordinates',
           align_corners_argument='omitted', runtime_dependency='torch.nn.functional.affine_grid',
           opaque_runtime_boundary=True, learnable=False),
        op('stn.sample', 'F.grid_sample(image, grid)', 'sampling', forward, '[B,1,28,28]',
           ['original image pixels + predicted sampling grid',
            'mode, padding_mode and align_corners arguments are all omitted'],
           expression='F.grid_sample(x, grid)', main_input='grid',
           input_ports=['image','grid'], ordered_operands=['stn.input','stn.grid'],
           align_corners_argument='omitted', mode_argument='omitted', padding_mode_argument='omitted',
           runtime_dependency='torch.nn.functional.grid_sample',
           opaque_runtime_boundary=True, learnable=False),
    ], forward, '[B,1,28,28]', expand=2,
        detail=['grid output points to original input-image coordinates'])
    module = chain('stn.module', 'Spatial transformer / Net.stn', [
        localization, parameters, resampling,
    ], forward, '[B,1,28,28]', expand=1,
        detail=['localization -> affine theta -> grid -> sample original image'])
    tree = chain('stn.root', 'STN submodule / MNIST image', [
        op('stn.input', 'Input image / retained pixels', 'input', forward, '[B,1,28,28]',
           tensor_shape=['B',1,28,28]),
        module,
        op('stn.output', 'Warped image', 'output', forward, '[B,1,28,28]',
           return_value='x after F.grid_sample'),
    ], forward, '[B,1,28,28]', expand=0)
    return finish(dict(key='stn', name='Spatial Transformer submodule', doc='STN.md',
        module_scope='Net.stn only; localization + affine regressor + grid/sample; classifier excluded',
        source_project='pytorch-tutorials-stn', entry=forward,
        profile=dict(task='learned affine image resampling submodule', mode='static selected path',
                     input_shape=['B',1,28,28], output_shape=['B',1,28,28],
                     localization_shapes=[[8,22,22],[8,11,11],[10,7,7],[10,3,3]],
                     affine_coefficients=6, theta_shape=['B',2,3], grid_shape=['B',28,28,2],
                     align_corners_argument='omitted', classifier_excluded=True,
                     drawing_scope='Net.stn and its __init__ localization/fc_loc definitions only',
                     initialization='fc_loc.2 weight zero; bias identity affine',
                     kernel_implementation_frozen=False),
        profile_label='Net.stn only / MNIST28x28 / learned affine / grid and image operands / static',
        tree=tree,
        extra_edges=[
            dict(src='stn.input', dst='stn.grid', role='shape_dependency',
                 label='', src_port='shape', dst_port='size',
                 src_side='right', dst_side='right', dashed=True),
            dict(src='stn.input', dst='stn.sample', role='retained_image',
                 label='', src_port='image', dst_port='image',
                 src_side='left', dst_side='left', dashed=False),
        ],
        visual_roles={'stn.root':'root', 'stn.input':'input', 'stn.module':'attention',
                      'stn.localization':'encoder', 'stn.parameters':'ffn',
                      'stn.resampling':'attention', 'stn.grid':'tensor',
                      'stn.sample':'sampling', 'stn.output':'output',
                      'stn.loc.pool1':'pool', 'stn.loc.pool2':'pool',
                      'stn.loc.conv1':'conv', 'stn.loc.conv2':'conv'},
        color_legend=[('input', 'Original image'), ('attention', 'STN / resample'), ('conv', 'Conv / regressor'), ('pool', 'MaxPool'), ('linear', 'Linear / output'), ('activation', 'ReLU'), ('tensor', 'View / grid'), ('sampling', 'Grid sampling')],
        fill_width=['stn.module','stn.localization','stn.parameters','stn.resampling'],
        facts=[
            'The selected artifact is the Net.stn submodule; Net.forward classification convolutions, dropout and log_softmax are outside the scope.',
            'For a28x28 single-channel image the localization sequence is Conv7, Pool2, ReLU, Conv5, Pool2, ReLU; its last map is10x3x3.',
            'The regressor views90 features then executes Linear90->32, ReLU, Linear32->6, and view[B,2,3].',
            'fc_loc.2 has learnable weight and bias. The constructor sets its weight to zero and bias to identity affine coefficients; training may change both.',
            'affine_grid receives theta and x.size(), so its dependency on the original image is shape-only, not a second localization pixel path.',
            'grid_sample receives the original image pixel values and the generated normalized(x,y) grid. It does not resample the localization feature map.',
            'The source omits align_corners in both functional calls; the drawing preserves omission instead of claiming explicitTrue or an executed backend default.',
            'Modern PyTorch APIs document align_corners=False by default, grid_sample bilinear mode and zero padding; these are API context, not extra arguments present in this source.',
            'affine_grid and grid_sample are opaque functional library boundaries; normalized grid shape and meanings are API contracts, not a traced implementation.',
            'All tensor shapes are statically inferred from the chosen image shape; no tutorial, model, training loop, initialization or resampling was executed.',
        ],
        corrections=[
            'Keep the original image value route to grid_sample distinct from the image-size route to affine_grid.',
            'Do not replace predicted theta with a permanently fixed identity matrix, a crop operator, or a classification head.',
            'Do not insert inverse(theta), pixel-coordinate normalization operators or interpolation-kernel internals absent from the frozen tutorial.',
        ],
        symbols={SOURCE:['Net.__init__','Net.stn']},
        legend=['B: batch; theta:[B,2,3]; grid:[B,H,W,2] in normalized(x,y) coordinates',
                'Solid side route: original image values; dashed side route: shape x.size()',
                'Library boundaries: affine_grid and grid_sample; omitted API arguments remain omitted']))


def validate_ir(ir):
    nodes={n['id']:n for n in ir['nodes']}; edges=ir['edges']; p=ir['profile']; checks=[]
    def check(condition,label):
        if not condition: raise ValueError('stn: '+label)
        checks.append(label)
    def has(src,dst,role=None,sp=None,dp=None):
        return any(e['src']==src and e['dst']==dst and (role is None or e['role']==role)
                   and (sp is None or e['src_port']==sp) and (dp is None or e['dst_port']==dp) for e in edges)
    check(ir.get('artifact_scope')=='module' and p['artifact_scope']=='module'
          and p['classifier_excluded'] is True and p['model_executed'] is False,
          'module-only static scope excludes Net classifier')
    check(p['input_shape']==['B',1,28,28] and p['output_shape']==['B',1,28,28],
          'selected image input and warped-image output shapes')
    loc_ids=['stn.loc.conv1','stn.loc.pool1','stn.loc.relu1','stn.loc.conv2','stn.loc.pool2','stn.loc.relu2']
    check([n['id'] for n in ir['nodes'] if n.get('parent')=='stn.localization']==loc_ids
          and all(has(a,b,'tensor') for a,b in zip(loc_ids,loc_ids[1:])),
          'source Conv-Pool-ReLU localization order')
    check(nodes['stn.loc.conv1']['kernel_size']==7 and nodes['stn.loc.conv1']['out_channels']==8
          and nodes['stn.loc.conv1']['shape']=='[B,8,22,22]'
          and nodes['stn.loc.conv2']['kernel_size']==5 and nodes['stn.loc.conv2']['out_channels']==10
          and nodes['stn.loc.conv2']['shape']=='[B,10,7,7]'
          and nodes['stn.loc.pool2']['shape']=='[B,10,3,3]',
          'unpadded localization convolution and pooling shapes')
    check(nodes['stn.flatten']['feature_width']==90 and nodes['stn.fc1']['in_features']==90
          and nodes['stn.fc1']['out_features']==32 and nodes['stn.fc2']['in_features']==32
          and nodes['stn.fc2']['out_features']==6 and nodes['stn.theta']['shape']=='[B,2,3]',
          '90->32->6 affine regressor and2x3 theta')
    check(nodes['stn.fc2']['initial_weight']=='zeros' and nodes['stn.fc2']['initial_bias']==[1,0,0,0,1,0]
          and nodes['stn.fc2']['parameters']==['fc_loc.2.weight','fc_loc.2.bias'],
          'identity initialization does not remove learnable affine parameters')
    check(nodes['stn.grid']['expression']=='F.affine_grid(theta, x.size())'
          and nodes['stn.grid']['shape']=='[B,28,28,2]'
          and nodes['stn.grid']['grid_coordinate_order']==['x','y']
          and has('stn.input','stn.grid','shape_dependency','shape','size'),
          'normalized x-y grid and original-image shape-only dependency')
    check(nodes['stn.sample']['expression']=='F.grid_sample(x, grid)'
          and nodes['stn.sample']['ordered_operands']==['stn.input','stn.grid']
          and nodes['stn.sample']['main_input']=='grid'
          and has('stn.grid','stn.sample','tensor')
          and has('stn.input','stn.sample','retained_image','image','image'),
          'sampler uses generated grid and original image pixels')
    check(nodes['stn.grid']['align_corners_argument']=='omitted'
          and nodes['stn.sample']['align_corners_argument']=='omitted'
          and nodes['stn.sample']['mode_argument']=='omitted'
          and nodes['stn.sample']['padding_mode_argument']=='omitted',
          'source omissions retained without invented align_corners value')
    check(all(nodes[i]['opaque_runtime_boundary'] is True and nodes[i]['learnable'] is False
              for i in ['stn.grid','stn.sample']) and p['kernel_implementation_frozen'] is False,
          'functional grid generator and sampler remain opaque library boundaries')
    check(not any(n.get('module_identity') in ['conv1','conv2','conv2_drop','fc1','fc2']
                  or n['kind'] in ['softmax','dropout','log_softmax'] for n in nodes.values()),
          'no classifier, dropout or Softmax is drawn within Net.stn')
    return checks
