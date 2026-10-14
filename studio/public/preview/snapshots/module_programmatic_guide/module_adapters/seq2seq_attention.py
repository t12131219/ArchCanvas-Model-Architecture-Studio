"""IBM Attention: unscaled dot, optional mask, context/decoder fusion."""
from module_adapters.sequence_support import chain,op,graph,ref,link,make,verify
SOURCE='ibm-seq2seq-attention/seq2seq/models/attention.py'


def build():
    init=ref(SOURCE,'Attention.__init__');s=ref(SOURCE,'Attention.forward');setmask=ref(SOURCE,'Attention.set_mask')
    score=op('ibm.score','bmm(output, context^T)','bmm',s,'[B,3,8]',scale=None,expression='torch.bmm(output, context.transpose(1, 2))')
    mask=op('ibm.mask','masked_fill_ / True -> -inf','mask',[s,setmask],'[B,3,8]',fill='-inf',mask_selected=True,source_storage='attn.data.masked_fill_')
    softmax=op('ibm.softmax','View2D + Softmax input positions','softmax',s,'[B,3,8]',dim=1,original_axis=2,
               expression='F.softmax(attn.view(-1, input_size), dim=1).view(batch_size, -1, input_size)')
    mix=op('ibm.mix','bmm(attn, same context)','bmm',s,'[B,3,16]')
    concat=op('ibm.concat','Concat [mix, original output]','concat',s,'[B,3,32]',dim=2,ordered_operands=['mix','output'])
    fusion=chain('ibm.fusion','Output fusion / source view wrappers',[
        op('ibm.flat','View2D / width32','tensor',s,'[B*3,32]'),
        op('ibm.linear','Linear32 -> 16','linear',init,'[B*3,16]',parameter='linear_out',bias=True),
        op('ibm.tanh','Tanh + restore sequence view','tanh',s,'[B,3,16]'),
    ],[init,s],'[B,3,16]',expand=2)
    body=graph('ibm.body','Dot attention + decoder fusion',[score,mask,softmax,mix,concat,fusion],[init,s],'[B,3,16]',expand=1,
        ranks=[['ibm.score'],['ibm.mask'],['ibm.softmax'],['ibm.mix'],['ibm.concat'],['ibm.fusion']],rank_gap=64)
    inputs=[op('ibm.query','Decoder output / query','input',s,'[B,3,16]'),op('ibm.context','Encoder context / keys and values','input',s,'[B,8,16]'),
            op('ibm.external_mask','Mask set by caller / optional branch','input',setmask,'[B,3,8]',True_means='blocked',selected=True)]
    output=op('ibm.output','Return fused output, attention','output',s,'[B,3,16]; [B,3,8]',return_fields=['output','attn'])
    edges=[link('ibm.query','ibm.score','query'),link('ibm.context','ibm.score','keys'),link('ibm.score','ibm.mask','scores'),
           link('ibm.external_mask','ibm.mask','mask',role='mask'),link('ibm.mask','ibm.softmax'),link('ibm.softmax','ibm.mix','weights'),
           link('ibm.context','ibm.mix','values'),link('ibm.mix','ibm.concat','mix'),link('ibm.query','ibm.concat','output'),
           link('ibm.concat','ibm.fusion'),link('ibm.fusion','ibm.output','output'),link('ibm.softmax','ibm.output','attention')]
    return make('seq2seq_attention','Seq2seq dot attention / context fusion','Seq2seq_Attention.md',
        'IBM Attention.forward only; mask-set branch explicitly selected; no encoder/decoder RNN',SOURCE,
        ['Attention.__init__','Attention.set_mask','Attention.forward'],inputs,body,[output],edges,
        dict(dim=16,query_length=3,context_length=8,mask_selected=True,score_scaled=False,label='IBM Attention / D16,query3,context8 / masked unscaled dot / returns weights'),
        ['Query is the decoder output, while context supplies both keys and values without learned QKV projections.',
         'The source computes an unscaled dot product, optionally masks attn.data in place with-inf, then normalizes context positions.',
         'mask startsNone; this example selects the real set_mask branch, and caller supplies the full broadcast-compatible score mask.',
         'The context mixture is concatenated before original decoder output, passed through one biased linear_out and Tanh.',
         'forward returns fused output and the same normalized attention weights; no attention Dropout is present.'],
        ['Do not insert sqrt(D) scaling, QKV linears or an additive scorer.',
         'Do not swap concat order; do not feed the newly fused output into its own scoring path.'],
        roles={'ibm.fusion':'ffn'},legend=['B=batch; query3 positions attend over8 encoder positions; D16.',
            'Gray mask is optional source state, selected here; True blocks a score.',
            'One learned linear_out follows [mix, original output]; no score projections.'])


def validate_ir(ir):
    return verify(ir,'seq2seq_attention',{
        'ibm.score':{'scale':None},'ibm.mask':{'fill':'-inf','mask_selected':True},
        'ibm.softmax':{'dim':1,'original_axis':2},'ibm.concat':{'dim':2,'ordered_operands':['mix','output']},
        'ibm.linear':{'parameter':'linear_out','bias':True},'ibm.output':{'return_fields':['output','attn']}},
        [('ibm.context','ibm.score','keys'),('ibm.context','ibm.mix','values'),('ibm.external_mask','ibm.mask','mask'),('ibm.query','ibm.concat','output'),('ibm.softmax','ibm.output','attention')])
