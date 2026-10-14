# Split prior / conditional Gaussian density

本例补充的是 **模块/选定子图**，范围：`Only split=True prior subgraph after the omitted Flow loop; excludes squeeze, flow logdet and reverse sampling.`。

入口：[三粒度图](../generated/glow_split_prior/index.html) · [逐节点源码映射](../generated/glow_split_prior/source_map.md) · [语义 IR](../generated/glow_split_prior/semantic_ir.json)。

## 固定源码与配置

- 索引：Awesome-pytorch-list README 第 695 行。
- 实现：[rosinality/glow-pytorch@97081ff115a6](https://github.com/rosinality/glow-pytorch/blob/97081ff115a694cf04aeedbd58447f33d242c879/model.py)。
- 选取入口：`Block.forward`。Notebook 原单元/派生行映射保存在证据中。
- 配置均为静态代表值，不是张量实际执行记录；不运行训练、源码 import 或模型。

```json
{
  "split": true,
  "input_channels_after_squeeze": 8,
  "retained_channels": 4,
  "prior_channels": 8,
  "head_order": [
    "mean",
    "log_sd"
  ],
  "sampling": false,
  "logdet_excluded": true
}
```

## 源码结构到图元

| 分组 / 节点 | 源码调用或公式 | 参数与状态身份 | 为何对应 |
| --- | --- | --- | --- |
| Split channel halves / `splitop` | `out.chunk(2, 1)` | Parameter: []; buffer: [] | out.chunk(2,dim=1)；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Prior on retained half / `priorop` | `Block.__init__, Block.forward, ZeroConv2d.forward` | Parameter: []; buffer: [] | ZeroConv2d prior 4 -> 8；`kind=conv2d` 表示真实操作类别，颜色单独表示视觉角色 |
| Mean / log standard deviation / `headsop` | `self.prior(out).chunk(2, 1)` | Parameter: []; buffer: [] | chunk -> mean, log_sd；`kind=tensor` 表示真实操作类别，颜色单独表示视觉角色 |
| Elementwise Gaussian log_p / `gauss` | `-0.5 * log(2 * pi) - log_sd - 0.5 * (x - mean) ** 2 / torch.exp(2 * log_sd)` | Parameter: []; buffer: [] | gaussian_log_p(z_new,mean,log_sd)；`kind=density` 表示真实操作类别，颜色单独表示视觉角色 |
| Per-example sum / `sum` | `log_p.view(b_size, -1).sum(1)` | Parameter: []; buffer: [] | view(B,-1).sum(1)；`kind=density` 表示真实操作类别，颜色单独表示视觉角色 |

## 依赖、并列与参数对应

- Prior sees retained out, whereas density is evaluated on z_new; these operands cannot be interchanged.
- log_sd denotes log standard deviation; density denominator is exp(2*log_sd), not exp(log_sd).
- The three outputs are independent values; there is no z-to-retained tensor chain.

| 源节点端口 | 目标节点端口 | 含义 |
| --- | --- | --- |
| `x:out` | `split:in` | tensor |
| `split:out` | `prior:in` | tensor |
| `split:out` | `keep:in` | retained_value |
| `split:z_new` | `z:in` | retained_value |
| `prior:out` | `heads:in` | tensor |
| `heads:mean_log_sd` | `density:parameters` | tensor |
| `split:z_new` | `density:sample` | tensor |
| `density:out` | `reduce:in` | tensor |
| `reduce:out` | `lp:in` | tensor |

## 程序化排布

三个粒度使用同一个完整语义 IR：概览折叠 body，模块图展开阶段容器，详细图展开每阶段内的调用。折叠只投影视图端点，不改变数据依赖。
底到顶 ranks 依次是：`[['split'], ['prior'], ['heads'], ['density'], ['reduce']]`。每行并列的阶段具有独立支路或输出；rank 本身不生成任何数据边。root 输入在底部、返回值在顶部，同一 tuple 的输出保持并列。
每个阶段尺寸由文字/形状标签与子节点尺寸计算。阶段间距 76px、列间距 58px 为两端各 24px 的箭头预留通道；路由器以 bbox 和真实端口避让边框，末段至少 18px。内部顺序调用自底向上；旁路/权重/状态使用 typed edge，不因并列或同色而暗示共享参数。
紫色用于 Linear/矩阵，蓝色用于卷积和重排，黄色用于归一化或算术，绿色用于概率/非线性，灰色用于状态。一个类别可以跨不同模块复用；共享与独立身份以 IR 的 parameters/module_identity 为准。

## 避免教科书模板替代源码

- Do not call this a whole Glow block or add a reparameterization sample to forward.

## 复用与验证

`module_adapters/glow_split_prior.py` 调用 `root_support.build_case()`，显式配置集中在 `root_definitions.py`。这复用图元和布局机制，仍不是任意源码自动识别。
`checks/flow_generative_extended.py` 使用独立 AST 子树对照关键公式，并注入删除关键依赖、改变参数/操作、错误配置等负例；`verify.py --png` 对实际 SVG、PNG、源码副本及哈希核验。
PyTorch/SciPy 算子的内部 kernel 为调用边界；初始化、反向分支和训练状态只按明确选定 profile 展示。更换 commit 或 profile 必须先复查语义与来源。
