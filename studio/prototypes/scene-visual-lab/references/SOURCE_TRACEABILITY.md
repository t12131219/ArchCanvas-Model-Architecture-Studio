# 图例、数据流与源码追溯

本文档对应 [`src/module-details.ts`](../src/module-details.ts) 中现有的九种 `NodeDetailKind`。目标是让后续实现者能从任一可见图例或箭头，追到实际张量语义、固定版本源码和已核对的外部图示；本文档不修改或重新解释正式 Architecture IR。

## 约定

- “入口/出口”是父模块边界端口。九种展开图都保证内部主流向从左到右，并由最后一个内部节点接回父模块右侧出口。
- “箭头”表示依赖或张量/状态传递。卷积核、池化窗口等参数图元虽然位于主线上，但不是运行时产生的张量；相应章节会明确标注。
- 原型源码位置按当前文件行号记录。上游源码按固定版本文件、类或函数记录；以后若升级版本，应重新生成行号与校验值。
- 主要离线源码简称：
  - `AT`：[`the_annotated_transformer.py`](./upstream-code/annotated-transformer-debc9fd/the_annotated_transformer.py)
  - `PT`：[`pytorch-v2.7.1/`](./upstream-code/pytorch-v2.7.1/)
  - `HF Switch`：[`modeling_switch_transformers.py`](./upstream-code/transformers-v4.56.2/modeling_switch_transformers.py)

## 1. Multi-head Attention

