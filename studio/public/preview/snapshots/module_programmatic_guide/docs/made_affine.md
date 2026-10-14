# MADE / autoregressive affine

本例补充的是 **模块/选定子图**，范围：`MADE forward direct branch only; inverse loop is documented rather than falsely parallelized.`。

入口：[三粒度图](../generated/made_affine/index.html) · [逐节点源码映射](../generated/made_affine/source_map.md) · [语义 IR](../generated/made_affine/semantic_ir.json)。

## 固定源码与配置

- 索引：Awesome-pytorch-list README 第 631 行。
- 实现：[ikostrikov/pytorch-flows@bf12ed91b868](https://github.com/ikostrikov/pytorch-flows/blob/bf12ed91b86867b38d74982f5e2d44c248604df9/flows.py)。
- 选取入口：`MADE.forward`。Notebook 原单元/派生行映射保存在证据中。
- 配置均为静态代表值，不是张量实际执行记录；不运行训练、源码 import 或模型。

```json
{
  "num_inputs": 4,
  "num_hidden": 8,
  "num_cond_inputs": null,
  "mode": "direct",
  "pre_exp_tanh": false,
  "independent_networks": false,
  "head_order": [
    "m",
    "a"
  ],
  "inverse": "sequential coordinate loop; same parameters"
}
```

## 源码结构到图元

| 分组 / 节点 | 源码调用或公式 | 参数与状态身份 | 为何对应 |
| --- | --- | --- | --- |
| Shared masked network / `netjoin` | `MADE.__init__, MaskedLinear.forward` | Parameter: ['joiner.linear.weight', 'joiner.linear.bias']; buffer: [] | MaskedLinear 4 -> 8；`kind=masked_linear` 表示真实操作类别，颜色单独表示视觉角色 |
| Shared masked network / `netact1` | `MADE.__init__` | Parameter: []; buffer: [] | ReLU；`kind=activation` 表示真实操作类别，颜色单独表示视觉角色 |
| Shared masked network / `nethidden` | `MADE.__init__, MaskedLinear.forward` | Parameter: ['trunk.1.linear.weight', 'trunk.1.linear.bias']; buffer: [] | MaskedLinear 8 -> 8；`kind=masked_linear` 表示真实操作类别，颜色单独表示视觉角色 |
| Shared masked network / `netact2` | `MADE.__init__` | Parameter: []; buffer: [] | ReLU；`kind=activation` 表示真实操作类别，颜色单独表示视觉角色 |
| Shared masked network / `netout` | `MADE.__init__, MaskedLinear.forward` | Parameter: ['trunk.3.linear.weight', 'trunk.3.linear.bias']; buffer: [] | MaskedLinear 8 -> 8；`kind=masked_linear` 表示真实操作类别，颜色单独表示视觉角色 |
| Split m and a / `chunk` | `self.trunk(h).chunk(2, 1)` | Parameter: []; buffer: [] | chunk(2,dim=1)；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Subtract conditional mean / `sub` | `inputs - m` | Parameter: []; buffer: [] | inputs - m；`kind=subtract` 表示真实操作类别，颜色单独表示视觉角色 |
| Inverse scale / `exp` | `torch.exp(-a)` | Parameter: []; buffer: [] | exp(-a)；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Affine output / `mul` | `(inputs - m) * torch.exp(-a)` | Parameter: []; buffer: [] | (inputs-m) * exp(-a)；`kind=multiply` 表示真实操作类别，颜色单独表示视觉角色 |
| Log determinant / `sum` | `-a.sum(-1, keepdim=True)` | Parameter: []; buffer: [] | -a.sum(-1,keepdim=True)；`kind=density` 表示真实操作类别，颜色单独表示视觉角色 |

## 依赖、并列与参数对应

- Degree masks enforce strict autoregressive dependence through the output degree offset; masks are registered buffers.
- MADE shares a masked trunk and chunks its 2D output into m then a; pre_exp_tanh is accepted but unused by this class.
- Inverse builds coordinates one at a time with the same learned networks; the direct view is a DAG, not that inverse execution.
- The returned logdet follows the exact source expression. It is not a third sequential layer applied to u.

| 源节点端口 | 目标节点端口 | 含义 |
| --- | --- | --- |
| `x:out` | `net:in` | tensor |
| `net:out` | `heads:in` | tensor |
| `heads:m` | `shift:m` | tensor |
| `heads:a` | `scale:in` | tensor |
| `heads:a` | `det:in` | tensor |
| `x:out` | `shift:in` | retained_value |
| `shift:out` | `affine:in` | tensor |
| `scale:out` | `affine:scale` | tensor |
| `affine:out` | `u:in` | tensor |
| `det:out` | `ld:in` | tensor |

## 程序化排布

三个粒度使用同一个完整语义 IR：概览折叠 body，模块图展开阶段容器，详细图展开每阶段内的调用。折叠只投影视图端点，不改变数据依赖。
底到顶 ranks 依次是：`[['net'], ['heads'], ['shift', 'scale', 'det'], ['affine']]`。每行并列的阶段具有独立支路或输出；rank 本身不生成任何数据边。root 输入在底部、返回值在顶部，同一 tuple 的输出保持并列。
每个阶段尺寸由文字/形状标签与子节点尺寸计算。阶段间距 76px、列间距 58px 为两端各 24px 的箭头预留通道；路由器以 bbox 和真实端口避让边框，末段至少 18px。内部顺序调用自底向上；旁路/权重/状态使用 typed edge，不因并列或同色而暗示共享参数。
紫色用于 Linear/矩阵，蓝色用于卷积和重排，黄色用于归一化或算术，绿色用于概率/非线性，灰色用于状态。一个类别可以跨不同模块复用；共享与独立身份以 IR 的 parameters/module_identity 为准。

## 避免教科书模板替代源码

- Do not swap m/a, use dense unmasked hidden layers, or claim pre_exp_tanh acts in MADE.

## 复用与验证

`module_adapters/made_affine.py` 调用 `root_support.build_case()`，显式配置集中在 `root_definitions.py`。这复用图元和布局机制，仍不是任意源码自动识别。
`checks/flow_generative_extended.py` 使用独立 AST 子树对照关键公式，并注入删除关键依赖、改变参数/操作、错误配置等负例；`verify.py --png` 对实际 SVG、PNG、源码副本及哈希核验。
PyTorch/SciPy 算子的内部 kernel 为调用边界；初始化、反向分支和训练状态只按明确选定 profile 展示。更换 commit 或 profile 必须先复查语义与来源。
