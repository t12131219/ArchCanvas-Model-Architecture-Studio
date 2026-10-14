"""Standard explicit LSTM equations and a three-step shared-cell source projection."""
from spec import op, graph, ref

SOURCE = 'pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py'


def build():
    init=ref(SOURCE,'LSTMCell.__init__'); forward=ref(SOURCE,'LSTMCell.forward')
    layer_init=ref(SOURCE,'LSTMLayer.__init__'); layer=ref(SOURCE,'LSTMLayer.forward')
    roles={};edges=[]
    def edge(src,dst,src_port='out',dst_port='in',role='tensor',label='',src_side='out',dst_side='in'):
        edges.append(dict(src=src,dst=dst,src_port=src_port,dst_port=dst_port,role=role,label=label,
                          src_side=src_side,dst_side=dst_side,dashed=False))
    def leaf(identity,label,kind,source,shape='[B,16]',**kw):
        roles[identity]=kw.pop('visual_role',kind)
        return op(identity,label,kind,source,shape,width=260,**kw)
    def group(identity,label,items,ranks,source,shape='',expand=2,**kw):
        roles[identity]='inner'
        return graph(identity,label,items,source,shape,ranks=ranks,expand=expand,rank_gap=52,column_gap=48,**kw)

    cells=[]
    for step in range(3):
        p=f'lstmcell.step{step}'
        x=leaf(p+'.x',f'Input x_{step}','input',[layer,forward],'[B,8]',
               expression=f'inputs[{step}]',time_index=step)
        hx=leaf(p+'.hx',f'Previous hidden h_{step-1}','tensor',forward,
                input_selector='state[0]',state_role='hidden',time_index=step-1)
        cx=leaf(p+'.cx',f'Previous cell c_{step-1}','tensor',forward,
                input_selector='state[1]',state_role='cell',time_index=step-1)
        x_mm=leaf(p+'.x_mm','MatMul x W_ih^T','linear',[init,forward],'[B,64]',
                  parameter='cell.weight_ih',parameter_shape=[64,8],expression='torch.mm(input, self.weight_ih.t())')
        h_mm=leaf(p+'.h_mm','MatMul h W_hh^T','linear',[init,forward],'[B,64]',
                  parameter='cell.weight_hh',parameter_shape=[64,16],expression='torch.mm(hx, self.weight_hh.t())')
        b_ih=leaf(p+'.b_ih','Add input bias b_ih','arithmetic',[init,forward],'[B,64]',visual_role='norm',operation='add',
                  parameter='cell.bias_ih',parameter_shape=[64],expression='x_affine + self.bias_ih')
        combine=leaf(p+'.affine_add','Add hidden projection','arithmetic',forward,'[B,64]',visual_role='norm',operation='add',
                     expression='(x_affine + bias_ih) + h_affine')
        b_hh=leaf(p+'.b_hh','Add hidden bias b_hh','arithmetic',[init,forward],'[B,64]',visual_role='norm',operation='add',
                  parameter='cell.bias_hh',parameter_shape=[64],expression='((x_affine + bias_ih) + h_affine) + self.bias_hh')
        affine=group(p+'.affine','Fused four-gate affine',[x_mm,h_mm,b_ih,combine,b_hh],
                     [[x_mm['id'],h_mm['id']],[b_ih['id']],[combine['id']],[b_hh['id']]],
                     [init,forward],'gates: [B,4H=64]',expand=2,
                     detail=['Two matrices store all four gate row slices; source does not concatenate x and h'],
                     parameter_scope='cell',source_addition_order=['x_mm','bias_ih','h_mm','bias_hh'])
        edge(p+'.x',p+'.x_mm');edge(p+'.hx',p+'.h_mm')
        edge(p+'.x_mm',p+'.b_ih');edge(p+'.b_ih',p+'.affine_add',dst_port='x_affine')
        edge(p+'.h_mm',p+'.affine_add',dst_port='h_affine')
        edge(p+'.affine_add',p+'.b_hh')
        chunk=leaf(p+'.chunk','Chunk gates: i / f / g / o','tensor',forward,
                   '4 x [B,16]',expression='gates.chunk(4, 1)',chunk_order=['i','f','g','o'],dim=1)
        edge(p+'.b_hh',p+'.chunk')
        gates=[]
        for slot,(gate,label,kind,activation) in enumerate([
            ('i','Input gate i: Sigmoid','activation','sigmoid'),
            ('f','Forget gate f: Sigmoid','activation','sigmoid'),
            ('g','Candidate g: Tanh','activation','tanh'),
            ('o','Output gate o: Sigmoid','activation','sigmoid')]):
            gates.append(leaf(p+'.'+gate,label,kind,forward,
                              visual_role='softmax' if activation=='sigmoid' else 'activation',
                              activation=activation,gate_name=gate,input_selector=f'item[{slot}]',
                              param_identity=f'cell four fused parameters; {gate} rows [{slot*16}:{(slot+1)*16}]',
                              parameter_slice=dict(parameters=['cell.weight_ih','cell.weight_hh','cell.bias_ih','cell.bias_hh'],
                                                   rows=[slot*16,(slot+1)*16]),
                              expression=f'torch.{activation}({["ingate","forgetgate","cellgate","outgate"][slot]})'))
            edge(p+'.chunk',p+'.'+gate,src_port=f'item[{slot}]',role='gate_slice',label=gate)
        gate_group=group(p+'.gates','Four distinct gate slices',gates,[[n['id'] for n in gates]],forward,
                         'i, f, g, o: [B,H]',expand=2,
                         detail=['i/f/o use sigmoid; candidate g uses tanh; slices belong to the same fused matrices'])
        old=leaf(p+'.forget_mul','Multiply f * previous c','arithmetic',forward,visual_role='norm',
                 operation='multiply',expression='forgetgate * cx',operands=[p+'.f',p+'.cx'])
        new=leaf(p+'.input_mul','Multiply i * candidate g','arithmetic',forward,visual_role='norm',
                 operation='multiply',expression='ingate * cellgate',operands=[p+'.i',p+'.g'])
        cy=leaf(p+'.cy',f'Add terms -> cell c_{step}','arithmetic',forward,visual_role='norm',
                operation='add',expression='(forgetgate * cx) + (ingate * cellgate)',
                operands=[p+'.forget_mul',p+'.input_mul'],state_role='cell',time_index=step)
        cell_update=group(p+'.cell_update','Cell state update',[old,new,cy],
                          [[old['id'],new['id']],[cy['id']]],forward,'c_t = f*c_prev + i*g',expand=2)
        edge(p+'.f',p+'.forget_mul',dst_port='f');edge(p+'.cx',p+'.forget_mul',dst_port='previous_c')
        edge(p+'.i',p+'.input_mul',dst_port='i');edge(p+'.g',p+'.input_mul',dst_port='g')
        edge(p+'.forget_mul',p+'.cy',dst_port='retained');edge(p+'.input_mul',p+'.cy',dst_port='new')
        tanh=leaf(p+'.tanh_c','Tanh updated cell','activation',forward,
                  activation='tanh',expression='torch.tanh(cy)')
        hy=leaf(p+'.hy',f'Multiply o * tanh(c) -> h_{step}','arithmetic',forward,visual_role='norm',
                operation='multiply',expression='outgate * torch.tanh(cy)',operands=[p+'.o',p+'.tanh_c'],
                state_role='hidden',time_index=step)
        hidden_update=group(p+'.hidden_update','Hidden state update',[tanh,hy],[[tanh['id']],[hy['id']]],
                            forward,'h_t = o*tanh(c_t)',expand=2)
        edge(p+'.cy',p+'.tanh_c');edge(p+'.tanh_c',p+'.hy',dst_port='tanh_c')
        edge(p+'.o',p+'.hy',dst_port='o')
        returned=leaf(p+'.return','Return h, (h, c)','output',forward,'h: [B,16]; state: 2 tensors',
                      output_tuple=['hy',['hy','cy']],aliases={'output':'state[0]'})
        edge(p+'.hy',p+'.return',dst_port='output_hidden');edge(p+'.hy',p+'.return',dst_port='state_hidden')
        edge(p+'.cy',p+'.return',dst_port='state_cell')
        cell=group(p,f'LSTM cell / time {step}',[x,hx,cx,affine,chunk,gate_group,cell_update,hidden_update,returned],
                   [[x['id'],hx['id'],cx['id']],[affine['id']],[chunk['id']],[gate_group['id']],
                    [cell_update['id']],[hidden_update['id']],[returned['id']]],
                   [layer,forward],'(output h, state(h,c))',expand=1 if step==1 else 3,
                   detail=['Same self.cell instance and same four parameter tensors at every time step'],
                   instance_identity='self.cell',parameter_scope='cell',time_index=step,
                   temporal_parameter_sharing=True)
        roles[p]='recurrent';cells.append(cell)

    sequence=leaf('lstmcell.sequence','Sequence input X','input',layer,'[T=3,B,I=8]',
                  origin='external argument input',selected_sequence_length=3)
    unbind=leaf('lstmcell.unbind','Unbind time axis 0','tensor',layer,'3 tensors [B,8]',
                expression='input.unbind(0)',dim=0)
    tokens=[leaf(f'lstmcell.x{t}',f'Select x_{t}','input',layer,'[B,8]',
                 input_selector=f'item[{t}]',time_index=t) for t in range(3)]
    stack=leaf('lstmcell.stack','Stack all time outputs','tensor',layer,'[3,B,16]',
               expression='torch.stack(outputs)',dim=0,ordered_inputs=[f'lstmcell.step{t}.hy' for t in range(3)])
    result=leaf('lstmcell.return','Layer return: sequence, final state','output',layer,
                '[3,B,16], ([B,16],[B,16])',output_tuple=['outputs',['h_final','c_final']],
                final_time_index=2)
    root=group('lstmcell.root','One LSTMLayer / three shared time steps',
               [sequence,unbind,*tokens,*cells,stack,result],
               [[sequence['id']],[unbind['id']],[n['id'] for n in tokens],[n['id'] for n in cells],
                [stack['id']],[result['id']]],
               [layer_init,layer],'T=3, one layer, one direction',expand=0,
               align_x={f'lstmcell.x{t}':f'lstmcell.step{t}' for t in range(3)})
    roles['lstmcell.root']='root'
    edge(sequence['id'],unbind['id'])
    for t in range(3):
        edge(unbind['id'],f'lstmcell.x{t}',src_port=f'item[{t}]',role='time_slice')
        edge(f'lstmcell.x{t}',f'lstmcell.step{t}.x')
        edge(f'lstmcell.step{t}.hy',stack['id'],dst_port=f'item[{t}]',role='sequence_output',label=f'h_{t}')
        if t:
            for state in ('h','c'):
                edge(f'lstmcell.step{t-1}.{state}y',f'lstmcell.step{t}.{state}x',
                     role='recurrent_state',label=f'{state}_{t-1}',src_side='right',dst_side='left')
    edge(stack['id'],result['id'],dst_port='output_sequence')
    edge('lstmcell.step2.hy',result['id'],dst_port='final_hidden',role='final_state',label='final h')
    edge('lstmcell.step2.cy',result['id'],dst_port='final_cell',role='final_state',label='final c')
    initial=[]
    for state,label in [('h','hidden'),('c','cell')]:
        node=leaf('lstmcell.initial_'+state,'External initial '+label,'input',layer,'[B,16]',
                  origin='external state argument',initial_state_default=None,state_role=label)
        initial.append(node)
        edge(node['id'],'lstmcell.step0.'+state+'x',role='initial_state',label=state+'_init',
             src_side='right',dst_side='left')
    return dict(key='lstmcell',name='LSTM (explicit gates, shared time steps)',
        source_project='pytorch-lstmcell-v2.5.1',entry=layer,
        profile=dict(input_size=8,hidden_size=16,sequence_length=3,batch='B',num_layers=1,bidirectional=False,
                     construction='LSTMLayer(LSTMCell, input_size=8, hidden_size=16)',
                     configuration_origin='explicit illustrative configuration, not upstream benchmark defaults',
                     input_layout='[T,B,I]',initial_state='external h_init,c_init; no default assumed',
                     source_variant='LSTMCell, not LayerNormLSTMCell or premultiplied variants',
                     chunk_order=['i','f','g','o'],parameter_shapes={'cell.weight_ih':[64,8],'cell.weight_hh':[64,16],
                         'cell.bias_ih':[64],'cell.bias_hh':[64]},bias_initialization='torch.randn, no +1 forget bias',
                     temporal_parameter_sharing=True,source_concat=False,peepholes=False,dropout=False,
                     model_executed=False,shapes='static derivation',output='(stacked h_0..h_2, (h_2,c_2))'),
        profile_label='Official PyTorch explicit cell / I=8 H=16 T=3 / same weights across time',
        tree=root,aux_inputs=initial,extra_edges=edges,visual_roles=roles,fill_width=[],
        facts=[
            'Official custom LSTMCell explicitly defines two 4H matrices and two biases; no opaque nn.LSTM is substituted.',
            'Source affine addition order is x W_ih^T + b_ih + h_prev W_hh^T + b_hh; the diagram preserves that order.',
            'gates.chunk(4,1) yields i,f,g,o; i/f/o use Sigmoid and candidate g uses Tanh.',
            'Cell update is f*c_prev+i*g; hidden update is o*tanh(c); c_prev never directly supplies the affine gates.',
            'Cell returns hy,(hy,cy), with the exact same hy tensor as output and state hidden.',
            'LSTMLayer creates one self.cell; its time loop reuses all four parameter tensors and carries both h and c.',
            'Three steps are a selected T=3 input; the input and hidden widths 8/16 are illustrative configuration, not inferred defaults.',
            'Layer unbinds time axis0 and stacks all outputs, returning the complete sequence and only the final h/c state.',
            'Initial h/c are mandatory supplied state arguments; the source does not create a zero default inside LSTMLayer.forward.',
        ],corrections=[
            'The reference image shows temporal recurrence and cell equations; replace implicit concatenation with the actual two source MatMuls.',
            'Draw one input gate, one forget gate, one output gate and a Tanh candidate; four gates are slices, not four independently constructed Linear modules.',
            'The candidate is not a fourth Sigmoid; the cell memory route is separate from the hidden-state route.',
            'Do not add peepholes, forget-bias+1, Dropout, LayerNorm, packing or a classifier absent from this chosen source variant.',
            'Time advances horizontally; operator dependencies inside the central cell advance bottom-to-top.',
            'Existing packed and bidirectional LSTM examples retain their separate source/configuration and explicit library boundaries.',
        ],symbols={SOURCE:['LSTMCell','LSTMCell.__init__','LSTMCell.forward','LSTMLayer','LSTMLayer.__init__','LSTMLayer.forward']},
        config_files=[SOURCE],legend=['B batch; I=8; H=16; T=3 chosen input; columns advance time left to right',
            'i/f/o Sigmoid; g Tanh; yellow blocks explicit elementwise Multiply/Add',
            'One self.cell instance, four fused parameter tensors; center cell expands; neighbor cells fold'],
        color_legend=[('input','Input / State'),('linear','Gate affine'),('softmax','Sigmoid gate'),
                      ('activation','Tanh'),('norm','Multiply / Add'),('recurrent','Shared cell')])


