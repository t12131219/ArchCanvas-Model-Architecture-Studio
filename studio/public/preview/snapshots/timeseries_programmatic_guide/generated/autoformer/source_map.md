# Autoformer：逐节点源码映射

每个图框的 `E###` 对应下表中的源码范围；SVG 悬停可查看来源。节点 ID 跨视图稳定。展开接口通过 IR 边递归绑定到实际内部算子；隐藏的整个模块才投影到最近可见祖先。
这些是人工审阅适配器的绑定，不是模型执行轨迹。完整片段及文件摘要见 `source_evidence.json`。

| 证据 ID | 文件与符号 | 行号 |
|---|---|---|
| E003 | [Autoformer-main/layers/AutoCorrelation.py](sources/Autoformer-main/layers/AutoCorrelation.py) · `AutoCorrelation.time_delay_agg_training` | 21–43 |
| E002 | [Autoformer-main/layers/AutoCorrelation.py](sources/Autoformer-main/layers/AutoCorrelation.py) · `AutoCorrelation.time_delay_agg_inference` | 45–71 |
| E001 | [Autoformer-main/layers/AutoCorrelation.py](sources/Autoformer-main/layers/AutoCorrelation.py) · `AutoCorrelation.forward` | 98–124 |
| E004 | [Autoformer-main/layers/AutoCorrelation.py](sources/Autoformer-main/layers/AutoCorrelation.py) · `AutoCorrelationLayer.__init__` | 128–140 |
| E005 | [Autoformer-main/layers/AutoCorrelation.py](sources/Autoformer-main/layers/AutoCorrelation.py) · `AutoCorrelationLayer.forward` | 142–159 |
| E011 | [Autoformer-main/layers/Autoformer_EncDec.py](sources/Autoformer-main/layers/Autoformer_EncDec.py) · `my_Layernorm.forward` | 14–17 |
| E010 | [Autoformer-main/layers/Autoformer_EncDec.py](sources/Autoformer-main/layers/Autoformer_EncDec.py) · `moving_avg.forward` | 29–36 |
| E012 | [Autoformer-main/layers/Autoformer_EncDec.py](sources/Autoformer-main/layers/Autoformer_EncDec.py) · `series_decomp.forward` | 47–50 |
| E009 | [Autoformer-main/layers/Autoformer_EncDec.py](sources/Autoformer-main/layers/Autoformer_EncDec.py) · `EncoderLayer.forward` | 68–79 |
| E008 | [Autoformer-main/layers/Autoformer_EncDec.py](sources/Autoformer-main/layers/Autoformer_EncDec.py) · `Encoder.forward` | 92–109 |
| E007 | [Autoformer-main/layers/Autoformer_EncDec.py](sources/Autoformer-main/layers/Autoformer_EncDec.py) · `DecoderLayer.forward` | 132–150 |
| E006 | [Autoformer-main/layers/Autoformer_EncDec.py](sources/Autoformer-main/layers/Autoformer_EncDec.py) · `Decoder.forward` | 163–173 |
| E016 | [Autoformer-main/layers/Embed.py](sources/Autoformer-main/layers/Embed.py) · `TokenEmbedding.forward` | 59–61 |
| E015 | [Autoformer-main/layers/Embed.py](sources/Autoformer-main/layers/Embed.py) · `TimeFeatureEmbedding.forward` | 122–123 |
| E013 | [Autoformer-main/layers/Embed.py](sources/Autoformer-main/layers/Embed.py) · `DataEmbedding_wo_pos.__init__` | 143–151 |
| E014 | [Autoformer-main/layers/Embed.py](sources/Autoformer-main/layers/Embed.py) · `DataEmbedding_wo_pos.forward` | 153–155 |
| E017 | [Autoformer-main/models/Autoformer.py](sources/Autoformer-main/models/Autoformer.py) · `Model.__init__` | 13–72 |
| E018 | [Autoformer-main/models/Autoformer.py](sources/Autoformer-main/models/Autoformer.py) · `Model.forward` | 74–96 |

