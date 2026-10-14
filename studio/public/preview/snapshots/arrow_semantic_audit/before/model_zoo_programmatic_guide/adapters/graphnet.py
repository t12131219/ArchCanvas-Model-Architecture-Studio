"""MNIST fixed-adjacency GraphNet, preserving constructor/buffer/operand roles."""
from spec import chain, op, parallel, ref

SOURCE = 'deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py'


def build():
    init=ref(SOURCE,'GraphNet.__init__');forward=ref(SOURCE,'GraphNet.forward')
    pre=ref(SOURCE,'precompute_adjacency_matrix')
    adjacency=chain('graphnet.adjacency','Fixed graph / init',[
        op('graphnet.coords','Normalized grid coords','tensor',pre,'coord: [N,2]',
           ['np.meshgrid; stack(col,row); reshape(-1,2) / img_size',
            'N=28*28; coordinates are 0..27 divided by28, not divided by27'],
           expression='np.stack((col,row),axis=2).reshape(-1,2) / img_size',learnable=False),
        op('graphnet.dist','Pairwise Euclidean distance','mixing',pre,'dist: [N,N]',
           expression="cdist(coord,coord,metric='euclidean')",metric='euclidean'),
        op('graphnet.kernel','exp(-distance / sigma^2)','mixing',pre,'A: [N,N]',
           ['sigma=.05*pi; actual source uses distance, not distance squared'],
           expression='np.exp(- dist / sigma ** 2)',sigma='0.05 * np.pi',distance_squared=False),
        op('graphnet.threshold','Set A < .01 to zero','control',pre,'A: [N,N]',
           expression='A[A < 0.01] = 0',threshold=0.01),
        op('graphnet.float','Convert NumPy to float tensor','tensor',pre,'A: [N,N]',
           expression='torch.from_numpy(A).float()',dtype='float32'),
        op('graphnet.row_sum','Sum A over columns','tensor',pre,'D: [N]',
           expression='A.sum(1)',dim=1),
        op('graphnet.inv_sqrt','Inverse sqrt / epsilon','tensor',pre,'D_hat: [N]',
           expression='(D + 1e-5) ** (-0.5)',epsilon=1e-5),
        op('graphnet.normalize','Scale rows and columns','mixing',pre,'A_hat: [N,N]',
           ['D_hat[:,None] * A * D_hat[None,:]; not row-average normalization'],
           expression='D_hat.view(-1,1) * A * D_hat.view(1,-1)',normalization='symmetric degree scaling',
           operands=['graphnet.float','graphnet.inv_sqrt']),
        op('graphnet.buffer','register_buffer("A")','control',init,'self.A: [784,784]',
           ['constructed once; non-learnable persistent buffer; moves with model.to',
            'same matrix used for every image, train or eval'],
           expression="self.register_buffer('A', A)",buffer_identity='A',learnable=False,
           param_identity='buffer self.A; no learned parameters; shared across images',persistent=True),
    ],[pre,init],'fixed A: [784,784]',
        ['constructor-time work; independent of input pixel values; not a forward layer'],
        expand=2,execution_scope='construction',buffer_identity='A',learnable=False,
        param_identity='fixed adjacency buffer A; constructed once')
    layout=chain('graphnet.layout','Image pixels to graph nodes',[
        op('graphnet.reshape','View pixels as node features','tensor',forward,'[B,784,1]',
           ['x.view(B,-1,1); fixed selected grayscale28x28 image'],
           expression='x.view(B,-1,1)',input_channels=1),
    ],forward,'[B,N=784,F=1]',expand=2)
    expand=chain('graphnet.broadcast','Broadcast fixed adjacency',[
        op('graphnet.expand','self.A.expand(B,-1,-1)','tensor',forward,'[B,784,784]',
           ['reads the registered2D buffer directly; no per-image learned adjacency',
            'B comes from x.size(0); expand is a broadcast view, not repeat/copy'],
           expression='self.A.expand(B,-1,-1)',buffer_identity='A',learnable=False,
           input_ports=['A','B'],param_identity='same buffer self.A for every batch item'),
    ],forward,'[B,N,N]',expand=2,suppress_input_boundary=True,
        input_relation=dict(role='external',producer='graphnet.adjacency',src_port='out'))
    operands=parallel('graphnet.operands','Node values / fixed weights',[
        op('graphnet.features_operand','Retain pixel features','tensor',forward,'[B,784,1]',
           expression='x_reshape'),expand,
    ],forward,'X and A operands',expand=2,semantic_mode='operand_bundle',literal_tuple=False,
        child_inputs={'graphnet.features_operand':dict(role='value',producer='graphnet.reshape',src_port='out'),
                      'graphnet.broadcast':dict(role='external',producer='graphnet.adjacency',src_port='out')},
        operand_order=['graphnet.broadcast','graphnet.features_operand'])
    aggregation=chain('graphnet.aggregation','Fixed neighbor aggregation',[
        operands,
        op('graphnet.bmm','Batch MatMul: A @ X','mixing',forward,'[B,784,1]',
           ['sum_j A_hat[i,j] * pixel[j]; no activation, attention or node-feature Linear'],
           expression='torch.bmm(A_tensor,x_reshape)',operation='bmm',
           ordered_operands=['graphnet.expand','graphnet.features_operand'],
           reduction='weighted neighbor sum, not row arithmetic mean'),
        op('graphnet.flatten','View aggregated nodes','tensor',forward,'[B,784]',
           expression='torch.bmm(A_tensor,x_reshape).view(B,-1)'),
    ],forward,'[B,784]',expand=1)
    returns=parallel('graphnet.returns','Return logits / probabilities',[
        op('graphnet.logits','Retain logits','tensor',forward,'[B,10]'),
        op('graphnet.softmax','Softmax along classes','softmax',forward,'[B,10]',
           expression='F.softmax(logits,dim=1)',dim=1),
    ],forward,'(logits,probas)',expand=2,dispatch=False)
    classifier=chain('graphnet.head','Whole-image linear head',[
        op('graphnet.fc','Linear 784 -> 10 / no bias','linear',[init,forward],'[B,10]',
           ['self.fc acts on the entire784-node vector; not a per-node channel projection'],
           parameter='fc.weight',bias=False,in_features=784,out_features=10,
           parameter_shape=[10,784]),returns,
    ],[init,forward],'2 x [B,10]',expand=1)
    model_forward=chain('graphnet.forward','GraphNet forward',[
        layout,aggregation,classifier,
    ],forward,'(logits,probas)',expand=1,
        detail=['live data dependencies of returned values; overwritten unsqueeze result is omitted'])
    tree=chain('graphnet.root','GraphNet: fixed pixel graph',[
        op('graphnet.input','MNIST grayscale image','input',forward,'[B,1,28,28]'),
        model_forward,
        op('graphnet.output','Forward return tuple','output',forward,'2 x [B,10]',
           ['raw logits + normalized class probabilities'],output_tuple=['logits','probas']),
    ],[init,forward],'2 x [B,10]',expand=0)
    return dict(key='graphnet',name='GraphNet (fixed MNIST pixel graph)',
        source_project='deeplearning-models-batch4',entry=forward,
        profile=dict(task='MNIST10-class classification',mode='eval',input_size=[28,28],input_channels=1,
                     nodes=784,node_feature_width=1,num_classes=10,batch_size_setting=128,
                     construction='fixed grid adjacency precomputed in __init__',buffer='A',adjacency_learnable=False,
                     adjacency_shape=[784,784],kernel='exp(-distance/sigma^2)',sigma='0.05*pi',
                     distance_squared=False,threshold=0.01,degree_epsilon=1e-5,
                     normalization='D_hat[:,None]*A*D_hat[None,:]',neighbor_operation='weighted sum',
                     self_loop='diagonal starts at exp(0)=1; no extra identity addition',
                     bias=False,classifier=[784,10],output='(logits,probas)',
                     dead_assignments=['A_tensor = self.A.unsqueeze(0); overwritten by self.A.expand(B,-1,-1)'],
                     drawing_scope='live dependencies of forward return plus explicit constructor buffer provenance',
                     model_executed=False),
        profile_label='MNIST28x28 / N=784 / fixed normalized A / one A@pixels / Linear784->10 / eval',
        tree=tree,aux_inputs=[adjacency],
        extra_edges=[
            dict(src='graphnet.float',dst='graphnet.normalize',role='retained_value',label='retain A',
                 src_port='out',dst_port='A',src_side='right',dst_side='right',dashed=False),
            dict(src='graphnet.adjacency',dst='graphnet.expand',role='fixed_buffer',label='buffer A',
                 src_port='out',dst_port='A',src_side='out'),
            dict(src='graphnet.input',dst='graphnet.expand',role='shape_dependency',label='B=x.size(0)',
                 src_port='shape',dst_port='B'),
        ],
        visual_roles={'graphnet.root':'root','graphnet.forward':'encoder','graphnet.layout':'embedding',
                      'graphnet.aggregation':'mixing','graphnet.operands':'inner','graphnet.broadcast':'inner',
                      'graphnet.bmm':'mixing','graphnet.head':'ffn','graphnet.fc':'linear',
                      'graphnet.returns':'group','graphnet.softmax':'softmax','graphnet.output':'output',
                      'graphnet.input':'input','graphnet.adjacency':'control',
                      'graphnet.inv_sqrt':'norm','graphnet.buffer':'control'},
        fill_width=['graphnet.forward','graphnet.layout','graphnet.aggregation','graphnet.head'],
        facts=[
            'Each grayscale28x28 image supplies784 scalar node features; graph edges come only from fixed pixel coordinates.',
            'The helper computes Euclidean distances of coordinates divided by img_size, then exp(-dist/sigma^2), not exp(-dist^2/sigma^2).',
            'Weights below.01 are zeroed, then symmetric inverse-square-root degree factors include epsilon1e-5.',
            'A starts with unit diagonal because distance(i,i)=0; source never separately adds identity or performs row-mean normalization.',
            'GraphNet.__init__ calls the helper once and registers A as a non-learnable persistent buffer, not an optimizer parameter.',
            'The same fixed matrix is broadcast over B with self.A.expand(B,-1,-1); batch size comes from input shape, not pixel values.',
            'The first A_tensor=self.A.unsqueeze(0) assignment executes but is overwritten immediately; its result is not on returned-value dependencies.',
            'bmm outputs[B,N,1]; only the subsequent view creates[B,N]. The variable name avg_neighbor_features is a weighted sum, not a row arithmetic mean.',
            'self.fc=Linear784->10 with bias=False classifies the entire node vector; there is no separate per-node learned feature transform.',
            'forward computes Softmax(dim=1) and actually returns both logits and probabilities. Loss and accuracy decisions are outside forward.',
            'The selected eval profile does not change operators: no Dropout or BatchNorm exists. No model/helper/scipy computation was executed.',
        ],corrections=[
            'Do not replace this simple GraphNet with stacked GCN layers, hidden-node channel projections, ReLU, attention or pooling absent from source.',
            'Do not label A as learned edges, an image-dependent graph, a row-average matrix, or an extra self-loop addition.',
            'Do not silently square distance in the source kernel or discard its threshold and degree epsilon.',
            'Do not chain unused unsqueeze output into expand: source expands self.A directly after overwriting A_tensor.',
            'Do not mix gnn-basic-edge-1 learned edge predictor into this fixed-buffer variant.',
        ],symbols={SOURCE:['precompute_adjacency_matrix','GraphNet','GraphNet.__init__','GraphNet.forward','compute_acc']},
        config_files=[SOURCE],legend=[
            'N=784 pixel nodes; B=batch; scalar node features; same fixed A shared across images',
            'gray side panel: constructor-only graph; dashed A/B routes: buffer and shape dependencies',
            'blue: A@X neighbor sum / purple: whole-image Linear / green: class Softmax',
            'only fc.weight is learnable; branch collection supplies two bmm operands, not a source tuple'],
        color_legend=[('input','Pixels'),('tensor','Tensor layout'),('mixing','Fixed A @ X'),
                      ('linear','Linear head'),('softmax','Softmax'),('control','Fixed buffer')])


