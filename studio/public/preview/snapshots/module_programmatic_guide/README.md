# 模块程序化绘图原型

本专题针对两个目录指向的源码，补绘现有模型案例未展开过的模块子图，扩展统一 IR、图元、状态与连线机制。入口：[可搜索画廊](generated/index.html) · [新增覆盖差异](coverage.md) · [完整目录审计](index_audit.md)。

当前 **76 个模块案例**，其中原有 8 个，本轮新增 68 个；每例有概览、内部模块、算子详细三粒度，共 **228 张 SVG 与 228 张 PNG**。它们独立于已有 30 个完整模型案例统计；源码变体分别作为适配案例，不等于不同完整模型。

沿用 Transformer 的 DejaVu Sans 字体、鲜明角色色和深色轮廓，整体与内部主流程均自底向上。同源独立分支并列、依赖调用顺序上下排列、tuple 返回值分别保留。颜色表示视觉角色；参数共享看实例身份和 IR。

[新增模块详细图总览](generated/contact_pages.html) · [最终审阅](generated/module_review.json) · [实际导出核验](generated/export_checks.json) · [错误注入检查](generated/semantic_negative_checks.json) · [源码快照检查](generated/pinned_source_checks.json)。[原8例当前总览](generated/detailed_contact.png) 已按本轮正式 PNG 刷新；每张输入图的 SHA256 见最终审阅中的 `original_eight_contact`。原8例的 [initial_eight 审阅](generated/reviews/initial_eight/module_review.json) 是历史报告，[旧总览图片](../arrow_semantic_audit/before/module_programmatic_guide/generated/detailed_contact.png) 按原始字节保存在 before。

箭头语义修订对所有 76 例的三视图重新导出，包括原8例。历史报告和原始哈希基线保留；当前图像、布局与接口 IR 的授权变更逐项记录在 [existing_artifacts_check.json](generated/existing_artifacts_check.json)，不再宣称当前导出与旧8例逐字节一致。[独立端点审计](../arrow_semantic_audit/modules/after_endpoint_audit.md) 逐条核对固定源码、IR 接口、真实布局端点和 SVG XML；[实际 SVG 错误注入](../arrow_semantic_audit/modules/actual_svg_negative_checks.json) 覆盖改错实际子算子、mean/var、features/logdet、保留输入及 shape 身份。

## 模块适配目录

