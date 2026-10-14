# 两个目录的完整条目审计

本轮共 **76 个模块案例 / 53 个模块族标签 / 228 个主 SVG 视图**。模块族标签是适配分类，不是数学模块的唯一标准。

已逐条给冻结 README 中的 **832 个条目（Awesome 706、rasbt 126）** 和 rasbt Git tree 中 **183 个 Notebook 路径** 赋予状态；完整机器清单见 [index_audit.json](index_audit.json)。

**“完整”在这里指索引条目都有记录；不能称全部外链仓库的所有模块已画完。** 两个目录含工具、教程、数据集、完整模型与重复实现，外链数量和动态配置没有封闭的模块总数。尚未读过的实现保留未核实状态，普通算子 kernel 仍是调用边界。

| 条目状态 | 数量 | 含义 |
| --- | ---: | --- |
| `resource_entry_no_exhaustive_module_audit` | 354 | 资源目录条目；未对整仓库做模块穷举 |
| `selected_module_subgraphs_drawn` | 36 | 已绘制所选模块边界，未声称整个条目所有模块覆盖 |
| `indexed_not_source_reviewed_for_new_modules` | 419 | 已收录，尚未获取/审阅新模块实现 |
| `existing_whole_model_case_has_module_inventory` | 22 | 已有完整模型与逐节点覆盖盘点 |
| `upstream_reference_missing` | 1 | 冻结 tree 中引用缺失 |

## 本轮可闭合的覆盖边界

- 新绘制模块都有固定 commit、源码符号、输入输出边界、参数/状态、三粒度图和语义核验。现有案例中的同构结构作为已覆盖依据保留。
- 对已取得 Python 文件，JSON 同时列出顶层类/函数的源码符号 census。未单画的 helper、整个模型容器、另一配置或同构原子操作，不能直接计为缺失的新模块。
- 同仓库出现于多条目录引用，只能说明选定实现来自该仓库；不能据此把整条目录或所有分支打成完成。
- 已审阅但未单画的同构/整模型/另一配置边界见 [module_boundary_notes.json](module_boundary_notes.json)，不计成新模块。
- 源码特有分支分别作为案例：如 Shuffle stride1/2、SignedSAGE Base/Deep、MixHop Sparse/Dense、Glow affine/additive；它们不是新增完整模型。

## 已绘制模块目录

