# Glow affine coupling

本例补充的是 **模块/选定子图**，范围：`One AffineCoupling with affine=True; forward only, independent reviewed branch profile.`。

入口：[三粒度图](../generated/glow_affine_coupling/index.html) · [逐节点源码映射](../generated/glow_affine_coupling/source_map.md) · [语义 IR](../generated/glow_affine_coupling/semantic_ir.json)。

## 固定源码与配置

- 索引：Awesome-pytorch-list README 第 695 行。
- 实现：[rosinality/glow-pytorch@97081ff115a6](https://github.com/rosinality/glow-pytorch/blob/97081ff115a694cf04aeedbd58447f33d242c879/model.py)。
- 选取入口：`AffineCoupling.forward`。Notebook 原单元/派生行映射保存在证据中。
- 配置均为静态代表值，不是张量实际执行记录；不运行训练、源码 import 或模型。

```json
{
  "affine": true,
  "channels": 8,
  "filter_size": 16,
  "split_dim": 1,
  "head_order": [
    "log_s",
    "t"
  ],
  "logdet_type": "per_batch"
}
```

## 源码结构到图元

| 分组 / 节点 | 源码调用或公式 | 参数与状态身份 | 为何对应 |
| --- | --- | --- | --- |
| Channel split / `splitop` | `input.chunk(2, 1)` | Parameter: []; buffer: [] | chunk(2, dim=1)；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Conditioner / a only / `conv1` | `AffineCoupling.__init__` | Parameter: ['net.0.weight', 'net.0.bias']; buffer: [] | Conv3x3 4 -> 16；`kind=conv2d` 表示真实操作类别，颜色单独表示视觉角色 |
| Conditioner / a only / `relu1` | `AffineCoupling.__init__` | Parameter: []; buffer: [] | ReLU inplace；`kind=activation` 表示真实操作类别，颜色单独表示视觉角色 |
| Conditioner / a only / `conv2` | `AffineCoupling.__init__` | Parameter: ['net.2.weight', 'net.2.bias']; buffer: [] | Conv1x1 16 -> 16；`kind=conv2d` 表示真实操作类别，颜色单独表示视觉角色 |
| Conditioner / a only / `relu2` | `AffineCoupling.__init__` | Parameter: []; buffer: [] | ReLU inplace；`kind=activation` 表示真实操作类别，颜色单独表示视觉角色 |
| Conditioner / a only / `zero` | `ZeroConv2d.__init__, ZeroConv2d.forward, AffineCoupling.__init__` | Parameter: []; buffer: [] | ZeroConv2d 16 -> 8；`kind=conv2d` 表示真实操作类别，颜色单独表示视觉角色 |
| Split scale / translation / `headsop` | `self.net(in_a).chunk(2, 1)` | Parameter: []; buffer: [] | chunk -> log_s, t；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Positive scale / `scaleop` | `F.sigmoid(log_s + 2)` | Parameter: []; buffer: [] | sigmoid(log_s + 2)；`kind=sigmoid` 表示真实操作类别，颜色单独表示视觉角色 |
| Shift b / `shiftop` | `in_b + t` | Parameter: []; buffer: [] | in_b + t；`kind=add` 表示真实操作类别，颜色单独表示视觉角色 |
| Scale shifted b / `mulop` | `(in_b + t) * s` | Parameter: []; buffer: [] | (in_b + t) * s；`kind=multiply` 表示真实操作类别，颜色单独表示视觉角色 |
| Per-example logdet / `detop` | `torch.sum(torch.log(s).view(input.shape[0], -1), 1)` | Parameter: []; buffer: [] | sum log(s) / C,H,W；`kind=density` 表示真实操作类别，颜色单独表示视觉角色 |
| Retain a + transformed b / `catop` | `torch.cat([in_a, out_b], 1)` | Parameter: []; buffer: [] | cat([in_a,out_b],dim=1)；`kind=concat` 表示真实操作类别，颜色单独表示视觉角色 |

## 依赖、并列与参数对应

- Conditioner consumes only a; b is retained through a separate update path. The two channel halves are rejoined in original order.
- Affine branch uses sigmoid(log_s+2) and (b+t)*s; it does not use exp(log_s).
- ZeroConv2d remains a source-defined call boundary; its expanded module is available separately.

| 源节点端口 | 目标节点端口 | 含义 |
| --- | --- | --- |
| `x:out` | `split:in` | tensor |
| `split:a` | `net:in` | tensor |
| `net:out` | `heads:in` | tensor |
| `heads:t` | `shift:in` | tensor |
| `heads:log_s` | `scale:in` | tensor |
| `split:b` | `shift:in` | tensor |
| `shift:out` | `transform:in` | tensor |
| `scale:out` | `transform:scale` | tensor |
| `scale:out` | `det:in` | tensor |
| `transform:out` | `join:out_b` | tensor |
| `split:a` | `join:in_a` | retained_value |
| `join:out` | `y:in` | tensor |
| `det:out` | `ld:in` | tensor |
| `x:shape` | `detop:shape` | shape_dependency |

## 程序化排布

三个粒度使用同一个完整语义 IR：概览折叠 body，模块图展开阶段容器，详细图展开每阶段内的调用。折叠只投影视图端点，不改变数据依赖。
底到顶 ranks 依次是：`[['split'], ['net'], ['heads'], ['shift', 'scale'], ['transform', 'det'], ['join']]`。每行并列的阶段具有独立支路或输出；rank 本身不生成任何数据边。root 输入在底部、返回值在顶部，同一 tuple 的输出保持并列。
每个阶段尺寸由文字/形状标签与子节点尺寸计算。阶段间距 76px、列间距 58px 为两端各 24px 的箭头预留通道；路由器以 bbox 和真实端口避让边框，末段至少 18px。内部顺序调用自底向上；旁路/权重/状态使用 typed edge，不因并列或同色而暗示共享参数。
紫色用于 Linear/矩阵，蓝色用于卷积和重排，黄色用于归一化或算术，绿色用于概率/非线性，灰色用于状态。一个类别可以跨不同模块复用；共享与独立身份以 IR 的 parameters/module_identity 为准。

## 避免教科书模板替代源码

- Do not exchange shift/scale order or feed b into the conditioner.
- This is one coupling block, not the Glow architecture.

## 复用与验证

`module_adapters/glow_affine_coupling.py` 调用 `root_support.build_case()`，显式配置集中在 `root_definitions.py`。这复用图元和布局机制，仍不是任意源码自动识别。
`checks/flow_generative_extended.py` 使用独立 AST 子树对照关键公式，并注入删除关键依赖、改变参数/操作、错误配置等负例；`verify.py --png` 对实际 SVG、PNG、源码副本及哈希核验。
PyTorch/SciPy 算子的内部 kernel 为调用边界；初始化、反向分支和训练状态只按明确选定 profile 展示。更换 commit 或 profile 必须先复查语义与来源。
