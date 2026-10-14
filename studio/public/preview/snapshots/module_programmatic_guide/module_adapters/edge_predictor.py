"""Only the coordinate-to-edge subgraph, never the enclosing classifier."""
from module_adapters.support import chain, op, ref, finish

SOURCE = 'rasbt-modules/pytorch_ipynb/gnn/gnn-basic-edge-1.py'


def build():
    init=ref(SOURCE,'GraphNet.__init__');fwd=ref(SOURCE,'GraphNet.forward')
    helper=ref(SOURCE,'make_coordinate_array')
    provenance=chain('edge.init','Coordinate buffer / constructor',[
        op('edge.grid','Grid coordinates / standardize','tensor',helper,'[784,2]',
           ['stack(col,row); mean/std independently per coordinate axis'],
           expression='(coord - np.mean(coord, axis=0)) / (np.std(coord, axis=0) + 1e-5)',
           epsilon=1e-5,coordinate_order=['col','row'],learnable=False),
        op('edge.pairs','Ordered coordinate pairs','concat',helper,'[784,784,4]',
           ['coord[i,j] = [col_j,row_j,col_i,row_i]; float tensor; concat dim=2'],
           expression='torch.cat((coord.unsqueeze(0).repeat(n_rows,1,int(out_size/2-1)),coord.unsqueeze(1).repeat(1,n_rows,1)),dim=2)',
           pair_order=['j.col','j.row','i.col','i.row'],dim=2,dtype='float32'),
        op('edge.buffer','Register coord buffer','control',init,'coord: [784,784,4]',
           expression="self.register_buffer('coord', coord)",buffer_identity='coord',
           storage_kind='buffer',learnable=False,persistent=True),
    ],[helper,init],'coord: [N,N,4]',
       ['Fixed grid coordinates; no image pixels or batch values'],expand=2,execution_scope='construction',
       buffer_identity='coord',storage_kind='buffer',learnable=False)
    mlp=chain('edge.mlp','Shared edge MLP / 4 -> 32 -> 1',[
        op('edge.linear1','Linear 4 -> 32','linear',[init,fwd],'[784,784,32]',
           parameter='pred_edge_fc.0',parameter_tensors=['pred_edge_fc.0.weight','pred_edge_fc.0.bias'],
           parameter_shape=[32,4],bias_shape=[32],in_features=4,out_features=32,bias=True,
           instance_identity='self.pred_edge_fc.0',shared_across='all ordered coordinate pairs'),
        op('edge.relu','ReLU','activation',[init,fwd],'[784,784,32]',inplace=False),
        op('edge.linear2','Linear 32 -> 1','linear',[init,fwd],'[784,784,1]',
           parameter='pred_edge_fc.2',parameter_tensors=['pred_edge_fc.2.weight','pred_edge_fc.2.bias'],
           parameter_shape=[1,32],bias_shape=[1],in_features=32,out_features=1,bias=True,
           instance_identity='self.pred_edge_fc.2',shared_across='all ordered coordinate pairs'),
        op('edge.tanh','Tanh / signed edge weights','tanh',[init,fwd],'[784,784,1]',
           activation='tanh',normalized_over_neighbors=False,range='(-1,1)'),
    ],[init,fwd],'[N,N,1]',expand=2,
       detail=['One Sequential instance is applied to every pair; not N*N separate MLPs'],
       instance_identity='self.pred_edge_fc',shared_across='all ordered coordinate pairs')
    forward=chain('edge.forward','Coordinate-to-adjacency module',[
        mlp,
        op('edge.squeeze','squeeze() + assign self.A','tensor',fwd,'A: [784,784]',
           expression='self.A = self.pred_edge_fc(self.coord).squeeze()',squeeze_dim=None,
           storage_kind='ordinary_tensor_attribute',registered_parameter=False,registered_buffer=False,
           recomputed_each_forward=True,image_conditioned=False),
    ],fwd,'A: [N,N]',expand=1)
    tree=chain('edge.root','EdgePredictor / selected subgraph',[
        op('edge.coord','Read registered coord buffer','input',[init,fwd],'[784,784,4]',
           expression='self.coord',buffer_identity='coord',storage_kind='buffer',learnable=False),
        forward,
        op('edge.output','Module result / adjacency A','output',fwd,'[784,784]',
           value='self.A',image_conditioned=False,requires_batch_axis=False),
    ],[init,fwd],'coord -> A',expand=0)
    return finish(dict(key='edge_predictor',name='EdgePredictor (coordinate-to-adjacency module)',
        source_project='rasbt-modules',entry=fwd,doc='EdgePredictor.md',
        module_scope='GraphNet.__init__.pred_edge_fc + forward coordinate-to-A expression; excludes pixel aggregation and classifier.',
        profile=dict(img_size=28,nodes=784,coord_features=4,hidden_features=32,output_features=1,
            input_shape=[784,784,4],output_shape=[784,784],pair_order=['j.col','j.row','i.col','i.row'],
            fixed_input_buffer='coord',weight_sharing='one pred_edge_fc instance for all ordered pairs',
            learnable_parameter_families=['pred_edge_fc.0','pred_edge_fc.2'],parameter_count=193,
            activation='Tanh',adjacency_image_conditioned=False,adjacency_batch_axis=False,
            adjacency_storage='ordinary tensor attribute self.A',symmetric_guaranteed=False,
            degree_normalization=False,threshold=False,model_executed=False),
        profile_label='N=784 / fixed ordered coords / shared MLP4->32->1 / signed A / module only',
        tree=tree,aux_inputs=[provenance],
        extra_edges=[dict(src='edge.init',dst='edge.coord',role='fixed_buffer',src_port='out',dst_port='coord',label='fixed coord')],
        visual_roles={'edge.root':'root','edge.forward':'encoder','edge.mlp':'ffn','edge.init':'control',
            'edge.tanh':'softmax','edge.buffer':'control'},fill_width=['edge.forward','edge.mlp'],
        symbols={SOURCE:['make_coordinate_array','GraphNet.__init__','GraphNet.forward']},config_files=[SOURCE],
        facts=[
            'This module boundary selects only self.pred_edge_fc(self.coord).squeeze(); pixel reshape/bmm, fc and Softmax are outside the artifact.',
            'make_coordinate_array standardizes each coordinate axis with epsilon1e-5, converts to float and concatenates ordered pairs.',
            'coord[i,j] is [col_j,row_j,col_i,row_i]; the helper does not encode undirected pair symmetry.',
            'coord is a fixed persistent buffer; one shared Sequential instance applies Linear4->32,ReLU,Linear32->1,Tanh to every pair.',
            'Linear defaults retain both biases; only the two Linear families contribute193 learned scalar parameters within this boundary.',
            'The resulting signed A depends on learned MLP weights and fixed coordinates, not image intensities or batch size.',
            'self.A is recomputed and assigned to an ordinary tensor attribute each forward; it is not registered as a parameter or buffer.',
            'No threshold, Softmax, symmetric constraint or degree normalization is present in this edge predictor.',
            'squeeze has no dim argument; with selected N784 it removes the final singleton. Other degenerate sizes need a separately reviewed shape profile.',
        ],corrections=[
            'Do not draw image pixels or batch B as edge-predictor inputs.',
            'Do not draw N*N independent MLPs, learned coordinate embeddings, normalized attention or guaranteed symmetric edges.',
            'Do not include the enclosing GraphNet classifier in this module-only example.',
        ],legend=['Pink: fixed coord read / purple: shared Linear / gray: ReLU / green: Tanh',
            'Gray side panel: constructor-only provenance; dashed edge supplies the registered coord buffer',
            'Matching Linear glyphs indicate an operator family; identities .0 and .2 denote distinct parameter tensors'],
        color_legend=[('input','Coord buffer'),('linear','Shared Linear'),('activation','ReLU'),
            ('softmax','Tanh'),('control','Constructor'),('output','Adjacency A')]))