| CLI key | 模块 | 模块族 | 图与源码说明 |
| --- | --- | --- | --- |
| `frn_tlu` | FRN + learned TLU | 归一化与阈值 | [三图](generated/frn_tlu/index.html) · [对应](docs/FRN_TLU.md) |
| `highway` | Highway gated fusion | 门控融合 | [三图](generated/highway/index.html) · [对应](docs/Highway.md) |
| `inception_a` | InceptionA / parallel convolution module | 多分支卷积 | [三图](generated/inception_a/index.html) · [对应](docs/InceptionA.md) |
| `channel_shuffle` | Channel shuffle / tensor permutation | 张量重排 | [三图](generated/channel_shuffle/index.html) · [对应](docs/ChannelShuffle.md) |
| `stn` | Spatial Transformer submodule | 空间变换 | [三图](generated/stn/index.html) · [对应](docs/STN.md) |
| `pixelshuffle` | Conv4 + PixelShuffle head | 空间上采样 | [三图](generated/pixelshuffle/index.html) · [对应](docs/PixelShuffle.md) |
| `edge_predictor` | EdgePredictor (coordinate-to-adjacency module) | 图边权预测 | [三图](generated/edge_predictor/index.html) · [对应](docs/EdgePredictor.md) |
| `spectral_filter` | SpectralFilter (truncated graph basis module) | 谱域图滤波 | [三图](generated/spectral_filter/index.html) · [对应](docs/SpectralFilter.md) |
| `glow_actnorm` | Glow ActNorm / data-initialized affine | 可逆归一化 | [三图](generated/glow_actnorm/index.html) · [对应](docs/glow_actnorm.md) |
| `glow_invconv` | Direct invertible 1x1 convolution | 可逆通道混合 | [三图](generated/glow_invconv/index.html) · [对应](docs/glow_invconv.md) |
| `glow_invconv_lu` | LU invertible 1x1 convolution | 可逆通道混合 | [三图](generated/glow_invconv_lu/index.html) · [对应](docs/glow_invconv_lu.md) |
| `zero_conv` | ZeroConv2d conditioner | 特殊卷积初始化 | [三图](generated/zero_conv/index.html) · [对应](docs/zero_conv.md) |
| `glow_affine_coupling` | Glow affine coupling | 可逆耦合 | [三图](generated/glow_affine_coupling/index.html) · [对应](docs/glow_affine_coupling.md) |
| `glow_additive_coupling` | Glow additive coupling | 可逆耦合 | [三图](generated/glow_additive_coupling/index.html) · [对应](docs/glow_additive_coupling.md) |
| `glow_squeeze` | Squeeze / space-to-channel | 张量重排 | [三图](generated/glow_squeeze/index.html) · [对应](docs/glow_squeeze.md) |
| `glow_split_prior` | Split prior / conditional Gaussian density | 条件密度头 | [三图](generated/glow_split_prior/index.html) · [对应](docs/glow_split_prior.md) |
| `masked_linear` | MaskedLinear / conditional projection | 掩码投影 | [三图](generated/masked_linear/index.html) · [对应](docs/masked_linear.md) |
| `made_affine` | MADE / autoregressive affine | 自回归流 | [三图](generated/made_affine/index.html) · [对应](docs/made_affine.md) |
| `made_split` | MADESplit / autoregressive affine | 自回归流 | [三图](generated/made_split/index.html) · [对应](docs/made_split.md) |
| `flow_batchnorm` | BatchNormFlow / affine + logdet | 可逆归一化 | [三图](generated/flow_batchnorm/index.html) · [对应](docs/flow_batchnorm.md) |
| `realnvp_coupling` | RealNVP / masked coupling | 可逆耦合 | [三图](generated/realnvp_coupling/index.html) · [对应](docs/realnvp_coupling.md) |
| `sigmoid_bijector` | Sigmoid bijector / Jacobian branch | 逐元素可逆变换 | [三图](generated/sigmoid_bijector/index.html) · [对应](docs/sigmoid_bijector.md) |
| `spectral_norm_linear` | Spectral normalization / Linear wrapper | 权重约束 | [三图](generated/spectral_norm_linear/index.html) · [对应](docs/spectral_norm_linear.md) |
| `manual_fused_bn` | Manual / fused BatchNorm arithmetic | 归一化统计展开 | [三图](generated/manual_fused_bn/index.html) · [对应](docs/manual_fused_bn.md) |
| `conditional_bn` | Conditional BatchNorm / two condition heads | 条件归一化 | [三图](generated/conditional_bn/index.html) · [对应](docs/conditional_bn.md) |
| `nonlocal_attention` | Non-local 2D attention / pooled keys-values | 非局部空间注意力 | [三图](generated/nonlocal_attention/index.html) · [对应](docs/nonlocal_attention.md) |
| `coral_head` | CORAL / shared ordinal score head | 序数输出头 | [三图](generated/coral_head/index.html) · [对应](docs/coral_head.md) |
| `corn_decoder` | CORN probability decoder | 序数概率解码 | [三图](generated/corn_decoder/index.html) · [对应](docs/corn_decoder.md) |
| `flow_sequential` | FlowSequential / dual-stream composition | 双流容器 | [三图](generated/flow_sequential/index.html) · [对应](docs/flow_sequential.md) |
| `sparse_gcn` | Sparse GCN layer | graph propagation | [三图](generated/sparse_gcn/index.html) · [对应](docs/SparseGCN.md) |
| `ggnn_step` | GGNN typed-edge propagation step | graph recurrence | [三图](generated/ggnn_step/index.html) · [对应](docs/GGNNStep.md) |
| `capsule_routing` | Capsule agreement routing | routing | [三图](generated/capsule_routing/index.html) · [对应](docs/CapsuleRouting.md) |
| `bilinear_attention` | BAN bilinear attention | multimodal fusion | [三图](generated/bilinear_attention/index.html) · [对应](docs/BilinearAttention.md) |
| `weighted_bilinear_pooling` | Weighted bilinear pooling | multimodal fusion | [三图](generated/weighted_bilinear_pooling/index.html) · [对应](docs/WeightedBilinearPooling.md) |
| `compact_bilinear_pooling` | Compact bilinear TensorSketch | multimodal fusion | [三图](generated/compact_bilinear_pooling/index.html) · [对应](docs/CompactBilinearPooling.md) |
| `appnp_propagation` | APPNP restart propagation | graph propagation | [三图](generated/appnp_propagation/index.html) · [对应](docs/APPNPPropagation.md) |
| `inner_product_decoder` | Graph inner-product decoder | graph generative | [三图](generated/inner_product_decoder/index.html) · [对应](docs/InnerProductDecoder.md) |
| `graphsage_mean` | GraphSAGE sampled mean | graph propagation | [三图](generated/graphsage_mean/index.html) · [对应](docs/GraphSAGEMean.md) |
| `mixhop_layer` | MixHop sparse multi-power stage | graph propagation | [三图](generated/mixhop_layer/index.html) · [对应](docs/MixHopLayer.md) |
| `mixhop_dense` | MixHop dense power branch | graph propagation | [三图](generated/mixhop_dense/index.html) · [对应](docs/MixHopDense.md) |
| `signed_graphconv` | Signed graph deep convolution | graph propagation | [三图](generated/signed_graphconv/index.html) · [对应](docs/SignedGraphConv.md) |
| `signed_graphconv_base` | Signed graph first-layer convolution | graph propagation | [三图](generated/signed_graphconv_base/index.html) · [对应](docs/SignedGraphConvBase.md) |
| `graph_attention` | DGL multi-head graph attention | graph attention | [三图](generated/graph_attention/index.html) · [对应](docs/GraphAttention.md) |
| `vgae_posterior` | VGAE graph posterior sampling | graph generative | [三图](generated/vgae_posterior/index.html) · [对应](docs/VGAEPosterior.md) |
| `tcn_block` | TCN TemporalBlock / causal residual | 因果扩张卷积残差 | [三图](generated/tcn_block/index.html) · [对应](docs/TCN_TemporalBlock.md) |
| `gru_cell` | GRUCell / explicit reset-update gates | 显式递归门控 | [三图](generated/gru_cell/index.html) · [对应](docs/GRUCell.md) |
| `layernorm_lstm_cell` | LayerNormLSTMCell / three independent norms | 归一化递归门控 | [三图](generated/layernorm_lstm_cell/index.html) · [对应](docs/LayerNormLSTMCell.md) |
| `wavenet_block` | WaveNet / gated residual and skip iteration | 时序卷积门控与双残差 | [三图](generated/wavenet_block/index.html) · [对应](docs/WaveNet_Block.md) |
| `structured_attention` | Structured hop attention | 多跳句子池化注意力 | [三图](generated/structured_attention/index.html) · [对应](docs/Structured_Attention.md) |
| `seq2seq_attention` | Seq2seq dot attention / context fusion | 未缩放点积与上下文融合 | [三图](generated/seq2seq_attention/index.html) · [对应](docs/Seq2seq_Attention.md) |
| `seq2seq_additive_attention` | Bahdanau attention / query-key-value roles | Bahdanau加性注意力 | [三图](generated/seq2seq_additive_attention/index.html) · [对应](docs/Seq2seq_Additive_Attention.md) |
| `qanet_context_query_attention` | QANet context-query attention | 三线性双向上下文查询注意力 | [三图](generated/qanet_context_query_attention/index.html) · [对应](docs/QANet_CQAttention.md) |
| `transformer_xl_relative` | Transformer-XL relative attention | 相对位置与记忆注意力 | [三图](generated/transformer_xl_relative/index.html) · [对应](docs/TransformerXL_Relative_Attention.md) |
| `fire` | Fire squeeze/expand | Squeeze/expand CNN block | [三图](generated/fire/index.html) · [对应](docs/Fire.md) |
| `aspp` | ASPP atrous context | Spatial pyramid context | [三图](generated/aspp/index.html) · [对应](docs/ASPP.md) |
| `pyramid_pooling` | Pyramid pooling / PSPModule | Spatial pyramid context | [三图](generated/pyramid_pooling/index.html) · [对应](docs/PyramidPooling.md) |
| `inception_reduction` | InceptionB / independent module | Inception branch modules | [三图](generated/inception_reduction/index.html) · [对应](docs/InceptionReduction.md) |
| `inception_factorized` | InceptionC / independent module | Inception branch modules | [三图](generated/inception_factorized/index.html) · [对应](docs/InceptionFactorized.md) |
| `inception_reduction_factorized` | InceptionD / independent module | Inception branch modules | [三图](generated/inception_reduction_factorized/index.html) · [对应](docs/InceptionReductionFactorized.md) |
| `inception_split` | InceptionE / independent module | Inception branch modules | [三图](generated/inception_split/index.html) · [对应](docs/InceptionSplit.md) |
| `roi_align` | RoIAlign region sampling | Region sampling | [三图](generated/roi_align/index.html) · [对应](docs/RoIAlign.md) |
| `deformable_conv` | DeformableConv modulated | Deformable sampling | [三图](generated/deformable_conv/index.html) · [对应](docs/DeformableConv.md) |
| `deformable_conv_unmodulated` | DeformableConv unmodulated | Deformable sampling | [三图](generated/deformable_conv_unmodulated/index.html) · [对应](docs/DeformableConvUnmodulated.md) |
| `shuffle_ir_stride1` | ShuffleNetV2 split/retain | ShuffleNet branch modules | [三图](generated/shuffle_ir_stride1/index.html) · [对应](docs/ShuffleIRStride1.md) |
| `shuffle_ir_stride2` | ShuffleNetV2 stride2/downsample | ShuffleNet branch modules | [三图](generated/shuffle_ir_stride2/index.html) · [对应](docs/ShuffleIRStride2.md) |
| `fpn` | Feature Pyramid Network | Multiscale pyramid DAG | [三图](generated/fpn/index.html) · [对应](docs/FPN.md) |
| `fpn_extra_levels` | FPN extra P6/P7 levels | Multiscale pyramid DAG | [三图](generated/fpn_extra_levels/index.html) · [对应](docs/FPNExtraLevels.md) |
| `psp_upsample` | PSP resize/convolution upsample | Upsampling and learned activation | [三图](generated/psp_upsample/index.html) · [对应](docs/PSPUpsample.md) |
| `graphwavelet_sparse` | Graph wavelet sparse layer | 图小波滤波 | [三图](generated/graphwavelet_sparse/index.html) · [对应](docs/GraphWaveletSparse.md) |
| `graphwavelet_dense` | Graph wavelet dense layer | 图小波滤波 | [三图](generated/graphwavelet_dense/index.html) · [对应](docs/GraphWaveletDense.md) |
| `simgnn_readout` | SimGNN graph attention readout | 图级读出 | [三图](generated/simgnn_readout/index.html) · [对应](docs/SimGNNReadout.md) |
| `simgnn_tensor` | SimGNN neural tensor comparison | 图对张量比较 | [三图](generated/simgnn_tensor/index.html) · [对应](docs/SimGNNTensor.md) |
| `tucker_core` | TuckER relation-conditioned core | 关系条件张量变换 | [三图](generated/tucker_core/index.html) · [对应](docs/TuckERCore.md) |
| `autoregressive_mask` | Degree mask / strict autoregressive topology | 掩码拓扑构造 | [三图](generated/autoregressive_mask/index.html) · [对应](docs/autoregressive_mask.md) |
| `milstm_projection` | MI-LSTM / multiplicative gate integration | 乘法集成门预激活 | [三图](generated/milstm_projection/index.html) · [对应](docs/MI_LSTM_Projection.md) |
| `childsum_treelstm` | Child-Sum TreeLSTM / per-child forgetting | 树递归与逐子遗忘归约 | [三图](generated/childsum_treelstm/index.html) · [对应](docs/ChildSum_TreeLSTM.md) |
