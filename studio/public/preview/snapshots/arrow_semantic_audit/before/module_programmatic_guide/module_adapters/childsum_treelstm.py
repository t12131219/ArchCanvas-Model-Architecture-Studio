"""Actual ChildSumTreeLSTM.node_forward with per-child forget and reductions."""
from module_adapters.sequence_support import chain,op,graph,ref,link,make,verify
SOURCE='childsum-treelstm-sequence/treelstm/model.py'


def build():
    init=ref(SOURCE,'ChildSumTreeLSTM.__init__');s=ref(SOURCE,'ChildSumTreeLSTM.node_forward');edges=[]
    def linear(identity,title,owner,shape,weight_shape):
        return op(identity,title,'linear',[init,s],shape,parameter=owner,parameters=[owner+'.weight',owner+'.bias'],bias=True,weight_shape=weight_shape)
    ioux=linear('tree.ioux','Node input Linear / ioux','ioux','[48]',[48,12])
    hsum=op('tree.hsum','Sum child hidden / dim0','tensor',s,'[1,16]',dim=0,keepdim=True,expression='torch.sum(child_h, dim=0, keepdim=True)')
    iouh=linear('tree.iouh','Child-sum Linear / iouh','iouh','[1,48]',[48,16])
    iouadd=op('tree.iou_add','ioux + iouh / broadcast','add',s,'[1,48]',expression='self.ioux(inputs) + self.iouh(child_h_sum)')
    split=op('tree.split','Split gates / i,o,u','tensor',s,'three [1,16]',fields=['i','o','u'],dim=1,split_size=16,expression='torch.split(iou, iou.size(1) // 3, dim=1)')
    gates=[op('tree.'+field,title,kind,s,'[1,16]') for field,title,kind in [('i','Input gate / Sigmoid','sigmoid'),('o','Output gate / Sigmoid','sigmoid'),('u','Candidate / Tanh','tanh')]]
    iou=graph('tree.iou','Node gates from summed children',[ioux,hsum,iouh,iouadd,split,*gates],[init,s],'i,o,u:[1,16]',expand=2,
              ranks=[['tree.ioux','tree.hsum'],['tree.iouh'],['tree.iou_add'],['tree.split'],['tree.i','tree.o','tree.u']],rank_gap=64)
    fx=linear('tree.fx','Node input Linear / fx','fx','[16]',[16,12])
    fh=linear('tree.fh','Per-child Linear / fh','fh','[3,16]',[16,16])
    repeat=op('tree.repeat','Repeat fx across3 children','tensor',s,'[3,16]',repeats=[3,1],expression='self.fx(inputs).repeat(len(child_h), 1)',new_parameter_instances=False)
    fadd=op('tree.f_add','fh(child_h) + repeated fx','add',s,'[3,16]')
    f=op('tree.f','Per-child forget / Sigmoid','sigmoid',s,'[3,16]',gate_count_per_node=3)
    fc=op('tree.fc','Forget * each child cell','multiply',s,'[3,16]',expression='torch.mul(f, child_c)')
    fsum=op('tree.fsum','Sum retained children / dim0','tensor',s,'[1,16]',dim=0,keepdim=True,expression='torch.sum(fc, dim=0, keepdim=True)')
    forgetting=graph('tree.forget','Per-child forgetting',[fx,fh,repeat,fadd,f,fc,fsum],[init,s],'retained:[1,16]',expand=2,
              ranks=[['tree.fx','tree.fh'],['tree.repeat'],['tree.f_add'],['tree.f'],['tree.fc'],['tree.fsum']],rank_gap=64)
    new=op('tree.new','Input gate * candidate','multiply',s,'[1,16]',expression='torch.mul(i, u)')
    cell=op('tree.cell','New cell + retained children','add',s,'[1,16]',expression='torch.mul(i, u) + torch.sum(fc, dim=0, keepdim=True)')
    ctanh=op('tree.ctanh','Tanh new cell c','tanh',s,'[1,16]')
    hidden=op('tree.hidden','Output gate * Tanh(c)','multiply',s,'[1,16]',expression='torch.mul(o, F.tanh(c))')
    body=graph('tree.body','Child-Sum TreeLSTM / one node',[iou,forgetting,new,cell,ctanh,hidden],[init,s],
               'c,h:[1,16]',expand=1,ranks=[['tree.iou','tree.forget'],['tree.new'],['tree.cell'],['tree.ctanh'],['tree.hidden']],rank_gap=64)
    inputs=[op('tree.x','One node input vector','input',[s,ref(SOURCE,'ChildSumTreeLSTM.forward')],'[12]',selected_from='inputs[tree.idx]'),
            op('tree.child_c','Three child cell states','input',s,'[3,16]',operand='child_c'),
            op('tree.child_h','Three child hidden states','input',s,'[3,16]',operand='child_h')]
    output=op('tree.output','Return c, h / cell first','output',s,'c,h:[1,16]',return_fields=['c','h'],actual_return=True)
    for a,b,p in [('tree.x','tree.ioux','input'),('tree.child_h','tree.hsum','child_h'),('tree.hsum','tree.iouh','summed_hidden'),
                 ('tree.ioux','tree.iou_add','input_projection'),('tree.iouh','tree.iou_add','sum_projection'),('tree.iou_add','tree.split','in'),
                 ('tree.x','tree.fx','input'),('tree.child_h','tree.fh','per_child_hidden'),('tree.fx','tree.repeat','in'),
                 ('tree.fh','tree.f_add','per_child'),('tree.repeat','tree.f_add','repeated_node'),('tree.f_add','tree.f','in'),
                 ('tree.f','tree.fc','forget'),('tree.child_c','tree.fc','child_cell'),('tree.fc','tree.fsum','in'),
                 ('tree.i','tree.new','input_gate'),('tree.u','tree.new','candidate'),('tree.new','tree.cell','new_cell'),
                 ('tree.fsum','tree.cell','retained_children'),('tree.cell','tree.ctanh','in'),('tree.o','tree.hidden','output_gate'),
                 ('tree.ctanh','tree.hidden','cell_tanh'),('tree.cell','tree.output','cell'),('tree.hidden','tree.output','hidden')]:edges.append(link(a,b,p))
    for field in ['i','o','u']:edges.append(link('tree.split','tree.'+field,'preactivation',source_port=field))
    return make('childsum_treelstm','Child-Sum TreeLSTM / per-child forgetting','ChildSum_TreeLSTM.md',
        'node_forward only; selected nonleaf node has3 children; no recursion, embeddings or similarity head',SOURCE,
        ['ChildSumTreeLSTM.__init__','ChildSumTreeLSTM.forward','ChildSumTreeLSTM.node_forward'],inputs,body,[output],edges,
        dict(in_dim=12,mem_dim=16,children=3,input_rank=1,leaf_zero_initializer_selected=False,return_fields=['c','h'],
             label='One nonleaf node / I12,H16,K3 / child-sum gates + per-child forget'),
        ['Child-Sum TreeLSTM first reduces child hidden states for shared i/o/u gates, but computes a distinct forget value for every child before reducing retained child cells.',
         'The selected source caller inputs[tree.idx] is a rank1 node vector; its ioux output broadcasts against the rank2 child-sum projection.',
         'Four independent nn.Linear instances ioux,iouh,fx,fh include default biases; repeat and per-child batch rows share fx/fh parameters.',
         'The source returns cell c first, hidden h second; this differs from the conventional hy,cy order of a sequence LSTM cell.',
         'The class recursively obtains child states outside node_forward; leaf callers supply a single zero child state, not a fabricated zero-length children tensor.'],
        ['Do not sum children before fh and thereby replace K forget gates with one shared forget gate.',
         'Do not swap child_c and child_h or label node_forward outputs as a full similarity model prediction.'],
        roles={'tree.iou':'ffn','tree.forget':'attention'},
        legend=['K=3 children; child_h/child_c:[3,16]; shared node gates and c,h:[1,16].',
                'Summation uses dim0,keepdim=True; all child rows reuse the same learned four Linear families.',
                'The selected actual method returns(c,h); recursive traversal is outside the diagram boundary.'])