| 节点 ID | 图中名称 | 静态 shape | 源码证据 | 参数身份 / 实例族 |
|---|---|---|---|---|
| af_model | Autoformer forecasting | B,P,C | E018 | — |
| af_input | Input time series | x_enc: B,L,C | E018 | — |
| af_prepare | Encoder + decoder preparation | (memory, seasonal, trend) | E018 | — |
| af_encoder | Encoder memory path | memory: B,L,D | E018,E008 | — |
| af_enc_embedding | Embedding (no PE) | B,L,D | E017,E014 | — |
| af_enc_embedding_terms | Value + time features |  | E014 | — |
| af_enc_embedding_value | Circular Conv1d | B,L,D | E016 | enc_embedding.value_embedding.tokenConv |
| af_enc_embedding_time | Time feature Linear | B,L,D | E015 | enc_embedding.temporal_embedding.embed |
| af_enc_embedding_sum | Add + dropout | B,L,D | E014 | — |
| af_enc_layer | Encoder layer x N_e=2 | B,L,D | E017,E009 | encoder.attn_layers[i]; i=0,1; no tied weights; {'count': 2, 'index': 'i', 'independent_parameters': True} |
| af_enc_ac_residual | AutoCorr + residual | B,L,D | E009 | — |
| af_enc_ac | AutoCorrelation | B,L,D | E005,E001 | — |
| af_enc_ac_qkv | Q / K / V projections | (Q,K,V) | E005 | encoder.attn_layers[i].attention.{query_projection,key_projection,value_projection} |
| af_enc_ac_operands | Correlation and values |  | E001 | — |
| af_enc_ac_corr | Q/K period discovery |  | E001 | — |
| af_enc_ac_align | Align K to Q length | Lq=L | E001 | — |
| af_enc_ac_fft | rFFT(Q) * conj(rFFT(K)) | B,H,E,freq | E001 | — |
| af_enc_ac_irfft | irFFT: lag correlation | B,H,E,L | E001 | — |
| af_enc_ac_values | V: align + bypass FFT | B,H,E,L | E001 | — |
| af_enc_ac_delay | Top-k delay aggregation | B,H,E,L | E002 | — |
| af_enc_ac_out | Merge heads + Linear | B,L,D | E005 | encoder.attn_layers[i].attention.out_projection |
| af_enc_ac_dropout | Dropout | B,L,D | E009 | — |
| af_enc_ac_add | Residual add | B,L,D | E009 | — |
| af_enc_decomp1 | Decomposition 1 | seasonal: B,L,D | E009,E012 | — |
| af_enc_decomp1_mean | Moving average | B,L,D | E010 | — |
| af_enc_decomp1_split | Seasonal = x - mean | seasonal: B,L,D | E012 | — |
| af_enc_ffn | Pointwise FFN + residual | B,L,D | E009 | — |
| af_enc_ffn_conv1 | Conv1d: D -> F | B,F,L | E009 | encoder.attn_layers[i].conv1 |
| af_enc_ffn_act | GELU + dropout | B,F,L | E009 | — |
| af_enc_ffn_conv2 | Conv1d: F -> D | B,L,D | E009 | encoder.attn_layers[i].conv2 |
| af_enc_ffn_add | Residual add | B,L,D | E009 | — |
| af_enc_decomp2 | Decomposition 2 | seasonal: B,L,D | E009,E012 | — |
| af_enc_decomp2_mean | Moving average | B,L,D | E010 | — |
| af_enc_decomp2_split | Seasonal = x - mean | seasonal: B,L,D | E012 | — |
| af_memory | Seasonal LayerNorm | B,L,D | E011 | — |
| af_memory_ln | LayerNorm over D | B,L,D | E011 | encoder.norm.layernorm |
| af_memory_center | Subtract time mean | B,L,D | E011 | — |
| af_decoder_init | Decoder initialization from x_enc | (seasonal[B,T,D], trend[B,T,C]) | E018 | — |
| af_init_decomp | Decompose raw input | (seasonal[B,L,C], trend[B,L,C]) | E018,E012 | — |
| af_init_states | Seasonal and trend seeds | (seasonal[B,T,D], trend[B,T,C]) | E018 | — |
| af_seasonal_seed | Seasonal seed + embedding | B,T,D | E018 | — |
| af_seasonal_init | Last label + future zeros | B,T,C | E018 | — |
| af_dec_embedding | Embedding (no PE) | B,T,D | E017,E014 | — |
| af_dec_embedding_terms | Value + time features |  | E014 | — |
| af_dec_embedding_value | Circular Conv1d | B,T,D | E016 | dec_embedding.value_embedding.tokenConv |
| af_dec_embedding_time | Time feature Linear | B,T,D | E015 | dec_embedding.temporal_embedding.embed |
| af_dec_embedding_sum | Add + dropout | B,T,D | E014 | — |
| af_trend_init | Last trend + input mean | B,T,C | E018 | — |
| af_dec_layer | Decoder layer x N_d=1 | (seasonal[B,T,D], trend[B,T,C]) | E017,E007,E006 | decoder.layers[0]; self/cross use distinct weights |
| af_dec_self_residual | AutoCorr + residual | B,T,D | E007 | — |
| af_dec_self | AutoCorrelation | B,T,D | E005,E001 | — |
| af_dec_self_qkv | Q / K / V projections | (Q,K,V) | E005 | decoder.layers[0].self_attention.{query_projection,key_projection,value_projection} |
| af_dec_self_operands | Correlation and values |  | E001 | — |
| af_dec_self_corr | Q/K period discovery |  | E001 | — |
| af_dec_self_align | Align K to Q length | Lq=T | E001 | — |
| af_dec_self_fft | rFFT(Q) * conj(rFFT(K)) | B,H,E,freq | E001 | — |
| af_dec_self_irfft | irFFT: lag correlation | B,H,E,T | E001 | — |
| af_dec_self_values | V: align + bypass FFT | B,H,E,T | E001 | — |
| af_dec_self_delay | Top-k delay aggregation | B,H,E,T | E002 | — |
| af_dec_self_out | Merge heads + Linear | B,T,D | E005 | decoder.layers[0].self_attention.out_projection |
| af_dec_self_dropout | Dropout | B,T,D | E007 | — |
| af_dec_self_add | Residual add | B,T,D | E007 | — |
| af_dec_decomp1 | Decomposition 1 | seasonal: B,T,D | E007,E012 | — |
| af_dec_decomp1_mean | Moving average | B,T,D | E010 | — |
| af_dec_decomp1_split | Seasonal = x - mean | seasonal: B,T,D | E012 | — |
| af_dec_cross_residual | Cross + residual | B,T,D | E007 | — |
| af_dec_cross | Cross AutoCorrelation | B,T,D | E005,E001 | — |
| af_dec_cross_qkv | Q / K / V projections | Q: decoder; K,V: memory | E005 | decoder.layers[0].cross_attention.{query_projection,key_projection,value_projection} |
| af_dec_cross_operands | Correlation and values |  | E001 | — |
| af_dec_cross_corr | Q/K period discovery |  | E001 | — |
| af_dec_cross_align | Align K to Q length | Lq=T | E001 | — |
| af_dec_cross_fft | rFFT(Q) * conj(rFFT(K)) | B,H,E,freq | E001 | — |
| af_dec_cross_irfft | irFFT: lag correlation | B,H,E,T | E001 | — |
| af_dec_cross_values | V: align + bypass FFT | B,H,E,T | E001 | — |
| af_dec_cross_delay | Top-k delay aggregation | B,H,E,T | E002 | — |
| af_dec_cross_out | Merge heads + Linear | B,T,D | E005 | decoder.layers[0].cross_attention.out_projection |
| af_dec_cross_dropout | Dropout | B,T,D | E007 | — |
| af_dec_cross_add | Residual add | B,T,D | E007 | — |
| af_dec_decomp2 | Decomposition 2 | seasonal: B,T,D | E007,E012 | — |
| af_dec_decomp2_mean | Moving average | B,T,D | E010 | — |
| af_dec_decomp2_split | Seasonal = x - mean | seasonal: B,T,D | E012 | — |
| af_dec_ffn | Pointwise FFN + residual | B,T,D | E007 | — |
| af_dec_ffn_conv1 | Conv1d: D -> F | B,F,T | E007 | decoder.layers[0].conv1 |
| af_dec_ffn_act | GELU + dropout | B,F,T | E007 | — |
| af_dec_ffn_conv2 | Conv1d: F -> D | B,T,D | E007 | decoder.layers[0].conv2 |
| af_dec_ffn_add | Residual add | B,T,D | E007 | — |
| af_dec_decomp3 | Decomposition 3 | seasonal: B,T,D | E007,E012 | — |
| af_dec_decomp3_mean | Moving average | B,T,D | E010 | — |
| af_dec_decomp3_split | Seasonal = x - mean | seasonal: B,T,D | E012 | — |
| af_trend_update | Trend update; carry seasonal | (seasonal[B,T,D], trend[B,T,C]) | E007,E006 | decoder.layers[0].projection |
| af_final_parts | Seasonal and trend outputs | (seasonal[B,T,C], trend[B,T,C]) | E006 | — |
| af_seasonal_output | Seasonal forecast | B,T,C | E006 | — |
| af_dec_norm | Seasonal LayerNorm | B,T,D | E011 | — |
| af_dec_norm_ln | LayerNorm over D | B,T,D | E011 | decoder.norm.layernorm |
| af_dec_norm_center | Subtract time mean | B,T,D | E011 | — |
| af_seasonal_projection | Linear: D -> C | B,T,C | E017,E006 | decoder.projection |
| af_trend_output | Accumulated trend | B,T,C | E006 | — |
| af_sum | Seasonal + trend | B,T,C | E018 | — |
| af_slice | Keep last pred_len | B,P,C | E018 | — |
| af_output | Forecast | B,P,C | E018 | — |
| af_x_mark_enc | Encoder time marks | B,L,4 | E018 | — |
| af_x_mark_dec | Decoder time marks | B,T,4 | E018 | — |

