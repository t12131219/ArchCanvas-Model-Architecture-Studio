# 独立源码关系基准

此文件是人工审核的关系要求，不从当前分析器输出生成答案。下面的预期以源码中的调用、变量绑定和返回值为依据；如果 fixture 改变，先重新审核源码，再修改预期。

## Transformer / 多输入 Attention

基准入口：`fixtures/transformer/model.py` 中的 `Transformer`，辅助模块位于 `blocks.py`。审核者应逐行记录以下关系，并在分析输出中按调用位置寻找对应关系，而不是以展示名称猜测：

| 源码关系 | 必须保留的事实 | 必须拒绝的错误 |
|---|---|---|
| 源序列与目标序列是两个 forward 输入 | 两个输入有不同身份；decoder 的初始查询来自目标序列 | 将两个输入合成单一 x |
| Encoder 的结果传给 decoder | memory producer 是 encoder 输出 | 用 decoder 自身输出代替 memory |
| Self-attention 的 query/key/value | 三个具名端口都绑定源码中的相应 tensor，即使它们共享 producer | 因为 producer 相同而只留下一个输入端口 |
| Cross-attention 的 query 与 key/value | query 来自 decoder 流，key/value 来自 memory | 假定三者相同，或假定 Lq = Lk |
| 注意力 mask 等显式实参 | 保存具名实参及来源；未提供时不能补造 | 把 mask 连接到 query/key/value |
| Attention 返回 tuple，源码选择第一个值 | tuple 选择和选中输出可区分；未使用的权重不等于 graph output | 直接丢失选择事实，或自动添加权重输出 |
| 每个残差加法 | 两个输入完整，旁路输入来自加法前的对应 tensor | 只保留主分支，或误接另一层的旁路 |
| Norm、attention、FFN 的源码顺序 | 以实际绑定和调用顺序为准 | 从教科书模板补成另一种 Pre/Post-LN |
| 模型 return | 图输出与返回的实际值一致 | 自动增加源码没有的最终 Softmax |

Alpha 静态图可以暴露 fused Attention 调用及真实 q/k/v 输入。没有 separate Q/K/V 投影源码时，不把示意投影声明为已恢复的算子或可写回端口；没有执行证据时，不把 sequence length 或 tensor shape 声称为已验证。

首批 fixture 的人工 gold：

- `Transformer.forward` 有 5 个具名参数：两种 token 输入，以及 `source_mask`、`target_mask`、`memory_mask`。这些 mask 的默认值是 None；图上的静态输入角色不说明本次真实运行提供了 mask。
- 默认 `n_layers=2`，两个 `EncoderLayer` 由列表推导分别构造，参数实例独立。一个 `DecoderLayer` 含 self-attention 与 cross-attention。总共有 4 个 MHA 调用。
- 两个 encoder self-attention 的 query/key/value 各自共享相同的当前 encoder tensor；`source_mask` 流向两个调用的 `attn_mask`。
- decoder self-attention 的 query/key/value 来自 `target_embedding`；`target_mask` 流向其 `attn_mask`。
- decoder cross-attention 的 query 来自 `self_norm`，key/value 来自第二个 encoder 的 `feedforward_norm` 输出；`memory_mask` 流向其 `attn_mask`。
- 两个 encoder 各有 2 个残差加法，decoder 有 3 个，总计 7 个 `Add`。每个都有 left/right 两个来源；本 fixture 是 Post-LN。
- MHA 源码通过 tuple 解包取 `attended`，`weights` 未参与模型 return。最终 graph output 来自 `output_projection`，没有 Softmax。

## MLP

基准入口：`fixtures/mlp/model.py` 中的 `MLP`。输入必须经过源码列出的层与 functional activation 后到达 return。层构造参数是静态来源证据；图上参数或显示文本不授予源码编辑能力。

本 fixture 的 `Sequential` 顺序是 Linear(16, 32) → GELU → Dropout(0.1) → Linear(32, 4)。其 activation 是模块调用；functional activation 留给独立反例覆盖，不能由此 fixture 宣称已验收。

## Residual CNN

基准入口：`fixtures/residual_cnn/model.py` 中的 `ResidualCNN`，辅助模块位于 `blocks.py`。残差块的加法必须有主分支和 skip 分支两个输入。模块层级不得被扁平展示误解为执行顺序；卷积、归一化和激活顺序依源码绑定判断。

默认有 2 个独立构造的 ResidualBlock，共 2 个 Add。块内主分支是 conv1 → norm1 → activation → conv2 → norm2；skip 保存块入口 tensor，两者相加后再调用相同的 `self.activation`。每个块中的 activation 有两次调用、一个 instance；两个块的卷积实例彼此独立。池化后 Flatten(1) 到 classifier，最终输出来自 classifier。

## 共享与未知

共享模块的每个调用有独立 call identity，引用同一个 module instance。两次调用不能制造两份独立参数；两处同名局部变量也不能合成一个 tensor。循环中的重复计数必须有源码依据，未知计数保留未知。

动态 `getattr`、反射、数据依赖分支、自定义未知函数和不能解析的参数表达式，必须登记 opaque/unknown 或保留来源证据，不能把确定性局部图当作完整的已证明模型。不得执行导入或 forward 来“补齐”静态分析。

## 反证验收

从最小源码反例检查同一模块被调用两次、多输入连接、两个残差来源、tuple 选择和未知表达式。人为换错一个关系后，基准检查必须失败，才能把对应检查登记为有效。视觉颜色、节点数量和 analyzer 输出快照不能代替这些关系检查。

注意力位置参数反例：`attn(q, memory, memory, mask)[0]` 的第四个实参依 PyTorch 合同是 `key_padding_mask`，不得因为只处理前三个端口而丢失。继承 forward 尚未支持时，`child(x)` 应产生保留 x 输入来源的 opaque 边界，不能仅剩无输入的输出节点。

首次浏览器验收记录：总览与三级展开、85/180 mm、黑白辨识、展开锚点、无关 pin、重展开局部位置、编辑后保存/重开、undo/redo 与当前 SVG。未完成的条目保持未验证。
