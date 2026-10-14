"""QANet's tri-linear two-direction context-query attention."""
from module_adapters.sequence_support import chain,op,graph,ref,link,make,verify
SOURCE='qanet-attention-sequence/models.py'
CONFIG='qanet-attention-sequence/config.py'


def build():
    init=ref(SOURCE,'CQAttention.__init__');s=ref(SOURCE,'CQAttention.forward');maskref=ref(SOURCE,'mask_logits');edges=[]
    c=op('cq.c','Transpose context to length,features','tensor',s,'[B,8,96]',axes=[1,2])
    q=op('cq.q','Transpose query to length,features','tensor',s,'[B,5,96]',axes=[1,2])
    ct=op('cq.ct','Context expand over queries','tensor',s,'[B,8,5,96]',unsqueeze_dim=2)
    qt=op('cq.qt','Query expand over context','tensor',s,'[B,8,5,96]',unsqueeze_dim=1)
    product=op('cq.cq','Ct * Qt / pairwise products','multiply',s,'[B,8,5,96]')
    cat=op('cq.features','Concat [Ct,Qt,Ct*Qt]','concat',s,'[B,8,5,288]',dim=3,ordered_operands=['Ct','Qt','CQ'])
    score=op('cq.score','Pair features @ learned w','matmul',[init,s],'[B,8,5]',parameters=['w'],parameter_shape=[288],bias=False)
    first=chain('cq.s1','Query-normalized attention S1',[
        op('cq.qmask','Apply query mask / -1e30','mask',[s,maskref],'[B,8,5]',expression='target * (1-mask) + mask * (-1e30)',fill=-1e30,expanded_mask_shape=['B',1,5]),
        op('cq.softmax1','Softmax along query positions','softmax',s,'[B,8,5]',dim=2),
    ],[s,maskref],'[B,8,5]',expand=2)
    second=chain('cq.s2','Context-normalized attention S2',[
        op('cq.cmask','Apply context mask / -1e30','mask',[s,maskref],'[B,8,5]',expression='target * (1-mask) + mask * (-1e30)',fill=-1e30,expanded_mask_shape=['B',8,1]),
        op('cq.softmax2','Softmax along context positions','softmax',s,'[B,8,5]',dim=1),
    ],[s,maskref],'[B,8,5]',expand=2)
    a=op('cq.a','A = S1 @ Q','bmm',s,'[B,8,96]')
    cross=op('cq.cross','S1 @ transpose(S2)','bmm',s,'[B,8,8]',transpose_dims=[1,2])
    b=op('cq.b','B = cross-attention @ C','bmm',s,'[B,8,96]')
    ca=op('cq.ca','C * A','multiply',s,'[B,8,96]');cb=op('cq.cb','C * B','multiply',s,'[B,8,96]')
    fuse=op('cq.fuse','Concat [C,A,C*A,C*B]','concat',s,'[B,8,384]',dim=2,ordered_operands=['C','A','C*A','C*B'])
    tail=chain('cq.tail','Dropout and restore channels-first',[
        op('cq.drop','Dropout p=.1 / eval identity','dropout',s,'[B,8,384]',p=0.1,training=False),
        op('cq.transpose','Transpose feature and context axes','tensor',s,'[B,384,8]',axes=[1,2]),
    ],s,'[B,384,8]',expand=2)
    items=[c,q,ct,qt,product,cat,score,first,second,a,cross,b,ca,cb,fuse,tail]
    body=graph('cq.body','Tri-linear bidirectional interaction',items,[init,s,maskref],'[B,384,8]',expand=1,
        ranks=[['cq.c','cq.q'],['cq.ct','cq.qt'],['cq.cq'],['cq.features'],['cq.score'],['cq.s1','cq.s2'],['cq.a','cq.cross'],['cq.b'],['cq.ca','cq.cb'],['cq.fuse'],['cq.tail']],rank_gap=64)
    inputs=[op('cq.input_c','Context C / channels-first','input',s,'[B,96,8]'),op('cq.input_q','Query Q / channels-first','input',s,'[B,96,5]'),
            op('cq.input_cm','Context padding mask / 0 or1','input',s,'[B,8]'),op('cq.input_qm','Query padding mask / 0 or1','input',s,'[B,5]')]
    output=op('cq.output','Context-query interaction output','output',s,'[B,384,8]',return_fields=['out.transpose(1,2)'])
    for x,y,p in [('cq.input_c','cq.c','input'),('cq.input_q','cq.q','input'),('cq.c','cq.ct','input'),('cq.q','cq.qt','input'),('cq.ct','cq.cq','context'),('cq.qt','cq.cq','query'),('cq.ct','cq.features','context'),('cq.qt','cq.features','query'),('cq.cq','cq.features','product'),('cq.features','cq.score','features'),('cq.score','cq.qmask','scores'),('cq.score','cq.cmask','scores'),('cq.input_cm','cq.cmask','mask'),('cq.input_qm','cq.qmask','mask'),('cq.s1','cq.a','weights'),('cq.q','cq.a','values'),('cq.s1','cq.cross','left'),('cq.s2','cq.cross','right_transposed'),('cq.cross','cq.b','weights'),('cq.c','cq.b','values'),('cq.c','cq.ca','context'),('cq.a','cq.ca','attended_query'),('cq.c','cq.cb','context'),('cq.b','cq.cb','attended_context'),('cq.c','cq.fuse','context'),('cq.a','cq.fuse','query_attention'),('cq.ca','cq.fuse','product_a'),('cq.cb','cq.fuse','product_b'),('cq.fuse','cq.tail','in'),('cq.tail','cq.output','output')]:edges.append(link(x,y,p,role='mask' if p=='mask' else 'tensor'))
    model=make('qanet_context_query_attention','QANet context-query attention','QANet_CQAttention.md',
        'CQAttention only; config d_model96/dropout.1; selected context8/query5; eval',SOURCE,
        ['CQAttention.__init__','mask_logits','CQAttention.forward'],inputs,body,[output],edges,
        dict(d_model=96,context_length=8,query_length=5,dropout=0.1,training=False,mask_true_means='padding',
             label='Tri-linear pair scores / D96 / context8,query5 / two normalization axes'),
        ['Frozen config.py supplies d_model96 and dropout.1; context8/query5 are explicit module example lengths, not claimed full-model limits.',
         'One learned vector w has3D entries and no bias; pair features concatenate C,Q,C*Q before the dot with w.',
         'The same raw S scores take different masks and normalize over query axis2(S1) versus context axis1(S2).',
         'A=S1@Q; B=(S1@S2.T)@C; the final four-part feature concat is C,A,C*A,C*B.',
         'Mask helper uses arithmetic with finite-1e30, not masked_fill(-inf). Only out is returned; attention matrices are internal.'],
        ['Do not replace S2 with a max-reduced query-to-context attention from another BiDAF implementation.',
         'Do not use the same mask or same normalization axis twice; do not insert QKV projections.'],
        roles={'cq.s1':'attention','cq.s2':'attention','cq.tail':'ffn'},
        additional_sources={CONFIG:['__module__']},
        legend=['C[B,96,8],Q[B,96,5]; pair scoreS[B,8,5]; final channels4D=384.',
                'Mask1 means padding; S1 normalizes query, S2 normalizes context.',
                'One shared288-vector w scores all C/Q pairs; selected eval keeps Dropout node.'])
    model['config_files'].append(CONFIG);return model


def validate_ir(ir):
    return verify(ir,'qanet_context_query_attention',{
        'cq.features':{'dim':3,'ordered_operands':['Ct','Qt','CQ']},'cq.score':{'parameters':['w'],'parameter_shape':[288],'bias':False},
        'cq.qmask':{'fill':-1e30,'expanded_mask_shape':['B',1,5]},'cq.cmask':{'fill':-1e30,'expanded_mask_shape':['B',8,1]},
        'cq.softmax1':{'dim':2},'cq.softmax2':{'dim':1},'cq.fuse':{'ordered_operands':['C','A','C*A','C*B'],'dim':2}},
        [('cq.input_qm','cq.qmask','mask'),('cq.input_cm','cq.cmask','mask'),('cq.q','cq.a','values'),
         ('cq.s2','cq.cross','right_transposed'),('cq.c','cq.b','values'),('cq.cb','cq.fuse','product_b')])
