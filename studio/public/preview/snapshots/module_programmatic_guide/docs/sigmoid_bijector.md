# Sigmoid bijector / Jacobian branch

本例补充的是 **模块/选定子图**，范围：`Sigmoid.forward direct branch only. The separate Logit subclass argument bug is explicitly documented.`。

入口：[三粒度图](../generated/sigmoid_bijector/index.html) · [逐节点源码映射](../generated/sigmoid_bijector/source_map.md) · [语义 IR](../generated/sigmoid_bijector/semantic_ir.json)。

## 固定源码与配置

- 索引：Awesome-pytorch-list README 第 631 行。
- 实现：[ikostrikov/pytorch-flows@bf12ed91b868](https://github.com/ikostrikov/pytorch-flows/blob/bf12ed91b86867b38d74982f5e2d44c248604df9/flows.py)。
- 选取入口：`Sigmoid.forward`。Notebook 原单元/派生行映射保存在证据中。
- 配置均为静态代表值，不是张量实际执行记录；不运行训练、源码 import 或模型。

```json
{
  "mode": "direct",
  "input_features": 4,
  "parameters": [],
  "inverse": "log(x/(1-x))",
  "logit_subclass_bug": true
}
```

## 源码结构到图元

| 分组 / 节点 | 源码调用或公式 | 参数与状态身份 | 为何对应 |
| --- | --- | --- | --- |
| Elementwise transform / `sigmoid` | `s(inputs)` | Parameter: []; buffer: [] | sigmoid(inputs)；`kind=sigmoid` 表示真实操作类别，颜色单独表示视觉角色 |
| Derivative and log-volume / `derivative` | `s(inputs) * (1 - s(inputs))` | Parameter: []; buffer: [] | s(x) * (1-s(x))；`kind=multiply` 表示真实操作类别，颜色单独表示视觉角色 |
| Derivative and log-volume / `logsum` | `torch.log(s(inputs) * (1 - s(inputs))).sum(-1, keepdim=True)` | Parameter: []; buffer: [] | log then sum over D；`kind=density` 表示真实操作类别，颜色单独表示视觉角色 |

## 依赖、并列与参数对应

- Sigmoid source implements a real direct/inverse bijector and returns the sum of log derivative.
- Logit subclass passes inverse as the second positional cond_inputs argument, leaving mode=direct. It is therefore not drawn as a correctly implemented logit wrapper.

| 源节点端口 | 目标节点端口 | 含义 |
| --- | --- | --- |
| `x:out` | `nonlinear:in` | tensor |
| `nonlinear:out` | `y:in` | tensor |
| `nonlinear:out` | `jacobian:in` | tensor |
| `jacobian:out` | `ld:in` | tensor |

## 程序化排布

三个粒度使用同一个完整语义 IR：概览折叠 body，模块图展开阶段容器，详细图展开每阶段内的调用。折叠只投影视图端点，不改变数据依赖。
底到顶 ranks 依次是：`[['nonlinear'], ['jacobian']]`。每行并列的阶段具有独立支路或输出；rank 本身不生成任何数据边。root 输入在底部、返回值在顶部，同一 tuple 的输出保持并列。
每个阶段尺寸由文字/形状标签与子节点尺寸计算。阶段间距 76px、列间距 58px 为两端各 24px 的箭头预留通道；路由器以 bbox 和真实端口避让边框，末段至少 18px。内部顺序调用自底向上；旁路/权重/状态使用 typed edge，不因并列或同色而暗示共享参数。
紫色用于 Linear/矩阵，蓝色用于卷积和重排，黄色用于归一化或算术，绿色用于概率/非线性，灰色用于状态。一个类别可以跨不同模块复用；共享与独立身份以 IR 的 parameters/module_identity 为准。

## 避免教科书模板替代源码

- Do not silently replace the actual buggy Logit.forward by the textbook logit implementation.

## 复用与验证

`module_adapters/sigmoid_bijector.py` 调用 `root_support.build_case()`，显式配置集中在 `root_definitions.py`。这复用图元和布局机制，仍不是任意源码自动识别。
`checks/flow_generative_extended.py` 使用独立 AST 子树对照关键公式，并注入删除关键依赖、改变参数/操作、错误配置等负例；`verify.py --png` 对实际 SVG、PNG、源码副本及哈希核验。
PyTorch/SciPy 算子的内部 kernel 为调用边界；初始化、反向分支和训练状态只按明确选定 profile 展示。更换 commit 或 profile 必须先复查语义与来源。
