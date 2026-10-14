from module_adapters._graph_extended_support import Diagram,validate
SOURCE='graphwavelet-modules/src/gwnn_layer.py'

def definitions(sparse):
 links=[('phi','rescale','phi','topology'),('diagindices','rescale','theta_indices','fixed_state'),('theta','rescale','theta_values','parameter_operand'),('rescale','kernel','rescaled_phi','tensor'),('inverse','kernel','phi_inverse','topology'),('x','project','X','tensor'),('weight','project','W','parameter_operand'),('kernel','localize','kernel','tensor'),('project','localize','features','tensor')]
 links+=([('localize','tail.relu','in','tensor'),('tail.drop','output','in','tensor')] if sparse else [('localize','output','in','tensor')])
 required={'diagindices':dict(storage_kind='ordinary Tensor attribute',registered_buffer=False,parameter=False),'theta':dict(parameter='diagonal_weight_filter',shape='[N,1]'),'weight':dict(parameter='weight_matrix',shape='[8,4]'),'rescale':dict(ordered_operands=['phi','diag(theta)'],operation='spspmm'),'kernel':dict(ordered_operands=['phi@diag(theta)','phi_inverse'],operation='spspmm'),'project':dict(operation='spmm' if sparse else 'mm'),'localize':dict(ordered_operands=['phi@diag(theta)@phi_inverse','X@W'],operation='spmm')}
 if sparse:required['tail.drop']=dict(p=.5,training='self.training');required['tail.relu']=dict(kind='relu')
 return links,required

def build_wavelet(key,sparse):
 cls='SparseGraphWaveletLayer' if sparse else 'DenseGraphWaveletLayer';links,required=definitions(sparse)
 d=Diagram(key,'Graph wavelet '+('sparse' if sparse else 'dense')+' layer',SOURCE,cls+'.forward','One '+cls+' only; supplied wavelet/inverse matrices, excludes wavelet construction, classifier and task network.',dict(in_channels=8,out_channels=4,ncount='N',input_sparse=sparse,theta_learned=True,diagonal_indices_buffer=False,dropout=.5 if sparse else None,activation='relu' if sparse else None,phi_preprocessing='external',library_kernels='opaque torch_sparse spmm/spspmm'))
 params=d.ref('GraphWaveletLayer.define_parameters');d.ref('GraphWaveletLayer.init_parameters')
 d.input('x','Sparse X indices / values' if sparse else 'Dense node features X','[N,8]');d.input('phi','Supplied sparse wavelet Phi','indices / values; [N,N]',kind='control');d.input('inverse','Supplied sparse inverse Phi','indices / values; [N,N]',kind='control');d.input('diagindices','Fixed diagonal index Tensor','[2,N]',kind='control',source=params,**required['diagindices']);d.input('theta','Owned diagonal filter theta','[N,1]',kind='parameter',source=params,parameter='diagonal_weight_filter');d.input('weight','Owned feature projection W','[8,4]',kind='parameter',source=params,parameter='weight_matrix')
 d.node('rescale','Sparse Phi @ diag(theta)','mixing','sparse pair [N,N]',0,**required['rescale'],opaque_runtime_boundary=True,theta_view='view(-1)')
 d.node('project','Sparse X @ W' if sparse else 'Dense X @ W','spmm' if sparse else 'matmul','[N,4]',0,**required['project'],opaque_runtime_boundary=sparse)
 d.node('kernel','Rescaled Phi @ Phi inverse','mixing','sparse pair [N,N]',1,**required['kernel'],opaque_runtime_boundary=True)
 d.node('localize','Learned wavelet kernel @ XW','spmm','[N,4]',2,**required['localize'],opaque_runtime_boundary=True)
 if sparse:d.stage('tail','ReLU THEN Dropout .5','[N,4]',3,[('relu','ReLU localized features','relu','[N,4]',dict()),('drop','Dropout .5 / caller mode','dropout','[N,4]',required['tail.drop'])])
 for s,t,p,r in links:d.edge(s,t,p,r,ss='left' if s=='inverse' or t=='localize' and p=='features' else 'out',ds='left' if s=='inverse' or t=='localize' and p=='features' else 'in')
 return d.build(d.entry,'[N,4]','GraphWavelet'+('Sparse' if sparse else 'Dense')+'.md',['Source constructs Phi @ diag(theta) first, multiplies by supplied Phi_inverse second, then applies resulting sparse kernel to X@W. Parentheses, sparse representation and multiplication order remain explicit.','theta[N,1] and W[8,4] are learned Parameters. Diagonal_weight_indices is an ordinary Tensor attribute moved to device, NOT registered_buffer and NOT Parameter.','Supplied Phi/inverse preprocessing and torch_sparse kernels stay opaque. The diagram does not assert an orthogonal transform, compute a wavelet spectrum or run sparse products.','Sparse forward applies ReLU then caller-mode Dropout after localization; Dense forward returns localization directly with no activation or Dropout.'],['Do not equate this learned diagonal graph-wavelet filter with the existing eigenspace elementwise SpectralFilter.','Do not register the fixed indices as a buffer absent in source or copy Sparse tail into Dense version.'])

def validate_wavelet(ir,key,sparse):
 links,required=definitions(sparse);return validate(ir,key,required,links,dict(input_sparse=sparse,diagonal_indices_buffer=False,activation='relu' if sparse else None))