## 参考图修正

- Replace the reference image's ordinary Add & Norm blocks by residual + progressive series decomposition.
- Remove positional encoding: it is constructed in DataEmbedding_wo_pos but unused by forward.
- Replace Linear token embedding with kernel-3 circular Conv1d; preserve the distinct time-feature Linear.
- Remove causal-mask claims for decoder AutoCorrelation; the supplied implementation does not apply masks.
- Move raw-series decomposition to decoder initialization; encoder consumes raw x_enc through embedding.
- Draw encoder self correlation before its FFN, and decoder self -> cross -> FFN in actual source order.
- Show three decoder trend contributions and accumulation separately from the seasonal forecast projection.
- Replace a right-shifted x_dec value path by x_enc-derived seasonal/trend initialization.

## 模型事实

- Reviewed handwritten adapter; AST evidence does not automatically recover semantics.
- DataEmbedding_wo_pos sums a circular Conv1d value embedding and time feature embedding; no positional encoding.
- Encoder has two residual-plus-decomposition stages per layer; discarded trends never feed the decoder.
- Decoder uses self AutoCorrelation, cross AutoCorrelation, and FFN with three decomposition stages.
- Cross Q is decoder seasonal state; cross K/V are final normalized encoder memory.
- Decoder trend1/2/3 are summed, Conv1d-projected to C, and added to the carried raw-channel trend.
- Autocorrelation uses FFT lag correlation and delay-weighted V aggregation, not dot-product attention.
- Inference picks delays per sample; training uses batch-shared delay indices and a different aggregation method.
- mask_flag and attn_mask are accepted but not applied in the supplied AutoCorrelation.forward.
- Forecast is the final pred_len slice of seasonal projection plus accumulated trend.
- Repeated encoder layers are distinct modules with independent parameters; same color does not mean weight sharing.
