"""Actual Bahdanau branch, distinct keys/values and post-dropout weights."""
from module_adapters.sequence_support import chain,op,graph,ref,link,make,verify
SOURCE='seq2seq-additive-sequence/seq2seq/models/modules/attention.py'


def build():
    init=ref(SOURCE,'AttentionLayer.__init__');s=ref(SOURCE,'AttentionLayer.forward');score=ref(SOURCE,'AttentionLayer.calc_score');maskref=ref(SOURCE,'AttentionLayer.set_mask')
    query=op('addatt.query','Query Linear12 -> key width16','linear',[init,s],'[B,3,16]',parameter='linear_q',bias=True)
    qexpand=op('addatt.qexpand','Unsqueeze + expand query over keys','tensor',score,'[B,3,8,16]',unsqueeze_dim=2)
    kexpand=op('addatt.kexpand','Unsqueeze + expand keys over queries','tensor',score,'[B,3,8,16]',unsqueeze_dim=1)
    add=op('addatt.add','Projected query + key','add',score,'[B,3,8,16]')
    scoring=chain('addatt.scoring','Bahdanau scalar scorer',[
        op('addatt.flat','View paired query-key rows','tensor',score,'[B*3*8,16]'),
        op('addatt.tanh','Tanh pair sum','tanh',score,'[B*3*8,16]'),
        op('addatt.linear','Score Linear16 -> 1','linear',[init,score],'[B*3*8,1]',parameter='linear_att',bias=True,weight_norm=False),
        op('addatt.reshape','View scores B,query,key','tensor',score,'[B,3,8]'),
    ],[init,score],'[B,3,8]',expand=2)
    mask=op('addatt.mask','Expand key mask / fill -1e12','mask',[s,maskref],'[B,3,8]',fill=-1e12,mask_expansion='unsqueeze(1).expand(b,t_q,t_k)')
    softmax=op('addatt.softmax','Softmax over key positions','softmax',s,'[B,3,8]',dim=2)
    drop=op('addatt.drop','Attention Dropout p=.1 / eval','dropout',[init,s],'[B,3,8]',p=0.1,training=False)
    context=op('addatt.context','bmm(post-drop weights, values)','bmm',s,'[B,3,20]',keys_equal_values=False)
    concat=op('addatt.concat','Concat [original query, context]','concat',s,'[B,3,32]',dim=2,ordered_operands=['query','context'])
    fusion=chain('addatt.fusion','Output fusion',[
        op('addatt.outlinear','Output Linear32 -> 12','linear',init,'[B,3,12]',parameter='linear_out',bias=True,weight_norm=False),
        op('addatt.outtanh','Tanh output','tanh',s,'[B,3,12]'),
    ],[init,s],'[B,3,12]',expand=2)
    body=graph('addatt.body','Additive scoring / explicit values',[query,qexpand,kexpand,add,scoring,mask,softmax,drop,context,concat,fusion],[init,s,score],
        '[B,3,12]',expand=1,ranks=[['addatt.query'],['addatt.qexpand','addatt.kexpand'],['addatt.add'],['addatt.scoring'],['addatt.mask'],['addatt.softmax'],['addatt.drop'],['addatt.context'],['addatt.concat'],['addatt.fusion']],rank_gap=64)
    inputs=[op('addatt.input_q','Query / original width12','input',s,'[B,3,12]'),op('addatt.input_k','Keys / width16','input',s,'[B,8,16]'),
            op('addatt.input_v','Explicit values / width20','input',s,'[B,8,20]'),op('addatt.input_mask','Key mask / selected','input',maskref,'[B,8]',True_means='blocked')]
    output=op('addatt.output','Return context, post-drop weights','output',s,'[B,3,12]; [B,3,8]',return_fields=['context','scores_normalized'],weight_origin='post_dropout')
    edges=[]
    for a,b,port in [('addatt.input_q','addatt.query','input'),('addatt.query','addatt.qexpand','input'),('addatt.input_k','addatt.kexpand','input'),('addatt.qexpand','addatt.add','query'),('addatt.kexpand','addatt.add','keys'),('addatt.add','addatt.scoring','in'),('addatt.scoring','addatt.mask','scores'),('addatt.input_mask','addatt.mask','mask'),('addatt.mask','addatt.softmax','in'),('addatt.softmax','addatt.drop','in'),('addatt.drop','addatt.context','weights'),('addatt.input_v','addatt.context','values'),('addatt.input_q','addatt.concat','query'),('addatt.context','addatt.concat','context'),('addatt.concat','addatt.fusion','in'),('addatt.fusion','addatt.output','context'),('addatt.drop','addatt.output','weights')]:edges.append(link(a,b,port,role='mask' if port=='mask' else 'tensor'))
    return make('seq2seq_additive_attention','Bahdanau attention / query-key-value roles','Seq2seq_Additive_Attention.md',
        'AttentionLayer Bahdanau branch only; batch_first=True; explicit values and mask; eval',SOURCE,
        ['AttentionLayer.__init__','AttentionLayer.set_mask','AttentionLayer.calc_score','AttentionLayer.forward'],inputs,body,[output],edges,
        dict(mode_selected='bahdanau',query_size=12,key_size=16,value_size=20,output_size=12,batch_first=True,
             normalize=False,weight_norm=False,query_transform=True,output_transform=True,dropout=0.1,training=False,
             single_query=False,values_argument='explicit',label='Bahdanau / query12,key16,value20 / mask / eval / post-drop weights'),
        ['linear_q projects queries to key width; keys are not projected by a separate K Linear in this selected source branch.',
         'Query/key tensors expand to all pairs, add, Tanh, and linear_att produce scalar additive scores.',
         'normalize=False and weight_norm=False explicitly select ordinary biased score/output linears.',
         'A supplied key mask expands over queries and uses finite-1e12, then Softmax(dim2) and attention Dropout.',
         'Values are explicitly distinct inputs; when values=None the source alternatively reuses keys.',
         'Output fusion concatenates original query before weighted context; returned weights come after Dropout, even though selected eval makes it identity.'],
        ['Do not replace additive scoring with dot or add K/V projections absent from this branch.',
         'Do not silently use keys as explicit values; do not return pre-dropout weights or swap concat operands.'],
        roles={'addatt.scoring':'attention','addatt.fusion':'ffn'},
        legend=['Q original width12; projectedQ/K width16; explicitV width20; lengths3 and8.',
                'Mask True blocks; finite fill-1e12; attention weights normalize keys.',
                'Source has several branches; this figure explicitly selects Bahdanau/batch-first/multiple queries.'])


def validate_ir(ir):
    return verify(ir,'seq2seq_additive_attention',{
        'addatt.query':{'parameter':'linear_q'},'addatt.linear':{'parameter':'linear_att','weight_norm':False},
        'addatt.mask':{'fill':-1e12},'addatt.softmax':{'dim':2},'addatt.context':{'keys_equal_values':False},
        'addatt.concat':{'ordered_operands':['query','context']},'addatt.output':{'weight_origin':'post_dropout'}},
        [('addatt.input_k','addatt.kexpand','input'),('addatt.input_v','addatt.context','values'),
         ('addatt.input_q','addatt.concat','query'),('addatt.drop','addatt.context','weights'),('addatt.drop','addatt.output','weights')])
