from module_adapters._graph_extended_support import Diagram,validate
SOURCE='mixhop-modules/src/trainer_and_networks.py';LAYER='mixhop-modules/src/layers.py';KEY='mixhop_layer'
LINKS=[]
REQUIRED={'concat':dict(dim=1,ordered_operands=['upper_layers.0','upper_layers.1','upper_layers.2'],shape='[N,12]')}
for i in range(3):
 b='branch'+str(i);LINKS.extend([('features',b+'.project','sparse_X','tensor'),('params'+str(i),b+'.project','W','parameter_operand'),('params'+str(i),b+'.bias','bias','parameter_operand')])
 if i:
  for j in range(i):LINKS.append(('adj',b+'.prop'+str(j),'A','topology'))
 LINKS.append((b+'.'+('prop'+str(i-1) if i else 'relu'),'concat','branch'+str(i),'tensor'))
 REQUIRED[b]=dict(instance_identity='upper_layers.'+str(i),iterations=i+1,adjacency_multiplications=i)
 REQUIRED[b+'.project']=dict(parameter_scope='upper_layers.'+str(i)+'.weight_matrix',shape='[N,4]')
 REQUIRED[b+'.bias']=dict(parameter_scope='upper_layers.'+str(i)+'.bias',before_propagation=True)
LINKS.append(('concat','output','in','tensor'))
CONTRACTS=[('MixHopNetwork.setup_layer_structure','[SparseNGCNLayer(self.feature_number, self.args.layers_1[i-1], i, self.args.dropout) for i in range(1, self.order_1+1)]'),('MixHopNetwork.forward','torch.cat([self.upper_layers[i](normalized_adjacency_matrix, features) for i in range(self.order_1)], dim=1)')]
EXTRA_CONTRACTS={LAYER:[('SparseNGCNLayer.forward','range(self.iterations-1)'),('SparseNGCNLayer.forward','base_features + self.bias'),('SparseNGCNLayer.forward','torch.nn.functional.relu(base_features)'),('SparseNGCNLayer.forward','spmm(features["indices"], features["values"], feature_count[0], feature_count[1], self.weight_matrix)'),('SparseNGCNLayer.define_parameters','torch.nn.Parameter(torch.Tensor(1, self.out_channels))')]}
def build():
 d=Diagram(KEY,'MixHop sparse multi-power stage',SOURCE,'MixHopNetwork.forward','Only upper_layers sparse stage and first concatenation; excludes bottom DenseNGCN stage, classifier and training losses.',dict(feature_dim=8,layers_1=[4,4,4],dropout=.5,source_iterations=[1,2,3],adjacency_powers=[0,1,2],independent_branch_parameters=True,topology_preprocessing='external'))
 init=d.ref('MixHopNetwork.setup_layer_structure');forward=d.ref('SparseNGCNLayer.forward',LAYER);params=d.ref('SparseNGCNLayer.define_parameters',LAYER)
 d.input('features','Supplied sparse node features','indices / values; [N,8]');d.input('adj','Supplied normalized sparse A','indices / values; [N,N]',kind='control')
 for i in range(3):
  d.input('params'+str(i),f'Branch{i} owned W, bias','W[8,4]; b[1,4]',kind='parameter',source=[init,params],instance_identity='upper_layers.'+str(i),parameters=['weight_matrix','bias'])
  scope='upper_layers.'+str(i);b='branch'+str(i)
  steps=[('project','Sparse X @ OWNED W','spmm','[N,4]',{k:v for k,v in REQUIRED[b+'.project'].items() if k!='shape'}),('bias','Add OWNED bias BEFORE A','add','[N,4]',REQUIRED[b+'.bias']),('drop','Dropout .5 / caller mode','dropout','[N,4]',dict(p=.5)),('relu','ReLU BEFORE propagation','relu','[N,4]',dict())]
  for j in range(i):steps.append(('prop'+str(j),f'A @ features / pass{j+1}','spmm','[N,4]',dict(opaque_runtime_boundary=True,same_topology=True)))
  d.stage(b,f'Branch{i}: A^{i} / iterations{i+1}','[N,4]',0,steps,source=[init,forward,params],suppress_input_boundary=True,**REQUIRED[b])
 d.node('concat','Concat independent power branches','cat','[N,12]',1,**{k:v for k,v in REQUIRED['concat'].items() if k!='shape'})
 for s,t,p,r in LINKS:d.edge(s,t,p,r,ss='right' if s=='adj' or p=='bias' else 'out',ds='right' if p=='A' or p=='bias' else 'in')
 return d.build(d.entry,'[N,12]','MixHopLayer.md',['The selected source constructs three SparseNGCNLayer instances with iterations1,2,3, then concatenates their outputs.','Source loop range(iterations-1) produces ZERO, ONE, TWO adjacency multiplications; do not label branches A^1,A^2,A^3.','Each sparse branch applies sparse feature projection, bias, Dropout and ReLU BEFORE any adjacency propagation.','Branch weights/biases are independent owned instances; sparse input and supplied normalized topology are reused. Shape uses the source max sparse index+1 inference, not an observed execution.'],['Do not substitute the DenseNGCN bias-at-end behavior or textbook sigma(A^j X W) ordering for this sparse source stage.','Do not include the entire MixHop task model in a module diagram.'])
def validate_ir(ir):return validate(ir,KEY,REQUIRED,LINKS,dict(adjacency_powers=[0,1,2],independent_branch_parameters=True))
