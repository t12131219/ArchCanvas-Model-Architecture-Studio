from module_adapters._graph_extended_support import Diagram,validate
SOURCE='dgl-graph-modules/examples/pytorch/vgae/model.py';KEY='inner_product_decoder'
LINKS=[('z','transpose','in','tensor'),('z','product.mm','left','retained_value'),('transpose','product.mm','right','tensor'),('product.mm','sigmoid','in','tensor'),('sigmoid','output','in','tensor')]
REQUIRED={'transpose':dict(expression='z.t()'),'product.mm':dict(expression='torch.matmul(z, z.t())',ordered_operands=['z','transpose']),'sigmoid':dict(kind='sigmoid')}
CONTRACTS=[('VGAEModel.decoder','torch.sigmoid(torch.matmul(z, z.t()))')]
def build():
 d=Diagram(KEY,'Graph inner-product decoder',SOURCE,'VGAEModel.decoder','Only VGAEModel.decoder(z); excludes graph posterior, sampling, loss and training.',dict(latent_width=8,output='dense pairwise adjacency probability',learned_decoder_parameters=0))
 d.input('z','Node latents Z','[N,8]');d.node('transpose','Transpose same Z','tensor','[8,N]',0,expression='z.t()')
 d.stage('product','All node-pair inner products','[N,N]',1,[('mm','Z @ Z.T','matmul','[N,N]',dict(expression='torch.matmul(z, z.t())',ordered_operands=['z','transpose']))],suppress_input_boundary=True)
 d.node('sigmoid','Elementwise Sigmoid','sigmoid','[N,N]',2)
 for s,t,p,r in LINKS:d.edge(s,t,p,r,ss='left' if s=='z' and t=='product.mm' else 'out',ds='left' if t=='product.mm' and s=='z' else 'in')
 return d.build(d.entry,'[N,N]','InnerProductDecoder.md',['Decoder reuses exactly one Z in both matrix operands, giving symmetric dense pair scores.','Sigmoid is elementwise; source does not perform row Softmax, masking, diagonal deletion or learned decoder Linear.'],['Do not turn the decoder into adjacency-conditioned message passing or a classification head.'])
def validate_ir(ir):return validate(ir,KEY,REQUIRED,LINKS,dict(learned_decoder_parameters=0))
