"""PyTorch benchmark functional GRU cell; reset follows recurrent affine."""
from module_adapters.sequence_support import chain,op,graph,ref,link,make,verify
SOURCE='pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py'


def build():
    s=ref(SOURCE,'gru_cell');sh='[B,16]';edges=[]
    gi=op('gru.gi','Input affine: x W_ih^T + b_ih','linear',s,'[B,48]',
          parameters=['w_ih','b_ih'],parameter_origin='caller-supplied Tensor arguments',expression='torch.mm(input, w_ih.t()) + b_ih')
    gh=op('gru.gh','Hidden affine: h W_hh^T + b_hh','linear',s,'[B,48]',
          parameters=['w_hh','b_hh'],parameter_origin='caller-supplied Tensor arguments',expression='torch.mm(hidden, w_hh.t()) + b_hh')
    ci=op('gru.ci','Chunk input affine / r,z,n','tensor',s,sh,chunk_dim=1,fields=['i_r','i_i','i_n'])
    ch=op('gru.ch','Chunk hidden affine / r,z,n','tensor',s,sh,chunk_dim=1,fields=['h_r','h_i','h_n'])
    reset=chain('gru.reset','Reset gate r',[
        op('gru.r_add','i_r + h_r','add',s,sh),op('gru.r','Sigmoid reset gate','sigmoid',s,sh)],s,sh,expand=2)
    update=chain('gru.update','Update gate z / source inputgate',[
        op('gru.z_add','i_i + h_i','add',s,sh),op('gru.z','Sigmoid update gate','sigmoid',s,sh)],s,sh,expand=2)
    product=op('gru.rhn','r * h_n / bias already included','multiply',s,sh,ordered_operands=['resetgate','h_n'])
    candidate=chain('gru.candidate','Candidate n',[
        op('gru.n_add','i_n + r * h_n','add',s,sh),
        op('gru.n','Tanh candidate','tanh',s,sh,expression='torch.tanh(i_n + resetgate * h_n)')],s,sh,expand=2)
    delta=op('gru.delta','h_previous - n','subtract',s,sh)
    retained=op('gru.zdelta','z * (h_previous - n)','multiply',s,sh)
    add=op('gru.hy','n + z * (h_previous - n)','add',s,sh,expression='newgate + inputgate * (hidden - newgate)')
    body=graph('gru.body','GRU / one functional step',
        [gi,gh,ci,ch,reset,update,product,candidate,delta,retained,add],s,sh,expand=1,
        ranks=[['gru.gi','gru.gh'],['gru.ci','gru.ch'],['gru.reset','gru.update'],['gru.rhn'],['gru.candidate'],['gru.delta'],['gru.zdelta'],['gru.hy']],rank_gap=64)
    inputs=[op('gru.x','Current input x','input',s,sh),op('gru.h','Previous hidden h','input',s,sh),
            op('gru.params','Caller weights / biases','input',s,'W_ih,W_hh:[48,16]; b:[48]',registered_in_function=False)]
    out=op('gru.output','Next hidden hy / one tensor','output',s,sh,return_fields=['hy'])
    for a,b,port in [('gru.x','gru.gi','input'),('gru.h','gru.gh','hidden'),('gru.params','gru.gi','parameters'),('gru.params','gru.gh','parameters'),('gru.gi','gru.ci','in'),('gru.gh','gru.ch','in')]:edges.append(link(a,b,port))
    for source,port,dst,dport in [('gru.ci','i_r','gru.r_add','input_r'),('gru.ch','h_r','gru.r_add','hidden_r'),('gru.ci','i_i','gru.z_add','input_z'),('gru.ch','h_i','gru.z_add','hidden_z'),('gru.ch','h_n','gru.rhn','hidden_n'),('gru.ci','i_n','gru.n_add','input_n')]:edges.append(link(source,dst,dport,source_port=port))
    for a,b,port in [('gru.r','gru.rhn','reset'),('gru.rhn','gru.n_add','recurrent_n'),('gru.h','gru.delta','hidden'),('gru.n','gru.delta','candidate'),('gru.z','gru.zdelta','update'),('gru.delta','gru.zdelta','delta'),('gru.n','gru.hy','candidate'),('gru.zdelta','gru.hy','retained_delta'),('gru.hy','gru.output','hy')]:edges.append(link(a,b,port))
    return make('gru_cell','GRUCell / explicit reset-update gates','GRUCell.md',
        'Functional gru_cell step only; supplied weights; no sequence loop or task head',SOURCE,['gru_cell'],inputs,body,[out],edges,
        dict(input_size=16,hidden_size=16,reset_after_affine=True,return_tuple=False,kernel_origin='supplementary PyTorch benchmark; not rasbt notebook kernel',label='One step / I=H=16 / reset after recurrent affine / supplied parameters'),
        ['The rasbt GRU model previously had an opaque nn.GRU boundary; this separately sourced benchmark function exposes a concrete GRU step.',
         'gi and gh each include their own bias before chunk(3,1); reset multiplies the complete h_n affine slice, including b_hh.',
         'The source inputgate is the standard update z. hy is n + z*(hidden-n); z retains old state.',
         'Weights and biases are Tensor arguments; this function does not register Parameters or prove the caller uses this implementation.'],
        ['Do not reset hidden before W_hh; do not swap reset/update gates; do not invent an LSTM cell state.',
         'Do not present the supplementary benchmark as the kernel extracted from the directory-listed rasbt notebook.'],
        roles={'gru.reset':'attention','gru.update':'attention','gru.candidate':'ffn'},
        legend=['B=batch; x,h:[B,16]; affine tensors:[B,48]; chunks ordered r,z,n.',
                'Reset multiplies h_n after its matrix multiplication and bias.',
                'The function returns one hy tensor; parameters arrive from its caller.'])


def validate_ir(ir):
    return verify(ir,'gru_cell',{
        'gru.gi':{'parameters':['w_ih','b_ih']},'gru.gh':{'parameters':['w_hh','b_hh']},
        'gru.ci':{'fields':['i_r','i_i','i_n'],'chunk_dim':1},'gru.ch':{'fields':['h_r','h_i','h_n']},
        'gru.rhn':{'ordered_operands':['resetgate','h_n']},
        'gru.hy':{'expression':'newgate + inputgate * (hidden - newgate)'},
        'gru.output':{'return_fields':['hy']}},
        [('gru.ch','gru.rhn','hidden_n'),('gru.r','gru.rhn','reset'),('gru.rhn','gru.n_add','recurrent_n'),
         ('gru.z','gru.zdelta','update'),('gru.h','gru.delta','hidden'),('gru.n','gru.hy','candidate'),('gru.zdelta','gru.hy','retained_delta')])
