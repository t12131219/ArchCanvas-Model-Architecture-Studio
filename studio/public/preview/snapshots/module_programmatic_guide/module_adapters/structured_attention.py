"""The actual unmasked structured-sentence-attention subgraph."""
from module_adapters.sequence_support import chain,op,graph,ref,link,make,verify
SOURCE='structured-self-attention-sequence/attention/model.py'


def build():
    init=ref(SOURCE,'StructuredSelfAttention.__init__');s=ref(SOURCE,'StructuredSelfAttention.forward');sm=ref(SOURCE,'StructuredSelfAttention.softmax')
    scorer=chain('struct.scorer','Two-layer hop scorer',[
        op('struct.first','Linear H16 -> d_a12','linear',init,'[B,8,12]',parameter='linear_first',bias=True,initial_bias=0),
        op('struct.tanh','Tanh','tanh',s,'[B,8,12]'),
        op('struct.second','Linear d_a12 -> hops3','linear',init,'[B,8,3]',parameter='linear_second',bias=True,initial_bias=0),
    ],[init,s],'[B,8,3]',expand=2)
    softmax=chain('struct.softmax','Normalize time / helper',[
        op('struct.swap','Transpose time to last axis','tensor',sm,'[B,3,8]',axes=[1,2]),
        op('struct.flat','Contiguous + view2D','tensor',sm,'[B*3,8]',expression='trans_input.contiguous().view(-1, trans_size[-1])'),
        op('struct.normalize','F.softmax / dim omitted','softmax',sm,'[B*3,8]',dim_argument='omitted',original_normalized_axis=1),
        op('struct.restore','View original transposed size','tensor',sm,'[B,3,8]'),
        op('struct.swapback','Transpose back to time,hops','tensor',sm,'[B,8,3]',axes=[1,2]),
    ],[s,sm],'[B,8,3]',expand=2)
    attn=op('struct.attention','Transpose to hop attention A','tensor',s,'[B,3,8]',axes=[1,2],padding_mask=False)
    pool=op('struct.pool','A @ original LSTM outputs','matmul',s,'[B,3,16]',expression='attention @ outputs')
    avg=op('struct.avg','Sum hop embeddings / r=3','tensor',s,'[B,16]',sum_dim=1,divisor=3,expression='torch.sum(sentence_embeddings, 1) / self.r')
    body=graph('struct.body','Structured sentence attention subgraph',[scorer,softmax,attn,pool,avg],[init,s,sm],
               'A:[B,3,8]; mean:[B,16]',expand=1,ranks=[['struct.scorer'],['struct.softmax'],['struct.attention'],['struct.pool'],['struct.avg']],rank_gap=64)
    inp=op('struct.input','Precomputed LSTM outputs H','input',s,'[B,8,16]',bidirectional=False,upstream_lstm_excluded=True)
    out=op('struct.output','Boundary: mean embedding and A','output',s,'[B,16]; [B,3,8]',actual_return=False,fields=['avg_sentence_embeddings','attention'])
    edges=[link('struct.input','struct.scorer'),link('struct.scorer','struct.softmax'),link('struct.softmax','struct.attention'),
           link('struct.attention','struct.pool','attention'),link('struct.input','struct.pool','values'),link('struct.pool','struct.avg'),
           link('struct.avg','struct.output','mean_embedding'),link('struct.attention','struct.output','attention')]
    return make('structured_attention','Structured hop attention','Structured_Attention.md',
        'Scoring and pooling expressions only; precomputed unidirectional LSTM outputs; classifier excluded',SOURCE,
        ['StructuredSelfAttention.__init__','StructuredSelfAttention.softmax','StructuredSelfAttention.forward'],[inp],body,[out],edges,
        dict(lstm_hid_dim=16,d_a=12,r=3,max_len=8,padding_mask=False,bidirectional=False,actual_return=False,
             label='Precomputed H / T8,H16,d_a12,hops3 / time Softmax / no mask in source'),
        ['Two independent biased Linear layers score three hops; constructor zeroes both biases but keeps them learnable.',
         'The actual source LSTM is unidirectional with width lstm_hid_dim, not twice that dimension.',
         'The helper moves axis1 to the final axis, makes a2D view, calls F.softmax with omitted dim, restores and transposes back.',
         'Hop attention multiplies the same original outputs used for scores; hop embeddings are averaged by sum/r, not concatenated.',
         'No padding mask, packed sequence, attention Dropout, or orthogonality loss is executed inside this selected subgraph; l2_matrix_norm is a separate helper.',
         'Top boundary variables are not a return tuple of a standalone method; full forward returns classifier output and attention.'],
        ['Do not invent padding-mask arrows or a bidirectional LSTM based on the paper.',
         'Do not normalize across hops or replace source mean-hop fusion with flatten/concatenation.'],
        roles={'struct.scorer':'ffn','struct.softmax':'attention'},
        legend=['B=batch; supplied H:[B,8,16]; r3 hops; attention:[B,3,8].',
                'Source lacks padding masking; each hop normalizes over sequence positions.',
                'Classifier and embedding/LSTM producer are outside the selected boundary.'])


def validate_ir(ir):
    return verify(ir,'structured_attention',{
        'struct.first':{'parameter':'linear_first','bias':True,'initial_bias':0},
        'struct.second':{'parameter':'linear_second','bias':True,'initial_bias':0},
        'struct.normalize':{'dim_argument':'omitted','original_normalized_axis':1},
        'struct.attention':{'padding_mask':False,'axes':[1,2]},'struct.avg':{'sum_dim':1,'divisor':3},
        'struct.input':{'bidirectional':False},'struct.output':{'actual_return':False}},
        [('struct.input','struct.pool','values'),('struct.attention','struct.pool','attention'),('struct.attention','struct.output','attention')])