| 模块族 | 案例数 | 模块例子 |
| --- | ---: | --- |
| 归一化与阈值 | 1 | [frn_tlu](generated/frn_tlu/index.html) |
| 门控融合 | 1 | [highway](generated/highway/index.html) |
| 多分支卷积 | 1 | [inception_a](generated/inception_a/index.html) |
| 张量重排 | 2 | [channel_shuffle](generated/channel_shuffle/index.html) · [glow_squeeze](generated/glow_squeeze/index.html) |
| 空间变换 | 1 | [stn](generated/stn/index.html) |
| 空间上采样 | 1 | [pixelshuffle](generated/pixelshuffle/index.html) |
| 图边权预测 | 1 | [edge_predictor](generated/edge_predictor/index.html) |
| 谱域图滤波 | 1 | [spectral_filter](generated/spectral_filter/index.html) |
| 可逆归一化 | 2 | [glow_actnorm](generated/glow_actnorm/index.html) · [flow_batchnorm](generated/flow_batchnorm/index.html) |
| 可逆通道混合 | 2 | [glow_invconv](generated/glow_invconv/index.html) · [glow_invconv_lu](generated/glow_invconv_lu/index.html) |
| 特殊卷积初始化 | 1 | [zero_conv](generated/zero_conv/index.html) |
| 可逆耦合 | 3 | [glow_affine_coupling](generated/glow_affine_coupling/index.html) · [glow_additive_coupling](generated/glow_additive_coupling/index.html) · [realnvp_coupling](generated/realnvp_coupling/index.html) |
| 条件密度头 | 1 | [glow_split_prior](generated/glow_split_prior/index.html) |
| 掩码投影 | 1 | [masked_linear](generated/masked_linear/index.html) |
| 自回归流 | 2 | [made_affine](generated/made_affine/index.html) · [made_split](generated/made_split/index.html) |
| 逐元素可逆变换 | 1 | [sigmoid_bijector](generated/sigmoid_bijector/index.html) |
| 权重约束 | 1 | [spectral_norm_linear](generated/spectral_norm_linear/index.html) |
| 归一化统计展开 | 1 | [manual_fused_bn](generated/manual_fused_bn/index.html) |
| 条件归一化 | 1 | [conditional_bn](generated/conditional_bn/index.html) |
| 非局部空间注意力 | 1 | [nonlocal_attention](generated/nonlocal_attention/index.html) |
| 序数输出头 | 1 | [coral_head](generated/coral_head/index.html) |
| 序数概率解码 | 1 | [corn_decoder](generated/corn_decoder/index.html) |
| 双流容器 | 1 | [flow_sequential](generated/flow_sequential/index.html) |
| graph propagation | 7 | [sparse_gcn](generated/sparse_gcn/index.html) · [appnp_propagation](generated/appnp_propagation/index.html) · [graphsage_mean](generated/graphsage_mean/index.html) · [mixhop_layer](generated/mixhop_layer/index.html) · [mixhop_dense](generated/mixhop_dense/index.html) · [signed_graphconv](generated/signed_graphconv/index.html) · [signed_graphconv_base](generated/signed_graphconv_base/index.html) |
| graph recurrence | 1 | [ggnn_step](generated/ggnn_step/index.html) |
| routing | 1 | [capsule_routing](generated/capsule_routing/index.html) |
| multimodal fusion | 3 | [bilinear_attention](generated/bilinear_attention/index.html) · [weighted_bilinear_pooling](generated/weighted_bilinear_pooling/index.html) · [compact_bilinear_pooling](generated/compact_bilinear_pooling/index.html) |
| graph generative | 2 | [inner_product_decoder](generated/inner_product_decoder/index.html) · [vgae_posterior](generated/vgae_posterior/index.html) |
| graph attention | 1 | [graph_attention](generated/graph_attention/index.html) |
| 因果扩张卷积残差 | 1 | [tcn_block](generated/tcn_block/index.html) |
| 显式递归门控 | 1 | [gru_cell](generated/gru_cell/index.html) |
| 归一化递归门控 | 1 | [layernorm_lstm_cell](generated/layernorm_lstm_cell/index.html) |
| 时序卷积门控与双残差 | 1 | [wavenet_block](generated/wavenet_block/index.html) |
| 多跳句子池化注意力 | 1 | [structured_attention](generated/structured_attention/index.html) |
| 未缩放点积与上下文融合 | 1 | [seq2seq_attention](generated/seq2seq_attention/index.html) |
| Bahdanau加性注意力 | 1 | [seq2seq_additive_attention](generated/seq2seq_additive_attention/index.html) |
| 三线性双向上下文查询注意力 | 1 | [qanet_context_query_attention](generated/qanet_context_query_attention/index.html) |
| 相对位置与记忆注意力 | 1 | [transformer_xl_relative](generated/transformer_xl_relative/index.html) |
| Squeeze/expand CNN block | 1 | [fire](generated/fire/index.html) |
| Spatial pyramid context | 2 | [aspp](generated/aspp/index.html) · [pyramid_pooling](generated/pyramid_pooling/index.html) |
| Inception branch modules | 4 | [inception_reduction](generated/inception_reduction/index.html) · [inception_factorized](generated/inception_factorized/index.html) · [inception_reduction_factorized](generated/inception_reduction_factorized/index.html) · [inception_split](generated/inception_split/index.html) |
| Region sampling | 1 | [roi_align](generated/roi_align/index.html) |
| Deformable sampling | 2 | [deformable_conv](generated/deformable_conv/index.html) · [deformable_conv_unmodulated](generated/deformable_conv_unmodulated/index.html) |
| ShuffleNet branch modules | 2 | [shuffle_ir_stride1](generated/shuffle_ir_stride1/index.html) · [shuffle_ir_stride2](generated/shuffle_ir_stride2/index.html) |
| Multiscale pyramid DAG | 2 | [fpn](generated/fpn/index.html) · [fpn_extra_levels](generated/fpn_extra_levels/index.html) |
| Upsampling and learned activation | 1 | [psp_upsample](generated/psp_upsample/index.html) |
| 图小波滤波 | 2 | [graphwavelet_sparse](generated/graphwavelet_sparse/index.html) · [graphwavelet_dense](generated/graphwavelet_dense/index.html) |
| 图级读出 | 1 | [simgnn_readout](generated/simgnn_readout/index.html) |
| 图对张量比较 | 1 | [simgnn_tensor](generated/simgnn_tensor/index.html) |
| 关系条件张量变换 | 1 | [tucker_core](generated/tucker_core/index.html) |
| 掩码拓扑构造 | 1 | [autoregressive_mask](generated/autoregressive_mask/index.html) |
| 乘法集成门预激活 | 1 | [milstm_projection](generated/milstm_projection/index.html) |
| 树递归与逐子遗忘归约 | 1 | [childsum_treelstm](generated/childsum_treelstm/index.html) |