- `NodeDetailKind`：`attention`
- 原型函数：[`attentionDiagram()`](../src/module-details.ts#L89)
- 权威图示：[The Annotated Transformer / Attention](https://nlp.seas.harvard.edu/annotated-transformer/#attention)
- 主源码：AT `attention()` 519-528 行、`MultiHeadedAttention` 589-628 行；PT [`MultiheadAttention`](./upstream-code/pytorch-v2.7.1/activation.py#L973)

| 可见图例或箭头 | 对应语义 | 对应源码 |
|---|---|---|
| 父入口 -> Q / K / V 三路 | self-attention 时三者可来自同一 `x`；cross-attention 时 query 与 key/value 可来自不同序列 | AT `MultiHeadedAttention.forward(query, key, value, mask)` 601-628 行 |
| Q -> Q Linear；K -> K Linear；V -> V Linear | 三组学习投影 `QW_i^Q`、`KW_i^K`、`VW_i^V` | AT 570-580、597、608-612 行；PT `MultiheadAttention` 的 `in_proj_weight` / 独立 projection weights |
| 每个 Linear -> `h × Q/K/V` | 将 `d_model` 拆成 `h × d_k`，并把 head 维转到序列维之前 | AT `.view(..., h, d_k).transpose(1, 2)` 608-612 行 |
| `h × Q` + `h × K` -> 第一个 `×` | 对每个 head 计算 `Q @ K.transpose(-2, -1)` | AT `torch.matmul(query, key.transpose(...))` 522 行 |
| 第一个 `×` -> Scale | logits 除以 `sqrt(d_k)` | AT 522 行；网页公式 `QK^T / sqrt(d_k)` |
| Scale -> Softmax | 若有 mask，真实执行会先 `masked_fill(..., -1e9)`；当前原型没有单独画 mask | AT 523-525 行 |
| Softmax -> weights | 沿 key 维形成 attention probability；训练时还可经过 dropout | AT 525-527 行 |
| weights + `h × V` -> 第二个 `×` | `attention_probability @ V` | AT 528 行 |
| 第二个 `×` -> context | 每个 head 的上下文结果 | AT `attention()` 返回值 528 行、调用位置 614-617 行 |
| context -> Concat h | 恢复 head 与通道的布局并拼接 | AT `.transpose(1, 2).contiguous().view(...)` 619-624 行 |
| Concat h -> Output `W^O` | 最终输出投影回 `d_model` | AT `self.linears[-1](x)` 628 行 |
| Output -> 父出口 -> 下一个外层模块 | attention 的输出张量成为外层后继模块输入 | [`boundaryPoints()`](../src/module-details.ts#L82) 与 [`expansion.ts`](../src/expansion.ts) 的展开端口契约 |

简化边界：原型画的是通用多头注意力核心，没有画 causal/padding mask、attention dropout、bias、KV cache、GQA/MQA，也没有把多个 head 逐一展开。`weights` 是注意力权重矩阵，不是单个标量。

## 2. Position-wise Feed Forward

- `NodeDetailKind`：`feedforward`
- 原型函数：[`feedforwardDiagram()`](../src/module-details.ts#L141)
- 主源码：AT `PositionwiseFeedForward` 677-687 行；PT [`TransformerEncoderLayer._ff_block()`](./upstream-code/pytorch-v2.7.1/transformer.py#L940)、[`Linear`](./upstream-code/pytorch-v2.7.1/linear.py#L50)、[`Dropout`](./upstream-code/pytorch-v2.7.1/dropout.py#L35)

| 可见图例或箭头 | 对应语义 | 对应源码 |
|---|---|---|
| 父入口 -> `x` | 输入保持形状 `(..., d_model)` | PT `TransformerEncoderLayer.forward()` |
| `x` -> Linear `d_model -> d_ff` | 对最后一维做第一次仿射变换 | PT `linear1` 与 `Linear.forward()`；AT `w_1` 682、686-687 行 |
| Linear -> GELU | 非线性激活；原始 Transformer 教学实现用 ReLU，现代配置常用 GELU | PT `self.activation(self.linear1(x))` 941 行；AT 664-667 行明确为 ReLU |
| GELU -> Dropout | 对扩展通道结果做训练期随机失活 | PT `self.dropout(...)` 941 行；AT `self.dropout(self.w_1(x).relu())` 687 行 |
| Dropout -> Linear `d_ff -> d_model` | 第二次仿射变换收缩回模型维度 | PT `self.linear2(...)` 941 行；AT `w_2` 683、687 行 |
| 第二个 Linear -> `FFN(x)` | 完成逐 position 的 FFN 输出 | AT 661-674 行 |
| `FFN(x)` -> 父出口 | 输出形状恢复为 `(..., d_model)`，可进入 residual/add-norm | 原型 155-157 行与父模块出口契约 |

简化边界：原型固定展示 GELU，但激活函数是模型配置；SwiGLU/GEGLU 等门控 FFN 会有额外分支和逐元素乘法，不能直接套用此图。

## 3. Add & Norm

- `NodeDetailKind`：`add-norm`
- 原型函数：[`addNormDiagram()`](../src/module-details.ts#L162)
- 主源码：PT [`TransformerEncoderLayer.forward()`](./upstream-code/pytorch-v2.7.1/transformer.py#L760)、[`LayerNorm`](./upstream-code/pytorch-v2.7.1/normalization.py#L94)；AT `LayerNorm` 315-327 行与 `SublayerConnection` 344-357 行

| 可见图例或箭头 | 对应语义 | 对应源码 |
|---|---|---|
| 父入口 -> `F(x)` 分支 | 子层输出，如 attention 或 FFN 结果 | AT 文本中的 `Sublayer(x)` 332-337 行 |
| 父入口 -> `x` 分支 | identity/residual 路径 | AT `return x + ...` 355-357 行 |
| `F(x)` -> `+` | residual 的变换支路输入 | PT post-norm 分支 `_sa_block/_ff_block` 返回值 |
| `x` -> `+` | residual 的原始输入 | PT `x = self.norm1(x + ...)` / `norm2(x + ...)`（`norm_first=False`） |
| `+` -> LayerNorm | 当前图明确表达 post-norm：先相加再标准化 | AT 文字公式 `LayerNorm(x + Sublayer(x))` 332-337 行；PT `norm_first=False` 路径 |
| LayerNorm -> `y` -> 父出口 | 对最后若干维计算均值/方差并应用可学习 `gamma/beta` | PT `LayerNorm.forward()` 216-218 行；AT 324-327 行 |

简化边界：AT 的说明文字是 post-norm，但其教学代码为 pre-norm：`x + Dropout(Sublayer(LayerNorm(x)))`。PT 同时支持两种顺序。当前图例只对应 post-norm，后续若从真实模型 IR 生成，应由 `norm_first`/源码证据决定布局。

## 4. Convolution

- `NodeDetailKind`：`convolution`
- 原型函数：[`convolutionDiagram()`](../src/module-details.ts#L185)
- 主源码：PT [`Conv2d`](./upstream-code/pytorch-v2.7.1/conv.py#L378)、[`MaxPool2d`](./upstream-code/pytorch-v2.7.1/pooling.py#L145)、[`AvgPool2d`](./upstream-code/pytorch-v2.7.1/pooling.py#L661) 与 [`ReLU`](./upstream-code/pytorch-v2.7.1/activation.py)

| 可见图例或箭头 | 对应语义 | 对应源码 |
|---|---|---|
| 父入口 -> Input stack | 输入特征图 `N × C_in × H × W` | PT `Conv2d` 文档与 `forward(input)` 553-554 行 |
| Input -> `k × k` | 表示卷积读取局部感受野；`k × k` 实际是 kernel size/权重参数，不是由 Input 生成的中间张量 | PT `Conv2d.__init__(kernel_size, stride, padding, ...)` |
| `k × k` -> Conv maps | `F.conv2d(input, weight, bias, stride, padding, dilation, groups)` 产生通道堆栈 | PT `Conv2d._conv_forward()` 与 `forward()` 536-554 行 |
| Conv maps -> ReLU | 对卷积结果逐元素激活 | PT `ReLU.forward()` -> `F.relu` |
| ReLU -> Pool | 将激活特征图交给池化算子 | PT `MaxPool2d.forward()` 212-213 行或 `AvgPool2d.forward()` 755-756 行 |
| Pool -> Output stack | 空间尺寸按 kernel/stride/padding 缩小，通道通常不变 | PT pooling 类的 shape 公式 |
| Output -> 父出口 | 下采样特征图进入下一个外层模块 | 原型 199-201 行与展开端口契约 |

简化边界：图把卷积、激活、池化组合为常见 CNN block，但真实模型可能没有 pooling、改用 stride convolution、先 norm 再 activation，或使用 depthwise/group convolution。

## 5. Tensor Transform

- `NodeDetailKind`：`tensor-transform`
- 原型函数：[`tensorTransformDiagram()`](../src/module-details.ts#L206)
- 主源码：PyTorch [`torch.permute`](https://docs.pytorch.org/docs/2.7/generated/torch.permute.html)、[`torch.reshape`](https://docs.pytorch.org/docs/2.7/generated/torch.reshape.html) 与 PT [`Linear`](./upstream-code/pytorch-v2.7.1/linear.py#L50)

| 可见图例或箭头 | 对应语义 | 对应源码 |
|---|---|---|
| 父入口 -> `B×T×C` | batch、time/token、channel 的三维输入 | 调用方张量契约；不是独立模块类 |
| `B×T×C` -> Permute | `x.permute(0, 2, 1)` 可得到 `B×C×T` view | `torch.permute(input, dims)` 官方 API |
| Permute -> Reshape | 改变视图/存储解释；必要时先 `contiguous()` | `torch.reshape(input, shape)` 或 `Tensor.reshape` |
| Reshape -> Project | 对最后一维做 `C -> D` 仿射映射 | PT `Linear.forward()` 124-125 行 |
| Project -> `BT×D` | 把 batch 与 token 维展平后的投影结果 | 常见写法 `x.reshape(B * T, C); linear(x)` |
| `BT×D` -> 父出口 | 下游需根据契约保持展平或恢复 `B×T×D` | 调用方张量 shape 证据 |

简化边界：当前标签把 `B×T×C -> B×C×T -> BT×C` 连成一条视觉链，但第二次 reshape 若要保持 `C` 的语义，通常应从原始 `B×T×C` 展平，或先把轴恢复到 `B×T×C`。因此该图应理解为“常见张量操作目录”，不是对所有模型都合法的单一 shape 推导。迁移到 Studio 时必须以 IR shape 证明每一步。

## 6. Token + Position Embedding

- `NodeDetailKind`：`embedding`
- 原型函数：[`embeddingDiagram()`](../src/module-details.ts#L225)
- 主源码：PT [`Embedding`](./upstream-code/pytorch-v2.7.1/sparse.py#L15)、[`LayerNorm`](./upstream-code/pytorch-v2.7.1/normalization.py#L94)、[`Dropout`](./upstream-code/pytorch-v2.7.1/dropout.py#L35)；AT `Embeddings` 704-711 行与 `PositionalEncoding` 748-768 行

| 可见图例或箭头 | 对应语义 | 对应源码 |
|---|---|---|
| 父入口 -> token ids / position 两路 | 输入 token 索引与对应 position 索引/位置序列 | AT embedding 与 positional encoding 的组合 |
| token ids -> Token lookup | 以整数索引读取 `vocab × d_model` 权重表 | PT `Embedding.forward()` 189-192 行；AT `self.lut(x)` 710-711 行 |
| Token lookup -> token E | 得到 `... × d_model` 的 token vectors；AT 还乘 `sqrt(d_model)` | AT 710-711 行 |
| position -> Position | learned position embedding 时也是 lookup；AT 示例则按 sin/cos 计算固定编码 | AT 727-764 行 |
| Position -> position E | 生成与 token E 同 shape 的 position vectors | AT buffer slice `self.pe[:, :x.size(1)]` 766-768 行 |
| token E -> `+` | token 表示的加法输入 | AT `x = x + self.pe[...]` 767 行 |
| position E -> `+` | position 表示的加法输入 | AT 720-725、767 行 |
| `+` -> optional LayerNorm | 部分体系（如 BERT 类 embedding block）会在 embedding sum 后归一化；原始 AT 流程没有这一步 | PT `LayerNorm.forward()`；必须由具体模型源码确认是否存在 |
| LayerNorm -> Dropout | embedding block 的正则化 | AT `return self.dropout(x)` 768 行；PT `Dropout.forward()` 69-70 行 |
| Dropout -> E -> 父出口 | 合成后的 sequence embeddings 进入 encoder/decoder | AT `make_model()` 中的 embedding + position sequential |

简化边界：`LayerNorm optional` 有意表达多个模型家族的并集，不应被解释为 Transformer 必有步骤。position 也可能是 rotary/relative bias，它们不会形成当前这条显式加法支路。

## 7. LSTM Recurrent State

- `NodeDetailKind`：`recurrent`
- 原型函数：[`recurrentDiagram()`](../src/module-details.ts#L256)
- 权威图示：[Colah LSTM walkthrough](https://colah.github.io/posts/2015-08-Understanding-LSTMs/#step-by-step-lstm-walk-through)
- 主源码：PT [`LSTM`](./upstream-code/pytorch-v2.7.1/rnn.py#L795) 的 802-810 行门公式、`forward()` 1029-1155 行

| 可见图例或箭头 | 对应语义 | 对应源码 |
|---|---|---|
| 父入口 -> `x_t` | 当前时间步输入 | PT LSTM 803-809 行所有 gate 公式中的 `x_t` |
| 父入口 -> `h_{t-1}` | 前一 hidden state | PT 803-809 行中的 `h_{t-1}` |
| 父入口 -> `c_{t-1}` | 前一 cell state，走独立长期状态路径 | PT `c_t` 公式 808 行 |
| `x_t` + `h_{t-1}` -> Concat | 教学图把共同 gate 输入画成 `[x_t, h_{t-1}]`；PyTorch 等价地用两组 input/hidden 权重相加 | PT 804-807 行的 `W_i* x_t + W_h* h_{t-1}` |
| Concat -> `i_t` | input gate：sigmoid | PT 804 行 |
| Concat -> `g_t` | candidate gate：tanh | PT 806 行 |
| Concat -> `f_t` | forget gate：sigmoid | PT 805 行 |
| Concat -> `o_t` | output gate：sigmoid | PT 807 行 |
| `i_t` + `g_t` -> 第一个 `×` | 逐元素候选写入量 `i_t ⊙ g_t` | PT 808 行后半 |
| `f_t` + `c_{t-1}` -> 第二个 `×` | 逐元素保留量 `f_t ⊙ c_{t-1}` | PT 808 行前半 |
| 两个 `×` -> `+` -> `c_t` | 新 cell state：保留旧状态并加入候选状态 | PT 808 行 |
| `c_t` -> tanh；tanh + `o_t` -> 最后 `×` -> `h_t` | 输出 hidden state `o_t ⊙ tanh(c_t)` | PT 809 行 |
| `h_t` + `c_t` -> 联合输出 -> 父出口 | LSTM API 返回 sequence output 与 `(h_n, c_n)`；图用一个边界出口压缩表达 | PT `LSTM.forward()` 返回值说明与实现 |

简化边界：图展示单层、单方向、单时间步，不画 stacked/bidirectional/projection/dropout。PyTorch 实际 forward 调用融合后端 `_VF.lstm`，门公式保存在类 docstring 中，而不是逐行 Python 运算。

## 8. Sparse Mixture of Experts

- `NodeDetailKind`：`mixture-of-experts`
- 原型函数：[`mixtureOfExpertsDiagram()`](../src/module-details.ts#L307)
- 权威说明：[Hugging Face MoE article](https://huggingface.co/blog/moe)
- 主源码：HF Switch `SwitchTransformersTop1Router` 126-236 行、`SwitchTransformersSparseMLP` 268-314 行、`SwitchTransformersLayerFF` 317-356 行

| 可见图例或箭头 | 对应语义 | 对应源码 |
|---|---|---|
| 父入口 -> tokens | 输入 hidden states 中的每个 token 表示 | HF Switch router `forward(hidden_states)` |
| tokens -> Router | 线性 classifier 产生各 expert logits，再以 softmax 得到 router probabilities | HF Switch `_compute_router_probabilities()` 与 `forward()` 126-236 行 |
| Router -> Top-k | 保留最高 k 个专家及其权重；Switch 固定 top-1，通用 sparse MoE 可 top-2 | HF Switch `torch.max(router_probs, dim=-1)`、one-hot router mask；网页 `KeepTopK` 公式 |
| Top-k -> Expert 1/2/3 分支 | 依据 mask 把 token dispatch 到激活专家 | HF Switch 295-311 行 |
| 每个 Expert | 独立 FFN，通常为 `wi -> activation -> dropout -> wo` | HF Switch `SwitchTransformersDenseActDense` 246-266 行与 expert ModuleDict |
| 每个 Expert -> `Σ` | 收集专家输出；通用 top-k 按 router 权重求和 | 网页 `y = sum_i G(x)_i E_i(x)`；HF Switch top-1 以 `router_probs * next_states` 实现 313 行 |
| `Σ` -> mixed | 每个 token 的稀疏专家输出 | HF Switch 300-314 行 |
| mixed -> Output | MoE/FFN 子层结果；外层还可能做 dropout 与 residual add | HF Switch `SwitchTransformersLayerFF.forward()` 342-356 行 |
| Output -> 父出口 | 进入外层 Transformer 后继模块 | 原型 329-331 行与展开端口契约 |

简化边界：原型固定画三个专家，实际数量由配置决定；Switch 是 top-1，没有多专家求和。capacity、token dropping、load-balancing auxiliary loss、router z-loss 与跨设备 all-to-all 都未画出。

## 9. Pooling

- `NodeDetailKind`：`pooling`
- 原型函数：[`poolingDiagram()`](../src/module-details.ts#L335)
- 主源码：PT [`MaxPool2d`](./upstream-code/pytorch-v2.7.1/pooling.py#L145) 与 [`AvgPool2d`](./upstream-code/pytorch-v2.7.1/pooling.py#L661)

| 可见图例或箭头 | 对应语义 | 对应源码 |
|---|---|---|
| 父入口 -> feature map | `N × C × H × W` 输入 | pooling 类 `forward(input)` |
| feature map -> window | 表示在输入上滑动 `kH × kW` 局部窗口；window 是算子参数/观察区域，不是独立张量输出 | `kernel_size`、`stride`、`padding` 参数 |
| window -> Max / Average | 每个窗口执行最大值或均值 reduction | `F.max_pool2d` / `F.avg_pool2d` |
| Max / Average -> pooled | 得到缩小空间分辨率的特征图 | 类 docstring 中 `H_out/W_out` 公式 |
| pooled -> Output | 命名后的模块输出；通常保持 channel identity | PT pooling shape 契约 |
| Output -> 父出口 | 下采样结果进入下一个外层模块 | 原型 347-349 行与展开端口契约 |

简化边界：未展示 indices、ceil mode、dilation、padding 对边界窗口的影响，也未区分 global/adaptive pooling。

## 外层箭头与展开兼容

内部图与外层场景共用以下契约：

1. [`boundaryPoints()`](../src/module-details.ts#L82) 把内部入口/出口固定在展开父模块左右边界中心。
2. [`deriveExpandedScene()`](../src/expansion.ts) 从基础场景重新计算父模块尺寸与下游位移，不原地改变基础坐标。
3. 外部边若源节点展开，从内部 `exitPoint` 起始；若目标节点展开，在内部 `entryPoint` 结束。对应行为由 [`expansion.test.ts`](../src/expansion.test.ts) 覆盖。
4. 因此 `Attention Output`、`FFN(x)`、`y`、CNN/Pooling `Output`、embedding `E`、LSTM `(h_t,c_t)`、MoE `Output` 都能继续连接外层下一模块；内部线条不是孤立装饰。

## 后续迁移检查表

- 从 Architecture IR/源码证据确定实际模块家族和 shape，不能只凭父节点标题套模板。
- 对每条内部边保存 source/target 图元、张量 shape、operation evidence 与可选条件。
- pre-norm/post-norm、ReLU/GELU/SwiGLU、top-1/top-2、learned/sinusoidal/rotary position 必须由证据选择。
- 如果 shape 无法证明，保留抽象父模块，不生成看似精确但错误的内部链路。
- 迁移绘图纯函数时仍保持 `VisualPatch` 与 `SourceTransaction` 分离，视觉调整不得反写模型源码。
