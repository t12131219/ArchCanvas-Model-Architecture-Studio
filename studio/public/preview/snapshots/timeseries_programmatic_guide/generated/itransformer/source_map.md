# iTransformer：逐节点源码映射

每个图框的 `E###` 对应下表中的源码范围；SVG 悬停可查看来源。节点 ID 跨视图稳定。展开接口通过 IR 边递归绑定到实际内部算子；隐藏的整个模块才投影到最近可见祖先。
这些是人工审阅适配器的绑定，不是模型执行轨迹。完整片段及文件摘要见 `source_evidence.json`。

| 证据 ID | 文件与符号 | 行号 |
|---|---|---|
| E001 | [iTransformer/data_provider/data_factory.py](sources/iTransformer/data_provider/data_factory.py) · `data_provider` | 16–54 |
| E002 | [iTransformer/data_provider/data_loader.py](sources/iTransformer/data_provider/data_loader.py) · `Dataset_ETT_hour.__read_data__` | 42–79 |
| E003 | [iTransformer/layers/Embed.py](sources/iTransformer/layers/Embed.py) · `DataEmbedding_inverted` | 127–142 |
| E004 | [iTransformer/layers/Embed.py](sources/iTransformer/layers/Embed.py) · `DataEmbedding_inverted.__init__` | 128–131 |
| E005 | [iTransformer/layers/Embed.py](sources/iTransformer/layers/Embed.py) · `DataEmbedding_inverted.forward` | 133–142 |
| E009 | [iTransformer/layers/SelfAttention_Family.py](sources/iTransformer/layers/SelfAttention_Family.py) · `FullAttention` | 134–161 |
| E010 | [iTransformer/layers/SelfAttention_Family.py](sources/iTransformer/layers/SelfAttention_Family.py) · `FullAttention.__init__` | 135–140 |
| E011 | [iTransformer/layers/SelfAttention_Family.py](sources/iTransformer/layers/SelfAttention_Family.py) · `FullAttention.forward` | 142–161 |
| E006 | [iTransformer/layers/SelfAttention_Family.py](sources/iTransformer/layers/SelfAttention_Family.py) · `AttentionLayer` | 266–300 |
| E007 | [iTransformer/layers/SelfAttention_Family.py](sources/iTransformer/layers/SelfAttention_Family.py) · `AttentionLayer.__init__` | 267–279 |
| E008 | [iTransformer/layers/SelfAttention_Family.py](sources/iTransformer/layers/SelfAttention_Family.py) · `AttentionLayer.forward` | 281–300 |
| E015 | [iTransformer/layers/Transformer_EncDec.py](sources/iTransformer/layers/Transformer_EncDec.py) · `EncoderLayer` | 26–50 |
| E016 | [iTransformer/layers/Transformer_EncDec.py](sources/iTransformer/layers/Transformer_EncDec.py) · `EncoderLayer.__init__` | 27–36 |
| E017 | [iTransformer/layers/Transformer_EncDec.py](sources/iTransformer/layers/Transformer_EncDec.py) · `EncoderLayer.forward` | 38–50 |
| E012 | [iTransformer/layers/Transformer_EncDec.py](sources/iTransformer/layers/Transformer_EncDec.py) · `Encoder` | 53–79 |
| E013 | [iTransformer/layers/Transformer_EncDec.py](sources/iTransformer/layers/Transformer_EncDec.py) · `Encoder.__init__` | 54–58 |
| E014 | [iTransformer/layers/Transformer_EncDec.py](sources/iTransformer/layers/Transformer_EncDec.py) · `Encoder.forward` | 60–79 |
| E018 | [iTransformer/model/iTransformer.py](sources/iTransformer/model/iTransformer.py) · `Model` | 10–80 |
| E019 | [iTransformer/model/iTransformer.py](sources/iTransformer/model/iTransformer.py) · `Model.__init__` | 15–40 |
| E020 | [iTransformer/model/iTransformer.py](sources/iTransformer/model/iTransformer.py) · `Model.forecast` | 42–71 |
| E021 | [iTransformer/model/iTransformer.py](sources/iTransformer/model/iTransformer.py) · `Model.forward` | 74–80 |
| E022 | [iTransformer/utils/timefeatures.py](sources/iTransformer/utils/timefeatures.py) · `time_features_from_frequency_str` | 90–144 |

