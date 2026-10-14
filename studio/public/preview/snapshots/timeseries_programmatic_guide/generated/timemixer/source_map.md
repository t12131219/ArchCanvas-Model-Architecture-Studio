# TimeMixer：逐节点源码映射

每个图框的 `E###` 对应下表中的源码范围；SVG 悬停可查看来源。节点 ID 跨视图稳定。展开接口通过 IR 边递归绑定到实际内部算子；隐藏的整个模块才投影到最近可见祖先。
这些是人工审阅适配器的绑定，不是模型执行轨迹。完整片段及文件摘要见 `source_evidence.json`。

| 证据 ID | 文件与符号 | 行号 |
|---|---|---|
| E001 | [TimeMixer-main/layers/Autoformer_EncDec.py](sources/TimeMixer-main/layers/Autoformer_EncDec.py) · `moving_avg.forward` | 31–38 |
| E002 | [TimeMixer-main/layers/Autoformer_EncDec.py](sources/TimeMixer-main/layers/Autoformer_EncDec.py) · `series_decomp.forward` | 50–53 |
| E005 | [TimeMixer-main/layers/Embed.py](sources/TimeMixer-main/layers/Embed.py) · `TokenEmbedding.forward` | 40–42 |
| E003 | [TimeMixer-main/layers/Embed.py](sources/TimeMixer-main/layers/Embed.py) · `DataEmbedding_wo_pos.__init__` | 177–185 |
| E004 | [TimeMixer-main/layers/Embed.py](sources/TimeMixer-main/layers/Embed.py) · `DataEmbedding_wo_pos.forward` | 187–194 |
| E009 | [TimeMixer-main/layers/StandardNorm.py](sources/TimeMixer-main/layers/StandardNorm.py) · `Normalize.forward` | 20–28 |
| E007 | [TimeMixer-main/layers/StandardNorm.py](sources/TimeMixer-main/layers/StandardNorm.py) · `Normalize._get_statistics` | 35–41 |
| E008 | [TimeMixer-main/layers/StandardNorm.py](sources/TimeMixer-main/layers/StandardNorm.py) · `Normalize._normalize` | 43–54 |
| E006 | [TimeMixer-main/layers/StandardNorm.py](sources/TimeMixer-main/layers/StandardNorm.py) · `Normalize._denormalize` | 56–67 |
| E017 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `MultiScaleSeasonMixing.__init__` | 33–52 |
| E018 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `MultiScaleSeasonMixing.forward` | 54–69 |
| E019 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `MultiScaleTrendMixing.__init__` | 77–94 |
| E020 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `MultiScaleTrendMixing.forward` | 96–114 |
| E021 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `PastDecomposableMixing.__init__` | 118–152 |
| E022 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `PastDecomposableMixing.forward` | 154–183 |
| E010 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `Model` | 186–527 |
| E011 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `Model.__init__` | 188–266 |
| E016 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `Model.pre_enc` | 276–286 |
| E012 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `Model.__multi_scale_process_inputs` | 288–329 |
| E013 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `Model.forecast` | 331–383 |
| E015 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `Model.future_multi_mixing` | 385–407 |
| E014 | [TimeMixer-main/models/TimeMixer.py](sources/TimeMixer-main/models/TimeMixer.py) · `Model.forward` | 513–527 |

