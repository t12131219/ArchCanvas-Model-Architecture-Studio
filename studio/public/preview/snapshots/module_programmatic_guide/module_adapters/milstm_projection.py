"""The distinctive multiplicative preactivation subgraph of benchmark milstm_cell."""
from module_adapters.sequence_support import chain,op,graph,ref,link,make,verify
SOURCE='pytorch-sequence-kernels-v2.5.1/benchmarks/fastrnns/cells.py'


def build():
    s=ref(SOURCE,'milstm_cell');sh='[B,64]';edges=[]
    wx=op('mi.wx','Input projection / Wx','linear',s,sh,parameters=['w_ih'],bias=False,
          weight_shape=[64,12],expression='x.mm(w_ih.t())',parameter_origin='caller Tensor argument')
    uz=op('mi.uz','Hidden projection / Uz','linear',s,sh,parameters=['w_hh'],bias=False,
          weight_shape=[64,16],expression='hx.mm(w_hh.t())',parameter_origin='caller Tensor argument')
    coupling=chain('mi.coupling','Coupling term',[
        op('mi.alpha_wx','alpha * Wx','multiply',s,sh,parameters=['alpha'],parameter_shape=[64],expression='alpha * Wx'),
        op('mi.product','(alpha * Wx) * Uz','multiply',s,sh,expression='alpha * Wx * Uz'),
    ],s,sh,expand=2)
    bi=op('mi.input_term','beta_i * Wx','multiply',s,sh,parameters=['beta_i'],parameter_shape=[64],expression='beta_i * Wx')
    bh=op('mi.hidden_term','beta_h * Uz','multiply',s,sh,parameters=['beta_h'],parameter_shape=[64],expression='beta_h * Uz')
    add1=op('mi.add_input','Coupling + input term','add',s,sh,ordered_operands=['alpha * Wx * Uz','beta_i * Wx'])
    add2=op('mi.add_hidden','Add hidden term','add',s,sh,ordered_operands=['coupling_plus_input','beta_h * Uz'])
    bias=op('mi.bias','Add one gate bias','add',s,sh,parameters=['bias'],parameter_shape=[64],
            expression='alpha * Wx * Uz + beta_i * Wx + beta_h * Uz + bias',registered_in_function=False)
    body=graph('mi.body','MI gate preactivation subgraph',[wx,uz,coupling,bi,bh,add1,add2,bias],s,sh,expand=1,
               ranks=[['mi.wx','mi.uz'],['mi.coupling','mi.input_term','mi.hidden_term'],['mi.add_input'],['mi.add_hidden'],['mi.bias']],rank_gap=64)
    inputs=[op('mi.x','Current input x','input',s,'[B,12]'),op('mi.h','Previous hidden hx','input',s,'[B,16]'),
            op('mi.params','Caller weights / coefficients','input',s,'W_ih:[64,12]; W_hh:[64,16]; vectors:[64]',registered_in_function=False)]
    output=op('mi.output','Boundary: gates before chunk','output',s,sh,actual_return=False,
              boundary_variable='gates',next_source_operation='gates.chunk(4, 1)',actual_function_return=['hy','cy'])
    for a,b,p in [('mi.x','mi.wx','input'),('mi.h','mi.uz','hidden'),('mi.wx','mi.alpha_wx','Wx'),
                 ('mi.uz','mi.product','Uz'),('mi.wx','mi.input_term','Wx'),('mi.uz','mi.hidden_term','Uz'),
                 ('mi.product','mi.add_input','coupling'),('mi.input_term','mi.add_input','input_term'),
                 ('mi.add_input','mi.add_hidden','partial'),('mi.hidden_term','mi.add_hidden','hidden_term'),
                 ('mi.add_hidden','mi.bias','partial'),('mi.bias','mi.output','gates')]:
        # Uz is the second operand of the upper multiplication inside the
        # coupling chain; a side operand port avoids the lower alpha*Wx node.
        routing={'dst_side':'right'} if b=='mi.product' else {}
        edges.append(link(a,b,p,**routing))
    for dest,param in [('mi.wx','w_ih'),('mi.uz','w_hh'),('mi.alpha_wx','alpha'),('mi.input_term','beta_i'),('mi.hidden_term','beta_h'),('mi.bias','bias')]:
        edges.append(link('mi.params',dest,param,source_port=param))
    return make('milstm_projection','MI-LSTM / multiplicative gate integration','MI_LSTM_Projection.md',
        'milstm_cell gate preactivation subgraph only; gates boundary is not a standalone source return',SOURCE,['milstm_cell'],inputs,body,[output],edges,
        dict(input_size=12,hidden_size=16,gate_width=64,coefficient_shape=[64],boundary_variable='gates',actual_function_return=['hy','cy'],
             kernel_origin='supplementary PyTorch benchmark; not rasbt notebook kernel',label='Gate preactivation only / I12,H16 / alpha,beta_i,beta_h,bias supplied'),
        ['Multiplicative integration introduces alpha*Wx*Uz plus independently weighted input and hidden terms before the ordinary four-gate LSTM suffix.',
         'The source multiplication is left-associated: alpha*Wx first, then multiply Uz; the diagram retains that operation order.',
         'Matrix projections have no separate b_ih/b_hh; a single supplied gate bias is added after the three terms.',
         'This is a source subgraph with gates as its chosen boundary; milstm_cell actually continues with chunk4 and returns hy,cy.',
         'Coefficient vectors and matrix weights are caller Tensor arguments; the function itself registers no Parameters.'],
        ['Do not replace the interaction term by Wx+Uz or confuse beta_i with beta_h.',
         'Do not claim gates is a source function return or that this benchmark implements the directory notebook kernel.'],
        roles={'mi.coupling':'attention'},
        legend=['Gate width4H=64; all three terms have the same static[B,64] shape.',
                'Shared Wx/Uz producers fan out to distinct real operand ports; colors do not imply weight sharing.',
                'The top boundary ends before chunk4; the standard LSTM suffix is outside this figure.'])


def validate_ir(ir):
    return verify(ir,'milstm_projection',{
        'mi.wx':{'parameters':['w_ih'],'weight_shape':[64,12],'bias':False},
        'mi.uz':{'parameters':['w_hh'],'weight_shape':[64,16],'bias':False},
        'mi.alpha_wx':{'parameters':['alpha'],'expression':'alpha * Wx'},
        'mi.product':{'expression':'alpha * Wx * Uz'},'mi.input_term':{'parameters':['beta_i']},
        'mi.hidden_term':{'parameters':['beta_h']},
        'mi.bias':{'expression':'alpha * Wx * Uz + beta_i * Wx + beta_h * Uz + bias','parameters':['bias']},
        'mi.output':{'actual_return':False,'boundary_variable':'gates','actual_function_return':['hy','cy']}},
        [('mi.wx','mi.alpha_wx','Wx'),('mi.uz','mi.product','Uz'),('mi.wx','mi.input_term','Wx'),
         ('mi.uz','mi.hidden_term','Uz'),('mi.product','mi.add_input','coupling'),('mi.input_term','mi.add_input','input_term'),
         ('mi.hidden_term','mi.add_hidden','hidden_term'),('mi.params','mi.bias','bias'),('mi.bias','mi.output','gates')])
