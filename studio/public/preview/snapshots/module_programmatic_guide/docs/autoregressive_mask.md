# Degree mask / strict autoregressive topology

本例补充的是 **模块/选定子图**，范围：`get_mask(mask_type=output) construction function only; no MaskedLinear forward or MADE model.`。

入口：[三粒度图](../generated/autoregressive_mask/index.html) · [逐节点源码映射](../generated/autoregressive_mask/source_map.md) · [语义 IR](../generated/autoregressive_mask/semantic_ir.json)。

## 固定源码与配置

- 索引：Awesome-pytorch-list README 第 631 行。
- 实现：[ikostrikov/pytorch-flows@bf12ed91b868](https://github.com/ikostrikov/pytorch-flows/blob/bf12ed91b86867b38d74982f5e2d44c248604df9/flows.py)。
- 选取入口：`get_mask`。Notebook 原单元/派生行映射保存在证据中。
- 配置均为静态代表值，不是张量实际执行记录；不运行训练、源码 import 或模型。

```json
{
  "in_features": 8,
  "out_features": 8,
  "in_flow_features": 4,
  "mask_type": "output",
  "parameters": [],
  "dtype": "float32",
  "input_degrees": [
    0,
    1,
    2,
    0,
    1,
    2,
    0,
    1
  ],
  "output_degrees": [
    -1,
    0,
    1,
    2,
    -1,
    0,
    1,
    2
  ]
}
```

## 源码结构到图元

| 分组 / 节点 | 源码调用或公式 | 参数与状态身份 | 为何对应 |
| --- | --- | --- | --- |
| Hidden-input degrees / `i_arange` | `torch.arange(in_features)` | Parameter: []; buffer: [] | arange(in_features)；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Hidden-input degrees / `i_mod` | `torch.arange(in_features) % (in_flow_features - 1)` | Parameter: []; buffer: [] | modulo (flowD - 1)；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Strict output degrees / `o_arange` | `torch.arange(out_features)` | Parameter: []; buffer: [] | arange(out_features)；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Strict output degrees / `o_mod` | `torch.arange(out_features) % in_flow_features - 1` | Parameter: []; buffer: [] | modulo flowD; subtract 1；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Broadcast dependency comparison / `ge` | `out_degrees.unsqueeze(-1) >= in_degrees.unsqueeze(0)` | Parameter: []; buffer: [] | out_deg[:,None] >= in_deg[None,:]；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Broadcast dependency comparison / `float` | `(out_degrees.unsqueeze(-1) >= in_degrees.unsqueeze(0)).float()` | Parameter: []; buffer: [] | float() / binary connectivity；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |

## 依赖、并列与参数对应

- Input degrees use modulo D-1 for hidden units. Output degrees use modulo D then minus1, so output coordinate i can only depend on preceding input degrees.
- Comparison result has row=output unit and column=input unit. The float mask is fixed topology, not an attention probability or learned parameter.
- This function merely returns a tensor; register_buffer belongs to its MaskedLinear caller. Input/hidden mask types are alternate source branches not mixed into this selected view.

| 源节点端口 | 目标节点端口 | 含义 |
| --- | --- | --- |
| `dims:out` | `inputdegree:in` | configuration |
| `dims:out` | `outputdegree:in` | configuration |
| `inputdegree:out` | `compare:input_degrees` | tensor |
| `outputdegree:out` | `compare:output_degrees` | tensor |
| `compare:out` | `mask:in` | tensor |

## 程序化排布

三个粒度使用同一个完整语义 IR：概览折叠 body，模块图展开阶段容器，详细图展开每阶段内的调用。折叠只投影视图端点，不改变数据依赖。
底到顶 ranks 依次是：`[['inputdegree', 'outputdegree'], ['compare']]`。每行并列的阶段具有独立支路或输出；rank 本身不生成任何数据边。root 输入在底部、返回值在顶部，同一 tuple 的输出保持并列。
每个阶段尺寸由文字/形状标签与子节点尺寸计算。阶段间距 76px、列间距 58px 为两端各 24px 的箭头预留通道；路由器以 bbox 和真实端口避让边框，末段至少 18px。内部顺序调用自底向上；旁路/权重/状态使用 typed edge，不因并列或同色而暗示共享参数。
紫色用于 Linear/矩阵，蓝色用于卷积和重排，黄色用于归一化或算术，绿色用于概率/非线性，灰色用于状态。一个类别可以跨不同模块复用；共享与独立身份以 IR 的 parameters/module_identity 为准。

## 避免教科书模板替代源码

- Do not omit output degree minus1, transpose the mask, or treat the >= comparison as a Softmax.

## 复用与验证

`module_adapters/autoregressive_mask.py` 调用 `root_support.build_case()`，显式配置集中在 `root_definitions.py`。这复用图元和布局机制，仍不是任意源码自动识别。
`checks/flow_generative_extended.py` 使用独立 AST 子树对照关键公式，并注入删除关键依赖、改变参数/操作、错误配置等负例；`verify.py --png` 对实际 SVG、PNG、源码副本及哈希核验。
PyTorch/SciPy 算子的内部 kernel 为调用边界；初始化、反向分支和训练状态只按明确选定 profile 展示。更换 commit 或 profile 必须先复查语义与来源。
