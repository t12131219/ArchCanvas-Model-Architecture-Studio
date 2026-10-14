# CORAL / shared ordinal score head

本例补充的是 **模块/选定子图**，范围：`Local CoralLayer class only. It overrides the imported same-name class; upstream MLP and training losses excluded.`。

入口：[三粒度图](../generated/coral_head/index.html) · [逐节点源码映射](../generated/coral_head/source_map.md) · [语义 IR](../generated/coral_head/semantic_ir.json)。

## 固定源码与配置

- 索引：deeplearning-models README 第 164 行。
- 实现：[rasbt/deeplearning-models@59beda3aa253](https://github.com/rasbt/deeplearning-models/blob/59beda3aa25337e576564f1c18c6edd26f9f30e3/pytorch_ipynb/ordinal/CORAL_cement.ipynb)。
- 选取入口：`CoralLayer.forward`。Notebook 原单元/派生行映射保存在证据中。
- 配置均为静态代表值，不是张量实际执行记录；不运行训练、源码 import 或模型。

```json
{
  "size_in": 16,
  "num_classes": 5,
  "thresholds": 4,
  "preinit_bias": true,
  "score_weights_shared": true,
  "parameters": [
    "coral_weights.weight",
    "coral_bias"
  ]
}
```

## 源码结构到图元

| 分组 / 节点 | 源码调用或公式 | 参数与状态身份 | 为何对应 |
| --- | --- | --- | --- |
| Single shared score / `linear` | `CoralLayer.__init__, CoralLayer.forward` | Parameter: ['coral_weights.weight']; buffer: [] | Linear 16 -> 1 / no bias；`kind=linear` 表示真实操作类别，颜色单独表示视觉角色 |
| Broadcast across K-1 thresholds / `add` | `self.coral_weights(x) + self.coral_bias` | Parameter: []; buffer: [] | score + coral_bias；`kind=add` 表示真实操作类别，颜色单独表示视觉角色 |

## 依赖、并列与参数对应

- A single biasless linear score is shared by all K-1 logits, then each threshold receives its own learned bias.
- Default preinitialized bias is arange(K-1,0,-1)/(K-1), here [1,.75,.5,.25]; the source does not impose a hard sorted-bias constraint after updates.
- This view stops at logits. Sigmoid decoding and loss calls are outside the class.

| 源节点端口 | 目标节点端口 | 含义 |
| --- | --- | --- |
| `x:out` | `score:in` | tensor |
| `score:out` | `broadcast:in` | tensor |
| `bias:out` | `broadcast:threshold_bias` | tensor |
| `broadcast:out` | `y:in` | tensor |

## 程序化排布

三个粒度使用同一个完整语义 IR：概览折叠 body，模块图展开阶段容器，详细图展开每阶段内的调用。折叠只投影视图端点，不改变数据依赖。
底到顶 ranks 依次是：`[['score'], ['broadcast']]`。每行并列的阶段具有独立支路或输出；rank 本身不生成任何数据边。root 输入在底部、返回值在顶部，同一 tuple 的输出保持并列。
每个阶段尺寸由文字/形状标签与子节点尺寸计算。阶段间距 76px、列间距 58px 为两端各 24px 的箭头预留通道；路由器以 bbox 和真实端口避让边框，末段至少 18px。内部顺序调用自底向上；旁路/权重/状态使用 typed edge，不因并列或同色而暗示共享参数。
紫色用于 Linear/矩阵，蓝色用于卷积和重排，黄色用于归一化或算术，绿色用于概率/非线性，灰色用于状态。一个类别可以跨不同模块复用；共享与独立身份以 IR 的 parameters/module_identity 为准。

## 避免教科书模板替代源码

- Do not draw K-1 independent score weight vectors or import an unreviewed external CoralLayer implementation.

## 复用与验证

`module_adapters/coral_head.py` 调用 `root_support.build_case()`，显式配置集中在 `root_definitions.py`。这复用图元和布局机制，仍不是任意源码自动识别。
`checks/flow_generative_extended.py` 使用独立 AST 子树对照关键公式，并注入删除关键依赖、改变参数/操作、错误配置等负例；`verify.py --png` 对实际 SVG、PNG、源码副本及哈希核验。
PyTorch/SciPy 算子的内部 kernel 为调用边界；初始化、反向分支和训练状态只按明确选定 profile 展示。更换 commit 或 profile 必须先复查语义与来源。
