# Non-local 2D attention / pooled keys-values

本例补充的是 **模块/选定子图**，范围：`One BigGAN Attention module; SNConv2d is a normalized-weight call boundary, see separate SNLinear mechanism.`。

入口：[三粒度图](../generated/nonlocal_attention/index.html) · [逐节点源码映射](../generated/nonlocal_attention/source_map.md) · [语义 IR](../generated/nonlocal_attention/semantic_ir.json)。

## 固定源码与配置

- 索引：Awesome-pytorch-list README 第 681 行。
- 实现：[ajbrock/BigGAN-PyTorch@98459431a5d6](https://github.com/ajbrock/BigGAN-PyTorch/blob/98459431a5d618d644d54cd1e9fceb1e5045648d/layers.py)。
- 选取入口：`Attention.forward`。Notebook 原单元/派生行映射保存在证据中。
- 配置均为静态代表值，不是张量实际执行记录；不运行训练、源码 import 或模型。

```json
{
  "ch": 32,
  "input_shape": [
    "B",
    32,
    8,
    8
  ],
  "which_conv": "SNConv2d default",
  "theta_positions": 64,
  "phi_positions": 16,
  "g_positions": 16,
  "softmax_dim": -1,
  "gamma_initial": 0.0,
  "attention_scaling": null
}
```

## 源码结构到图元

| 分组 / 节点 | 源码调用或公式 | 参数与状态身份 | 为何对应 |
| --- | --- | --- | --- |
| Full-resolution theta / `theta_conv` | `Attention.__init__, Attention.forward, SNConv2d.forward` | Parameter: ['theta.weight']; buffer: [] | SNConv1x1 32 -> 4；`kind=conv2d` 表示真实操作类别，颜色单独表示视觉角色 |
| Full-resolution theta / `theta_view` | `theta.view(-1, self.ch // 8, x.shape[2] * x.shape[3])` | Parameter: []; buffer: [] | view B,4,64；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Pooled phi / `phi_conv` | `Attention.__init__, Attention.forward, SNConv2d.forward` | Parameter: ['phi.weight']; buffer: [] | SNConv1x1 32 -> 4；`kind=conv2d` 表示真实操作类别，颜色单独表示视觉角色 |
| Pooled phi / `phi_pool` | `F.max_pool2d(self.phi(x), [2, 2])` | Parameter: []; buffer: [] | MaxPool2x2; view B,4,16；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Pooled values g / `g_conv` | `Attention.__init__, Attention.forward, SNConv2d.forward` | Parameter: ['g.weight']; buffer: [] | SNConv1x1 32 -> 16；`kind=conv2d` 表示真实操作类别，颜色单独表示视觉角色 |
| Pooled values g / `g_pool` | `F.max_pool2d(self.g(x), [2, 2])` | Parameter: []; buffer: [] | MaxPool2x2; view B,16,16；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Spatial similarity / `score` | `torch.bmm(theta.transpose(1, 2), phi)` | Parameter: []; buffer: [] | theta.T @ phi；`kind=matmul` 表示真实操作类别，颜色单独表示视觉角色 |
| Spatial similarity / `softmax` | `F.softmax(torch.bmm(theta.transpose(1, 2), phi), -1)` | Parameter: []; buffer: [] | Softmax over pooled positions；`kind=softmax` 表示真实操作类别，颜色单独表示视觉角色 |
| Attend and restore space / `bmm` | `torch.bmm(g, beta.transpose(1, 2))` | Parameter: []; buffer: [] | g @ beta.T；`kind=matmul` 表示真实操作类别，颜色单独表示视觉角色 |
| Attend and restore space / `view` | `Attention.forward` | Parameter: []; buffer: [] | view B,16,8,8；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Attend and restore space / `o_conv` | `Attention.__init__, Attention.forward, SNConv2d.forward` | Parameter: ['o.weight']; buffer: [] | SNConv1x1 16 -> 32；`kind=conv2d` 表示真实操作类别，颜色单独表示视觉角色 |
| Learned residual gain / `gain` | `self.gamma * o` | Parameter: ['gamma']; buffer: [] | gamma * o；`kind=multiply` 表示真实操作类别，颜色单独表示视觉角色 |
| Learned residual gain / `add` | `self.gamma * o + x` | Parameter: []; buffer: [] | gamma*o + x；`kind=add` 表示真实操作类别，颜色单独表示视觉角色 |

## 依赖、并列与参数对应

- Theta remains full-resolution; phi and g use max pooling and therefore have four times fewer spatial positions.
- Softmax normalizes the last pooled-position axis. No 1/sqrt(d) scale or positional embedding appears.
- theta,phi,g,o weights are four independent instances; gamma is a learned scalar initialized zero.
- Source y argument is unused. It is not an additional condition input in this attention view.

| 源节点端口 | 目标节点端口 | 含义 |
| --- | --- | --- |
| `x:out` | `theta:in` | tensor |
| `x:out` | `phi:in` | tensor |
| `x:out` | `g:in` | tensor |
| `theta:out` | `beta:theta` | tensor |
| `phi:out` | `beta:phi` | tensor |
| `beta:out` | `aggregate:beta` | tensor |
| `g:out` | `aggregate:values` | tensor |
| `aggregate:out` | `residual:in` | tensor |
| `x:out` | `add:x` | retained_value |
| `residual:out` | `y:in` | tensor |
| `x:shape` | `theta_view:shape` | shape_dependency |
| `x:shape` | `phi_pool:shape` | shape_dependency |
| `x:shape` | `g_pool:shape` | shape_dependency |
| `x:shape` | `view:shape` | shape_dependency |

## 程序化排布

三个粒度使用同一个完整语义 IR：概览折叠 body，模块图展开阶段容器，详细图展开每阶段内的调用。折叠只投影视图端点，不改变数据依赖。
底到顶 ranks 依次是：`[['theta', 'phi', 'g'], ['beta'], ['aggregate'], ['residual']]`。每行并列的阶段具有独立支路或输出；rank 本身不生成任何数据边。root 输入在底部、返回值在顶部，同一 tuple 的输出保持并列。
每个阶段尺寸由文字/形状标签与子节点尺寸计算。阶段间距 76px、列间距 58px 为两端各 24px 的箭头预留通道；路由器以 bbox 和真实端口避让边框，末段至少 18px。内部顺序调用自底向上；旁路/权重/状态使用 typed edge，不因并列或同色而暗示共享参数。
紫色用于 Linear/矩阵，蓝色用于卷积和重排，黄色用于归一化或算术，绿色用于概率/非线性，灰色用于状态。一个类别可以跨不同模块复用；共享与独立身份以 IR 的 parameters/module_identity 为准。

## 避免教科书模板替代源码

- Do not label this standard full-resolution Transformer Q/K/V attention or permanently zero residual.

## 复用与验证

`module_adapters/nonlocal_attention.py` 调用 `root_support.build_case()`，显式配置集中在 `root_definitions.py`。这复用图元和布局机制，仍不是任意源码自动识别。
`checks/flow_generative_extended.py` 使用独立 AST 子树对照关键公式，并注入删除关键依赖、改变参数/操作、错误配置等负例；`verify.py --png` 对实际 SVG、PNG、源码副本及哈希核验。
PyTorch/SciPy 算子的内部 kernel 为调用边界；初始化、反向分支和训练状态只按明确选定 profile 展示。更换 commit 或 profile 必须先复查语义与来源。
