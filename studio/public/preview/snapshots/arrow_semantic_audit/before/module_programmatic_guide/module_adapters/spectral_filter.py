"""Truncated-basis GraphNet filtering subgraph with true registered buffers."""
from module_adapters.support import chain, op, graph, ref, finish

SOURCE='rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py'
GRAD_STATUS='runtime-dependent: Parameter created requires_grad=True; float/to identity not executed'


def build():
    init=ref(SOURCE,'GraphNet.__init__');fwd=ref(SOURCE,'GraphNet.forward')
    adj=ref(SOURCE,'precompute_adjacency_matrix');lap=ref(SOURCE,'get_graph_laplacian')
    basis=chain('spectral.basis_init','Fixed basis / constructor',[
        op('spectral.adj','Grid adjacency helper','mixing',adj,'A: [784,784]',
           ['coords / img_size; Euclidean distance; exp(-dist/sigma^2); values<.01 set to0'],
           expression='np.exp(- dist / sigma ** 2)',distance_squared=False,sigma='0.05*np.pi',
           threshold=0.01,normalized_adjacency=False),
        op('spectral.laplacian','Normalized graph Laplacian','norm',lap,'L: [784,784]',
           ['D=sum(A,axis=0); D_hat=diag((D+1e-5)^(-.5)); L=I-D_hat A D_hat'],
           expression='np.identity(N) - np.dot(D_hat, A).dot(D_hat)',degree_axis=0,epsilon=1e-5),
        op('spectral.eigsh','eigsh / SciPy boundary','control',init,'V: [784,20]; Lambda: [20]',
           ['eigsh(L.numpy(),k=20,which="SM"); library internals not expanded or executed'],
           expression="eigsh(L.numpy(), k=20, which='SM')",library_boundary='scipy.sparse.linalg.eigsh',
           k=20,which='SM',executed=False,eigenvalues_used_in_forward=False),
        op('spectral.vbuffer','from_numpy(V) / register V','control',init,'V: [784,20]',
           ['A and L are also registered buffers; V has no explicit .float() in source'],
           expression="V = torch.from_numpy(V); self.register_buffer('V', V)",
           buffer_identity='V',storage_kind='buffer',learnable=False,persistent=True,
           dtype='inherits eigsh array; not forced to float32'),
    ],[adj,lap,init],'V: [N=784,K=20]',expand=2,execution_scope='construction',
       buffer_identity='V',learnable=False)
    weights=chain('spectral.w_init','Filter buffer / constructor',[
        op('spectral.wcreate','Create Parameter / cast float','control',init,'W: [784,2]',
           ['Constructor expression starts with nn.Parameter; storage is decided by later registration'],
           expression='nn.Parameter(torch.ones((img_size**2, num_filters))).float()',
           construction_origin='nn.Parameter',requires_grad=GRAD_STATUS,not_executed=True),
        op('spectral.wkaiming','Kaiming uniform init','control',init,'W: [784,2]',
           expression='torch.nn.init.kaiming_uniform_(W_spectral)',execution_scope='construction'),
        op('spectral.wbuffer','Register W buffer','control',init,'W_spectral: [784,2]',
           ['Buffer registration does not expose W via model.parameters(); grad state is runtime dependent'],
           expression="self.register_buffer('W_spectral', W_spectral)",buffer_identity='W_spectral',
           storage_kind='buffer',optimizer_parameter=False,requires_grad=GRAD_STATUS,persistent=True),
    ],init,'registered W: [N=784,F=2]',expand=2,execution_scope='construction',
       buffer_identity='W_spectral',storage_kind='buffer',optimizer_parameter=False,requires_grad=GRAD_STATUS)
    # 300+2*32=364px panels leave31px to the main frame in the420px gutter.
    for constructor in (basis,weights):
        for item in constructor['items']:item['width']=300
    xbranch=chain('spectral.xbranch','Image to node features',[
        op('spectral.input','Input grayscale image','input',fwd,'[B,1,28,28]',input_channels=1),
        op('spectral.reshape','view(B,-1,1)','tensor',fwd,'X: [B,784,1]',expression='x.view(B,-1,1)'),
    ],fwd,'X: [B,784,1]',expand=1,suppress_input_boundary=True)
    vbranch=chain('spectral.vbranch','Basis read / transpose view',[
        op('spectral.vread','Read same V buffer','input',[init,fwd],'V: [784,20]',
           expression='self.V',buffer_identity='V',storage_kind='buffer'),
        op('spectral.vt','V.T.expand(B,-1,-1)','tensor',fwd,'V_T: [B,20,784]',
           expression='self.V.T.expand(B,-1,-1)',buffer_identity='V',broadcast_batch=True,
           input_ports=['V','B'],no_copy=True),
    ],[init,fwd],'V_T: [B,20,784]',expand=1,suppress_input_boundary=True)
    wbranch=chain('spectral.wbranch','Node-domain filter read',[
        op('spectral.wread','Read W_spectral buffer','input',[init,fwd],'W: [784,2]',
           expression='self.W_spectral',buffer_identity='W_spectral',storage_kind='buffer',
           optimizer_parameter=False,requires_grad=GRAD_STATUS),
        op('spectral.wexpand','W.expand(B,-1,-1)','tensor',fwd,'W_batch: [B,784,2]',
           expression='self.W_spectral.expand(B,-1,-1)',buffer_identity='W_spectral',broadcast_batch=True,
           input_ports=['W','B'],no_copy=True),
    ],[init,fwd],'W_batch: [B,784,2]',expand=1,suppress_input_boundary=True)
    def project(identity,title,expression,shape,operands,ports):
        return chain(identity,title,[op(identity+'.bmm','Batch MatMul / '+title.split(' / ')[0],'mixing',fwd,shape,
                expression=expression,operation='bmm',ordered_operands=operands,input_ports=ports)],
            fwd,shape,expand=2,suppress_input_boundary=True)
    xp=project('spectral.xproject','Signal projection / V_T @ X','V_tensor_T.bmm(x_reshape)',
               '[B,20,1]',['spectral.vt','spectral.reshape'],['V_T','X'])
    wp=project('spectral.wproject','Filter projection / V_T @ W','V_tensor_T.bmm(W_spectral_tensor)',
               '[B,20,2]',['spectral.vt','spectral.wexpand'],['V_T','W'])
    vb=op('spectral.vexpand','V.expand(B,-1,-1)','tensor',fwd,'V_batch: [B,784,20]',
          expression='self.V.expand(B,-1,-1)',buffer_identity='V',broadcast_batch=True,
          input_ports=['V','B'],no_copy=True)
    product=op('spectral.product','Broadcast elementwise multiply','multiply',fwd,'[B,20,2]',
               ['[B,20,1] * [B,20,2]; singleton channel broadcasts across F=2'],
               expression='X_hat * W_hat',operation='elementwise_multiply',broadcast_axis=2,
               ordered_operands=['spectral.xproject.bmm','spectral.wproject.bmm'])
    inv=project('spectral.reconstruct','Reconstruct / V @ product','V_tensor.bmm(X_hat * W_hat)',
                '[B,784,2]',['spectral.vexpand','spectral.product'],['V','product'])
    filtering=graph('spectral.filter','Truncated spectral filtering',[xp,wp,vb,product,inv],fwd,'Y: [B,784,2]',
        ['Two real projections; multiplication broadcasts channels; same V reconstructs nodes'],
        ranks=[['spectral.xproject','spectral.wproject'],['spectral.vexpand','spectral.product'],['spectral.reconstruct']],
        expand=1,rank_gap=72,column_gap=64,
        align_x={'spectral.vexpand':'spectral.xproject','spectral.product':'spectral.wproject'},literal_tuple=False)
    output=op('spectral.output','Module result / node features Y','output',fwd,'[B,784,2]',
              expression='Y',output_shape=['B',784,2],classifier_excluded=True)
    tree=graph('spectral.root','SpectralFilter / selected subgraph',[xbranch,vbranch,wbranch,filtering,output],
        [init,fwd],'X + V + W -> Y',ranks=[['spectral.xbranch','spectral.vbranch','spectral.wbranch'],
            ['spectral.filter'],['spectral.output']],expand=0,rank_gap=72,column_gap=64,
        literal_tuple=False,semantic_scope='forward_filtering_only')
    edges=[]
    def edge(src,dst,dp,role='tensor',sp='out',ss='out',ds='in',label=''):
        edges.append(dict(src=src,dst=dst,src_port=sp,dst_port=dp,role=role,
                          src_side=ss,dst_side=ds,dashed=role!='tensor',label=label))
    edge('spectral.basis_init','spectral.vread','V','fixed_buffer',ss='right',ds='left')
    edge('spectral.w_init','spectral.wread','W','fixed_buffer',ss='right',ds='left')
    edge('spectral.reshape','spectral.xproject.bmm','X')
    edge('spectral.vt','spectral.xproject.bmm','V_T')
    edge('spectral.vt','spectral.wproject.bmm','V_T')
    edge('spectral.wexpand','spectral.wproject.bmm','W')
    edge('spectral.xproject.bmm','spectral.product','X_hat')
    edge('spectral.wproject.bmm','spectral.product','W_hat')
    edge('spectral.vread','spectral.vexpand','V',role='fixed_buffer',ss='left',ds='left')
    edge('spectral.vexpand','spectral.reconstruct.bmm','V')
    edge('spectral.product','spectral.reconstruct.bmm','product')
    edge('spectral.reconstruct.bmm','spectral.output','Y')
    for target in ('spectral.vt','spectral.vexpand','spectral.wexpand'):
        edge('spectral.input',target,'B','shape_dependency','shape',ss='right',ds='right')
    return finish(dict(key='spectral_filter',name='SpectralFilter (truncated graph basis module)',
        source_project='rasbt-modules',entry=fwd,doc='SpectralFilter.md',
        module_scope='GraphNet forward image/buffer reads through Y reconstruction; excludes flatten, fc, Softmax and training.',
        profile=dict(img_size=28,nodes=784,input_channels=1,num_filters=2,k=20,which='SM',
            input_shape=['B',1,28,28],basis_shape=[784,20],filter_shape=[784,2],output_shape=['B',784,2],
            registered_buffers=['A','L','V','W_spectral'],module_parameter_families=[],
            W_spectral_storage='buffer',W_spectral_optimizer_parameter=False,W_spectral_requires_grad=GRAD_STATUS,
            V_dtype='torch.from_numpy preserves eigsh array dtype; compatibility not executed',
            spectral_coefficients='V_T @ node-domain W at each forward; not a stored20xF coefficient parameter',
            reconstruction='V @ ((V_T @ X) * (V_T @ W))',eigenvalues_used_in_forward=False,
            dead_assignments=['V_tensor = self.V.unsqueeze(0)', 'V_tensor_T = self.V.T.unsqueeze(0)',
                              'W_spectral_tensor = self.W_spectral.unsqueeze(0)'],
            dead_assignment_reason='Each temporary is immediately overwritten by direct buffer.expand, not used by returned filtering values',
            source_activation=None,model_executed=False),
        profile_label='N=784 / K=20 / F=2 / V,X,W operands / buffer W / module only',
        tree=tree,aux_inputs=[basis,weights],extra_edges=edges,
        visual_roles={'spectral.root':'root','spectral.filter':'encoder','spectral.xbranch':'embedding',
            'spectral.vbranch':'inner','spectral.wbranch':'inner','spectral.basis_init':'control',
            'spectral.w_init':'control','spectral.xproject':'mixing','spectral.wproject':'mixing',
            'spectral.reconstruct':'mixing','spectral.product':'concat'},
        symbols={SOURCE:['precompute_adjacency_matrix','get_graph_laplacian','GraphNet.__init__','GraphNet.forward']},
        config_files=[SOURCE],facts=[
            'Selected boundary ends at Y; it excludes the enclosing classification head and all training operations.',
            'Constructor creates A from an unsquared Euclidean-distance exponential kernel and threshold. Its triple-quoted degree-normalization block after return is not executed.',
            'L=I-D_hat A D_hat uses D=sum(A,axis0),epsilon1e-5; eigsh returns20 smallest-magnitude modes, not a full784-mode basis.',
            'A,L,V,W_spectral are all explicitly register_buffer entries. W starts from nn.Parameter(...).float(), then buffer registration; model.parameters() does not discover W through this registration.',
            'Whether float/to preserves Parameter identity, leaf status and gradients depends dtype/runtime. Drawing does not execute these conversions or claim W has requires_grad=False.',
            'V=torch.from_numpy(V) has no explicit float32 conversion. Dtype compatibility of bmm must be checked in a separate runtime audit; this source-grounded example does not silently cast or fix source.',
            'Live batch views are self.V.expand,self.V.T.expand,self.W_spectral.expand; three earlier unsqueeze assignments are overwritten and omitted from the live-dependency graph.',
            'X_hat=V_T@X is[B,20,1], W_hat=V_T@W is[B,20,2]; elementwise multiplication broadcasts the singleton feature axis.',
            'Reconstruction uses the same V buffer and produces Y[B,784,2]; Lambda is computed during construction but is not used in forward.',
            'W is a node-domain784x2 buffer, projected every forward; it is not a stored20x2 learned spectral coefficient parameter.',
            'Ranks are layout constraints on dependency stages; they do not promise Python parallel execution or reproduce the textual assignment order.',
        ],corrections=[
            'Do not label this example FFT, Chebyshev filtering, a full eigendecomposition or a canonical learned GCN.',
            'Do not label W an optimizer parameter solely because its construction starts with nn.Parameter.',
            'Do not add eigenvalue multiplication, activation, pooling or a classification head inside the selected module.',
            'Do not chain overwritten unsqueeze results into expand or collapse Y into a one-channel image.',
        ],legend=['Blue: batch views and bmm / yellow: Laplacian or elementwise merge / gray: constructor buffers',
            'Three bottom operands are independent values, not a tuple fork from image pixels',
            'V read/projection/reconstruction reuse one buffer identity; dashed shape edges carry B only',
            'W_spectral is registered as buffer; optimizer discovery and autograd status are separate properties'],
        color_legend=[('input','X / V / W'),('mixing','bmm'),('tensor','Batch view'),
            ('concat','Product'),('control','Constructor'),('output','Y')]))


