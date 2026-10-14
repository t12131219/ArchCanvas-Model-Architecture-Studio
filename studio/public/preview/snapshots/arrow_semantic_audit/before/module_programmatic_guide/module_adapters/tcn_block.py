"""TemporalBlock with two weight-normalized causal/chomp convolutions."""
from module_adapters.sequence_support import chain,op,graph,ref,link,make,verify
SOURCE='tcn-sequence/TCN/tcn.py'


def build():
    init=ref(SOURCE,'TemporalBlock.__init__');s=ref(SOURCE,'TemporalBlock.forward');crop=ref(SOURCE,'Chomp1d.forward');edges=[]
    stages=[]
    for i,ci in [(1,16),(2,32)]:
        prefix='tcn.stage'+str(i)
        stages.append(chain(prefix,'Causal Conv stage '+str(i),[
            op(prefix+'.conv','Weight-norm Conv3 / dilation2','conv1d',init,'[B,32,20]',
               parameter=f'conv{i}',parameters=[f'conv{i}.weight_g',f'conv{i}.weight_v',f'conv{i}.bias'],
               in_channels=ci,out_channels=32,kernel_size=3,stride=1,padding=4,dilation=2,bias=True,weight_norm=True),
            op(prefix+'.chomp','Chomp right4 + contiguous','tensor',[init,crop],'[B,32,16]',
               expression='x[:, :, :-self.chomp_size].contiguous()',chomp_size=4,crop_side='right'),
            op(prefix+'.relu','ReLU','relu',init,'[B,32,16]',inplace=False),
            op(prefix+'.drop','Dropout p=.2 / eval identity','dropout',init,'[B,32,16]',p=0.2,training=False),
        ],[init,s,crop],'[B,32,16]',expand=2))
    main=chain('tcn.main','net / two convolution stages',stages,[init,s],'[B,32,16]',expand=2)
    shortcut=op('tcn.projection','Residual Conv1 / 16 -> 32','conv1d',[init,s],'[B,32,16]',
                parameter='downsample',parameters=['downsample.weight','downsample.bias'],kernel_size=1,bias=True,in_channels=16,out_channels=32)
    add=op('tcn.add','Main out + projected residual','add',s,'[B,32,16]',expression='out + res')
    relu=op('tcn.relu','Final ReLU after residual sum','relu',[init,s],'[B,32,16]')
    body=graph('tcn.body','TemporalBlock / projected shortcut',[main,shortcut,add,relu],[init,s],'[B,16,16] -> [B,32,16]',expand=1,
               ranks=[['tcn.main','tcn.projection'],['tcn.add'],['tcn.relu']],rank_gap=64)
    inp=op('tcn.input','Input causal sequence','input',s,'[B,16,16]');out=op('tcn.output','TemporalBlock output','output',s,'[B,32,16]')
    for a,b,port in [('tcn.input','tcn.main','in'),('tcn.input','tcn.projection','input'),('tcn.main','tcn.add','main'),('tcn.projection','tcn.add','residual'),('tcn.add','tcn.relu','in'),('tcn.relu','tcn.output','output')]:edges.append(link(a,b,port))
    return make('tcn_block','TCN TemporalBlock / causal residual','TCN_TemporalBlock.md',
        'TemporalBlock16->32, k3,dilation2,padding4; no TCN stack or task head',SOURCE,
        ['Chomp1d.__init__','Chomp1d.forward','TemporalBlock.__init__','TemporalBlock.init_weights','TemporalBlock.forward'],[inp],body,[out],edges,
        dict(n_inputs=16,n_outputs=32,kernel_size=3,dilation=2,padding=4,stride=1,dropout=0.2,training=False,
             input_shape=['B',16,16],output_shape=['B',32,16],label='16->32 channels / k3,d2,p4 / right Chomp4 / eval example'),
        ['Two independent legacy weight_norm Conv1d instances expand length16 to20; each right Chomp4 restores16 and removes future-padding positions.',
         'Both stages execute Conv, Chomp.contiguous, ReLU, Dropout; the selected eval profile preserves the source Dropout nodes with identity behavior.',
         'Channel widths differ, so downsample is a learned1x1 Conv; identity shortcut is the source alternative when widths match.',
         'TemporalConvNet defines dilation=2**i and padding=(k-1)*dilation; this module selects a valid d2/k3 example, not a complete stack.',
         'weight_norm exposes weight_g and weight_v plus bias; this caller source does not expand the library reparameterization.'],
        ['Do not put dilation2 into a stride; do not crop left or crop before convolution.',
         'Do not add final Dropout after Add; final source operation is ReLU.'],
        roles={'tcn.main':'ffn','tcn.stage1':'ffn','tcn.stage2':'ffn'},
        legend=['B=batch; inputC16 -> outputC32; L16 -> convL20 -> right cropL16.',
                'Conv1/Conv2 parameter families are independent; shortcut has its own Conv1.',
                'Legacy weight_norm boundary retained; no upstream model execution.'])


def validate_ir(ir):
    fields={'tcn.projection':{'parameter':'downsample','kernel_size':1},'tcn.add':{'expression':'out + res'}}
    for i,ci in [(1,16),(2,32)]:
        prefix='tcn.stage'+str(i)
        fields[prefix+'.conv']={'padding':4,'dilation':2,'stride':1,'in_channels':ci,'weight_norm':True,
                               'parameters':[f'conv{i}.weight_g',f'conv{i}.weight_v',f'conv{i}.bias']}
        fields[prefix+'.chomp']={'chomp_size':4,'crop_side':'right','shape':'[B,32,16]'}
    return verify(ir,'tcn_block',fields,[('tcn.input','tcn.projection','input'),('tcn.main','tcn.add','main'),('tcn.projection','tcn.add','residual'),('tcn.add','tcn.relu','in')])
