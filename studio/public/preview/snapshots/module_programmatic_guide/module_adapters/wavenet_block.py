"""One real WaveNet loop iteration with phase dilation and two state updates."""
from module_adapters.sequence_support import chain,op,graph,ref,link,make,verify
SOURCE='pytorch-wavenet-sequence/wavenet_model.py'
HELPER='pytorch-wavenet-sequence/wavenet_modules.py'


def build():
    init=ref(SOURCE,'WaveNetModel.__init__');s=ref(SOURCE,'WaveNetModel.wavenet');d=ref(HELPER,'dilate');edges=[]
    dilate=op('wave.dilate','Dilate2 / fold phases into N','tensor',[s,ref(SOURCE,'WaveNetModel.wavenet_dilate'),d],
              '[2,32,9]',dilation=2,init_dilation=1,padding_applied=False,expression='dilate(input, dilation, init_dilation)',
              detail=['selected inputN1,L18 divisible by2; permute/view/permute helper'])
    branches=[]
    for name,kind in [('filter','tanh'),('gate','sigmoid')]:
        branches.append(chain('wave.'+name,name.title()+' branch',[
            op('wave.'+name+'_conv','Conv2 / 32 -> 32','conv1d',init,'[2,32,8]',
               parameter=name+'_convs.1',parameters=[name+'_convs.1.weight'],kernel_size=2,dilation=1,bias=False),
            op('wave.'+name+'_act','Tanh' if kind=='tanh' else 'Sigmoid',kind,s,'[2,32,8]'),
        ],[init,s],'[2,32,8]',expand=2))
    product=op('wave.product','Filter * gate','multiply',s,'[2,32,8]')
    skip=chain('wave.skip','Skip path / undo phase folding',[
        op('wave.undilate','Restore phases / dilation1','tensor',[s,d],'[1,32,16]',dilation=1,init_dilation=2,
           expression='dilate(x, 1, init_dilation=dilation)'),
        op('wave.skip_conv','Skip Conv1 / 32 -> 256','conv1d',[init,s],'[1,256,16]',
           parameter='skip_convs.1',parameters=['skip_convs.1.weight'],kernel_size=1,bias=False),
    ],[init,s,d],'[1,256,16]',expand=2)
    projection=op('wave.res_conv','Residual Conv1 / 32 -> 32','conv1d',[init,s],'[2,32,8]',
                  parameter='residual_convs.1',parameters=['residual_convs.1.weight'],kernel_size=1,bias=False)
    crop=op('wave.res_crop','Crop residual left1','tensor',s,'[2,32,8]',
            expression='residual[:, :, (self.kernel_size - 1):]',crop_side='left',crop_size=1)
    skipcrop=op('wave.skip_crop','Keep last16 previous skip positions','tensor',s,'[1,256,16]',
                expression='skip[:, :, -s.size(2):]',exception_path_selected=False)
    skipadd=op('wave.skip_add','s + cropped previous skip','add',s,'[1,256,16]')
    resadd=op('wave.res_add','Projected x + cropped residual','add',s,'[2,32,8]')
    body=graph('wave.body','WaveNet loop iteration i=1',[dilate,*branches,product,skip,projection,crop,skipcrop,skipadd,resadd],[init,s,d],
        'x_next:[2,32,8]; skip_next:[1,256,16]',expand=1,
        ranks=[['wave.dilate'],['wave.filter','wave.gate'],['wave.product'],['wave.skip','wave.res_conv','wave.res_crop','wave.skip_crop'],['wave.skip_add','wave.res_add']],rank_gap=64)
    inputs=[op('wave.x','Previous loop residual x','input',s,'[1,32,18]'),
            op('wave.previous_skip','Previous tensor skip','input',s,'[1,256,18]',zero_initial_skip_selected=False)]
    outputs=[op('wave.output_x','Updated loop x / phase-folded','output',s,'[2,32,8]',actual_return=False),
             op('wave.output_skip','Updated loop skip','output',s,'[1,256,16]',actual_return=False)]
    for a,b,port in [('wave.x','wave.dilate','input'),('wave.dilate','wave.filter','in'),('wave.dilate','wave.gate','in'),('wave.filter_act','wave.product','filter'),('wave.gate_act','wave.product','gate'),('wave.product','wave.skip','in'),('wave.product','wave.res_conv','input'),('wave.dilate','wave.res_crop','residual'),('wave.previous_skip','wave.skip_crop','previous_skip'),('wave.skip_conv','wave.skip_crop','shape'),('wave.skip','wave.skip_add','new_skip'),('wave.skip_crop','wave.skip_add','previous_skip'),('wave.res_conv','wave.res_add','projected'),('wave.res_crop','wave.res_add','retained'),('wave.res_add','wave.output_x','x'),('wave.skip_add','wave.output_skip','skip')]:
        # The length-only dependency leaves the inner skip Conv on the side;
        # its tensor output exits through the containing skip path above.
        routing={'src_side':'right','dst_side':'left'} if port=='shape' else {}
        edges.append(link(a,b,port,role='shape_dependency' if port=='shape' else 'tensor',**routing))
    return make('wavenet_block','WaveNet / gated residual and skip iteration','WaveNet_Block.md',
        'wavenet loop i1 only; dilation2/init1; no start/end heads or fast-generation queues',SOURCE,
        ['WaveNetModel.__init__','WaveNetModel.wavenet_dilate','WaveNetModel.wavenet'],inputs,body,outputs,edges,
        dict(iteration=1,dilation=2,init_dilation=1,kernel_size=2,bias=False,previous_skip_is_tensor=True,
             loop_boundary_outputs=['x','skip'],actual_function_return=False,label='Loop i1 / phase dilation2 / gated Conv2 / residual + skip states'),
        ['The actual implementation obtains dilation through permute/view phase folding, not Conv1d(dilation=2); filter/gate Conv1d have ordinary dilation1.',
         'For selected N1,L18, dilation2 gives N2,L9, valid Conv2 gives L8; the skip helper restores N1,L16 before its1x1 Conv.',
         'The residual uses left-cropped phase-folded residual after(kernel_size-1); skip keeps the trailing new-skip length.',
         'Selected i1 has an existing tensor skip; the except zero initializer path is not selected.',
         'Two glyph outputs are loop-boundary variables, not a tuple returned by WaveNetModel.wavenet; its final waveform logits head is outside scope.'],
        ['Do not replace phase folding with a falsely claimed source dilation kwarg; do not swap skip and residual convolution outputs.',
         'Do not crop the residual right side as in TCN; do not call the selected loop states a source return tuple.'],
        roles={'wave.filter':'ffn','wave.gate':'attention','wave.skip':'ffn'},
        additional_sources={HELPER:['dilate']},
        legend=['First dimension encodes folded dilation phases in this implementation; selectedN1, not an arbitrary batch claim.',
                'Filter/gate/residual/skip ModuleList index1 are four independent weight families.',
                'Two top outputs are loop-state boundaries; the model output head is excluded.'])


def validate_ir(ir):
    return verify(ir,'wavenet_block',{
        'wave.dilate':{'dilation':2,'init_dilation':1,'shape':'[2,32,9]'},
        'wave.filter_conv':{'parameter':'filter_convs.1','dilation':1,'bias':False},
        'wave.gate_conv':{'parameter':'gate_convs.1','dilation':1,'bias':False},
        'wave.res_crop':{'crop_side':'left','crop_size':1},
        'wave.undilate':{'dilation':1,'init_dilation':2,'shape':'[1,32,16]'},
        'wave.output_x':{'actual_return':False},'wave.output_skip':{'actual_return':False}},
        [('wave.filter_act','wave.product','filter'),('wave.gate_act','wave.product','gate'),('wave.product','wave.skip','in'),
         ('wave.dilate','wave.res_crop','residual'),('wave.res_crop','wave.res_add','retained'),('wave.skip_crop','wave.skip_add','previous_skip')])
