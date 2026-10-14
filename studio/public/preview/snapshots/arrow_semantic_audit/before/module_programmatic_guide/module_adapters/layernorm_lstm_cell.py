"""Explicit custom-LayerNorm LSTM branch of PyTorch's benchmark."""
from module_adapters.sequence_support import chain,op,graph,ref,link,make,verify
SOURCE='pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/custom_lstms.py'


def build():
    init=ref(SOURCE,'LayerNormLSTMCell.__init__');s=ref(SOURCE,'LayerNormLSTMCell.forward')
    ns=[ref(SOURCE,v) for v in ['LayerNorm.__init__','LayerNorm.compute_layernorm_stats','LayerNorm.forward']]
    edges=[];roles={};sh='[B,16]'
    def norm(prefix,width,producer,owner):
        shape=f'[B,{width}]'
        mean=op(prefix+'.mean','Mean over last axis','tensor',ns,'[B,1]',dim=-1,keepdim=True)
        std=op(prefix+'.std','Std / unbiased=False','tensor',ns,'[B,1]',dim=-1,unbiased=False,epsilon=None)
        center=op(prefix+'.center','Input - mean','subtract',ns,shape)
        divide=op(prefix+'.divide','Divide by std / no epsilon','tensor',ns,shape,expression='(input - mu) / sigma',epsilon=None)
        affine=op(prefix+'.affine','Learned gamma + beta','tensor',ns,shape,
                  expression='normalized * self.weight + self.bias',parameters=[owner+'.weight',owner+'.bias'],parameter_shape=[width])
        obj=graph(prefix,'Custom LayerNorm / '+owner.split('_')[-1],[mean,std,center,divide,affine],ns,shape,expand=2,
                  ranks=[[mean['id'],std['id']],[center['id']],[divide['id']],[affine['id']]],rank_gap=64)
        for a,b,port in [(producer,mean['id'],'input'),(producer,std['id'],'input'),(producer,center['id'],'input'),(mean['id'],center['id'],'mean'),(center['id'],divide['id'],'centered'),(std['id'],divide['id'],'std'),(divide['id'],affine['id'],'normalized')]:edges.append(link(a,b,port))
        roles[prefix]='norm';roles[affine['id']]='linear';return obj,affine['id']
    wi=op('lnlstm.wi','Input matrix product / no bias','matmul',[init,s],'[B,64]',parameters=['weight_ih'],parameter_shape=[64,16],bias=False)
    wh=op('lnlstm.wh','Hidden matrix product / no bias','matmul',[init,s],'[B,64]',parameters=['weight_hh'],parameter_shape=[64,16],bias=False)
    ni,oi=norm('lnlstm.lni',64,'lnlstm.wi','layernorm_i');nh,oh=norm('lnlstm.lnh',64,'lnlstm.wh','layernorm_h')
    add=op('lnlstm.gates','Add separately normalized affines','add',s,'[B,64]')
    split=op('lnlstm.split','Chunk4 / input,forget,cell,output','tensor',s,sh,chunk_dim=1,fields=['ingate','forgetgate','cellgate','outgate'])
    gates=[op('lnlstm.'+k,label,kind,s,sh) for k,label,kind in [('i','Sigmoid input i','sigmoid'),('f','Sigmoid forget f','sigmoid'),('g','Tanh cell candidate g','tanh'),('o','Sigmoid output o','sigmoid')]]
    keep=op('lnlstm.keep','f * previous cell','multiply',s,sh)
    new=op('lnlstm.new','i * candidate g','multiply',s,sh)
    cadd=op('lnlstm.cadd','Sum retained + new cell','add',s,sh)
    nc,cy=norm('lnlstm.lnc',16,'lnlstm.cadd','layernorm_c')
    ctanh=op('lnlstm.ctanh','Tanh normalized cell cy','tanh',s,sh)
    hy=op('lnlstm.hy','o * tanh(cy)','multiply',s,sh)
    body=graph('lnlstm.body','LayerNorm LSTM / one step',[wi,wh,ni,nh,add,split,*gates,keep,new,cadd,nc,ctanh,hy],s,sh,expand=1,
        ranks=[['lnlstm.wi','lnlstm.wh'],['lnlstm.lni','lnlstm.lnh'],['lnlstm.gates'],['lnlstm.split'],[x['id'] for x in gates],['lnlstm.keep','lnlstm.new'],['lnlstm.cadd'],['lnlstm.lnc'],['lnlstm.ctanh'],['lnlstm.hy']],rank_gap=64)
    inputs=[op('lnlstm.x','Input x','input',s,sh),op('lnlstm.h','State hidden hx','input',s,sh),op('lnlstm.c','State cell cx','input',s,sh)]
    output=op('lnlstm.output','Return hy, (hy,cy)','output',s,'hy,cy:[B,16]',return_fields=['hy',['hy','cy']])
    for a,b,port in [('lnlstm.x','lnlstm.wi','input'),('lnlstm.h','lnlstm.wh','hidden'),(oi,'lnlstm.gates','input_affine'),(oh,'lnlstm.gates','hidden_affine'),('lnlstm.gates','lnlstm.split','in'),('lnlstm.f','lnlstm.keep','gate'),('lnlstm.c','lnlstm.keep','previous_cell'),('lnlstm.i','lnlstm.new','gate'),('lnlstm.g','lnlstm.new','candidate'),('lnlstm.keep','lnlstm.cadd','retained'),('lnlstm.new','lnlstm.cadd','new'),(cy,'lnlstm.ctanh','in'),('lnlstm.o','lnlstm.hy','gate'),('lnlstm.ctanh','lnlstm.hy','value'),('lnlstm.hy','lnlstm.output','hy'),('lnlstm.hy','lnlstm.output','state_hidden'),(cy,'lnlstm.output','state_cell')]:edges.append(link(a,b,port))
    for field,dst in zip(['ingate','forgetgate','cellgate','outgate'],gates):edges.append(link('lnlstm.split',dst['id'],source_port=field))
    return make('layernorm_lstm_cell','LayerNormLSTMCell / three independent norms','LayerNormLSTMCell.md',
        'One cell; explicitly decompose_layernorm=True; no sequence wrapper',SOURCE,
        ['LayerNormLSTMCell.__init__','LayerNorm.__init__','LayerNorm.compute_layernorm_stats','LayerNorm.forward','LayerNormLSTMCell.forward'],inputs,body,[output],edges,
        dict(input_size=16,hidden_size=16,decompose_layernorm=True,normalization='source custom LayerNorm',norm_epsilon=None,affine_biases=False,label='One step / I=H=16 / custom LayerNorm branch explicitly selected'),
        ['The supplementary PyTorch benchmark source selects custom LayerNorm when decompose_layernorm=True; the defaultFalse branch uses opaque nn.LayerNorm.',
         'Input and hidden products have no separate bias tensors; each has its own learned LayerNorm weight/bias.',
         'The source custom norm uses population std(unbiased=False), no epsilon, then elementwise gamma/beta; three norms have independent parameters.',
         'Cell accumulation is normalized by layernorm_c before both state return and tanh; hy returns twice in hy,(hy,cy).'],
        ['Do not merge the two affine products before normalization; do not add bias_ih/bias_hh absent from this cell.',
         'Do not substitute default nn.LayerNorm epsilon into the explicitly selected custom branch.'],roles=roles,
        legend=['I=H=16; norm_i/norm_h widths64; norm_c width16; three independent gamma/beta pairs.',
                'Explicit custom branch: population std and no epsilon; source code was not run.',
                'Return contract: hy and nested state(hy,cy), with normalized cy.'])