| 节点 ID | 图中名称 | 静态 shape | 源码证据 | 参数身份 / 实例族 |
|---|---|---|---|---|
| tm.model | TimeMixer | [B,L,N] -> [B,H,N] | E014 | — |
| tm.input | Input time series | [B,96,7] | E013 | — |
| tm.pyramid | Multi-scale input pyramid | list[B,L_i,N] | E012 | — |
| tm.scale0 | Retain original scale | [B,96,N] | E012 | — |
| tm.pool1 | AvgPool scale 1 | [B,48,N] | E012 | — |
| tm.pool2 | AvgPool scale 2 | [B,24,N] | E012 | — |
| tm.pool3 | AvgPool scale 3 | [B,12,N] | E012 | — |
| tm.collect | Collect all four scales | list x_i: [B,L_i,N] | E012 | — |
| tm.embedding | Per-scale normalize + embed | list[BN,L_i,D] | E013 | — |
| tm.input_scale0 | Scale 0: L=96 | [BN,96,D] | E013,E005 | — |
| tm.norm0 | Normalize per variable | [B,96,N] | E013,E009,E008 | normalize_layers.0 |
| tm.fold0 | Fold variables into batch | [BN,96,1] | E013 | — |
| tm.embed0 | Shared value embedding | [BN,96,D] | E004 | enc_embedding.value_embedding.tokenConv |
| tm.input_scale1 | Scale 1: L=48 | [BN,48,D] | E013,E005 | — |
| tm.norm1 | Normalize per variable | [B,48,N] | E013,E009,E008 | normalize_layers.1 |
| tm.fold1 | Fold variables into batch | [BN,48,1] | E013 | — |
| tm.embed1 | Shared value embedding | [BN,48,D] | E004 | enc_embedding.value_embedding.tokenConv |
| tm.input_scale2 | Scale 2: L=24 | [BN,24,D] | E013,E005 | — |
| tm.norm2 | Normalize per variable | [B,24,N] | E013,E009,E008 | normalize_layers.2 |
| tm.fold2 | Fold variables into batch | [BN,24,1] | E013 | — |
| tm.embed2 | Shared value embedding | [BN,24,D] | E004 | enc_embedding.value_embedding.tokenConv |
| tm.input_scale3 | Scale 3: L=12 | [BN,12,D] | E013,E005 | — |
| tm.norm3 | Normalize per variable | [B,12,N] | E013,E009,E008 | normalize_layers.3 |
| tm.fold3 | Fold variables into batch | [BN,12,1] | E013 | — |
| tm.embed3 | Shared value embedding | [BN,12,D] | E004 | enc_embedding.value_embedding.tokenConv |
| tm.pdm | Past Decomposable Mixing x 2 | list[BN,L_i,D] | E011,E013 | — |
| tm.pdm1 | PDM block 1 | list[BN,L_i,D] | E021,E022 | pdm_blocks.0 |
| tm.pdm1.decomp | Per-scale series decomposition | (season_i, trend_i) | E022,E002 | — |
| tm.pdm1.mix | Directional scale mixing | (season_list, trend_list) | E022 | — |
| tm.pdm1.season | Season: fine -> coarse | list[BN,L_i,D] | E017,E018 | — |
| tm.pdm1.season.initial | Season scale 0 | [BN,D,96] | E018 | — |
| tm.pdm1.season.step0 | 0 -> 1: temporal mixing | [BN,D,48] | E017,E018 | — |
| tm.pdm1.season.step0.linear1 | Linear 96 -> 48 | [BN,D,48] | E017 | pdm_blocks.0.mixing_multi_scale_season.down_sampling_layers.0.0 |
| tm.pdm1.season.step0.gelu | GELU | [BN,D,48] | E017 | — |
| tm.pdm1.season.step0.linear2 | Linear 48 -> 48 | [BN,D,48] | E017 | pdm_blocks.0.mixing_multi_scale_season.down_sampling_layers.0.2 |
| tm.pdm1.season.step0.add | Add original season scale 1 | [BN,D,48] | E018 | — |
| tm.pdm1.season.step1 | 1 -> 2: temporal mixing | [BN,D,24] | E017,E018 | — |
| tm.pdm1.season.step1.linear1 | Linear 48 -> 24 | [BN,D,24] | E017 | pdm_blocks.0.mixing_multi_scale_season.down_sampling_layers.1.0 |
| tm.pdm1.season.step1.gelu | GELU | [BN,D,24] | E017 | — |
| tm.pdm1.season.step1.linear2 | Linear 24 -> 24 | [BN,D,24] | E017 | pdm_blocks.0.mixing_multi_scale_season.down_sampling_layers.1.2 |
| tm.pdm1.season.step1.add | Add original season scale 2 | [BN,D,24] | E018 | — |
| tm.pdm1.season.step2 | 2 -> 3: temporal mixing | [BN,D,12] | E017,E018 | — |
| tm.pdm1.season.step2.linear1 | Linear 24 -> 12 | [BN,D,12] | E017 | pdm_blocks.0.mixing_multi_scale_season.down_sampling_layers.2.0 |
| tm.pdm1.season.step2.gelu | GELU | [BN,D,12] | E017 | — |
| tm.pdm1.season.step2.linear2 | Linear 12 -> 12 | [BN,D,12] | E017 | pdm_blocks.0.mixing_multi_scale_season.down_sampling_layers.2.2 |
| tm.pdm1.season.step2.add | Add original season scale 3 | [BN,D,12] | E018 | — |
| tm.pdm1.season.list | Return all mixed scales | list[BN,L_i,D] | E018 | — |
| tm.pdm1.trend | Trend: coarse -> fine | list[BN,L_i,D] | E019,E020 | — |
| tm.pdm1.trend.initial | Trend scale 3 | [BN,D,12] | E020 | — |
| tm.pdm1.trend.step0 | 3 -> 2: temporal mixing | [BN,D,24] | E019,E020 | — |
| tm.pdm1.trend.step0.linear1 | Linear 12 -> 24 | [BN,D,24] | E019 | pdm_blocks.0.mixing_multi_scale_trend.up_sampling_layers.0.0 |
| tm.pdm1.trend.step0.gelu | GELU | [BN,D,24] | E019 | — |
| tm.pdm1.trend.step0.linear2 | Linear 24 -> 24 | [BN,D,24] | E019 | pdm_blocks.0.mixing_multi_scale_trend.up_sampling_layers.0.2 |
| tm.pdm1.trend.step0.add | Add original trend scale 2 | [BN,D,24] | E020 | — |
| tm.pdm1.trend.step1 | 2 -> 1: temporal mixing | [BN,D,48] | E019,E020 | — |
| tm.pdm1.trend.step1.linear1 | Linear 24 -> 48 | [BN,D,48] | E019 | pdm_blocks.0.mixing_multi_scale_trend.up_sampling_layers.1.0 |
| tm.pdm1.trend.step1.gelu | GELU | [BN,D,48] | E019 | — |
| tm.pdm1.trend.step1.linear2 | Linear 48 -> 48 | [BN,D,48] | E019 | pdm_blocks.0.mixing_multi_scale_trend.up_sampling_layers.1.2 |
| tm.pdm1.trend.step1.add | Add original trend scale 1 | [BN,D,48] | E020 | — |
| tm.pdm1.trend.step2 | 1 -> 0: temporal mixing | [BN,D,96] | E019,E020 | — |
| tm.pdm1.trend.step2.linear1 | Linear 48 -> 96 | [BN,D,96] | E019 | pdm_blocks.0.mixing_multi_scale_trend.up_sampling_layers.2.0 |
| tm.pdm1.trend.step2.gelu | GELU | [BN,D,96] | E019 | — |
| tm.pdm1.trend.step2.linear2 | Linear 96 -> 96 | [BN,D,96] | E019 | pdm_blocks.0.mixing_multi_scale_trend.up_sampling_layers.2.2 |
| tm.pdm1.trend.step2.add | Add original trend scale 0 | [BN,D,96] | E020 | — |
| tm.pdm1.trend.list | Return all mixed scales | list[BN,L_i,D] | E020 | — |
| tm.pdm1.sum | Per-scale season + trend | list[BN,L_i,D] | E022 | — |
| tm.pdm1.out_cross | Shared feature MLP | list[BN,L_i,D] | E021 | — |
| tm.pdm1.mlp1 | Linear D -> F | list[BN,L_i,F] | E021 | pdm_blocks.0.out_cross_layer.0 |
| tm.pdm1.gelu | GELU | list[BN,L_i,F] | E021 | — |
| tm.pdm1.mlp2 | Linear F -> D | list[BN,L_i,D] | E021 | pdm_blocks.0.out_cross_layer.2 |
| tm.pdm1.add | Add original scale states | list[BN,L_i,D] | E022 | — |
| tm.pdm2 | PDM block 2 | list[BN,L_i,D] | E021,E022 | pdm_blocks.1 |
| tm.pdm2.decomp | Per-scale series decomposition | (season_i, trend_i) | E022,E002 | — |
| tm.pdm2.mix | Directional scale mixing | (season_list, trend_list) | E022 | — |
| tm.pdm2.season | Season: fine -> coarse | list[BN,L_i,D] | E017,E018 | — |
| tm.pdm2.season.initial | Season scale 0 | [BN,D,96] | E018 | — |
| tm.pdm2.season.step0 | 0 -> 1: temporal mixing | [BN,D,48] | E017,E018 | — |
| tm.pdm2.season.step0.linear1 | Linear 96 -> 48 | [BN,D,48] | E017 | pdm_blocks.1.mixing_multi_scale_season.down_sampling_layers.0.0 |
| tm.pdm2.season.step0.gelu | GELU | [BN,D,48] | E017 | — |
| tm.pdm2.season.step0.linear2 | Linear 48 -> 48 | [BN,D,48] | E017 | pdm_blocks.1.mixing_multi_scale_season.down_sampling_layers.0.2 |
| tm.pdm2.season.step0.add | Add original season scale 1 | [BN,D,48] | E018 | — |
| tm.pdm2.season.step1 | 1 -> 2: temporal mixing | [BN,D,24] | E017,E018 | — |
| tm.pdm2.season.step1.linear1 | Linear 48 -> 24 | [BN,D,24] | E017 | pdm_blocks.1.mixing_multi_scale_season.down_sampling_layers.1.0 |
| tm.pdm2.season.step1.gelu | GELU | [BN,D,24] | E017 | — |
| tm.pdm2.season.step1.linear2 | Linear 24 -> 24 | [BN,D,24] | E017 | pdm_blocks.1.mixing_multi_scale_season.down_sampling_layers.1.2 |
| tm.pdm2.season.step1.add | Add original season scale 2 | [BN,D,24] | E018 | — |
| tm.pdm2.season.step2 | 2 -> 3: temporal mixing | [BN,D,12] | E017,E018 | — |
| tm.pdm2.season.step2.linear1 | Linear 24 -> 12 | [BN,D,12] | E017 | pdm_blocks.1.mixing_multi_scale_season.down_sampling_layers.2.0 |
| tm.pdm2.season.step2.gelu | GELU | [BN,D,12] | E017 | — |
| tm.pdm2.season.step2.linear2 | Linear 12 -> 12 | [BN,D,12] | E017 | pdm_blocks.1.mixing_multi_scale_season.down_sampling_layers.2.2 |
| tm.pdm2.season.step2.add | Add original season scale 3 | [BN,D,12] | E018 | — |
| tm.pdm2.season.list | Return all mixed scales | list[BN,L_i,D] | E018 | — |
| tm.pdm2.trend | Trend: coarse -> fine | list[BN,L_i,D] | E019,E020 | — |
| tm.pdm2.trend.initial | Trend scale 3 | [BN,D,12] | E020 | — |
| tm.pdm2.trend.step0 | 3 -> 2: temporal mixing | [BN,D,24] | E019,E020 | — |
| tm.pdm2.trend.step0.linear1 | Linear 12 -> 24 | [BN,D,24] | E019 | pdm_blocks.1.mixing_multi_scale_trend.up_sampling_layers.0.0 |
| tm.pdm2.trend.step0.gelu | GELU | [BN,D,24] | E019 | — |
| tm.pdm2.trend.step0.linear2 | Linear 24 -> 24 | [BN,D,24] | E019 | pdm_blocks.1.mixing_multi_scale_trend.up_sampling_layers.0.2 |
| tm.pdm2.trend.step0.add | Add original trend scale 2 | [BN,D,24] | E020 | — |
| tm.pdm2.trend.step1 | 2 -> 1: temporal mixing | [BN,D,48] | E019,E020 | — |
| tm.pdm2.trend.step1.linear1 | Linear 24 -> 48 | [BN,D,48] | E019 | pdm_blocks.1.mixing_multi_scale_trend.up_sampling_layers.1.0 |
| tm.pdm2.trend.step1.gelu | GELU | [BN,D,48] | E019 | — |
| tm.pdm2.trend.step1.linear2 | Linear 48 -> 48 | [BN,D,48] | E019 | pdm_blocks.1.mixing_multi_scale_trend.up_sampling_layers.1.2 |
| tm.pdm2.trend.step1.add | Add original trend scale 1 | [BN,D,48] | E020 | — |
| tm.pdm2.trend.step2 | 1 -> 0: temporal mixing | [BN,D,96] | E019,E020 | — |
| tm.pdm2.trend.step2.linear1 | Linear 48 -> 96 | [BN,D,96] | E019 | pdm_blocks.1.mixing_multi_scale_trend.up_sampling_layers.2.0 |
| tm.pdm2.trend.step2.gelu | GELU | [BN,D,96] | E019 | — |
| tm.pdm2.trend.step2.linear2 | Linear 96 -> 96 | [BN,D,96] | E019 | pdm_blocks.1.mixing_multi_scale_trend.up_sampling_layers.2.2 |
| tm.pdm2.trend.step2.add | Add original trend scale 0 | [BN,D,96] | E020 | — |
| tm.pdm2.trend.list | Return all mixed scales | list[BN,L_i,D] | E020 | — |
| tm.pdm2.sum | Per-scale season + trend | list[BN,L_i,D] | E022 | — |
| tm.pdm2.out_cross | Shared feature MLP | list[BN,L_i,D] | E021 | — |
| tm.pdm2.mlp1 | Linear D -> F | list[BN,L_i,F] | E021 | pdm_blocks.1.out_cross_layer.0 |
| tm.pdm2.gelu | GELU | list[BN,L_i,F] | E021 | — |
| tm.pdm2.mlp2 | Linear F -> D | list[BN,L_i,D] | E021 | pdm_blocks.1.out_cross_layer.2 |
| tm.pdm2.add | Add original scale states | list[BN,L_i,D] | E022 | — |
| tm.fmm | Future Multipredictor Mixing | tuple of 4 forecasts | E015 | — |
| tm.predict0 | Scale 0 predictor | [B,H,N] | E015 | — |
| tm.temporal0 | Temporal Linear 96 -> H | [BN,H,D] | E015 | predict_layers.0 |
| tm.project0 | Shared Linear D -> 1 | [BN,H,1] | E011,E015 | projection_layer |
| tm.restore0 | Restore variables | [B,H,N] | E015 | — |
| tm.predict1 | Scale 1 predictor | [B,H,N] | E015 | — |
| tm.temporal1 | Temporal Linear 48 -> H | [BN,H,D] | E015 | predict_layers.1 |
| tm.project1 | Shared Linear D -> 1 | [BN,H,1] | E011,E015 | projection_layer |
| tm.restore1 | Restore variables | [B,H,N] | E015 | — |
| tm.predict2 | Scale 2 predictor | [B,H,N] | E015 | — |
| tm.temporal2 | Temporal Linear 24 -> H | [BN,H,D] | E015 | predict_layers.2 |
| tm.project2 | Shared Linear D -> 1 | [BN,H,1] | E011,E015 | projection_layer |
| tm.restore2 | Restore variables | [B,H,N] | E015 | — |
| tm.predict3 | Scale 3 predictor | [B,H,N] | E015 | — |
| tm.temporal3 | Temporal Linear 12 -> H | [BN,H,D] | E015 | predict_layers.3 |
| tm.project3 | Shared Linear D -> 1 | [BN,H,1] | E011,E015 | projection_layer |
| tm.restore3 | Restore variables | [B,H,N] | E015 | — |
| tm.forecast_sum | Sum four scale forecasts | [B,96,7] | E013 | — |
| tm.denorm | Restore original-scale statistics | [B,96,7] | E013,E006 | — |
| tm.output | Forecast | [B,96,7] | E014 | — |