def validate_ir(ir):
    n={node['id']:node for node in ir['nodes']};p=ir['profile'];edges=ir['edges'];checks=[]
    def check(condition,label):
        if not condition:raise ValueError('spectral_filter: '+label)
        checks.append(label)
    def has(src,dst,dp,role='tensor',sp='out'):
        return any(e['src']==src and e['dst']==dst and e['src_port']==sp and e['dst_port']==dp and e['role']==role for e in edges)
    check(ir['artifact_scope']=='module' and n['spectral.root']['semantic_scope']=='forward_filtering_only','module-only forward filtering boundary')
    check(p['nodes']==784 and p['k']==20 and p['num_filters']==2 and p['basis_shape']==[784,20]
          and p['filter_shape']==[784,2] and p['output_shape']==['B',784,2],'actual truncated basis and two-channel output shapes')
    check(n['spectral.eigsh']['k']==20 and n['spectral.eigsh']['which']=='SM'
          and n['spectral.eigsh']['library_boundary']=='scipy.sparse.linalg.eigsh' and n['spectral.eigsh']['executed'] is False,'constructor eigsh library boundary remains unexecuted')
    check(n['spectral.adj']['distance_squared'] is False and n['spectral.adj']['threshold']==0.01
          and n['spectral.adj']['normalized_adjacency'] is False and n['spectral.laplacian']['degree_axis']==0
          and n['spectral.laplacian']['epsilon']==1e-5,'real adjacency/laplacian provenance, not string-block normalization')
    check(p['registered_buffers']==['A','L','V','W_spectral'] and n['spectral.vbuffer']['buffer_identity']=='V'
          and n['spectral.vbuffer']['learnable'] is False,'source registered graph/basis buffers')
    check(n['spectral.wbuffer']['storage_kind']=='buffer' and n['spectral.wbuffer']['optimizer_parameter'] is False
          and n['spectral.wread']['storage_kind']=='buffer' and n['spectral.wread']['optimizer_parameter'] is False
          and p['W_spectral_optimizer_parameter'] is False and p['module_parameter_families']==[]
          and not any('parameter' in node for node in n.values()),'W buffer is not discovered through model.parameters')
    check(n['spectral.wcreate']['construction_origin']=='nn.Parameter'
          and n['spectral.wbuffer']['requires_grad']==GRAD_STATUS and p['W_spectral_requires_grad']==GRAD_STATUS,'conditional autograd state separate from buffer registration')
    check(n['spectral.vbuffer']['dtype']=='inherits eigsh array; not forced to float32','no invented V dtype cast')
    for identity,expr,shape in [('spectral.vt','self.V.T.expand(B,-1,-1)','V_T: [B,20,784]'),
            ('spectral.vexpand','self.V.expand(B,-1,-1)','V_batch: [B,784,20]'),
            ('spectral.wexpand','self.W_spectral.expand(B,-1,-1)','W_batch: [B,784,2]')]:
        check(n[identity]['expression']==expr and n[identity]['shape']==shape
              and has('spectral.input',identity,'B','shape_dependency','shape'),identity+' direct buffer expansion with real B shape dependency')
    check(has('spectral.reshape','spectral.xproject.bmm','X')
          and has('spectral.vt','spectral.xproject.bmm','V_T')
          and has('spectral.vt','spectral.wproject.bmm','V_T')
          and has('spectral.wexpand','spectral.wproject.bmm','W'),'two projections consume independent correct ordered operands')
    check(n['spectral.xproject.bmm']['expression']=='V_tensor_T.bmm(x_reshape)'
          and n['spectral.xproject.bmm']['shape']=='[B,20,1]'
          and n['spectral.xproject.bmm']['ordered_operands']==['spectral.vt','spectral.reshape']
          and n['spectral.wproject.bmm']['expression']=='V_tensor_T.bmm(W_spectral_tensor)'
          and n['spectral.wproject.bmm']['shape']=='[B,20,2]'
          and n['spectral.wproject.bmm']['ordered_operands']==['spectral.vt','spectral.wexpand'],'signal and node-domain filter projected every forward')
    check(n['spectral.product']['kind']=='multiply' and n['spectral.product']['expression']=='X_hat * W_hat' and n['spectral.product']['operation']=='elementwise_multiply'
          and n['spectral.product']['broadcast_axis']==2 and n['spectral.product']['shape']=='[B,20,2]'
          and has('spectral.xproject.bmm','spectral.product','X_hat') and has('spectral.wproject.bmm','spectral.product','W_hat'),'singleton-channel broadcast multiply, not matmul or concat')
    check(n['spectral.reconstruct.bmm']['expression']=='V_tensor.bmm(X_hat * W_hat)'
          and has('spectral.vread','spectral.vexpand','V','fixed_buffer')
          and has('spectral.vexpand','spectral.reconstruct.bmm','V')
          and has('spectral.product','spectral.reconstruct.bmm','product')
          and n['spectral.reconstruct.bmm']['ordered_operands']==['spectral.vexpand','spectral.product']
          and n['spectral.output']['output_shape']==['B',784,2],'same truncated V reconstructs two node-feature channels')
    check(p['eigenvalues_used_in_forward'] is False and p['source_activation'] is None
          and len(p['dead_assignments'])==3 and not any('unsqueeze' in node['id'] for node in n.values()),'unused eigenvalues and overwritten unsqueeze omitted from live dependencies')
    check(not any(e['role']=='fork' for e in edges) and not any(node.get('parameter')=='fc.weight' or node.get('kind')=='softmax' for node in n.values()),'no artificial image fork, classifier or activation')
    return checks
