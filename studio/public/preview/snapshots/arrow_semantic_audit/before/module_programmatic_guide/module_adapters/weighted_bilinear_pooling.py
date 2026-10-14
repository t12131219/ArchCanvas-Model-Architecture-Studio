from module_adapters._graph_extended_support import Diagram,validate
from module_adapters.bilinear_attention import projections,BC,FC
SOURCE=BC;KEY='weighted_bilinear_pooling'
LINKS=[('v','vproject.drop','in','tensor'),('q','qproject.drop','in','tensor'),('vproject.relu','einsum','V','tensor'),('qproject.relu','einsum','Q','tensor'),('w','einsum','weights','tensor'),('einsum','pool.unsqueeze','in','tensor'),('pool.sum','output','in','tensor')]
REQUIRED={'einsum':dict(expression="torch.einsum('bvk,bvq,bqk->bk', (v_, w, q_))"),'pool.avg':dict(kernel=3,stride=3),'pool.sum':dict(expression='self.p_net(logits).squeeze(1) * self.k',factor=3),'vproject.drop':dict(p=.2),'qproject.drop':dict(p=.2)}
CONTRACTS=[('BCNet.forward_with_weights',"torch.einsum('bvk,bvq,bqk->bk', (v_, w, q_))"),('BCNet.forward_with_weights','self.p_net(logits).squeeze(1) * self.k'),('BCNet.__init__','nn.AvgPool1d(self.k, stride=self.k)')]
EXTRA_CONTRACTS={FC:[('FCNet.__init__','weight_norm(nn.Linear(dims[-2], dims[-1]), dim=None)')]}
def build():
 d=Diagram(KEY,'Weighted bilinear pooling',SOURCE,'BCNet.forward_with_weights','Only BCNet.forward_with_weights(v,q,w), k3/h_dim4; excludes attention score generation and VQA task head.',dict(v_dim=8,q_dim=6,h_dim=4,k=3,h_out=None,output_shape=['B',4],pool='AvgPool*k equals grouped sum',attention_dropout_used=False))
 d.input('v','Visual features V','[B,5,8]');d.input('q','Language features Q','[B,3,6]');d.input('w','External pair weights w','[B,5,3]');projections(d,0,False)
 d.node('einsum','Weighted bilinear contraction','einsum','[B,12]',1,**REQUIRED['einsum'])
 d.stage('pool','Group k3 factors / sum','[B,4]',2,[('unsqueeze','Insert pool channel axis','tensor','[B,1,12]',dict()),('avg','AvgPool1d k3 / stride3','mean','[B,1,4]',REQUIRED['pool.avg']),('sum','Squeeze + multiply by k','multiply','[B,4]',REQUIRED['pool.sum'])])
 for s,t,p,r in LINKS:d.edge(s,t,p,r)
 return d.build(d.entry,'[B,4]','WeightedBilinearPooling.md',['Two FCNet projections are separate owned parameter families; external w is a two-axis pair weight input, not a learned module parameter.','einsum contracts both visual and question positions; k3 feature factors then pool by AvgPool1d and multiplication by3, which implements sum-pooling.','This method does not use BCNet.dropout(.5), h_mat or h_bias; attention-generation and pooling examples do not imply shared instances.'],['Do not add Softmax, concatenate modalities, or insert the attention-only extra visual Dropout.5.','Do not label the output as average pooling: source multiplies pooled values by k.'])
def validate_ir(ir):return validate(ir,KEY,REQUIRED,LINKS,dict(attention_dropout_used=False,h_out=None))
