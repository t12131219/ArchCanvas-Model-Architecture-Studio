# 三张参考图的布局观察与可编程约束

本文是主说明的补充笔记。观察对象是提供的三张图片；图片只作为视觉目标，不是源码行为的证据。

## 布局的核心不是按源码文件的声明顺序排矩形

源码的类声明顺序、模块树、数据依赖图是三种结构。模块树决定嵌套边框，`forward` 的数据依赖决定箭头与先后，同类操作决定视觉模板。同一类实例不等于同一参数对象：Q/K/V 的投影均可使用紫色 Linear 图例，但仍要具有不同 `param_identity`。Encoder 与 Decoder 的 attention 可以复用图例模板，不能据此声称共享权重。

图1是模块语义的折叠视图；图2展开 MHA 与 FFN 的操作摘要；图3进一步展开投影、张量、分头、注意力内部矩阵计算和 Add & Norm。当前图3仅把 Encoder / Decoder self-attention 的 SDPA 全展开，cross 的 Q/K/V 来源和投影展开、SDPA 折叠成横条。这三图从同一个语义 IR 派生，`view` 只控制节点可见性和展开方式；本次紧凑度调整不改变 `semantic_ir.json`。

## 图3的视觉骨架

1. Encoder 与 Decoder 是左右两栏，主流程向上；输入 embedding 底部对齐。Encoder 少一个 cross-attention，而 Decoder 同时多一个 Add & Norm，因此两栏天然高度不同。
2. 顶部 FFN 与归一化在参考图中接近对齐。Encoder 下方留下更长输入主干。这是为了局部比较而增加的布局自由度，不能简单地“所有栈底部对齐”推导。
3. Q/K/V 为等宽三列，表示三个并列投影，无 Q→K→V 执行依赖。当前细图每列内 Linear 与 tensor 左右并排，水平箭头长 24 px，再从 tensor 向下直达 Split / SDPA；Cross-attention 的 Q 独立分组，K/V 有共同 memory 分组。
4. 主流程向上与模块内部上→下、左→右的说明流程共存。程序需要显式边界端口及内外路由；不能让矩形边缘的最近位置代替数据端口。
5. 两栏之间是 memory 专用通道；每个 sublayer 左侧是残差专用通道。N× 在 stack 旁边是重复元数据，不是第三个输入。
6. 色彩绑定语义类型：embedding 粉、FFN 蓝、attention 橙、Add & Norm 黄、Linear 紫、softmax 绿。Tensor 的 Q/K/V 颜色绑定角色；同一张量跨线应保留身份。输出投影的紫色操作与投影后张量不必同色。

## 度量与放置

先测量叶子文字和 glyph，再自底向上测量容器，最后自顶向下放置。用真实字体测量最好；纯标准库示例用保守字符宽估计、换行和额外余量，不能宣称像素级字体测量。

以下给出测量方法；当前生成器的栈间距 `g=24`、顶底内边距 `P=22`，Q/K/V 列间距 `g_col=18`、内侧路由距边框 18 px。正文一般为 18–20 px，叶节点内容另留余量。对于竖向容器：

```text
W = P_left + max(child.width) + P_right + routing_reserve
H = t + P_top + sum(child.height) + g * (n - 1) + P_bottom
y[i+1] = y[i] + h[i] + g
```

对于三列 Q/K/V：

```text
w_col = max(measure(Q), measure(K), measure(V))
W_qkv = 3*w_col + 2*g_col
x_Q = x_inner
x_K = x_inner + w_col + g_col
x_V = x_inner + 2*(w_col + g_col)
```

尺寸随长标签增加，不能先定很小的框再压缩字体。Cross-attention 的两个输入组可以用 `1 : 2` 列宽，两个分组共享投影行与 tensor 行基线。

两个 stack 可以使用共同 `top=Y0`，embedding 使用共同 `y=Yb`：

```text
Yb = max(Y0 + H_encoder, Y0 + H_decoder) + input_stem_min + PE_height
y_embedding_encoder = y_embedding_decoder = Yb
input_stem_encoder = Yb - PE_height - (Y0 + H_encoder)
input_stem_decoder = Yb - PE_height - (Y0 + H_decoder)
```

这让短 Encoder 获得较长主干，与参考图的处理一致。若更重视紧凑，可改为 stack 底边对齐；若更重视比较，可增加 `FFN_top_encoder ≈ FFN_top_decoder` 的软约束。不能同时把“所有子模块同高、两栏顶底都对齐、所有内部间距相同”都作为硬约束，因两栏结构不同，这组要求通常不可满足。

更通用的布局器把必要关系作为硬约束，把美观作为优化目标：

```text
硬约束：containment、兄弟不重叠、dataflow order、QKV equal width、port identity
软目标：画布面积、总线长、转弯数、交叉数、同类模块对齐偏差
min  α*area + β*wire_length + γ*bends + δ*crossings + ε*alignment_error
```

源码确定依赖与身份；对齐、展开预算和方向属于设计策略，不能称为从源码自动恢复的唯一布局。

