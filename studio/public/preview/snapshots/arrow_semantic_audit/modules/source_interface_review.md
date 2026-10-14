# 展开模块的源码接口合同

独立库存：20 个模块中 68 个特殊接口。普通 chain 的输入/输出由明确 IR boundary 推导；parallel 的 fork/tuple 不以 rank 建造依赖。

## 为什么不直接连到容器边框

原始 228 个视图中 SVG 坐标与布局记录完全一致，但 110 个显式端点缺少展开接口或实际边界续线。这个结果说明“画出的线符合布局记录”和“线连接了正确算子”是两个不同检查。
多输入时每条箭头被移到 in.auxN；多输出时移到 out.auxN，而容器的内部 boundary 仍停在中心 in/out。没有续线时这些端点停在边框，并没有实际连接到内部计算。

## 有源码含义的修复

- BatchNormFlow：均值和方差是两个真实的赋值结果，各自供应标准化与 EMA；方差不能作为 mean_var bundle 的生产者。
- Manual/fused BN：均值来自 compound moments 并被保留；方差来自 m2-m²。gain 进入 gainop，而不是进入前面的 rsqrt。
- FlowSequential：features 与 logdet 是一个 call 的不同输出；下一组件消费 features，累加器消费 logdet。
- Glow：chunk 的 a/b、log_s/t、retained/z_new 都保持独立名字；split_prior 的 out 指保留的首项。
- ActNorm：loc/scale 始终从原 Parameter 状态读取；初始化 Copy 修改该状态，不能替代正常 affine 的输入。
- Transformer-XL：graph helper 的输出明确是 shift_slice；不能依据最高 rank 猜输出，也不能仅从 helper 框顶发出无续线箭头。

## 完整接口表

