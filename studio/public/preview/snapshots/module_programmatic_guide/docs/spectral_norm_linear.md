# Spectral normalization / Linear wrapper

本例补充的是 **模块/选定子图**，范围：`One SNLinear with one power iteration/singular value; conv and embedding wrappers are excluded.`。

入口：[三粒度图](../generated/spectral_norm_linear/index.html) · [逐节点源码映射](../generated/spectral_norm_linear/source_map.md) · [语义 IR](../generated/spectral_norm_linear/semantic_ir.json)。

## 固定源码与配置

- 索引：Awesome-pytorch-list README 第 681 行。
- 实现：[ajbrock/BigGAN-PyTorch@98459431a5d6](https://github.com/ajbrock/BigGAN-PyTorch/blob/98459431a5d618d644d54cd1e9fceb1e5045648d/layers.py)。
- 选取入口：`SNLinear.forward`。Notebook 原单元/派生行映射保存在证据中。
- 配置均为静态代表值，不是张量实际执行记录；不运行训练、源码 import 或模型。

```json
{
  "in_features": 16,
  "out_features": 8,
  "num_svs": 1,
  "num_itrs": 1,
  "transpose": false,
  "training": true,
  "buffers": [
    "u0",
    "sv0"
  ],
  "parameters": [
    "weight",
    "bias"
  ],
  "sv_logging_only": true
}
```

## 源码结构到图元

| 分组 / 节点 | 源码调用或公式 | 参数与状态身份 | 为何对应 |
| --- | --- | --- | --- |
| Power iteration / 1 SV / `flatten` | `self.weight.view(self.weight.size(0), -1)` | Parameter: []; buffer: [] | W.view(out_channels,-1)；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Power iteration / 1 SV / `vectors` | `power_iteration, gram_schmidt` | Parameter: []; buffer: [] | v=norm(uW); u=norm(vW.T)；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Power iteration / 1 SV / `sigma` | `torch.squeeze(torch.matmul(torch.matmul(v, W.t()), u.t()))` | Parameter: []; buffer: [] | sigma = squeeze(v W.T u.T)；`kind=matmul` 表示真实操作类别，颜色单独表示视觉角色 |
| Normalize learned weight / `divide` | `self.weight / svs[0]` | Parameter: ['weight']; buffer: [] | weight / svs[0]；`kind=norm` 表示真实操作类别，颜色单独表示视觉角色 |
| Training-only buffer writes / `write` | `SN.W_, power_iteration` | Parameter: []; buffer: ['u0', 'sv0'] | Update u0 and logging sv0；`kind=control` 表示真实操作类别，颜色单独表示视觉角色 |
| F.linear with normalized weight / `linearop` | `F.linear(x, self.W_(), self.bias)` | Parameter: ['bias']; buffer: [] | F.linear(x,W_,bias)；`kind=linear` 表示真实操作类别，颜色单独表示视觉角色 |

## 依赖、并列与参数对应

- Power vectors are estimated under no_grad, but the singular value calculation occurs outside that context.
- u0 and sv0 are buffers. sv0 is for logging, whereas division uses current svs[0]; replacing the denominator by the buffer changes semantics.
- Every forward normalizes W. Training controls the state writes, not whether normalization happens.

| 源节点端口 | 目标节点端口 | 含义 |
| --- | --- | --- |
| `weight:out` | `estimate:in` | tensor |
| `estimate:out` | `normalize:in` | weight |
| `weight:out` | `normalize:in` | weight |
| `normalize:out` | `linear:in` | weight |
| `x:out` | `linear:in` | tensor |
| `linear:out` | `y:in` | tensor |
| `flatten:out` | `sigma:weight` | weight |
| `vectors:out` | `write:u` | state_update |
| `sigma:out` | `write:sv` | state_update |

## 程序化排布

三个粒度使用同一个完整语义 IR：概览折叠 body，模块图展开阶段容器，详细图展开每阶段内的调用。折叠只投影视图端点，不改变数据依赖。
底到顶 ranks 依次是：`[['estimate'], ['normalize', 'state'], ['linear']]`。每行并列的阶段具有独立支路或输出；rank 本身不生成任何数据边。root 输入在底部、返回值在顶部，同一 tuple 的输出保持并列。
每个阶段尺寸由文字/形状标签与子节点尺寸计算。阶段间距 76px、列间距 58px 为两端各 24px 的箭头预留通道；路由器以 bbox 和真实端口避让边框，末段至少 18px。内部顺序调用自底向上；旁路/权重/状态使用 typed edge，不因并列或同色而暗示共享参数。
紫色用于 Linear/矩阵，蓝色用于卷积和重排，黄色用于归一化或算术，绿色用于概率/非线性，灰色用于状态。一个类别可以跨不同模块复用；共享与独立身份以 IR 的 parameters/module_identity 为准。

## 避免教科书模板替代源码

- Do not turn spectral normalization into an activation normalization layer.

## 复用与验证

`module_adapters/spectral_norm_linear.py` 调用 `root_support.build_case()`，显式配置集中在 `root_definitions.py`。这复用图元和布局机制，仍不是任意源码自动识别。
`checks/flow_generative_extended.py` 使用独立 AST 子树对照关键公式，并注入删除关键依赖、改变参数/操作、错误配置等负例；`verify.py --png` 对实际 SVG、PNG、源码副本及哈希核验。
PyTorch/SciPy 算子的内部 kernel 为调用边界；初始化、反向分支和训练状态只按明确选定 profile 展示。更换 commit 或 profile 必须先复查语义与来源。