当前 detailed 的内容高度分别为 FFN 210 px、cross-attention 438 px、self-attention 542 px，按各容器的展示粒度测量。图3画布为 `1600×2308`，相比先前 `1600×2562` 高度减少约 9.9%；减少的是重复代数展开和多余留白，不是删去源码算子。这仍是特定 Transformer 的规则布局，不是通用最优求解器。

## 连线通道

残差从 sublayer 输入下方 12 px 的入边处分叉，用独立 junction 圆点标明，绕过该 sublayer，接入其对应 Add & Norm 的 `skip` 端口。这个点只表示同一输入张量的分叉，不新增算子。每个残差只绕一个 sublayer，正常边不沿圆角框边界延伸，也不穿过标签。

```text
skip_lane_x = sublayer.left - residual_gutter
branch = (sublayer.in.x, sublayer.in.y + 12)
path = [branch, (skip_lane_x, branch.y),
        (skip_lane_x, norm.skip.y), norm.skip]
```

Memory 必须从整个 Encoder stack 的最终输出分叉，而不是从视觉上最接近 Cross-attention 的矩形边缘出发：

```text
memory_lane_x = encoder.right + column_gap / 2
path = [encoder.out, (encoder.out.x, encoder.top-clearance),
        (memory_lane_x, encoder.top-clearance),
        (memory_lane_x, cross.memory.y), cross.memory]
```

Cross-attention 内部再从 memory 边界端口扇出到 K、V 投影输入。图上的“Encoder output / memory”只是一条线的标签，不是运算节点。路由应避开两栏 stack，不允许为缩短距离穿过 Encoder 的 FFN/归一化面板。

当宏观向上、内部向下时，每个展开面板保留左右各一条内边界通道，距边框 18 px：底部 `in` 沿左侧接入顶部输入行；末端 Wo 沿右侧接回顶部 `out`，外部后继消费这一输出。也可以把详细内容画作独立放大视窗。当前箭头固定长 9 px，SVG 设置 `markerUnits="userSpaceOnUse"`；带箭头的最后一段至少 18 px，常用 24 px，避免箭头被末端小折线挤压或随线宽放大。

## 图3需要主动纠正的歧义

- Memory 线在参考图3从 Encoder self-attention 的 X 行附近出发，视觉上容易被理解为该 attention 的输入。真实语义是最终 Encoder 输出；示例应从最终归一化后的 stack 顶部输出引出。
- 图3顶部主干穿过 Add & Norm 的加号附近，而 LayerNorm→Z 是横向，后续主干究竟来自残差和还是 Z 不够明确。必须将 Add & Norm 的 `out` 明确绑定 LayerNorm 输出。
- 底部输入箭头进入 MHA 容器的下边缘，而容器内部 X 在顶端；没有内部接口路由时，会像直接进入 Wo。不能照抄这一视觉捷径。
- 图2/3的 `ReLU / GELU` 与 `sinusoidal / learned` 是架构选项，不是提供的教育版 PyTorch 源码同时执行两种激活或两种 PE。与该源码对应时应写 ReLU、fixed sinusoidal；其 dropout 可以折叠但必须注明。
- 三列 Q/K/V 投影后仍为 `[B,L,D]`，split 后为 `[B,H,L,D/H]`；attention weights 为 `[B,H,Lq,Lk]`，不是普通 `[B,L,D]` 张量。Cross-attention 的 `Lq=T`、`Lk=S`，不能都写 seq。
- Tensor 小网格是符号 glyph，不代表真实行列数；应有明确图例，尤其 mask 网格上三角为禁止/−∞，不是零权重的直接源码写入。
- `N×` 表示串行的 N 个独立层实例，通常不是复用一个层参数 N 次。提供的源码使用 deepcopy clones。
- 源码的 Transformer.forward 返回 logits。图中最顶层 Softmax 如保留，只能作为虚线解释步骤，标明 outside forward。注意力内部的 softmax 才是真实 forward 操作。
- Decoder 的因果性取决于传入正确 tgt_mask；不能因为类名叫 Decoder 就声称 forward 自动创建 causal mask。

## 可审核输出（本轮端点修订）

当前两版实际 SVG 路径均为 24 / 40 / 83 条；模块摘要具有明确 source members 和命名接口，展开后箭头继续到真实叶算子。PE 的 buffer 与 Add 分别具有身份；残差来源追到上游状态；memory 从最终 Encoder LayerNorm 分别接 cross WK/WV。Q/K/V、FFN X/Z 网格按 producer 作为值别名，分段箭头保留同一 canonical edge。

`semantic_projection.edge_dispositions` 记录全部 134 条 IR 边，防止隐藏依赖无声消失。`check_svg_routes.py generated --border 0.1 --summary --strict` 同时检查实际 SVG 与 layout 的路径/端点/trace 一致性，以及 source projection 与别名续线。默认版保持模块内部向上；compact 明确采用混合方向。本轮 semantic_ir 增加准确 PE 算子、接口绑定和摘要来源，源码字节未修改。历史检查记录和 preservation manifest 只描述当时版本。

详细数字、负例与最终渲染凭据见 [Transformer 专项审查](../../../arrow_semantic_audit/transformer/README.md)。这些检查不证明任意源码等价，也不证明所有文字与箭头在任意缩放下无碰撞。
