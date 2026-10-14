from module_adapters._graph_extended_support import Diagram,validate
SOURCE='pygcn-modules/pygcn/layers.py'
KEY='sparse_gcn'
def build():
    d=Diagram(KEY,'Sparse GCN layer',SOURCE,'GraphConvolution.forward','One GraphConvolution(8,4,bias=True); excludes the GCN classifier and normalization preprocessing.',dict(in_features=8,out_features=4,bias=True,adjacency_normalized_inside=False,activation=None))
    init=d.ref('GraphConvolution.__init__')
    d.input('x','Node features X','[N,8]');d.input('adj','Supplied sparse adjacency','[N,N]',kind='control',normalization='external',learnable=False)
    d.input('weight','Owned weight W','[8,4]',kind='parameter',source=init,parameter='weight');d.input('bias','Owned bias b','[4]',kind='parameter',source=init,parameter='bias')
    d.stage('project','Feature projection','[N,4]',0,[('mm','X @ W','matmul','[N,4]',dict(expression='torch.mm(input, self.weight)',ordered_operands=['x','weight']))],suppress_input_boundary=True)
    d.stage('aggregate','Sparse neighbor sum','[N,4]',1,[('spmm','A @ support','spmm','[N,4]',dict(expression='torch.spmm(adj, support)',ordered_operands=['adj','project.mm'],opaque_runtime_boundary=True))],suppress_input_boundary=True)
    d.node('add','Broadcast bias add','add','[N,4]',2,expression='output + self.bias')
    for src,dst,port,role in LINKS:d.edge(src,dst,port,role)
    return d.build(d.entry,'[N,4]','SparseGCN.md',['Source projects node features before sparse adjacency multiplication.','Adjacency is supplied by caller; this layer does not add self-loops, compute degree normalization or apply ReLU.','Weight[Nin,Nout] and bias[Nout] are owned Parameters; same weight is used for every node.'],['Do not substitute the existing fixed GraphNet A@pixels: this layer has an actual learned node-feature projection.','Do not add preprocessing or classifier layers from a textbook GCN.'])
LINKS=[('x','project.mm','X','tensor'),('weight','project.mm','W','parameter_operand'),('adj','aggregate.spmm','A','topology'),('project.mm','aggregate.spmm','support','tensor'),('aggregate.spmm','add','value','tensor'),('bias','add','bias','parameter_operand'),('add','output','in','tensor')]
REQUIRED={'project.mm':dict(expression='torch.mm(input, self.weight)'), 'aggregate.spmm':dict(expression='torch.spmm(adj, support)'), 'weight':dict(parameter='weight',shape='[8,4]'),'add':dict(expression='output + self.bias')}
CONTRACTS=[('GraphConvolution.forward','torch.mm(input, self.weight)'),('GraphConvolution.forward','torch.spmm(adj, support)'),('GraphConvolution.forward','output + self.bias')]
def validate_ir(ir):return validate(ir,KEY,REQUIRED,LINKS,dict(adjacency_normalized_inside=False,activation=None))