完整清单、所选实现、源码 SHA 和逐模块范围在 [module_catalog.json](module_catalog.json)；每例说明位于 docs，对应关系也能从图中 E###、SVG tooltip 和 source_map.md 检查。

## 本地生成与验证

保留本目录与同级 `model_zoo_programmatic_guide`。`bootstrap.py` 复用其静态 `spec/evidence/layout/theme/notebook_source` 引擎。本专题拥有独立 manifest、registry、适配器与产物，不接入 Studio 编辑会话。Python 3.10+ 即可生成 SVG；PNG 需要 `rsvg-convert`，检查 PNG 需要 Pillow。无需 PyTorch、GPU、权重或训练数据。

```bash
cd "prototype/module_programmatic_guide"
python3 fetch_sources.py --offline --report generated/pinned_source_checks.json
python3 generate.py --png
python3 verify.py generated --png
python3 checks/verify_semantics.py
python3 ../arrow_semantic_audit/modules/audit.py --report ../arrow_semantic_audit/modules/after_endpoint_audit.json
python3 ../arrow_semantic_audit/modules/negative_checks.py
python3 audit_coverage.py
python3 review_expansion.py
```

从工作区根目录运行上例的 cd；已经在本目录时略过它。只修改一个模块时优先小范围生成：

```bash
python3 generate.py --module nonlocal_attention --png
python3 verify.py generated --module nonlocal_attention --png
python3 generate.py --module fpn --out /tmp/fpn-preview --png
python3 verify.py /tmp/fpn-preview --module fpn --png
```

`fetch_sources.py --offline` 只核对固定 SHA256/Git blob 与 Notebook 单元映射，不联网、不写回。默认模式仅在文件缺失或被修改时恢复固定 commit。Notebook 派生 Python 保留单元/行映射，魔法命令被注释，从不执行。源码许可证缺失时 manifest 明确标记，不能用别的仓库 LICENSE 代替。

## 目录与产物

```text
module_adapters/     每例 build() + validate_ir()，以及局部共享声明 helper
sources/             固定 commit 源码、原 Notebook、派生 Python 与许可证
upstream/            两个 README 索引与固定 tree/revision
source_manifest.json 来源、原始/派生哈希与 Notebook 单元映射
module_catalog.json  索引条目→仓库→源码符号→所选模块边界
existing_coverage.json 原30个主模型的逐节点覆盖盘点
coverage.json/.md    模块覆盖差异、旧候选到实现的映射
index_audit.json/.md 两目录全部条目、Notebook、已取源码符号的审计
docs/                每例源码↔图元、端口/参数身份和布局理由
checks/              独立 AST 合同、关键语义与错误注入检查
generated/           SVG/PNG、搜索画廊、IR/证据/布局、最终报告
staging/             此次分组获取/集成记录与合并前试绘工具
```

