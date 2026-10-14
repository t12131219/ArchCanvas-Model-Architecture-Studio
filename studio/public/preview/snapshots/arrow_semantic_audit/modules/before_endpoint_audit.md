# 模块箭头语义独立审计

范围：76 个模块 × 3 视图，共 228 个 SVG。
核对 2723 个实际图框、3157 条 SVG 路径、1763 条显式类型依赖。

Independent fixed source hash + AST span references + IR boundary alias traversal + actual SVG XML coordinates; no drawing-engine functions imported.

## 当前结果

通过：False。错误分类：`{'wrong or unbound visible endpoint': 110}`。

## 待修复的实际端点

| 模块 | 视图 | 路径 | 实际端点与期望 |
|---|---|---|---|
| autoregressive_mask | detailed | route-0012 | dst autoregressive_mask.compare:input_degrees -> autoregressive_mask.compare:in.aux0; expected []; expanded scope has no declared interface for input_degrees |
| autoregressive_mask | detailed | route-0013 | dst autoregressive_mask.compare:output_degrees -> autoregressive_mask.compare:in.aux1; expected []; expanded scope has no declared interface for output_degrees |
| conditional_bn | detailed | route-0016 | dst conditional_bn.multiply:in -> conditional_bn.multiply:in.aux0; expected [('conditional_bn.mul', 'in')]; visible opaque/leaf endpoint |
| conditional_bn | detailed | route-0017 | dst conditional_bn.multiply:gain -> conditional_bn.multiply:in.aux1; expected []; expanded scope has no declared interface for gain |
| conditional_bn | detailed | route-0018 | dst conditional_bn.add:in -> conditional_bn.add:in.aux0; expected [('conditional_bn.addop', 'in')]; visible opaque/leaf endpoint |
| conditional_bn | detailed | route-0019 | dst conditional_bn.add:bias -> conditional_bn.add:in.aux1; expected []; expanded scope has no declared interface for bias |
| coral_head | detailed | route-0006 | dst coral_head.broadcast:in -> coral_head.broadcast:in.aux0; expected [('coral_head.add', 'in')]; visible opaque/leaf endpoint |
| coral_head | detailed | route-0007 | dst coral_head.broadcast:threshold_bias -> coral_head.broadcast:in.aux1; expected []; expanded scope has no declared interface for threshold_bias |
| edge_predictor | detailed | route-0017 | src edge.init:out -> edge.init:right; expected [('edge.buffer', 'out')]; visible opaque/leaf endpoint |
| flow_batchnorm | detailed | route-0013 | src flow_batchnorm.stats:mean_var -> flow_batchnorm.stats:out.aux0; expected []; expanded scope has no declared interface for mean_var |
| flow_batchnorm | detailed | route-0013 | dst flow_batchnorm.normalize:in -> flow_batchnorm.normalize:in.aux0; expected [('flow_batchnorm.norm', 'in')]; visible opaque/leaf endpoint |
| flow_batchnorm | detailed | route-0015 | dst flow_batchnorm.normalize:in -> flow_batchnorm.normalize:in.aux1; expected [('flow_batchnorm.norm', 'in')]; visible opaque/leaf endpoint |
| flow_batchnorm | detailed | route-0017 | src flow_batchnorm.stats:var -> flow_batchnorm.stats:out.aux2; expected []; expanded scope has no declared interface for var |
| flow_sequential | detailed | route-0012 | src flow_sequential.first:features -> flow_sequential.first:out.aux0; expected []; expanded scope has no declared interface for features |
| flow_sequential | detailed | route-0012 | dst flow_sequential.second:features -> flow_sequential.second:in; expected []; expanded scope has no declared interface for features |
| flow_sequential | detailed | route-0013 | dst flow_sequential.add0:accumulator -> flow_sequential.add0:in.aux0; expected []; expanded scope has no declared interface for accumulator |
| flow_sequential | detailed | route-0014 | src flow_sequential.first:logdet -> flow_sequential.first:out.aux1; expected []; expanded scope has no declared interface for logdet |
| flow_sequential | detailed | route-0014 | dst flow_sequential.add0:increment -> flow_sequential.add0:in.aux1; expected []; expanded scope has no declared interface for increment |
| flow_sequential | detailed | route-0015 | dst flow_sequential.add1:accumulator -> flow_sequential.add1:in.aux0; expected []; expanded scope has no declared interface for accumulator |
| flow_sequential | detailed | route-0016 | src flow_sequential.second:logdet -> flow_sequential.second:out.aux0; expected []; expanded scope has no declared interface for logdet |
| flow_sequential | detailed | route-0016 | dst flow_sequential.add1:increment -> flow_sequential.add1:in.aux1; expected []; expanded scope has no declared interface for increment |
| flow_sequential | detailed | route-0017 | src flow_sequential.second:features -> flow_sequential.second:out.aux1; expected []; expanded scope has no declared interface for features |
| glow_actnorm | detailed | route-0012 | src glow_actnorm.init:out -> glow_actnorm.init:out.aux0; expected [('glow_actnorm.copy', 'out')]; visible opaque/leaf endpoint |
| glow_actnorm | detailed | route-0012 | dst glow_actnorm.affine:in -> glow_actnorm.affine:in.aux0; expected [('glow_actnorm.shift', 'in')]; visible opaque/leaf endpoint |
| glow_actnorm | detailed | route-0013 | dst glow_actnorm.affine:in -> glow_actnorm.affine:in.aux1; expected [('glow_actnorm.shift', 'in')]; visible opaque/leaf endpoint |
| glow_actnorm | detailed | route-0014 | src glow_actnorm.init:out -> glow_actnorm.init:out.aux1; expected [('glow_actnorm.copy', 'out')]; visible opaque/leaf endpoint |
| glow_additive_coupling | detailed | route-0016 | src glow_additive_coupling.split:a -> glow_additive_coupling.split:out.aux0; expected []; expanded scope has no declared interface for a |
| glow_additive_coupling | detailed | route-0017 | dst glow_additive_coupling.transform:in -> glow_additive_coupling.transform:in.aux0; expected [('glow_additive_coupling.addop', 'in')]; visible opaque/leaf endpoint |
| glow_additive_coupling | detailed | route-0018 | src glow_additive_coupling.split:b -> glow_additive_coupling.split:out.aux1; expected []; expanded scope has no declared interface for b |
| glow_additive_coupling | detailed | route-0018 | dst glow_additive_coupling.transform:in -> glow_additive_coupling.transform:in.aux1; expected [('glow_additive_coupling.addop', 'in')]; visible opaque/leaf endpoint |
| glow_additive_coupling | detailed | route-0019 | dst glow_additive_coupling.join:out_b -> glow_additive_coupling.join:in.aux0; expected []; expanded scope has no declared interface for out_b |
| glow_additive_coupling | detailed | route-0020 | src glow_additive_coupling.split:a -> glow_additive_coupling.split:out.aux2; expected []; expanded scope has no declared interface for a |
| glow_additive_coupling | detailed | route-0020 | dst glow_additive_coupling.join:in_a -> glow_additive_coupling.join:in.aux1; expected []; expanded scope has no declared interface for in_a |
| glow_affine_coupling | detailed | route-0022 | src glow_affine_coupling.split:a -> glow_affine_coupling.split:out.aux0; expected []; expanded scope has no declared interface for a |
| glow_affine_coupling | detailed | route-0024 | src glow_affine_coupling.heads:t -> glow_affine_coupling.heads:out.aux0; expected []; expanded scope has no declared interface for t |
| glow_affine_coupling | detailed | route-0024 | dst glow_affine_coupling.shift:in -> glow_affine_coupling.shift:in.aux0; expected [('glow_affine_coupling.shiftop', 'in')]; visible opaque/leaf endpoint |
| glow_affine_coupling | detailed | route-0025 | src glow_affine_coupling.heads:log_s -> glow_affine_coupling.heads:out.aux1; expected []; expanded scope has no declared interface for log_s |
| glow_affine_coupling | detailed | route-0026 | src glow_affine_coupling.split:b -> glow_affine_coupling.split:out.aux1; expected []; expanded scope has no declared interface for b |
| glow_affine_coupling | detailed | route-0026 | dst glow_affine_coupling.shift:in -> glow_affine_coupling.shift:in.aux1; expected [('glow_affine_coupling.shiftop', 'in')]; visible opaque/leaf endpoint |
| glow_affine_coupling | detailed | route-0027 | dst glow_affine_coupling.transform:in -> glow_affine_coupling.transform:in.aux0; expected [('glow_affine_coupling.mulop', 'in')]; visible opaque/leaf endpoint |
| glow_affine_coupling | detailed | route-0028 | src glow_affine_coupling.scale:out -> glow_affine_coupling.scale:out.aux0; expected [('glow_affine_coupling.scaleop', 'out')]; visible opaque/leaf endpoint |
| glow_affine_coupling | detailed | route-0028 | dst glow_affine_coupling.transform:scale -> glow_affine_coupling.transform:in.aux1; expected []; expanded scope has no declared interface for scale |
| glow_affine_coupling | detailed | route-0029 | src glow_affine_coupling.scale:out -> glow_affine_coupling.scale:out.aux1; expected [('glow_affine_coupling.scaleop', 'out')]; visible opaque/leaf endpoint |
| glow_affine_coupling | detailed | route-0030 | dst glow_affine_coupling.join:out_b -> glow_affine_coupling.join:in.aux0; expected []; expanded scope has no declared interface for out_b |
| glow_affine_coupling | detailed | route-0031 | src glow_affine_coupling.split:a -> glow_affine_coupling.split:out.aux2; expected []; expanded scope has no declared interface for a |
| glow_affine_coupling | detailed | route-0031 | dst glow_affine_coupling.join:in_a -> glow_affine_coupling.join:in.aux1; expected []; expanded scope has no declared interface for in_a |
| glow_invconv | detailed | route-0008 | src glow_invconv.weight:out -> glow_invconv.weight:out.aux0; expected [('glow_invconv.weight_read', 'out')]; visible opaque/leaf endpoint |
| glow_invconv | detailed | route-0008 | dst glow_invconv.conv:in -> glow_invconv.conv:in.aux0; expected [('glow_invconv.convop', 'in')]; visible opaque/leaf endpoint |
| glow_invconv | detailed | route-0009 | dst glow_invconv.conv:in -> glow_invconv.conv:in.aux1; expected [('glow_invconv.convop', 'in')]; visible opaque/leaf endpoint |
| glow_invconv | detailed | route-0010 | src glow_invconv.weight:out -> glow_invconv.weight:out.aux1; expected [('glow_invconv.weight_read', 'out')]; visible opaque/leaf endpoint |
| glow_invconv_lu | detailed | route-0009 | dst glow_invconv_lu.conv:in -> glow_invconv_lu.conv:in.aux0; expected [('glow_invconv_lu.convop', 'in')]; visible opaque/leaf endpoint |
| glow_invconv_lu | detailed | route-0010 | dst glow_invconv_lu.conv:in -> glow_invconv_lu.conv:in.aux1; expected [('glow_invconv_lu.convop', 'in')]; visible opaque/leaf endpoint |
| glow_split_prior | detailed | route-0012 | src glow_split_prior.split:out -> glow_split_prior.split:out.aux0; expected [('glow_split_prior.splitop', 'out')]; visible opaque/leaf endpoint |
| glow_split_prior | detailed | route-0013 | src glow_split_prior.split:out -> glow_split_prior.split:out.aux1; expected [('glow_split_prior.splitop', 'out')]; visible opaque/leaf endpoint |
| glow_split_prior | detailed | route-0014 | src glow_split_prior.split:z_new -> glow_split_prior.split:out.aux2; expected []; expanded scope has no declared interface for z_new |
| glow_split_prior | detailed | route-0016 | src glow_split_prior.heads:mean_log_sd -> glow_split_prior.heads:out; expected []; expanded scope has no declared interface for mean_log_sd |
| glow_split_prior | detailed | route-0016 | dst glow_split_prior.density:parameters -> glow_split_prior.density:in.aux0; expected []; expanded scope has no declared interface for parameters |
| glow_split_prior | detailed | route-0017 | src glow_split_prior.split:z_new -> glow_split_prior.split:out.aux3; expected []; expanded scope has no declared interface for z_new |
| glow_split_prior | detailed | route-0017 | dst glow_split_prior.density:sample -> glow_split_prior.density:in.aux1; expected []; expanded scope has no declared interface for sample |
| made_affine | detailed | route-0019 | src made_affine.heads:m -> made_affine.heads:out.aux0; expected []; expanded scope has no declared interface for m |
| made_affine | detailed | route-0019 | dst made_affine.shift:m -> made_affine.shift:in.aux0; expected []; expanded scope has no declared interface for m |
| made_affine | detailed | route-0020 | src made_affine.heads:a -> made_affine.heads:out.aux1; expected []; expanded scope has no declared interface for a |
| made_affine | detailed | route-0021 | src made_affine.heads:a -> made_affine.heads:out.aux2; expected []; expanded scope has no declared interface for a |
| made_affine | detailed | route-0022 | dst made_affine.shift:in -> made_affine.shift:in.aux1; expected [('made_affine.sub', 'in')]; visible opaque/leaf endpoint |
| made_affine | detailed | route-0023 | dst made_affine.affine:in -> made_affine.affine:in.aux0; expected [('made_affine.mul', 'in')]; visible opaque/leaf endpoint |
| made_affine | detailed | route-0024 | dst made_affine.affine:scale -> made_affine.affine:in.aux1; expected []; expanded scope has no declared interface for scale |
| made_split | detailed | route-0023 | dst made_split.shift:m -> made_split.shift:in.aux0; expected []; expanded scope has no declared interface for m |
| made_split | detailed | route-0024 | src made_split.anet:out -> made_split.anet:out.aux0; expected [('made_split.anetout', 'out')]; visible opaque/leaf endpoint |
| made_split | detailed | route-0025 | src made_split.anet:out -> made_split.anet:out.aux1; expected [('made_split.anetout', 'out')]; visible opaque/leaf endpoint |
| made_split | detailed | route-0026 | dst made_split.shift:in -> made_split.shift:in.aux1; expected [('made_split.sub', 'in')]; visible opaque/leaf endpoint |
| made_split | detailed | route-0027 | dst made_split.affine:in -> made_split.affine:in.aux0; expected [('made_split.mul', 'in')]; visible opaque/leaf endpoint |
| made_split | detailed | route-0028 | dst made_split.affine:scale -> made_split.affine:in.aux1; expected []; expanded scope has no declared interface for scale |
| manual_fused_bn | detailed | route-0013 | src manual_fused_bn.stats:var -> manual_fused_bn.stats:out.aux0; expected []; expanded scope has no declared interface for var |
| manual_fused_bn | detailed | route-0013 | dst manual_fused_bn.scale:in -> manual_fused_bn.scale:in.aux0; expected [('manual_fused_bn.rsqrt', 'in')]; visible opaque/leaf endpoint |
| manual_fused_bn | detailed | route-0014 | dst manual_fused_bn.scale:gain -> manual_fused_bn.scale:in.aux1; expected []; expanded scope has no declared interface for gain |
| manual_fused_bn | detailed | route-0015 | src manual_fused_bn.stats:mean -> manual_fused_bn.stats:out.aux1; expected []; expanded scope has no declared interface for mean |
| manual_fused_bn | detailed | route-0015 | dst manual_fused_bn.shift:mean -> manual_fused_bn.shift:in.aux0; expected []; expanded scope has no declared interface for mean |
| manual_fused_bn | detailed | route-0016 | src manual_fused_bn.scale:out -> manual_fused_bn.scale:out.aux0; expected [('manual_fused_bn.gainop', 'out')]; visible opaque/leaf endpoint |
| manual_fused_bn | detailed | route-0016 | dst manual_fused_bn.shift:scale -> manual_fused_bn.shift:in.aux1; expected []; expanded scope has no declared interface for scale |
| manual_fused_bn | detailed | route-0017 | dst manual_fused_bn.shift:bias -> manual_fused_bn.shift:in.aux2; expected []; expanded scope has no declared interface for bias |
| manual_fused_bn | detailed | route-0018 | src manual_fused_bn.scale:out -> manual_fused_bn.scale:out.aux1; expected [('manual_fused_bn.gainop', 'out')]; visible opaque/leaf endpoint |
| manual_fused_bn | detailed | route-0018 | dst manual_fused_bn.affine:scale -> manual_fused_bn.affine:in.aux0; expected []; expanded scope has no declared interface for scale |
| manual_fused_bn | detailed | route-0019 | dst manual_fused_bn.affine:shift -> manual_fused_bn.affine:in.aux1; expected []; expanded scope has no declared interface for shift |
| manual_fused_bn | detailed | route-0020 | dst manual_fused_bn.affine:in -> manual_fused_bn.affine:in.aux2; expected [('manual_fused_bn.out', 'in')]; visible opaque/leaf endpoint |
| masked_linear | detailed | route-0010 | dst masked_linear.sum:in -> masked_linear.sum:in.aux0; expected [('masked_linear.add', 'in')]; visible opaque/leaf endpoint |
| masked_linear | detailed | route-0011 | dst masked_linear.sum:condition -> masked_linear.sum:in.aux1; expected []; expanded scope has no declared interface for condition |
| nonlocal_attention | detailed | route-0023 | dst nonlocal_attention.beta:theta -> nonlocal_attention.beta:in.aux0; expected []; expanded scope has no declared interface for theta |
| nonlocal_attention | detailed | route-0024 | dst nonlocal_attention.beta:phi -> nonlocal_attention.beta:in.aux1; expected []; expanded scope has no declared interface for phi |
| nonlocal_attention | detailed | route-0025 | dst nonlocal_attention.aggregate:beta -> nonlocal_attention.aggregate:in.aux0; expected []; expanded scope has no declared interface for beta |
| nonlocal_attention | detailed | route-0026 | dst nonlocal_attention.aggregate:values -> nonlocal_attention.aggregate:in.aux1; expected []; expanded scope has no declared interface for values |
| qanet_context_query_attention | detailed | route-0024 | src cq.s1:out -> cq.s1:out.aux0; expected [('cq.softmax1', 'out')]; visible opaque/leaf endpoint |
| qanet_context_query_attention | detailed | route-0026 | src cq.s1:out -> cq.s1:out.aux1; expected [('cq.softmax1', 'out')]; visible opaque/leaf endpoint |
| realnvp_coupling | detailed | route-0015 | dst realnvp_coupling.masked:in -> realnvp_coupling.masked:in.aux0; expected [('realnvp_coupling.maskedop', 'in')]; visible opaque/leaf endpoint |
| realnvp_coupling | detailed | route-0016 | dst realnvp_coupling.masked:in -> realnvp_coupling.masked:in.aux1; expected [('realnvp_coupling.maskedop', 'in')]; visible opaque/leaf endpoint |
| realnvp_coupling | detailed | route-0017 | src realnvp_coupling.masked:out -> realnvp_coupling.masked:out.aux0; expected [('realnvp_coupling.maskedop', 'out')]; visible opaque/leaf endpoint |
| realnvp_coupling | detailed | route-0018 | src realnvp_coupling.masked:out -> realnvp_coupling.masked:out.aux1; expected [('realnvp_coupling.maskedop', 'out')]; visible opaque/leaf endpoint |
| realnvp_coupling | detailed | route-0019 | src realnvp_coupling.snet:out -> realnvp_coupling.snet:out.aux0; expected [('realnvp_coupling.smask', 'out')]; visible opaque/leaf endpoint |
| realnvp_coupling | detailed | route-0020 | src realnvp_coupling.snet:out -> realnvp_coupling.snet:out.aux1; expected [('realnvp_coupling.smask', 'out')]; visible opaque/leaf endpoint |
| realnvp_coupling | detailed | route-0021 | dst realnvp_coupling.affine:scale -> realnvp_coupling.affine:in.aux0; expected []; expanded scope has no declared interface for scale |
| realnvp_coupling | detailed | route-0022 | dst realnvp_coupling.affine:t -> realnvp_coupling.affine:in.aux1; expected []; expanded scope has no declared interface for t |
| realnvp_coupling | detailed | route-0023 | dst realnvp_coupling.affine:in -> realnvp_coupling.affine:in.aux2; expected [('realnvp_coupling.mul', 'in')]; visible opaque/leaf endpoint |
| sigmoid_bijector | detailed | route-0007 | src sigmoid_bijector.nonlinear:out -> sigmoid_bijector.nonlinear:out.aux0; expected [('sigmoid_bijector.sigmoid', 'out')]; visible opaque/leaf endpoint |
| sigmoid_bijector | detailed | route-0008 | src sigmoid_bijector.nonlinear:out -> sigmoid_bijector.nonlinear:out.aux1; expected [('sigmoid_bijector.sigmoid', 'out')]; visible opaque/leaf endpoint |
| spectral_filter | detailed | route-0019 | src spectral.basis_init:out -> spectral.basis_init:right; expected [('spectral.vbuffer', 'out')]; visible opaque/leaf endpoint |
| spectral_filter | detailed | route-0020 | src spectral.w_init:out -> spectral.w_init:right; expected [('spectral.wbuffer', 'out')]; visible opaque/leaf endpoint |
| spectral_norm_linear | detailed | route-0012 | dst spectral_norm_linear.normalize:in -> spectral_norm_linear.normalize:in.aux0; expected [('spectral_norm_linear.divide', 'in')]; visible opaque/leaf endpoint |
| spectral_norm_linear | detailed | route-0013 | dst spectral_norm_linear.normalize:in -> spectral_norm_linear.normalize:in.aux1; expected [('spectral_norm_linear.divide', 'in')]; visible opaque/leaf endpoint |
| spectral_norm_linear | detailed | route-0014 | dst spectral_norm_linear.linear:in -> spectral_norm_linear.linear:in.aux0; expected [('spectral_norm_linear.linearop', 'in')]; visible opaque/leaf endpoint |
| spectral_norm_linear | detailed | route-0015 | dst spectral_norm_linear.linear:in -> spectral_norm_linear.linear:in.aux1; expected [('spectral_norm_linear.linearop', 'in')]; visible opaque/leaf endpoint |
| transformer_xl_relative | detailed | route-0024 | src txl.shift:out -> txl.shift:out; expected [('txl.shift_slice', 'out')]; visible opaque/leaf endpoint |

JSON 保留每条显式箭头的源码符号/行号、IR 端口、期望可见节点、实际布局端口和 SVG 坐标。
折叠容器可作为不透明摘要；展开容器必须有真实边界续线或显式接口绑定。布局 rank 不能充当数据依赖。
本检查没有执行模型；叶子命名端口的值身份仍依赖可审查的源码适配合同，不能仅由 SVG 像素证明。
