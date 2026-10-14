from module_adapters._graph_extended_support import Diagram,validate
SOURCE='mixhop-modules/src/layers.py';KEY='mixhop_dense'
LINKS=[('x','project','X','tensor'),('weight','project','W','parameter_operand'),('project','drop','in','tensor'),('drop','prop0','features','tensor'),('adj','prop0','A','topology'),('prop0','prop1','features','tensor'),('adj','prop1','A','topology'),('prop1','biasadd','features','tensor'),('bias','biasadd','bias','parameter_operand'),('biasadd','output','in','tensor')]
REQUIRED={'weight':dict(parameter='weight_matrix',shape='[12,4]'),'bias':dict(parameter='bias',shape='[1,4]'),'project':dict(expression='torch.mm(features, self.weight_matrix)'),'drop':dict(p=.5),'prop0':dict(iteration=1),'prop1':dict(iteration=2),'biasadd':dict(bias_after_propagation=True,activation=None)}
CONTRACTS=[('DenseNGCNLayer.forward','torch.mm(features, self.weight_matrix)'),('DenseNGCNLayer.forward','range(self.iterations-1)'),('DenseNGCNLayer.forward','base_features + self.bias'),('DenseNGCNLayer.forward','torch.nn.functional.dropout(base_features, p=self.dropout_rate, training=self.training)')]
def build():
 d=Diagram(KEY,'MixHop dense power branch',SOURCE,'DenseNGCNLayer.forward','One DenseNGCNLayer(12,4,iterations3,dropout.5); excludes multi-branch concatenation and classifier.',dict(in_channels=12,out_channels=4,iterations=3,adjacency_multiplications=2,dropout=.5,activation=None,bias_position='after propagation'))
 params=d.ref('DenseNGCNLayer.define_parameters')
 d.input('x','Dense node features','[N,12]');d.input('adj','Supplied normalized sparse A','[N,N]',kind='control');d.input('weight','Owned dense W','[12,4]',kind='parameter',source=params,parameter='weight_matrix');d.input('bias','Owned dense bias','[1,4]',kind='parameter',source=params,parameter='bias')
 d.node('project','Dense X @ W','matmul','[N,4]',0,**REQUIRED['project']);d.node('drop','Dropout .5 / caller mode','dropout','[N,4]',1,p=.5)
 for i in range(2):d.node('prop'+str(i),f'A @ features / pass{i+1}','spmm','[N,4]',i+2,iteration=i+1,opaque_runtime_boundary=True)
 d.node('biasadd','Add bias AFTER propagation','add','[N,4]',4,**REQUIRED['biasadd'])
 for s,t,p,r in LINKS:d.edge(s,t,p,r,ss='left' if s=='adj' else 'out',ds='left' if p=='A' else 'in')
 return d.build(d.entry,'[N,4]','MixHopDense.md',['DenseNGCN differs materially from SparseNGCN: dense mm, Dropout, iterations-1 adjacency products, THEN bias; no ReLU.','iterations3 denotes two repeated uses of supplied adjacency, and the SAME node-feature weight is applied only once.','Sparse multiplication remains an opaque torch_sparse library boundary; normalization is supplied externally.'],['Do not merge sparse/dense NGNC branches merely because both names contain GCN.','Do not move bias before propagation or add a missing ReLU.'])
def validate_ir(ir):return validate(ir,KEY,REQUIRED,LINKS,dict(adjacency_multiplications=2,activation=None,bias_position='after propagation'))
