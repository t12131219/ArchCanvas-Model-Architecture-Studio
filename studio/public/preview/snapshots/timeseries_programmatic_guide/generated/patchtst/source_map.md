# PatchTST：逐节点源码映射

每个图框的 `E###` 对应下表中的源码范围；SVG 悬停可查看来源。节点 ID 跨视图稳定。展开接口通过 IR 边递归绑定到实际内部算子；隐藏的整个模块才投影到最近可见祖先。
这些是人工审阅适配器的绑定，不是模型执行轨迹。完整片段及文件摘要见 `source_evidence.json`。

| 证据 ID | 文件与符号 | 行号 |
|---|---|---|
| E003 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `PatchTST_backbone` | 16–87 |
| E004 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `PatchTST_backbone.__init__` | 17–57 |
| E005 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `PatchTST_backbone.forward` | 60–82 |
| E001 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `Flatten_Head.__init__` | 91–108 |
| E002 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `Flatten_Head.forward` | 110–123 |
| E010 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `TSTiEncoder.__init__` | 129–154 |
| E011 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `TSTiEncoder.forward` | 157–172 |
| E006 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `TSTEncoder.__init__` | 178–187 |
| E007 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `TSTEncoder.forward` | 189–197 |
| E008 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `TSTEncoderLayer.__init__` | 202–234 |
| E009 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `TSTEncoderLayer.forward` | 237–267 |
| E012 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `_MultiheadAttention.__init__` | 273–295 |
| E013 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `_MultiheadAttention.forward` | 298–322 |
| E014 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `_ScaledDotProductAttention.__init__` | 330–336 |
| E015 | [PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_backbone.py) · `_ScaledDotProductAttention.forward` | 338–378 |
| E016 | [PatchTST/PatchTST_supervised/layers/PatchTST_layers.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_layers.py) · `get_activation_fn` | 16–20 |
| E018 | [PatchTST/PatchTST_supervised/layers/PatchTST_layers.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_layers.py) · `series_decomp.forward` | 52–55 |
| E017 | [PatchTST/PatchTST_supervised/layers/PatchTST_layers.py](sources/PatchTST/PatchTST_supervised/layers/PatchTST_layers.py) · `positional_encoding` | 96–121 |
| E019 | [PatchTST/PatchTST_supervised/layers/RevIN.py](sources/PatchTST/PatchTST_supervised/layers/RevIN.py) · `RevIN` | 4–61 |
| E023 | [PatchTST/PatchTST_supervised/layers/RevIN.py](sources/PatchTST/PatchTST_supervised/layers/RevIN.py) · `RevIN.forward` | 19–26 |
| E021 | [PatchTST/PatchTST_supervised/layers/RevIN.py](sources/PatchTST/PatchTST_supervised/layers/RevIN.py) · `RevIN._get_statistics` | 33–39 |
| E022 | [PatchTST/PatchTST_supervised/layers/RevIN.py](sources/PatchTST/PatchTST_supervised/layers/RevIN.py) · `RevIN._normalize` | 41–50 |
| E020 | [PatchTST/PatchTST_supervised/layers/RevIN.py](sources/PatchTST/PatchTST_supervised/layers/RevIN.py) · `RevIN._denormalize` | 52–61 |
| E024 | [PatchTST/PatchTST_supervised/models/PatchTST.py](sources/PatchTST/PatchTST_supervised/models/PatchTST.py) · `Model` | 15–92 |
| E025 | [PatchTST/PatchTST_supervised/models/PatchTST.py](sources/PatchTST/PatchTST_supervised/models/PatchTST.py) · `Model.__init__` | 16–77 |
| E026 | [PatchTST/PatchTST_supervised/models/PatchTST.py](sources/PatchTST/PatchTST_supervised/models/PatchTST.py) · `Model.forward` | 80–92 |

