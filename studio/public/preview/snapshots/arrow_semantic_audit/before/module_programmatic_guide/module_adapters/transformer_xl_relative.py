"""Relative content/position scores, memory keys and actual relative shift."""
from module_adapters.sequence_support import chain,op,graph,ref,link,make,verify
SOURCE='transformer-xl-relative/pytorch/mem_transformer.py'


def build():
    init=ref(SOURCE,'RelMultiHeadAttn.__init__');rinit=ref(SOURCE,'RelPartialLearnableMultiHeadAttn.__init__')
    s=ref(SOURCE,'RelPartialLearnableMultiHeadAttn.forward');shiftref=ref(SOURCE,'RelMultiHeadAttn._rel_shift');edges=[]
    cat=op('txl.cat','Concat [memory, current w] / time','concat',s,'[7,B,16]',dim=0,ordered_operands=['mems','w'])
    qkv=op('txl.qkv','Joint QKV Linear16 -> 48','linear',[init,s],'[7,B,48]',parameter='qkv_net',bias=False)
    split=op('txl.split','Chunk Q_all,K,V / last axis','tensor',s,'each:[7,B,16]',fields=['w_head_q','w_head_k','w_head_v'],dim=-1)
    q=op('txl.q','Keep last3 Q + view heads','tensor',s,'[3,B,2,8]',query_slice='[-qlen:]',source_length=7,output_length=3)
    k=op('txl.k','View memory + current K heads','tensor',s,'[7,B,2,8]',includes_memory=True)
    v=op('txl.v','View memory + current V heads','tensor',s,'[7,B,2,8]',includes_memory=True)
    r=chain('txl.r','Relative-position projection',[
        op('txl.rlinear','Position Linear16 -> 16','linear',[rinit,s],'[7,16]',parameter='r_net',bias=False),
        op('txl.rview','View relative heads / no batch','tensor',s,'[7,2,8]'),
    ],[rinit,s],'[7,2,8]',expand=2)
    rw=op('txl.rw','Q + external content bias','add',s,'[3,B,2,8]',bias_argument='r_w_bias')
    rr=op('txl.rr','Q + external relative bias','add',s,'[3,B,2,8]',bias_argument='r_r_bias')
    ac=op('txl.ac','Content score AC / einsum','einsum',s,'[3,7,B,2]',equation='ibnd,jbnd->ijbn')
    bd=op('txl.bd','Relative score BD / einsum','einsum',s,'[3,7,B,2]',equation='ibnd,jnd->ijbn')
    zeros=op('txl.zero','Zeros from BD shape/device/dtype','tensor',shiftref,'[3,1,B,2]',origin='internal_zero_tensor')
    padded=op('txl.pad','Prepend zero column / dim1','concat',shiftref,'[3,8,B,2]',dim=1,ordered_operands=['zero_pad','x'])
    reshaped=op('txl.shift_view','View [K+1,T,B,heads]','tensor',shiftref,'[8,3,B,2]')
    shifted=op('txl.shift_slice','Drop first row + view_as(BD)','tensor',shiftref,'[3,7,B,2]',expression='x_padded[1:].view_as(x)',zero_triu=False)
    shift=graph('txl.shift','Relative shift / source helper',[zeros,padded,reshaped,shifted],shiftref,'[3,7,B,2]',expand=2,
                ranks=[['txl.zero'],['txl.pad'],['txl.shift_view'],['txl.shift_slice']],rank_gap=64)
    add=op('txl.score','AC + shifted BD','add',s,'[3,7,B,2]')
    scale=op('txl.scale','Multiply by 1 / sqrt(d_head8)','tensor',[init,s],'[3,7,B,2]',scale='1/sqrt(8)')
    mask=op('txl.mask','3D mask / True -> -inf','mask',s,'[3,7,B,2]',mask_rank=3,fill='-inf',dtype_roundtrip='float().masked_fill(...).type_as(attn_score)')
    sm=op('txl.softmax','Softmax on key-time axis1','softmax',s,'[3,7,B,2]',dim=1)
    drop=op('txl.dropatt','Attention Dropout .1 / eval','dropout',[init,s],'[3,7,B,2]',p=0.1,training=False)
    aggregate=op('txl.aggregate','einsum(prob, memory+current V)','einsum',s,'[3,B,2,8]',equation='ijbn,jbnd->ibnd')
    tail=chain('txl.tail','Head merge and output projection',[
        op('txl.merge','Contiguous + merge heads','tensor',s,'[3,B,16]'),
        op('txl.olinear','Output Linear16 -> 16','linear',[init,s],'[3,B,16]',parameter='o_net',bias=False),
        op('txl.odrop','Output Dropout .1 / eval','dropout',[init,s],'[3,B,16]',p=0.1,training=False),
    ],[init,s],'[3,B,16]',expand=2)
    residual=op('txl.residual','Original current w + attention out','add',s,'[3,B,16]',memory_not_residual=True)
    norm=op('txl.norm','Post LayerNorm16 / library','layer_norm',[init,s],'[3,B,16]',
            parameter='layer_norm',parameters=['layer_norm.weight','layer_norm.bias'],opaque_runtime_boundary=True,eps_argument='omitted',pre_lnorm=False)
    items=[cat,qkv,split,q,k,v,r,rw,rr,ac,bd,shift,add,scale,mask,sm,drop,aggregate,tail,residual,norm]
    body=graph('txl.body','Relative attention / memory branch',items,[init,rinit,s,shiftref],'[3,B,16]',expand=1,
        ranks=[['txl.cat','txl.r'],['txl.qkv'],['txl.split'],['txl.q','txl.k','txl.v'],['txl.rw','txl.rr'],['txl.ac','txl.bd'],['txl.shift'],['txl.score'],['txl.scale'],['txl.mask'],['txl.softmax'],['txl.dropatt'],['txl.aggregate'],['txl.tail'],['txl.residual'],['txl.norm']],rank_gap=64)
    inputs=[op('txl.w','Current sequence w','input',s,'[3,B,16]'),op('txl.memory','Caller memory / fixed branch','input',s,'[4,B,16]'),
            op('txl.position','Supplied relative encoding r','input',s,'[7,16]'),
            op('txl.biases','Caller content / relative biases','input',s,'r_w_bias,r_r_bias:[2,8]',registered_in_module=False),
            op('txl.external_mask','Caller 3D attention mask','input',s,'[3,7,B]',True_means='blocked',contains_true_selected=True)]
    output=op('txl.output','Return normalized current output','output',s,'[3,B,16]',return_fields=['output'])
    for a,b,p in [('txl.memory','txl.cat','memory'),('txl.w','txl.cat','current'),('txl.cat','txl.qkv','input'),('txl.qkv','txl.split','in'),('txl.position','txl.r','in'),('txl.q','txl.rw','query'),('txl.q','txl.rr','query'),('txl.rw','txl.ac','query'),('txl.k','txl.ac','key'),('txl.rr','txl.bd','query'),('txl.r','txl.bd','position_key'),('txl.bd','txl.pad','relative_scores'),('txl.zero','txl.pad','zeros'),('txl.pad','txl.shift_view','in'),('txl.shift_view','txl.shift_slice','in'),('txl.ac','txl.score','content'),('txl.shift','txl.score','relative'),('txl.score','txl.scale','in'),('txl.scale','txl.mask','scores'),('txl.external_mask','txl.mask','mask'),('txl.mask','txl.softmax','in'),('txl.softmax','txl.dropatt','in'),('txl.dropatt','txl.aggregate','probability'),('txl.v','txl.aggregate','values'),('txl.aggregate','txl.tail','in'),('txl.tail','txl.residual','attention_out'),('txl.w','txl.residual','current'),('txl.residual','txl.norm','in'),('txl.norm','txl.output','output')]:edges.append(link(a,b,p,role='mask' if p=='mask' else 'tensor'))
    edges.append(link('txl.bd','txl.zero','shape',role='shape_dependency',source_port='shape'))
    edges.append(link('txl.shift_slice','txl.shift','out',role='boundary'))
    for field,dst in [('w_head_q','txl.q'),('w_head_k','txl.k'),('w_head_v','txl.v')]:edges.append(link('txl.split',dst,source_port=field))
    edges += [link('txl.biases','txl.rw','bias',source_port='r_w_bias'),link('txl.biases','txl.rr','bias',source_port='r_r_bias')]
    return make('transformer_xl_relative','Transformer-XL relative attention','TransformerXL_Relative_Attention.md',
        'RelPartialLearnableMultiHeadAttn; memory present; pre_lnorm=False; caller mask3D; eval',SOURCE,
        ['RelMultiHeadAttn.__init__','RelPartialLearnableMultiHeadAttn.__init__','RelMultiHeadAttn._rel_shift','RelPartialLearnableMultiHeadAttn.forward'],inputs,body,[output],edges,
        dict(n_head=2,d_model=16,d_head=8,current_length=3,memory_length=4,relative_length=7,mems_selected=True,
             pre_lnorm=False,mask_rank=3,dropout=0.1,dropatt=0.1,training=False,zero_triu=False,
             label='Relative AC+shift(BD) / memory4,current3 / heads2x8 / post-norm / eval'),
        ['Memory and current sequence concatenate before joint QKV projection; only Q keeps the trailing current positions, while K/V retain all7.',
         'r_net projects caller-provided relative encodings, without a batch dimension; content and relative biases are separate caller arguments.',
         'AC uses Q+r_w_bias against K; BD uses Q+r_r_bias against r_net(r), then the actual _rel_shift helper changes relative alignment.',
         'Selected relative shift uses prepend zeros, view, slice and view_as; zero_triu defaultFalse is retained.',
         'Scores add AC+shiftedBD, scale by1/sqrt(d_head), optionally mask and normalize key-time dim1 before attention Dropout.',
         'The residual adds original current w only; post LayerNorm is selected. Memory creation/update/detach in the enclosing model is outside this module.',
         'The module returns output only, not attention probability or newly generated memory.'],
        ['Do not add sinusoidal encodings to token embeddings in place of the relative score term.',
         'Do not use memory positions as queries or residual state; do not treat zero padding as a learned parameter.',
         'Do not claim this isolated attention module updates or detaches its memory input.'],
        roles={'txl.r':'ffn','txl.shift':'attention','txl.tail':'ffn'},
        legend=['Current T3; memoryM4; K7; two heads width8; external relative encodings and separate biases.',
                'Content score AC and shifted relative score BD are separate source branches.',
                'Caller memory is consumed; output contains current positions only; no memory update is drawn.'])


def validate_ir(ir):
    return verify(ir,'transformer_xl_relative',{
        'txl.cat':{'dim':0,'ordered_operands':['mems','w']},'txl.q':{'query_slice':'[-qlen:]','output_length':3},
        'txl.k':{'includes_memory':True},'txl.v':{'includes_memory':True},'txl.qkv':{'parameter':'qkv_net','bias':False},
        'txl.rlinear':{'parameter':'r_net','bias':False},'txl.ac':{'equation':'ibnd,jbnd->ijbn'},'txl.bd':{'equation':'ibnd,jnd->ijbn'},
        'txl.pad':{'ordered_operands':['zero_pad','x'],'dim':1},'txl.shift_slice':{'zero_triu':False},
        'txl.softmax':{'dim':1},'txl.norm':{'pre_lnorm':False,'opaque_runtime_boundary':True},'txl.residual':{'memory_not_residual':True}},
        [('txl.memory','txl.cat','memory'),('txl.biases','txl.rw','bias'),('txl.biases','txl.rr','bias'),
         ('txl.r','txl.bd','position_key'),('txl.shift','txl.score','relative'),('txl.v','txl.aggregate','values'),('txl.w','txl.residual','current')])