def validate_ir(ir):
    return verify(ir,'childsum_treelstm',{
        'tree.x':{'shape':'[12]','selected_from':'inputs[tree.idx]'},
        'tree.hsum':{'dim':0,'keepdim':True},'tree.fsum':{'dim':0,'keepdim':True},
        'tree.ioux':{'parameter':'ioux','weight_shape':[48,12],'bias':True},
        'tree.iouh':{'parameter':'iouh','weight_shape':[48,16],'bias':True},
        'tree.fx':{'parameter':'fx','weight_shape':[16,12],'bias':True},
        'tree.fh':{'parameter':'fh','weight_shape':[16,16],'bias':True},
        'tree.split':{'fields':['i','o','u'],'dim':1,'split_size':16},
        'tree.repeat':{'repeats':[3,1],'new_parameter_instances':False},
        'tree.f':{'shape':'[3,16]','gate_count_per_node':3},
        'tree.output':{'return_fields':['c','h'],'actual_return':True}},
        [('tree.child_h','tree.hsum','child_h'),('tree.child_h','tree.fh','per_child_hidden'),
         ('tree.fh','tree.f_add','per_child'),('tree.repeat','tree.f_add','repeated_node'),
         ('tree.child_c','tree.fc','child_cell'),('tree.fsum','tree.cell','retained_children'),
         ('tree.o','tree.hidden','output_gate'),('tree.cell','tree.output','cell'),('tree.hidden','tree.output','hidden')])