## 参考图修正

- Replace the reference short/mid/long Conv1d mixers with directional season/trend temporal MLPs.
- Remove reference Add & Norm blocks; PDM forward does not call its initialized LayerNorm.
- Replace X=Season+Trend+Residual with the actual two-output series decomposition.
- Replace concat/fusion and flatten head with per-scale prediction, summation and denormalization.
- No positional embedding is added by DataEmbedding_wo_pos.forward; embedding remains rank 3.
- Multi-scale downsampling happens before normalization/embedding, not after a single embedding.

## 模型事实

- Multi-scale input pyramid precedes embedding; scale lengths are 96,48,24,12.
- Channel independence reshapes each variable into the batch; embedding and projection are shared across scales and variables.
- PDM decomposes each embedded scale into season and trend; there is no third independent residual component.
- Season mixes fine to coarse; trend mixes coarse to fine, using learned temporal Linear/GELU/Linear maps.
- Each PDM has independently parameterized scale transforms; the feature out_cross_layer is shared across scales within one block.
- PDM.layer_norm and PDM.dropout are initialized but not used by its forward; they are not drawn.
- FMM uses one independent Li->H temporal predictor per scale and a shared D->1 projection; forecasts are summed.
- Denormalization reuses only normalize_layers[0] statistics, not an average of all scale statistics.
- The second PDM is retained in IR and folded visually; no attention block exists on this path.