def validate_ir(ir):
    nodes={n['id']:n for n in ir['nodes']};edges=ir['edges'];p=ir['profile'];checks=[]
    def check(condition,label):
        if not condition:raise ValueError('graphnet: '+label)
        checks.append(label)
    def has(src,dst,role=None,sp=None,dp=None):
        return any(e['src']==src and e['dst']==dst and (role is None or e['role']==role)
                   and (sp is None or e['src_port']==sp) and (dp is None or e['dst_port']==dp) for e in edges)
    check({'graphnet.kernel','graphnet.threshold','graphnet.normalize','graphnet.buffer','graphnet.expand',
           'graphnet.bmm','graphnet.flatten','graphnet.fc','graphnet.softmax','graphnet.returns'}<=nodes.keys(),
          'required fixed adjacency, aggregation and returned-value nodes')
    check(p['input_size']==[28,28] and p['input_channels']==1 and p['nodes']==784 and p['node_feature_width']==1,
          'MNIST784 scalar pixel nodes')
    check(nodes['graphnet.kernel']['expression']=='np.exp(- dist / sigma ** 2)'
          and nodes['graphnet.kernel']['distance_squared'] is False and nodes['graphnet.threshold']['threshold']==0.01,
          'actual unsquared-distance kernel and .01 threshold')
    check(nodes['graphnet.inv_sqrt']['epsilon']==1e-5 and nodes['graphnet.normalize']['expression']=='D_hat.view(-1,1) * A * D_hat.view(1,-1)',
          'symmetric degree normalization with source epsilon')
    check(nodes['graphnet.buffer']['buffer_identity']=='A' and nodes['graphnet.buffer']['learnable'] is False
          and nodes['graphnet.buffer']['persistent'] is True and nodes['graphnet.adjacency']['execution_scope']=='construction',
          'constructor-only registered non-learnable A buffer')
    check(nodes['graphnet.expand']['expression']=='self.A.expand(B,-1,-1)'
          and has('graphnet.adjacency','graphnet.expand','fixed_buffer',dp='A')
          and has('graphnet.input','graphnet.expand','shape_dependency',sp='shape',dp='B'),
          'fixed buffer broadcast reads A directly and B from input shape')
    operands=nodes['graphnet.operands']
    check(operands['semantic_mode']=='operand_bundle' and operands['literal_tuple'] is False
          and operands['child_inputs']['graphnet.features_operand']==dict(role='value',producer='graphnet.reshape',src_port='out')
          and operands['child_inputs']['graphnet.broadcast']==dict(role='external',producer='graphnet.adjacency',src_port='out'),
          'independent pixel values and fixed adjacency operands')
    check(nodes['graphnet.bmm']['expression']=='torch.bmm(A_tensor,x_reshape)'
          and nodes['graphnet.bmm']['shape']=='[B,784,1]' and nodes['graphnet.flatten']['shape']=='[B,784]'
          and nodes['graphnet.bmm']['ordered_operands']==['graphnet.expand','graphnet.features_operand'],
          'bmm A@X before flatten, without arithmetic row average')
    check(nodes['graphnet.fc']['parameter']=='fc.weight' and nodes['graphnet.fc']['bias'] is False
          and nodes['graphnet.fc']['parameter_shape']==[10,784]
          and {n['parameter'] for n in nodes.values() if 'parameter' in n}=={'fc.weight'},
          'only whole-image bias-free784->10 Linear is learnable')
    check(nodes['graphnet.softmax']['dim']==1 and nodes['graphnet.output']['output_tuple']==['logits','probas']
          and has('graphnet.returns','graphnet.logits','fork') and has('graphnet.returns','graphnet.softmax','fork'),
          'actual logits and class probabilities returned as tuple')
    check(p['dead_assignments']==['A_tensor = self.A.unsqueeze(0); overwritten by self.A.expand(B,-1,-1)']
          and not any('unsqueeze' in n['id'] or n.get('kind') in ('gcn','attention','dropout','batchnorm') for n in nodes.values()),
          'dead unsqueeze excluded without invented GCN or neural graph edges')
    return checks
