# Conditional BatchNorm / two condition heads

本例补充的是 **模块/选定子图**，范围：`ccbn with norm_style=bn, mybn=False, cross_replica=False, which_linear=nn.Linear selected.`。

入口：[三粒度图](../generated/conditional_bn/index.html) · [逐节点源码映射](../generated/conditional_bn/source_map.md) · [语义 IR](../generated/conditional_bn/semantic_ir.json)。

## 固定源码与配置

- 索引：Awesome-pytorch-list README 第 681 行。
- 实现：[ajbrock/BigGAN-PyTorch@98459431a5d6](https://github.com/ajbrock/BigGAN-PyTorch/blob/98459431a5d618d644d54cd1e9fceb1e5045648d/layers.py)。
- 选取入口：`ccbn.forward`。Notebook 原单元/派生行映射保存在证据中。
- 配置均为静态代表值，不是张量实际执行记录；不运行训练、源码 import 或模型。

```json
{
  "output_size": 8,
  "input_size": 16,
  "which_linear": "nn.Linear explicitly selected",
  "cross_replica": false,
  "mybn": false,
  "norm_style": "bn",
  "training": true,
  "source_momentum_literal": 0.1
}
```

## 源码结构到图元

| 分组 / 节点 | 源码调用或公式 | 参数与状态身份 | 为何对应 |
| --- | --- | --- | --- |
| BatchNorm without affine / `bn` | `F.batch_norm(x, self.stored_mean, self.stored_var, None, None, self.training, 0.1, self.eps)` | Parameter: []; buffer: ['stored_mean', 'stored_var'] | F.batch_norm / affine=None；`kind=norm` 表示真实操作类别，颜色单独表示视觉角色 |
| Gain from condition / `gainlinear` | `ccbn.__init__, ccbn.forward` | Parameter: ['gain.weight', 'gain.bias']; buffer: [] | Independent Linear 16 -> 8；`kind=linear` 表示真实操作类别，颜色单独表示视觉角色 |
| Gain from condition / `gainview` | `(1 + self.gain(y)).view(y.size(0), -1, 1, 1)` | Parameter: []; buffer: [] | 1+gain(y); view B,C,1,1；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Bias from condition / `biaslinear` | `ccbn.__init__, ccbn.forward` | Parameter: ['bias.weight', 'bias.bias']; buffer: [] | Independent Linear 16 -> 8；`kind=linear` 表示真实操作类别，颜色单独表示视觉角色 |
| Bias from condition / `biasview` | `self.bias(y).view(y.size(0), -1, 1, 1)` | Parameter: []; buffer: [] | bias(y); view B,C,1,1；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Condition scale / `mul` | `out * gain` | Parameter: []; buffer: [] | out * gain；`kind=multiply` 表示真实操作类别，颜色单独表示视觉角色 |
| Condition shift / `addop` | `out * gain + bias` | Parameter: []; buffer: [] | scaled + bias；`kind=add` 表示真实操作类别，颜色单独表示视觉角色 |

## 依赖、并列与参数对应

- Two independent condition heads predict per-example gain and bias; gain has an explicit +1 offset.
- Feature normalization has no affine parameters. stored_mean/var are buffers and the selected training call may update them inside the library.
- F.batch_norm receives literal momentum .1, irrespective of the constructor self.momentum attribute.
- Other branches are excluded. The GN path references self.normstyle, a source typo, and is not silently repaired.

| 源节点端口 | 目标节点端口 | 含义 |
| --- | --- | --- |
| `x:out` | `norm:in` | tensor |
| `condition:out` | `gain:in` | tensor |
| `condition:out` | `bias:in` | tensor |
| `norm:out` | `multiply:in` | tensor |
| `gain:out` | `multiply:gain` | tensor |
| `multiply:out` | `add:in` | tensor |
| `bias:out` | `add:bias` | tensor |
| `add:out` | `y:in` | tensor |

## 程序化排布

三个粒度使用同一个完整语义 IR：概览折叠 body，模块图展开阶段容器，详细图展开每阶段内的调用。折叠只投影视图端点，不改变数据依赖。
底到顶 ranks 依次是：`[['norm', 'gain', 'bias'], ['multiply'], ['add']]`。每行并列的阶段具有独立支路或输出；rank 本身不生成任何数据边。root 输入在底部、返回值在顶部，同一 tuple 的输出保持并列。
每个阶段尺寸由文字/形状标签与子节点尺寸计算。阶段间距 76px、列间距 58px 为两端各 24px 的箭头预留通道；路由器以 bbox 和真实端口避让边框，末段至少 18px。内部顺序调用自底向上；旁路/权重/状态使用 typed edge，不因并列或同色而暗示共享参数。
紫色用于 Linear/矩阵，蓝色用于卷积和重排，黄色用于归一化或算术，绿色用于概率/非线性，灰色用于状态。一个类别可以跨不同模块复用；共享与独立身份以 IR 的 parameters/module_identity 为准。

## 避免教科书模板替代源码

- Do not replace conditional y by class indices or one-hot embeddings absent from this boundary.

## 复用与验证

`module_adapters/conditional_bn.py` 调用 `root_support.build_case()`，显式配置集中在 `root_definitions.py`。这复用图元和布局机制，仍不是任意源码自动识别。
`checks/flow_generative_extended.py` 使用独立 AST 子树对照关键公式，并注入删除关键依赖、改变参数/操作、错误配置等负例；`verify.py --png` 对实际 SVG、PNG、源码副本及哈希核验。
PyTorch/SciPy 算子的内部 kernel 为调用边界；初始化、反向分支和训练状态只按明确选定 profile 展示。更换 commit 或 profile 必须先复查语义与来源。