def validate_ir(ir):
    n={node['id']:node for node in ir['nodes']};p=ir['profile'];e=ir['edges'];checks=[]
    def check(condition,label):
        if not condition:raise ValueError('edge_predictor: '+label)
        checks.append(label)
    check(ir['artifact_scope']=='module' and p['artifact_scope']=='module','module-only boundary')
    check(p['nodes']==784 and p['input_shape']==[784,784,4] and p['output_shape']==[784,784],'selected coordinate and adjacency shapes')
    check(n['edge.pairs']['pair_order']==['j.col','j.row','i.col','i.row'],'source ordered pair construction')
    check(n['edge.grid']['epsilon']==1e-5 and n['edge.buffer']['buffer_identity']=='coord'
          and n['edge.buffer']['learnable'] is False and n['edge.buffer']['persistent'] is True,'fixed standardized coordinate buffer')
    for identity,width_in,width_out,index in [('edge.linear1',4,32,0),('edge.linear2',32,1,2)]:
        node=n[identity]
        check(node['parameter']=='pred_edge_fc.'+str(index) and node['parameter_shape']==[width_out,width_in]
              and node['bias'] is True and node['shared_across']=='all ordered coordinate pairs',identity+' true shared parameter identity')
    check(p['parameter_count']==193 and {node['parameter'] for node in n.values() if 'parameter' in node}=={'pred_edge_fc.0','pred_edge_fc.2'},'only selected MLP weights/biases')
    check(n['edge.relu']['inplace'] is False and n['edge.tanh']['kind']=='tanh' and n['edge.tanh']['activation']=='tanh'
          and n['edge.tanh']['normalized_over_neighbors'] is False,'ReLU followed by signed unnormalized Tanh')
    check(n['edge.squeeze']['squeeze_dim'] is None and n['edge.squeeze']['shape']=='A: [784,784]'
          and n['edge.squeeze']['recomputed_each_forward'] is True,'actual undimensioned squeeze and forward reassignment')
    check(n['edge.squeeze']['storage_kind']=='ordinary_tensor_attribute'
          and n['edge.squeeze']['registered_parameter'] is False and n['edge.squeeze']['registered_buffer'] is False,'A storage identity differs from coord buffer')
    check(n['edge.output']['image_conditioned'] is False and p['adjacency_image_conditioned'] is False
          and p['adjacency_batch_axis'] is False and n['edge.output']['requires_batch_axis'] is False,'adjacency independent of image values and B')
    check(any(x['src']=='edge.init' and x['dst']=='edge.coord' and x['role']=='fixed_buffer' for x in e),'constructor supplies real registered input')
    check(not any(node.get('kind') in ('attention','conv','pool') or node.get('parameter')=='fc.weight' for node in n.values())
          and p['symmetric_guaranteed'] is False and p['degree_normalization'] is False and p['threshold'] is False,'no invented aggregation, head or normalization')
    return checks