每例生成目录含 `semantic_ir.json`、`source_evidence.json`、`profile.json`、`visual_style.json`、`source_map.md`、`layout_*.json`、`layout_checks.json` 以及 index.html。完整 IR 保留折叠节点，layout 只记录当前可见节点、bbox、端口和实际路径。形状是静态推导，不能当作数值执行观测。

`module_adapters/endpoint_contracts.py` 声明展开 scope 的特殊命名接口；普通 chain 通过 IR boundary 递归解析。布局的 `endpoint_projections` 为每条 IR 边记录渲染、接口别名或折叠处置，`port_fields` 保留每个物理侧端口所承载的语义字段。每条 SVG `<path>` 的 `data-endpoint-binding` 绑定真实生产者/消费者及其字段，可以核验箭头最终连接的图元；tooltip 只作解释。

## 源码语义与视觉布局的分工

1. 固定实现与构造配置，先选模块输入/输出和排除项，核对 Parameter、buffer、普通属性及 train/eval 分支。不能用教科书默认替代源码。
2. `build()` 显式声明节点、层次、实例身份和 typed edges。chain 只用于真实顺序；复杂多输入用 graph 和显式端口；状态/参数面板只表达来源或归属。图的 ranks 不自动创建数据依赖。
3. 从完整 IR 投影三个粒度：折叠模块 → 内部分组 → 算子详细。measure 计算标签/形状/内容尺寸，再按底到顶 rank、并列列距与组间距分配 bbox。
4. 先按真实接口解析可见生产者/消费者，再根据 bbox 和端口寻找正交通道。展开容器不是默认数据端点；多输入必须进入实际消费者，命名输出必须来自实际生产者。保留的 `:in` 追踪变换前输入，折叠接口仍保留字段身份；正交通道避开无关图元与边框，提前转弯，显式端口终段预留24px。
5. `validate_ir()` 核对所选语义，独立 AST 与负例检查关键源码合同；实际 SVG/PNG 检查核对 metadata、几何和源码副本，再目视复查。静态检查通过不等于数值运行正确。

新增来源使用新的 source-project slug，保持旧 manifest 项的整个快照 digest 不变。只增加已有 slug 的文件也会改变其快照，造成旧图证据失配，需避免。历史输出哈希保存在 `staging/original_output_hashes.json`，未覆盖旧基线；本次箭头/接口修订以独立端点审计和前后哈希记录证明授权变更，源码与证据副本继续核对固定哈希。`review_expansion.py` 刷新详细图总览、链接核验和最终报告；其他专题的导出在各自审计中核验，不将新版图像错误标记为逐字节保留。

## 完整性边界与后续扩展

本轮尽量合并可取得、可审阅、具有不同结构机制的模块，而不是再次分成小模型批次。目录审计覆盖全部832条记录，但外链仓库并未全部递归读取，不宣称它们的所有模块和动态配置都已绘制。未获取实现、普通 kernel、另一训练/反向配置、同构模块与整模型容器均保留明确边界。

如 ROI Align / DeformConv 的底层 kernel 未冻结，图只能解释 Python 参数准备和真实库调用边界；GRU 门内部采用补充固定 PyTorch 实现时，说明区分 rasbt 的库调用与补充实现证据；CORN 解码来自 Notebook 调用段，不伪造一个 nn.Module 类。

后续添加模块：先查 coverage 与 index_audit，冻结新实现和许可状态，编写显式适配器、来源记录与中文对应文档，添加独立源码合同及关键依赖负例，试绘三个粒度并完成导出/目视核验。可复用图元和布局引擎；当前仍需要源码审阅后写适配器，不能仅修改 --source 输入任意源码自动生成正确结构。