| 节点 ID | 图中名称 | 静态 shape | 源码证据 | 参数身份 / 实例族 |
|---|---|---|---|---|
| patchtst | PatchTST supervised forecast | (B,L,C) -> (B,H,C) | E026 | — |
| patch_input | Input time series | (B,L,C) | E026 | — |
| patch_to_channels | Permute to channels | (B,C,L) | E026 | — |
| patch_revin_norm | RevIN normalize | (B,C,L) | E005,E022 | — |
| patch_patching | End padding + patching | (B,C,p,P) | E004,E005 | — |
| patch_pad | Repeat endpoint s times | (B,C,L+s) | E004 | — |
| patch_unfold | Unfold temporal patches | (B,C,P,p) | E005 | — |
| patch_permute_patch | Permute for backbone | (B,C,p,P) | E005 | — |
| patch_embedding | Patch embedding + position | (BC,P,D) | E010,E011 | — |
| patch_projection | Patch Linear p -> D | (B,C,P,D) | E010,E011 | backbone.W_P |
| patch_fold_channels | Fold B and C | (BC,P,D) | E011 | — |
| patch_position | Add learnable position | (BC,P,D) | E011,E017 | backbone.W_pos |
| patch_embedding_dropout | Embedding dropout | (BC,P,D) | E011 | — |
| patch_encoder | Channel-independent encoder | (BC,P,D) | E011,E007 | — |
| patch_layer1 | Encoder layer 1 | (BC,P,D) | E009,E006 | encoder.layers.0 |
| patch_layer1_attn_res | Attention + residual | (BC,P,D) | E009 | — |
| patch_layer1_attention | Self-attention | (BC,P,D) | E013,E015 | — |
| patch_layer1_qkv | Q / K / V projections | tuple(Q,K,V) | E013 | — |
| patch_layer1_q | Linear Q + split | (BC,h,P,d) | E013 | encoder.layers.0.W_Q |
| patch_layer1_k | Linear K + split | (BC,h,d,P) | E013 | encoder.layers.0.W_K |
| patch_layer1_v | Linear V + split | (BC,h,P,d) | E013 | encoder.layers.0.W_V |
| patch_layer1_sdpa | Scaled dot-product attention | Z:(BC,h,P,d) | E015 | — |
| patch_layer1_sdpa_operands | Attention weights and values | tuple(A,V) | E015 | — |
| patch_layer1_weights | QK -> attention weights | A:(BC,h,P,P) | E015 | — |
| patch_layer1_raw_scores | QK / sqrt(d) + prev | S1:(BC,h,P,P) | E015 | encoder.layers.0.sdp_attn.scale (fixed) |
| patch_layer1_softmax | Softmax over key patches | A:(BC,h,P,P) | E015 | — |
| patch_layer1_attention_dropout | Attention dropout | A:(BC,h,P,P) | E015 | — |
| patch_layer1_value_bypass | V: independent value operand | V:(BC,h,P,d) | E015 | — |
| patch_layer1_weighted_values | A @ V | Z:(BC,h,P,d) | E015 | — |
| patch_layer1_merge | Merge + output projection | (BC,P,D) | E013 | encoder.layers.0.to_out |
| patch_layer1_attndrop | Residual dropout | (BC,P,D) | E009 | — |
| patch_layer1_attnadd | Add input | (BC,P,D) | E009 | — |
| patch_layer1_bn1 | Post BatchNorm | (BC,P,D) | E008,E009 | encoder.layers.0.norm_attn |
| patch_layer1_ffn_res | FFN + residual | (BC,P,D) | E009 | — |
| patch_layer1_ffn | Position-wise FFN | (BC,P,D) | E008 | — |
| patch_layer1_ff1 | Linear D -> F | (BC,P,F) | E008 | encoder.layers.0.ff.0 |
| patch_layer1_gelu | GELU | (BC,P,F) | E016 | — |
| patch_layer1_ffdrop | Dropout | (BC,P,F) | E008 | — |
| patch_layer1_ff2 | Linear F -> D | (BC,P,D) | E008 | encoder.layers.0.ff.3 |
| patch_layer1_ffnoutdrop | Residual dropout | (BC,P,D) | E009 | — |
| patch_layer1_ffnadd | Add input | (BC,P,D) | E009 | — |
| patch_layer1_bn2 | Post BatchNorm | (BC,P,D) | E008,E009 | encoder.layers.0.norm_ffn |
| patch_layer2 | Encoder layer 2 | (BC,P,D) | E009,E006 | encoder.layers.1 |
| patch_layer2_attn_res | Attention + residual | (BC,P,D) | E009 | — |
| patch_layer2_attention | Self-attention | (BC,P,D) | E013,E015 | — |
| patch_layer2_qkv | Q / K / V projections | tuple(Q,K,V) | E013 | — |
| patch_layer2_q | Linear Q + split | (BC,h,P,d) | E013 | encoder.layers.1.W_Q |
| patch_layer2_k | Linear K + split | (BC,h,d,P) | E013 | encoder.layers.1.W_K |
| patch_layer2_v | Linear V + split | (BC,h,P,d) | E013 | encoder.layers.1.W_V |
| patch_layer2_sdpa | Scaled dot-product attention | Z:(BC,h,P,d) | E015 | — |
| patch_layer2_sdpa_operands | Attention weights and values | tuple(A,V) | E015 | — |
| patch_layer2_weights | QK -> attention weights | A:(BC,h,P,P) | E015 | — |
| patch_layer2_raw_scores | QK / sqrt(d) + prev | S2:(BC,h,P,P) | E015 | encoder.layers.1.sdp_attn.scale (fixed) |
| patch_layer2_softmax | Softmax over key patches | A:(BC,h,P,P) | E015 | — |
| patch_layer2_attention_dropout | Attention dropout | A:(BC,h,P,P) | E015 | — |
| patch_layer2_value_bypass | V: independent value operand | V:(BC,h,P,d) | E015 | — |
| patch_layer2_weighted_values | A @ V | Z:(BC,h,P,d) | E015 | — |
| patch_layer2_merge | Merge + output projection | (BC,P,D) | E013 | encoder.layers.1.to_out |
| patch_layer2_attndrop | Residual dropout | (BC,P,D) | E009 | — |
| patch_layer2_attnadd | Add input | (BC,P,D) | E009 | — |
| patch_layer2_bn1 | Post BatchNorm | (BC,P,D) | E008,E009 | encoder.layers.1.norm_attn |
| patch_layer2_ffn_res | FFN + residual | (BC,P,D) | E009 | — |
| patch_layer2_ffn | Position-wise FFN | (BC,P,D) | E008 | — |
| patch_layer2_ff1 | Linear D -> F | (BC,P,F) | E008 | encoder.layers.1.ff.0 |
| patch_layer2_gelu | GELU | (BC,P,F) | E016 | — |
| patch_layer2_ffdrop | Dropout | (BC,P,F) | E008 | — |
| patch_layer2_ff2 | Linear F -> D | (BC,P,D) | E008 | encoder.layers.1.ff.3 |
| patch_layer2_ffnoutdrop | Residual dropout | (BC,P,D) | E009 | — |
| patch_layer2_ffnadd | Add input | (BC,P,D) | E009 | — |
| patch_layer2_bn2 | Post BatchNorm | (BC,P,D) | E008,E009 | encoder.layers.1.norm_ffn |
| patch_restore_channels | Restore channels + permute | (B,C,D,P) | E011 | — |
| patch_head | Shared flatten forecast head | (B,C,H) | E001,E002 | — |
| patch_flatten | Flatten D and P | (B,C,D*P) | E002 | — |
| patch_head_linear | Linear D*P -> H | (B,C,H) | E001,E002 | head.linear |
| patch_head_dropout | Head dropout | (B,C,H) | E002 | — |
| patch_revin_denorm | RevIN denormalize | (B,C,H) | E005,E020 | — |
| patch_to_time | Permute to forecast | (B,H,C) | E026 | — |
| patch_output | Forecast | (B,H,C) | E026 | — |