def validate_ir(ir):
    nodes={n['id']:n for n in ir['nodes']};edges=ir['edges'];checks=[]
    def check(condition,label):
        if not condition:raise ValueError('lstmcell: '+label)
        checks.append(label)
    def has(src,dst,role=None,sp=None,dp=None):
        return any(e['src']==src and e['dst']==dst and (role is None or e['role']==role)
                   and (sp is None or e['src_port']==sp) and (dp is None or e['dst_port']==dp) for e in edges)
    p=ir['profile']
    check(p['sequence_length']==3 and p['input_size']==8 and p['hidden_size']==16 and p['num_layers']==1
          and p['bidirectional'] is False,'selected one-layer three-step profile')
    check(p['source_concat'] is False and p['peepholes'] is False and p['dropout'] is False,
          'actual explicit source variant without invented concatenation or peepholes')
    for t in range(3):
        prefix=f'lstmcell.step{t}'
        n=lambda name:nodes[prefix+'.'+name]
        check(nodes[prefix]['instance_identity']=='self.cell' and nodes[prefix]['temporal_parameter_sharing'],
              f'time {t} uses same cell instance')
        check(n('chunk')['chunk_order']==['i','f','g','o'] and n('chunk')['dim']==1,
              f'time {t} fused chunk order')
        check([n(g)['activation'] for g in ('i','f','g','o')]==['sigmoid','sigmoid','tanh','sigmoid'],
              f'time {t} three Sigmoid gates and Tanh candidate')
        for slot,gate in enumerate(('i','f','g','o')):
            check(n(gate)['kind']=='activation' and n(gate)['input_selector']==f'item[{slot}]'
                  and n(gate)['parameter_slice']==dict(parameters=['cell.weight_ih','cell.weight_hh','cell.bias_ih','cell.bias_hh'],
                                                      rows=[slot*16,(slot+1)*16])
                  and has(prefix+'.chunk',prefix+'.'+gate,'gate_slice',sp=f'item[{slot}]',dp='in'),
                  f'time {t} {gate} exact fused parameter slice and binding')
        for name,param,shape in [('x_mm','weight_ih',[64,8]),('h_mm','weight_hh',[64,16]),
                                 ('b_ih','bias_ih',[64]),('b_hh','bias_hh',[64])]:
            check(n(name)['parameter']=='cell.'+param and n(name)['parameter_shape']==shape,
                  f'time {t} shared {param} identity and dimensions')
        check(has(prefix+'.x',prefix+'.x_mm',sp='out',dp='in')
              and has(prefix+'.hx',prefix+'.h_mm',sp='out',dp='in')
              and has(prefix+'.b_hh',prefix+'.chunk',sp='out',dp='in'),
              f'time {t} actual input-hidden affine producers and fused result')
        check(n('affine')['source_addition_order']==['x_mm','bias_ih','h_mm','bias_hh']
              and has(prefix+'.x_mm',prefix+'.b_ih') and has(prefix+'.b_ih',prefix+'.affine_add')
              and has(prefix+'.h_mm',prefix+'.affine_add') and has(prefix+'.affine_add',prefix+'.b_hh'),
              f'time {t} exact source affine addition structure')
        check(n('cy')['expression']=='(forgetgate * cx) + (ingate * cellgate)'
              and n('hy')['expression']=='outgate * torch.tanh(cy)',f'time {t} cell and hidden equations')
        for src,dst,port in [('f','forget_mul','f'),('cx','forget_mul','previous_c'),('i','input_mul','i'),
                             ('g','input_mul','g'),('forget_mul','cy','retained'),('input_mul','cy','new'),
                             ('cy','tanh_c','in'),('tanh_c','hy','tanh_c'),('o','hy','o')]:
            check(has(prefix+'.'+src,prefix+'.'+dst,dp=port),f'time {t} operand {src}->{dst}:{port}')
        check(n('return')['output_tuple']==['hy',['hy','cy']] and n('return')['aliases']=={'output':'state[0]'},
              f'time {t} output-hidden alias and cell return')
        check(has(prefix+'.hy',prefix+'.return',dp='output_hidden') and
              has(prefix+'.hy',prefix+'.return',dp='state_hidden') and
              has(prefix+'.cy',prefix+'.return',dp='state_cell'),f'time {t} exact return field producers')
        check(has('lstmcell.unbind',f'lstmcell.x{t}',sp=f'item[{t}]') and
              has(f'lstmcell.x{t}',prefix+'.x') and n('x')['time_index']==t and
              n('hx')['input_selector']=='state[0]' and n('cx')['input_selector']=='state[1]',
              f'time {t} input slice and supplied state selection')
        check(not any(e['src']==prefix+'.cx' and e['dst']!=prefix+'.forget_mul' for e in edges),
              f'time {t} no cell-state peephole into gates')
        check(has(prefix+'.hy','lstmcell.stack','sequence_output',dp=f'item[{t}]'),
              f'time {t} ordered sequence collection')
        if t:
            check(has(f'lstmcell.step{t-1}.hy',prefix+'.hx','recurrent_state') and
                  has(f'lstmcell.step{t-1}.cy',prefix+'.cx','recurrent_state'),f'time {t} two distinct recurrent states')
    check(nodes['lstmcell.stack']['ordered_inputs']==[f'lstmcell.step{t}.hy' for t in range(3)]
          and nodes['lstmcell.stack']['expression']=='torch.stack(outputs)', 'real stacked output sequence')
    check(has('lstmcell.sequence','lstmcell.unbind') and has('lstmcell.stack','lstmcell.return',dp='output_sequence'),
          'layer sequence argument and returned stacked output')
    check(has('lstmcell.step2.hy','lstmcell.return','final_state',dp='final_hidden') and
          has('lstmcell.step2.cy','lstmcell.return','final_state',dp='final_cell'),'only final state is returned by layer')
    check(all(nodes['lstmcell.initial_'+s]['initial_state_default'] is None and
              has('lstmcell.initial_'+s,'lstmcell.step0.'+s+'x','initial_state') for s in ('h','c')),
          'explicit supplied initial hidden and cell arguments')
    return checks
