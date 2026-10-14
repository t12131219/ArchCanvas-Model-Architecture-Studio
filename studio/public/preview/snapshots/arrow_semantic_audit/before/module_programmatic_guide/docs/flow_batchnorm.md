# BatchNormFlow / affine + logdet

本例补充的是 **模块/选定子图**，范围：`BatchNormFlow direct training profile. Evaluation reads running statistics; inverse training requires saved batch statistics.`。

入口：[三粒度图](../generated/flow_batchnorm/index.html) · [逐节点源码映射](../generated/flow_batchnorm/source_map.md) · [语义 IR](../generated/flow_batchnorm/semantic_ir.json)。

## 固定源码与配置

- 索引：Awesome-pytorch-list README 第 631 行。
- 实现：[ikostrikov/pytorch-flows@bf12ed91b868](https://github.com/ikostrikov/pytorch-flows/blob/bf12ed91b86867b38d74982f5e2d44c248604df9/flows.py)。
- 选取入口：`BatchNormFlow.forward`。Notebook 原单元/派生行映射保存在证据中。
- 配置均为静态代表值，不是张量实际执行记录；不运行训练、源码 import 或模型。

```json
{
  "num_inputs": 4,
  "mode": "direct",
  "training": true,
  "momentum": 0.0,
  "epsilon": 1e-05,
  "parameters": [
    "log_gamma",
    "beta"
  ],
  "buffers": [
    "running_mean",
    "running_var"
  ],
  "det_shape": [
    1
  ]
}
```

## 源码结构到图元

| 分组 / 节点 | 源码调用或公式 | 参数与状态身份 | 为何对应 |
| --- | --- | --- | --- |
| Training statistics / `mean` | `inputs.mean(0)` | Parameter: []; buffer: [] | mean over batch；`kind=statistics` 表示真实操作类别，颜色单独表示视觉角色 |
| Training statistics / `var` | `(inputs - self.batch_mean).pow(2).mean(0) + self.eps` | Parameter: []; buffer: [] | mean((x-mean)^2) + eps；`kind=statistics` 表示真实操作类别，颜色单独表示视觉角色 |
| Update persistent statistics / `ema` | `BatchNormFlow.__init__, BatchNormFlow.forward` | Parameter: []; buffer: ['running_mean', 'running_var'] | old*m + batch*(1-m)；`kind=control` 表示真实操作类别，颜色单独表示视觉角色 |
| Standardize current batch / `norm` | `(inputs - mean) / var.sqrt()` | Parameter: []; buffer: [] | (inputs-mean) / sqrt(var)；`kind=norm` 表示真实操作类别，颜色单独表示视觉角色 |
| Learned logscale / shift / `out` | `torch.exp(self.log_gamma) * x_hat + self.beta` | Parameter: ['log_gamma', 'beta']; buffer: [] | exp(log_gamma)*x_hat + beta；`kind=multiply` 表示真实操作类别，颜色单独表示视觉角色 |
| Jacobian contribution / `detop` | `(self.log_gamma - 0.5 * torch.log(var)).sum(-1, keepdim=True)` | Parameter: ['log_gamma']; buffer: [] | sum(log_gamma - .5*log(var))；`kind=density` 表示真实操作类别，颜色单独表示视觉角色 |

## 依赖、并列与参数对应

- Mean/variance are vectors of length D. Source returns determinant shape [1], broadcastable across B.
- Variance uses biased mean squared deviations and adds eps before sqrt; momentum weights the old value, unlike common PyTorch momentum naming.
- State-update arrows indicate mutation; they are not the input used to normalize this batch.

| 源节点端口 | 目标节点端口 | 含义 |
| --- | --- | --- |
| `x:out` | `stats:in` | tensor |
| `stats:mean_var` | `normalize:in` | statistics |
| `stats:out` | `running:in` | state_update |
| `x:out` | `normalize:in` | tensor |
| `normalize:out` | `affine:in` | tensor |
| `stats:var` | `det:in` | statistics |
| `affine:out` | `y:in` | tensor |
| `det:out` | `ld:in` | tensor |
| `x:out` | `var:input` | tensor |

## 程序化排布

三个粒度使用同一个完整语义 IR：概览折叠 body，模块图展开阶段容器，详细图展开每阶段内的调用。折叠只投影视图端点，不改变数据依赖。
底到顶 ranks 依次是：`[['stats'], ['normalize', 'running', 'det'], ['affine']]`。每行并列的阶段具有独立支路或输出；rank 本身不生成任何数据边。root 输入在底部、返回值在顶部，同一 tuple 的输出保持并列。
每个阶段尺寸由文字/形状标签与子节点尺寸计算。阶段间距 76px、列间距 58px 为两端各 24px 的箭头预留通道；路由器以 bbox 和真实端口避让边框，末段至少 18px。内部顺序调用自底向上；旁路/权重/状态使用 typed edge，不因并列或同色而暗示共享参数。
紫色用于 Linear/矩阵，蓝色用于卷积和重排，黄色用于归一化或算术，绿色用于概率/非线性，灰色用于状态。一个类别可以跨不同模块复用；共享与独立身份以 IR 的 parameters/module_identity 为准。

## 避免教科书模板替代源码

- Do not invent unbiased variance or per-example [B,1] determinant as the literal source return.

## 复用与验证

`module_adapters/flow_batchnorm.py` 调用 `root_support.build_case()`，显式配置集中在 `root_definitions.py`。这复用图元和布局机制，仍不是任意源码自动识别。
`checks/flow_generative_extended.py` 使用独立 AST 子树对照关键公式，并注入删除关键依赖、改变参数/操作、错误配置等负例；`verify.py --png` 对实际 SVG、PNG、源码副本及哈希核验。
PyTorch/SciPy 算子的内部 kernel 为调用边界；初始化、反向分支和训练状态只按明确选定 profile 展示。更换 commit 或 profile 必须先复查语义与来源。