| 模块 | scope:port | 实际子算子:port | AST 源码证据 |
|---|---|---|---|
| edge_predictor | edge.init:out | edge.buffer:out | rasbt-modules/pytorch_ipynb/gnn/gnn-basic-edge-1.py:109–123 GraphNet.__init__ |
| spectral_filter | spectral.basis_init:out | spectral.vbuffer:out | rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py:147–166 GraphNet.__init__ |
| spectral_filter | spectral.w_init:out | spectral.wbuffer:out | rasbt-modules/pytorch_ipynb/gnn/gnn-basic-graph-spectral-1.py:147–166 GraphNet.__init__ |
| glow_actnorm | glow_actnorm.affine:loc | glow_actnorm.shift:loc | glow-modules/model.py:42–57 ActNorm.forward |
| glow_actnorm | glow_actnorm.affine:scale | glow_actnorm.scale:scale | glow-modules/model.py:42–57 ActNorm.forward |
| glow_actnorm | glow_actnorm.det:scale | glow_actnorm.abslog:scale | glow-modules/model.py:42–57 ActNorm.forward |
| glow_invconv | glow_invconv.conv:weight | glow_invconv.convop:weight | glow-modules/model.py:72–80 InvConv2d.forward |
| glow_invconv | glow_invconv.det:weight | glow_invconv.detop:weight | glow-modules/model.py:72–80 InvConv2d.forward |
| glow_invconv_lu | glow_invconv_lu.conv:weight | glow_invconv_lu.convop:weight | glow-modules/model.py:114–122 InvConv2dLU.forward |
| glow_invconv_lu | glow_invconv_lu.det:weight | glow_invconv_lu.detop:weight | glow-modules/model.py:114–122 InvConv2dLU.forward |
| glow_affine_coupling | glow_affine_coupling.split:a | glow_affine_coupling.splitop:a | glow-modules/model.py:176–193 AffineCoupling.forward |
| glow_affine_coupling | glow_affine_coupling.split:b | glow_affine_coupling.splitop:b | glow-modules/model.py:176–193 AffineCoupling.forward |
| glow_affine_coupling | glow_affine_coupling.heads:t | glow_affine_coupling.headsop:t | glow-modules/model.py:176–193 AffineCoupling.forward |
| glow_affine_coupling | glow_affine_coupling.heads:log_s | glow_affine_coupling.headsop:log_s | glow-modules/model.py:176–193 AffineCoupling.forward |
| glow_affine_coupling | glow_affine_coupling.transform:scale | glow_affine_coupling.mulop:scale | glow-modules/model.py:176–193 AffineCoupling.forward |
| glow_affine_coupling | glow_affine_coupling.join:out_b | glow_affine_coupling.catop:out_b | glow-modules/model.py:176–193 AffineCoupling.forward |
| glow_affine_coupling | glow_affine_coupling.join:in_a | glow_affine_coupling.catop:in_a | glow-modules/model.py:176–193 AffineCoupling.forward |
| glow_additive_coupling | glow_additive_coupling.split:a | glow_additive_coupling.splitop:a | glow-modules/model.py:176–193 AffineCoupling.forward |
| glow_additive_coupling | glow_additive_coupling.split:b | glow_additive_coupling.splitop:b | glow-modules/model.py:176–193 AffineCoupling.forward |
| glow_additive_coupling | glow_additive_coupling.join:out_b | glow_additive_coupling.catop:out_b | glow-modules/model.py:176–193 AffineCoupling.forward |
| glow_additive_coupling | glow_additive_coupling.join:in_a | glow_additive_coupling.catop:in_a | glow-modules/model.py:176–193 AffineCoupling.forward |
| glow_split_prior | glow_split_prior.split:out | glow_split_prior.splitop:retained | glow-modules/model.py:271–296 Block.forward |
| glow_split_prior | glow_split_prior.split:z_new | glow_split_prior.splitop:z_new | glow-modules/model.py:271–296 Block.forward |
| glow_split_prior | glow_split_prior.heads:mean_log_sd | glow_split_prior.headsop:mean_log_sd | glow-modules/model.py:271–296 Block.forward |
| glow_split_prior | glow_split_prior.density:parameters | glow_split_prior.gauss:parameters | glow-modules/model.py:271–296 Block.forward; glow-modules/model.py:245–246 gaussian_log_p |
| glow_split_prior | glow_split_prior.density:sample | glow_split_prior.gauss:sample | glow-modules/model.py:271–296 Block.forward; glow-modules/model.py:245–246 gaussian_log_p |
| masked_linear | masked_linear.sum:condition | masked_linear.add:condition | density-flow-modules/flows.py:47–52 MaskedLinear.forward |
| made_affine | made_affine.heads:m | made_affine.chunk:m | density-flow-modules/flows.py:163–177 MADE.forward |
| made_affine | made_affine.heads:a | made_affine.chunk:a | density-flow-modules/flows.py:163–177 MADE.forward |
| made_affine | made_affine.shift:m | made_affine.sub:m | density-flow-modules/flows.py:163–177 MADE.forward |
| made_affine | made_affine.affine:scale | made_affine.mul:scale | density-flow-modules/flows.py:163–177 MADE.forward |
| made_split | made_split.shift:m | made_split.sub:m | density-flow-modules/flows.py:102–130 MADESplit.forward |
| made_split | made_split.affine:scale | made_split.mul:scale | density-flow-modules/flows.py:102–130 MADESplit.forward |
| flow_batchnorm | flow_batchnorm.stats:mean | flow_batchnorm.mean:out | density-flow-modules/flows.py:223–261 BatchNormFlow.forward |
| flow_batchnorm | flow_batchnorm.stats:var | flow_batchnorm.var:out | density-flow-modules/flows.py:223–261 BatchNormFlow.forward |
| flow_batchnorm | flow_batchnorm.running:mean | flow_batchnorm.ema:mean | density-flow-modules/flows.py:212–221 BatchNormFlow.__init__; density-flow-modules/flows.py:223–261 BatchNormFlow.forward |
| flow_batchnorm | flow_batchnorm.running:var | flow_batchnorm.ema:var | density-flow-modules/flows.py:212–221 BatchNormFlow.__init__; density-flow-modules/flows.py:223–261 BatchNormFlow.forward |
| flow_batchnorm | flow_batchnorm.normalize:mean | flow_batchnorm.norm:mean | density-flow-modules/flows.py:223–261 BatchNormFlow.forward |
| flow_batchnorm | flow_batchnorm.normalize:var | flow_batchnorm.norm:var | density-flow-modules/flows.py:223–261 BatchNormFlow.forward |
| flow_batchnorm | flow_batchnorm.det:var | flow_batchnorm.detop:var | density-flow-modules/flows.py:223–261 BatchNormFlow.forward |
| realnvp_coupling | realnvp_coupling.affine:scale | realnvp_coupling.mul:scale | density-flow-modules/flows.py:442–458 CouplingLayer.forward |
| realnvp_coupling | realnvp_coupling.affine:t | realnvp_coupling.mul:t | density-flow-modules/flows.py:442–458 CouplingLayer.forward |
| manual_fused_bn | manual_fused_bn.stats:mean | manual_fused_bn.moments:mean | biggan-modules/layers.py:191–208 manual_bn |
| manual_fused_bn | manual_fused_bn.stats:var | manual_fused_bn.variance:out | biggan-modules/layers.py:191–208 manual_bn |
| manual_fused_bn | manual_fused_bn.scale:gain | manual_fused_bn.gainop:gain | biggan-modules/layers.py:173–185 fused_bn |
| manual_fused_bn | manual_fused_bn.shift:mean | manual_fused_bn.shiftop:mean | biggan-modules/layers.py:173–185 fused_bn |
| manual_fused_bn | manual_fused_bn.shift:scale | manual_fused_bn.shiftop:scale | biggan-modules/layers.py:173–185 fused_bn |
| manual_fused_bn | manual_fused_bn.shift:bias | manual_fused_bn.shiftop:bias | biggan-modules/layers.py:173–185 fused_bn |
| manual_fused_bn | manual_fused_bn.affine:scale | manual_fused_bn.out:scale | biggan-modules/layers.py:173–185 fused_bn |
| manual_fused_bn | manual_fused_bn.affine:shift | manual_fused_bn.out:shift | biggan-modules/layers.py:173–185 fused_bn |
| conditional_bn | conditional_bn.multiply:gain | conditional_bn.mul:gain | biggan-modules/layers.py:306–325 ccbn.forward |
| conditional_bn | conditional_bn.add:bias | conditional_bn.addop:bias | biggan-modules/layers.py:306–325 ccbn.forward |
| nonlocal_attention | nonlocal_attention.beta:theta | nonlocal_attention.score:theta | biggan-modules/layers.py:156–169 Attention.forward |
| nonlocal_attention | nonlocal_attention.beta:phi | nonlocal_attention.score:phi | biggan-modules/layers.py:156–169 Attention.forward |
| nonlocal_attention | nonlocal_attention.aggregate:beta | nonlocal_attention.bmm:beta | biggan-modules/layers.py:156–169 Attention.forward |
| nonlocal_attention | nonlocal_attention.aggregate:values | nonlocal_attention.bmm:values | biggan-modules/layers.py:156–169 Attention.forward |
| coral_head | coral_head.broadcast:threshold_bias | coral_head.add:threshold_bias | rasbt-ordinal-modules/pytorch_ipynb/ordinal/CORAL_cement.py:147–160 CoralLayer.forward |
| flow_sequential | flow_sequential.first:features | flow_sequential.call0:features | density-flow-modules/flows.py:184–192 Sigmoid.forward; density-flow-modules/flows.py:467–488 FlowSequential.forward |
| flow_sequential | flow_sequential.first:logdet | flow_sequential.call0:logdet | density-flow-modules/flows.py:184–192 Sigmoid.forward; density-flow-modules/flows.py:467–488 FlowSequential.forward |
| flow_sequential | flow_sequential.second:features | flow_sequential.call1:features | density-flow-modules/flows.py:393–399 Reverse.forward; density-flow-modules/flows.py:388–391 Reverse.__init__; density-flow-modules/flows.py:467–488 FlowSequential.forward |
| flow_sequential | flow_sequential.second:logdet | flow_sequential.call1:logdet | density-flow-modules/flows.py:393–399 Reverse.forward; density-flow-modules/flows.py:388–391 Reverse.__init__; density-flow-modules/flows.py:467–488 FlowSequential.forward |
| flow_sequential | flow_sequential.add0:accumulator | flow_sequential.sum0:accumulator | density-flow-modules/flows.py:467–488 FlowSequential.forward |
| flow_sequential | flow_sequential.add0:increment | flow_sequential.sum0:increment | density-flow-modules/flows.py:467–488 FlowSequential.forward |
| flow_sequential | flow_sequential.add1:accumulator | flow_sequential.sum1:accumulator | density-flow-modules/flows.py:467–488 FlowSequential.forward |
| flow_sequential | flow_sequential.add1:increment | flow_sequential.sum1:increment | density-flow-modules/flows.py:467–488 FlowSequential.forward |
| transformer_xl_relative | txl.shift:out | txl.shift_slice:out | transformer-xl-relative/pytorch/mem_transformer.py:194–207 RelMultiHeadAttn._rel_shift |
| autoregressive_mask | autoregressive_mask.compare:input_degrees | autoregressive_mask.ge:input_degrees | density-flow-modules/flows.py:12–29 get_mask |
| autoregressive_mask | autoregressive_mask.compare:output_degrees | autoregressive_mask.ge:output_degrees | density-flow-modules/flows.py:12–29 get_mask |

合同代码：`module_programmatic_guide/module_adapters/endpoint_contracts.py`。JSON 库存逐项保留 AST 来源和绑定理由。
该合同描述静态选定分支，不证明任意配置与任意新源码。所有上游模型均未导入或执行。