def validate_ir(ir):
    fields={'lnlstm.wi':{'parameters':['weight_ih'],'bias':False},'lnlstm.wh':{'parameters':['weight_hh'],'bias':False},
            'lnlstm.split':{'fields':['ingate','forgetgate','cellgate','outgate']},'lnlstm.output':{'return_fields':['hy',['hy','cy']]}}
    for prefix,width,owner in [('lnlstm.lni',64,'layernorm_i'),('lnlstm.lnh',64,'layernorm_h'),('lnlstm.lnc',16,'layernorm_c')]:
        fields[prefix+'.std']={'unbiased':False,'epsilon':None}
        fields[prefix+'.affine']={'parameters':[owner+'.weight',owner+'.bias'],'parameter_shape':[width]}
    return verify(ir,'layernorm_lstm_cell',fields,[('lnlstm.lni.affine','lnlstm.gates','input_affine'),('lnlstm.lnh.affine','lnlstm.gates','hidden_affine'),('lnlstm.c','lnlstm.keep','previous_cell'),('lnlstm.cadd','lnlstm.lnc.mean','input'),('lnlstm.lnc.affine','lnlstm.ctanh','in'),('lnlstm.lnc.affine','lnlstm.output','state_cell'),('lnlstm.o','lnlstm.hy','gate')])