## 参考图修正

- Reference image shows (B,C,L) input and (B,C,H) output; Model.forward actually exposes (B,L,C) and (B,H,C).
- Flatten head projects D*P to H, not D to H; channel restoration yields (B,C,D,P), not (B,C,D).
- Default Add & Norm uses BatchNorm, not LayerNorm, and the default path is post-norm.
- End replication padding, RevIN normalization/denormalization and residual attention scores were missing from the reference image.
- P is determined by patch_len, stride and padding; stride=8 differs from patch_len=16 in the selected profile.
- The name pe='zeros' denotes a learnable (P,D) matrix initialized uniformly, not an all-zero fixed encoding.

## 模型事实

- The selected entry is PatchTST_supervised.models.PatchTST.Model, not the self-supervised implementation.
- Default run_longExp forecast profile: L=96,H=96,C=7,p=16,s=8,P=12,D=512,F=2048,h=8,N=2.
- Channel independence folds C into batch; W_P, W_pos, encoder and the individual=False head are shared across variables.
- Encoder layers are distinct ModuleList instances; repeated appearance does not mean shared layer weights.
- Default post normalization is BatchNorm1d(D), whose statistics aggregate the folded BC batch and P patches.
- res_attention=True passes pre-softmax attention scores to the next layer; it is separate from feature residual additions.
- RevIN normalizes each sample/variable and restores the saved input statistics after the forecast head.
- The adapter is explicit static source interpretation and does not import or execute the model.