| 节点 ID | 图中名称 | 静态 shape | 源码证据 | 参数身份 / 实例族 |
|---|---|---|---|---|
| it.model | iTransformer | [B,P,N] | E018 | — |
| it.input | Input time series | [B,L,N] | E020 | — |
| it.normalize | Series normalize | [B,L,N] | E020 | — |
| it.embedding | Inverted embedding | [B,T,D] | E004,E005,E020 | — |
| it.invert | Invert axes | [B,N,L] | E005 | — |
| it.concat | Append time tokens | [B,T,L] | E005 | — |
| it.embed_linear | Temporal projection | [B,T,D] | E004,E005 | enc_embedding.value_embedding |
| it.embed_dropout | Embedding dropout | [B,T,D] | E005 | — |
| it.encoder | Encoder x 2 | [B,T,D] | E019,E014 | — |
| it.enc1 | Encoder layer 1 | [B,T,D] | E019,E017 | encoder.attn_layers.0 |
| it.enc1.attention_residual | Attention + residual | [B,T,D] | E017 | — |
| it.enc1.attention | Full self-attention | [B,T,D] | E019,E008,E011 | — |
| it.enc1.attention.operands | Weights / values | (A,V) | E008,E011 | — |
| it.enc1.attention.weights | QK -> weights | A: [B,H,T,T] | E011 | — |
| it.enc1.attention.qk | Q / K projections | (Q,K) | E007,E008 | — |
| it.enc1.attention.q | Q | [B,T,H,d] | E007,E008 | — |
| it.enc1.attention.q.linear | Linear Q | [B,T,D] | E007,E008 | encoder.attn_layers.0.attention.query_projection |
| it.enc1.attention.q.heads | Split heads | [B,T,H,d] | E008 | — |
| it.enc1.attention.k | K | [B,T,H,d] | E007,E008 | — |
| it.enc1.attention.k.linear | Linear K | [B,T,D] | E007,E008 | encoder.attn_layers.0.attention.key_projection |
| it.enc1.attention.k.heads | Split heads | [B,T,H,d] | E008 | — |
| it.enc1.attention.scores | QK contraction | [B,H,T,T] | E011 | — |
| it.enc1.attention.scale | Scale scores | [B,H,T,T] | E011 | — |
| it.enc1.attention.softmax | Softmax | [B,H,T,T] | E011 | — |
| it.enc1.attention.attn_drop | Attention dropout | [B,H,T,T] | E011 | — |
| it.enc1.attention.v | V | [B,T,H,d] | E007,E008 | — |
| it.enc1.attention.v.linear | Linear V | [B,T,D] | E007,E008 | encoder.attn_layers.0.attention.value_projection |
| it.enc1.attention.v.heads | Split heads | [B,T,H,d] | E008 | — |
| it.enc1.attention.av | A times V | [B,T,H,d] | E011 | — |
| it.enc1.attention.merge | Merge heads | [B,T,D] | E008 | — |
| it.enc1.attention.out | Output projection | [B,T,D] | E007,E008 | encoder.attn_layers.0.attention.out_projection |
| it.enc1.attention_dropout | Output dropout | [B,T,D] | E017 | — |
| it.enc1.add1 | Add residual | [B,T,D] | E017 | — |
| it.enc1.norm1 | LayerNorm 1 | [B,T,D] | E016,E017 | encoder.attn_layers.0.norm1 |
| it.enc1.ffn_residual | FFN + residual | [B,T,D] | E017 | — |
| it.enc1.ffn | Pointwise FFN | [B,T,D] | E016,E017 | — |
| it.enc1.ffn_transpose_in | Transpose | [B,D,T] | E017 | — |
| it.enc1.conv1 | Conv1d D -> F | [B,F,T] | E016,E017 | encoder.attn_layers.0.conv1 |
| it.enc1.gelu | GELU | [B,F,T] | E016,E017 | — |
| it.enc1.ffn_dropout1 | Dropout | [B,F,T] | E017 | — |
| it.enc1.conv2 | Conv1d F -> D | [B,D,T] | E016,E017 | encoder.attn_layers.0.conv2 |
| it.enc1.ffn_transpose_out | Transpose | [B,T,D] | E017 | — |
| it.enc1.ffn_dropout2 | Dropout | [B,T,D] | E017 | — |
| it.enc1.add2 | Add residual | [B,T,D] | E017 | — |
| it.enc1.norm2 | LayerNorm 2 | [B,T,D] | E016,E017 | encoder.attn_layers.0.norm2 |
| it.enc2 | Encoder layer 2 | [B,T,D] | E019,E017 | encoder.attn_layers.1 |
| it.enc2.attention_residual | Attention + residual | [B,T,D] | E017 | — |
| it.enc2.attention | Full self-attention | [B,T,D] | E019,E008,E011 | — |
| it.enc2.attention.operands | Weights / values | (A,V) | E008,E011 | — |
| it.enc2.attention.weights | QK -> weights | A: [B,H,T,T] | E011 | — |
| it.enc2.attention.qk | Q / K projections | (Q,K) | E007,E008 | — |
| it.enc2.attention.q | Q | [B,T,H,d] | E007,E008 | — |
| it.enc2.attention.q.linear | Linear Q | [B,T,D] | E007,E008 | encoder.attn_layers.1.attention.query_projection |
| it.enc2.attention.q.heads | Split heads | [B,T,H,d] | E008 | — |
| it.enc2.attention.k | K | [B,T,H,d] | E007,E008 | — |
| it.enc2.attention.k.linear | Linear K | [B,T,D] | E007,E008 | encoder.attn_layers.1.attention.key_projection |
| it.enc2.attention.k.heads | Split heads | [B,T,H,d] | E008 | — |
| it.enc2.attention.scores | QK contraction | [B,H,T,T] | E011 | — |
| it.enc2.attention.scale | Scale scores | [B,H,T,T] | E011 | — |
| it.enc2.attention.softmax | Softmax | [B,H,T,T] | E011 | — |
| it.enc2.attention.attn_drop | Attention dropout | [B,H,T,T] | E011 | — |
| it.enc2.attention.v | V | [B,T,H,d] | E007,E008 | — |
| it.enc2.attention.v.linear | Linear V | [B,T,D] | E007,E008 | encoder.attn_layers.1.attention.value_projection |
| it.enc2.attention.v.heads | Split heads | [B,T,H,d] | E008 | — |
| it.enc2.attention.av | A times V | [B,T,H,d] | E011 | — |
| it.enc2.attention.merge | Merge heads | [B,T,D] | E008 | — |
| it.enc2.attention.out | Output projection | [B,T,D] | E007,E008 | encoder.attn_layers.1.attention.out_projection |
| it.enc2.attention_dropout | Output dropout | [B,T,D] | E017 | — |
| it.enc2.add1 | Add residual | [B,T,D] | E017 | — |
| it.enc2.norm1 | LayerNorm 1 | [B,T,D] | E016,E017 | encoder.attn_layers.1.norm1 |
| it.enc2.ffn_residual | FFN + residual | [B,T,D] | E017 | — |
| it.enc2.ffn | Pointwise FFN | [B,T,D] | E016,E017 | — |
| it.enc2.ffn_transpose_in | Transpose | [B,D,T] | E017 | — |
| it.enc2.conv1 | Conv1d D -> F | [B,F,T] | E016,E017 | encoder.attn_layers.1.conv1 |
| it.enc2.gelu | GELU | [B,F,T] | E016,E017 | — |
| it.enc2.ffn_dropout1 | Dropout | [B,F,T] | E017 | — |
| it.enc2.conv2 | Conv1d F -> D | [B,D,T] | E016,E017 | encoder.attn_layers.1.conv2 |
| it.enc2.ffn_transpose_out | Transpose | [B,T,D] | E017 | — |
| it.enc2.ffn_dropout2 | Dropout | [B,T,D] | E017 | — |
| it.enc2.add2 | Add residual | [B,T,D] | E017 | — |
| it.enc2.norm2 | LayerNorm 2 | [B,T,D] | E016,E017 | encoder.attn_layers.1.norm2 |
| it.encoder_norm | Final LayerNorm | [B,T,D] | E019,E014 | encoder.norm |
| it.head | Forecast projection | [B,P,N] | E020 | — |
| it.project | Linear D -> P | [B,T,P] | E019,E020 | projector |
| it.restore | Restore time axis | [B,P,T] | E020 | — |
| it.select | Keep N variates | [B,P,N] | E020 | — |
| it.denormalize | Restore series scale | [B,P,N] | E020 | — |
| it.output | Forecast | [B,96,7] | E021 | — |
| it.marks | Time covariates | [B,C,L] | E020,E005 | — |
| it.marks_input | Time features | [B,L,C] | E020 | — |
| it.marks_invert | Invert time features | [B,C,L] | E005 | — |

## 参考图修正

- Reference figure reverses output permute/projector order; code projects D->P before permute.
- Reference figure omits covariate tokens, their output slicing, and series denormalization.
- Reference figure omits the encoder's final LayerNorm after the repeated layers.
- FFN labels now identify actual Conv1d(kernel=1) modules instead of only equivalent Linear operations.
- Attention internals now flow bottom-to-top; Q/K generate A while V reaches A*V independently.

## 模型事实

- One variate is one token; attention is over T=N+C tokens, not L time steps.
- Inverted embedding uses Linear(seq_len,d_model), with no positional embedding.
- Optional x_mark_enc is appended as additional tokens before the same Linear.
- FullAttention(False) and attn_mask=None mean no causal mask in this forecast path.
- Encoder FFN is two kernel=1 Conv1d operations; GELU comes from selected CLI defaults.
- Both encoder layers have independent parameters; final Encoder LayerNorm is additional.
- Projection precedes output permutation; covariate forecasts are then discarded.
- Input series statistics are reused for output denormalization; this is distinct from dataset scaling.
- x_dec and x_mark_dec are accepted by forecast but unused in this model.
