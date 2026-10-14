"""TimeMixer's selected avg-pyramid / channel-independent forecasting path."""
from spec import op, chain, parallel, ref

MODEL='TimeMixer-main/models/TimeMixer.py'
EMBED='TimeMixer-main/layers/Embed.py'
NORM='TimeMixer-main/layers/StandardNorm.py'
DECOMP='TimeMixer-main/layers/Autoformer_EncDec.py'


def build():
    r=lambda symbol:ref(MODEL,symbol)
    f=r('Model.forecast')
    edges=[]
    lengths=[96,48,24,12]
    # The pyramid retains each intermediate x_i; it is not merely its last pool output.
    pyramid_items=[op('tm.scale0','Retain original scale','tensor',r('Model.__multi_scale_process_inputs'),'[B,96,N]')]
    for i in range(1,4):
        pyramid_items.append(op(f'tm.pool{i}',f'AvgPool scale {i}','decomposition',
                                r('Model.__multi_scale_process_inputs'),f'[B,{lengths[i]},N]',
                                ['Permute -> AvgPool1d(2) -> back']))
    pyramid_items.append(op('tm.collect','Collect all four scales','tensor',r('Model.__multi_scale_process_inputs'),
                            'list x_i: [B,L_i,N]',['L_i = 96 / 2^i; i=0..3']))
    for i,src in enumerate(['tm.scale0','tm.pool1','tm.pool2']):
        edges.append(dict(src=src,dst='tm.collect',role='scale',label=f'x{i}',src_port='out',dst_port='side'))
    pyramid=chain('tm.pyramid','Multi-scale input pyramid',pyramid_items,r('Model.__multi_scale_process_inputs'),
                  'list[B,L_i,N]',expand=2)
    scale_inputs=[]
    for i,li in enumerate(lengths):
        scale_inputs.append(chain(f'tm.input_scale{i}',f'Scale {i}: L={li}',[
            op(f'tm.norm{i}','Normalize per variable','norm',[f,ref(NORM,'Normalize.forward'),ref(NORM,'Normalize._normalize')],
               f'[B,{li},N]',['Separate normalization per scale; affine=True'],param_identity=f'normalize_layers.{i}'),
            op(f'tm.fold{i}','Fold variables into batch','tensor',f,f'[BN,{li},1]',['B*N independent univariate series']),
            op(f'tm.embed{i}','Shared value embedding','embedding',ref(EMBED,'DataEmbedding_wo_pos.forward'),
               f'[BN,{li},D]',['Conv1d 1 -> D, kernel=3; dropout','x_mark_enc=None; no position added'],
               param_identity='enc_embedding.value_embedding.tokenConv'),
        ],[f,ref(EMBED,'TokenEmbedding.forward')],f'[BN,{li},D]',expand=2,input_selector=f'x[{i}]'))
    embedding=parallel('tm.embedding','Per-scale normalize + embed',scale_inputs,f,
                        'list[BN,L_i,D]',expand=1,dispatch=True)

    def mixing(block,season):
        kind='season' if season else 'trend'
        symbol='MultiScaleSeasonMixing' if season else 'MultiScaleTrendMixing'
        p=f'tm.pdm{block}.{kind}'
        indices=list(range(4)) if season else list(reversed(range(4)))
        first=indices[0]
        items=[op(p+'.initial',f'{kind.capitalize()} scale {first}','tensor',r(symbol+'.forward'),
                  f'[BN,D,{lengths[first]}]',['Retain this scale in output list'])]
        for step,(a,b) in enumerate(zip(indices,indices[1:])):
            dest=lengths[b];origin=lengths[a]
            items.append(chain(p+f'.step{step}',f'{a} -> {b}: temporal mixing',[
                op(p+f'.step{step}.linear1',f'Linear {origin} -> {dest}','linear',r(symbol+'.__init__'),
                   f'[BN,D,{dest}]',param_identity=f'pdm_blocks.{block-1}.mixing_multi_scale_{kind}.'+
                   ('down_sampling_layers' if season else 'up_sampling_layers')+f'.{step}.0'),
                op(p+f'.step{step}.gelu','GELU','activation',r(symbol+'.__init__'),f'[BN,D,{dest}]'),
                op(p+f'.step{step}.linear2',f'Linear {dest} -> {dest}','linear',r(symbol+'.__init__'),f'[BN,D,{dest}]',
                   param_identity=f'pdm_blocks.{block-1}.mixing_multi_scale_{kind}.'+
                   ('down_sampling_layers' if season else 'up_sampling_layers')+f'.{step}.2'),
                op(p+f'.step{step}.add',f'Add original {kind} scale {b}','mixing',r(symbol+'.forward'),
                   f'[BN,D,{dest}]',['Original component is a separate operand'], glyph_expression='out_low + out_low_res' if season else 'out_high + out_high_res'),
            ],[r(symbol+'.__init__'),r(symbol+'.forward')],f'[BN,D,{dest}]',expand=2))
        items.append(op(p+'.list','Return all mixed scales','tensor',r(symbol+'.forward'),
                        'list[BN,L_i,D]',['Restore [time,feature]; retain four scales'],
                        ordered_output_scales=[0,1,2,3],main_input_operand=f'scale[{indices[-1]}]'))
        # The collection reads every retained intermediate, not only the final
        # recurrence state. Trend's list.reverse restores scale order 0..3.
        retained=[p+'.initial',p+'.step0',p+'.step1']
        for source,scale in zip(retained,indices[:-1]):
            edges.append(dict(src=source,dst=p+'.list',role='retained_scale',label='',
                              src_port='out',dst_port=f'scale[{scale}]'))
        return chain(p,'Season: fine -> coarse' if season else 'Trend: coarse -> fine',items,
                     [r(symbol+'.__init__'),r(symbol+'.forward')],'list[BN,L_i,D]',expand=2,
                     input_selector=kind)

    def pdm(block,expand):
        p=f'tm.pdm{block}'
        return chain(p,f'PDM block {block}',[
            op(p+'.decomp','Per-scale series decomposition','decomposition',
               [r('PastDecomposableMixing.forward'),ref(DECOMP,'series_decomp.forward')],
               '(season_i, trend_i)',['Moving average 25; season=x-trend','No independent third residual component']),
            parallel(p+'.mix','Directional scale mixing',[mixing(block,True),mixing(block,False)],
                     r('PastDecomposableMixing.forward'),'(season_list, trend_list)',expand=2,dispatch=True),
            op(p+'.sum','Per-scale season + trend','mixing',r('PastDecomposableMixing.forward'),'list[BN,L_i,D]'),
            chain(p+'.out_cross','Shared feature MLP',[
                op(p+'.mlp1','Linear D -> F','linear',r('PastDecomposableMixing.__init__'),'list[BN,L_i,F]',
                   param_identity=f'pdm_blocks.{block-1}.out_cross_layer.0'),
                op(p+'.gelu','GELU','activation',r('PastDecomposableMixing.__init__'),'list[BN,L_i,F]'),
                op(p+'.mlp2','Linear F -> D','linear',r('PastDecomposableMixing.__init__'),'list[BN,L_i,D]',
                   param_identity=f'pdm_blocks.{block-1}.out_cross_layer.2'),
            ],r('PastDecomposableMixing.__init__'),'list[BN,L_i,D]',expand=2),
            op(p+'.add','Add original scale states','mixing',r('PastDecomposableMixing.forward'),
               'list[BN,L_i,D]',['ori + out_cross_layer(season + trend)','Trim to original scale lengths'], glyph_expression='ori + self.out_cross_layer(out)'),
        ],[r('PastDecomposableMixing.__init__'),r('PastDecomposableMixing.forward')],
           'list[BN,L_i,D]',expand=expand,residual=True,param_identity=f'pdm_blocks.{block-1}')

    # A recurrence step's target S_j/T_j also comes from the decomposition tuple.
    # These cross edges make the separate Add operand explicit.
    for block in (1,2):
        for kind in ('season','trend'):
            for step in range(3):
                scale=(step+1) if kind=='season' else (2-step)
                edges.append(dict(src=f'tm.pdm{block}.decomp',dst=f'tm.pdm{block}.{kind}.step{step}.add',
                                  role='component',label='',src_port=f'{kind}[{scale}]',dst_port='original_scale'))
    pdm_stack=chain('tm.pdm','Past Decomposable Mixing x 2',[pdm(1,1),pdm(2,3)],
                    [r('Model.__init__'),f],'list[BN,L_i,D]',expand=1)
    predictions=[]
    for i,li in enumerate(lengths):
        predictions.append(chain(f'tm.predict{i}',f'Scale {i} predictor',[
            op(f'tm.temporal{i}',f'Temporal Linear {li} -> H','linear',r('Model.future_multi_mixing'),
               '[BN,H,D]',['Permute -> predict_layers[i] -> back'],param_identity=f'predict_layers.{i}'),
            op(f'tm.project{i}','Shared Linear D -> 1','linear',[r('Model.__init__'),r('Model.future_multi_mixing')],
               '[BN,H,1]',param_identity='projection_layer'),
            op(f'tm.restore{i}','Restore variables','tensor',r('Model.future_multi_mixing'),
               '[B,H,N]',['reshape(B,N,H) -> permute(0,2,1)']),
        ],r('Model.future_multi_mixing'),'[B,H,N]',expand=2,input_selector=f'scale[{i}]'))
    fmm=parallel('tm.fmm','Future Multipredictor Mixing',predictions,r('Model.future_multi_mixing'),
                 'tuple of 4 forecasts',expand=1,dispatch=True)
    tree=chain('tm.model','TimeMixer',[
        op('tm.input','Input time series','input',f,'[B,96,7]'),
        pyramid,embedding,pdm_stack,fmm,
        op('tm.forecast_sum','Sum four scale forecasts','mixing',f,'[B,96,7]',['stack(dim=-1).sum(-1); no concat head']),
        op('tm.denorm','Restore original-scale statistics','norm',[f,ref(NORM,'Normalize._denormalize')],
           '[B,96,7]',['normalize_layers[0](forecast, denorm)','Inverse affine; multiply std, add mean']),
        op('tm.output','Forecast','output',r('Model.forward'),'[B,96,7]'),
    ],r('Model.forward'),'[B,L,N] -> [B,H,N]',expand=0)
    edges.append(dict(src='tm.norm0',dst='tm.denorm',role='statistics',label='scale 0 stats',src_port='statistics',dst_port='statistics'))
    return dict(key='timemixer',name='TimeMixer',archive='TimeMixer-main.zip',entry=r('Model'),tree=tree,extra_edges=edges,
                profile_label='avg pyramid / channel-independent',
                profile=dict(task_name='long_term_forecast',mode='eval',seq_len=96,label_len=0,pred_len=96,enc_in=7,c_out=7,d_model=16,d_ff=32,
                    e_layers=2,down_sampling_layers=3,down_sampling_window=2,down_sampling_method='avg',
                    channel_independence=1,use_norm=1,decomp_method='moving_avg',moving_avg=25,
                    use_future_temporal_feature=0,x_mark_enc=None,dropout=0.1,embed='timeF',freq='h',
                    config_source='ETTh1 first shell invocation + run.py defaults; explicitly choose x_mark_enc=None'),
                facts=[
                    'Multi-scale input pyramid precedes embedding; scale lengths are 96,48,24,12.',
                    'Channel independence reshapes each variable into the batch; embedding and projection are shared across scales and variables.',
                    'PDM decomposes each embedded scale into season and trend; there is no third independent residual component.',
                    'Season mixes fine to coarse; trend mixes coarse to fine, using learned temporal Linear/GELU/Linear maps.',
                    'Each PDM has independently parameterized scale transforms; the feature out_cross_layer is shared across scales within one block.',
                    'PDM.layer_norm and PDM.dropout are initialized but not used by its forward; they are not drawn.',
                    'FMM uses one independent Li->H temporal predictor per scale and a shared D->1 projection; forecasts are summed.',
                    'Denormalization reuses only normalize_layers[0] statistics, not an average of all scale statistics.',
                    'The second PDM is retained in IR and folded visually; no attention block exists on this path.'
                ],corrections=[
                    'Replace the reference short/mid/long Conv1d mixers with directional season/trend temporal MLPs.',
                    'Remove reference Add & Norm blocks; PDM forward does not call its initialized LayerNorm.',
                    'Replace X=Season+Trend+Residual with the actual two-output series decomposition.',
                    'Replace concat/fusion and flatten head with per-scale prediction, summation and denormalization.',
                    'No positional embedding is added by DataEmbedding_wo_pos.forward; embedding remains rank 3.',
                    'Multi-scale downsampling happens before normalization/embedding, not after a single embedding.'
                ],symbols={MODEL:['Model','Model.__init__','Model.forward','Model.forecast','Model.__multi_scale_process_inputs',
                    'Model.pre_enc','Model.future_multi_mixing','PastDecomposableMixing.__init__','PastDecomposableMixing.forward',
                    'MultiScaleSeasonMixing.__init__','MultiScaleSeasonMixing.forward','MultiScaleTrendMixing.__init__','MultiScaleTrendMixing.forward'],
                    EMBED:['DataEmbedding_wo_pos.__init__','DataEmbedding_wo_pos.forward','TokenEmbedding.forward'],
                    NORM:['Normalize.forward','Normalize._get_statistics','Normalize._normalize','Normalize._denormalize'],
                    DECOMP:['moving_avg.forward','series_decomp.forward']},
                config_files=['TimeMixer-main/run.py','TimeMixer-main/scripts/long_term_forecast/ETT_script/TimeMixer_ETTh1_unify.sh'],
                legend=['B batch; N=7 variables; BN=B*N','L_i=96/2^i; i=0..3; H=96','D=16; F=32; independent PDM blocks=2'])
