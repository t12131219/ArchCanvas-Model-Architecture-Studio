# 从 Transformer 源码到三层架构图：图元对应、语义依据与程序化排布

本文针对所给的图1、图2、图3，以及 `pytorch_transformer_original.zip` 和 `tensor2tensor-1.0.14.tar.gz`。重点不是复述 Transformer 原理，而是回答：**源码中的什么事实应该成为哪个图元，为什么这样映射，以及怎样用程序分配图元的位置、大小、间距和连接线。**

最核心的结论是：不能把“类定义”直接变成“一个矩形”，再交给自动布局。要先得到带有调用关系、张量端口、层级和来源证据的语义图，再用可复用的视觉模板进行约束布局。图3的紧凑来自“整体双栏、层间竖排、Q/K/V 横排、Attention 内部横向流水线、残差走侧边”的组合，而不是某一种全局自动排图算法。

交付目录中的 [draw_transformer.py](draw_transformer.py) 是可运行示例；它静态读取 PyTorch 源码，不导入或运行模型，以一个明确编写的 Transformer 语义适配器生成三种粒度的 SVG 和可审查的 JSON。它展示实际落地方法，不宣称能够自动理解任意 Python 模型。本文对 Tensor2Tensor 的对应关系另外逐项说明，避免把两份实现中的差异混成一张“看似通用”的图。

## 1. 先确定画的是哪一份实现、哪一种配置

### 1.1 本文的主图口径

主依据是 [PyTorch transformer.py](sources/pytorch_transformer_original/transformer.py)，采用构造函数默认结构：

| 项目 | 选定事实 | 源码依据 |
|---|---|---|
| 模型入口 | `Transformer.forward(src, tgt, …)` | 470–499 行 |
| 张量顺序 | batch first：`[B, L, D]` | 7 行；各 `forward` 与 reshape |
| Encoder / Decoder 层数 | 各 6 层 | 405–415 行 |
| 隐藏宽度 / FFN 宽度 / 头数 | `D=512, F=2048, h=8, d_k=D/h=64` | 409–414 行；118–120 行 |
| 子层顺序 | Post-LN：`LayerNorm(x + Dropout(Sublayer(x)))` | 284、287、352、361、365 行 |
| FFN 激活 | **ReLU** | 191、194 行 |
| 位置编码 | **固定正弦/余弦** | 197–233 行 |
| 网络输出 | logits，形状 `[B,T,V_tgt]` | 430、487、499 行 |
| 概率 Softmax | 主 `forward` 之外的解释操作 | 主返回值没有此调用 |
| 目标序列右移 | 调用方准备输入，主网络不自动右移 | [example.py](sources/pytorch_transformer_original/example.py) 34–39 行 |
| 因果 mask | 调用方传入；`tgt_mask=None` 不会自行生成 | 476、494 行；example 43、50 行 |

这里用 `S` 表示源序列长度，`T` 表示目标序列长度，`D=d_model`，`F=d_ff`，`V_tgt` 表示目标词表大小。源码没有确定 `B,S,T,V_tgt` 的单一取值，因此图中保留符号形状。它们是静态推导结果，不是运行观测。

绘图口径为 teacher forcing 下的一次前向结构；推理时的自回归循环另外说明。`Dropout` 在概览和细节图中折叠到说明文字，但在语义记录中保留。若选择 eval 模式，它才在数值上成为恒等操作；不能因为省略图元就说训练代码没有 Dropout。

特别注意：`example.py` 使用的是 **2 层、D=128、F=512**，不是构造函数的 6 层默认配置。若以该示例调用为入口，图上的层数和维度也必须相应变化。

### 1.2 两份源码的身份与可追溯性

本次核对的压缩包 SHA-256：

```text
pytorch_transformer_original.zip
7b450cd08737e14b4e9ad33cb240a53be08bf5882986b3d43fa5988d644ae552

tensor2tensor-1.0.14.tar.gz
83dd1393fdceeeddd77922a36798b7200b979f1c00424b737498438157b8b82f
```

`pytorch_transformer_original` 是一份可读的教学实现；文件名中的 original 不能作为“2017 年官方原始 PyTorch 代码”的证明。Tensor2Tensor 是另一个实现体系，包含模型 body、modality、训练框架等分层。两者可以对齐到相同的数学结构，但不能把其中一个的函数名、参数共享和张量包装直接套到另一个上。

本目录的 `sources/` 保存由这两个包解压的只读分析副本，本文行号以这些文件为准。未执行其中模型，也未修改原始压缩包或既有源码。

## 2. 三张图是同一语义图的三种可见粒度

| 可见粒度 | 图1 | 图2 | 图3 |
|---|---|---|---|
| 全局组成 | Embedding、PE、Encoder、Decoder、输出头 | 相同 | 相同 |
| 一层内子层 | Attention / FFN / Add & Norm | 相同 | 相同 |
| Attention 内部 | 折叠成一个块 | 列出投影、SDPA、Concat、输出投影 | 展开 Q/K/V 分支、张量、分头、矩阵运算、mask |
| FFN 内部 | 一个块 | Linear → 激活 → Linear | 同时展示算子和宽度变化的张量 |
| Add & Norm | 一个黄块和残差线 | 补充文字 | 展开求和、LayerNorm、输入输出端口 |
| 重复结构 | 一个代表层 + `N×` | 一个代表层 + `N×` | 一个代表层详细展开 + `N×` |

程序中应当保留同一套稳定语义身份，例如：

```text
transformer
├─ source_input
├─ source_embedding
├─ source_position_add
├─ encoder_stack: repeat[6]
│  └─ encoder_layer_template
│     ├─ self_attention
│     │  ├─ q_projection / k_projection / v_projection
│     │  ├─ split_heads
│     │  ├─ scaled_dot_product_attention
│     │  ├─ merge_heads
│     │  └─ output_projection
│     ├─ residual_norm_1
│     ├─ ffn: linear1 → relu → dropout → linear2
│     └─ residual_norm_2
├─ target_input / target_embedding / target_position_add
├─ decoder_stack: repeat[6]
│  └─ decoder_layer_template
│     ├─ masked_self_attention / residual_norm_1
│     ├─ cross_attention / residual_norm_2
│     └─ ffn / residual_norm_3
└─ generator → logits
```

这是一棵**包含关系树**；另外还需要一张**数据流图**。例如 Encoder 输出 `M` 到 Decoder 的 K/V，是跨树枝的数据边；残差旁路是跨越子层内部的边。只保存上述树，不足以还原图3。

三个视图通过展开/折叠同一子图得到。折叠 `self_attention` 时，把子图内部边隐藏，但必须保留边界输入、输出、mask 等端口。展开后，连接到这些端口的外部边应继续接到正确的内部生产者/消费者。

可以把图1形式化为细图的商图：细节点按语义分组后，每组变为一个可见节点；边界连接继承。图2、图3细分这些组。**展开只增加可见细节，不能改变数据依赖、参数身份或 mask 行为。**

图3也不是“把所有运算都展开”。它详细展示 Encoder self-attention 和 Decoder masked self-attention，而对 cross-attention 的 SDPA 保持紧凑。这是受解释目标驱动的非均匀展开：同一算子模板可以采用不同展示深度，仍指向相同种类的语义操作。

## 3. 图元与源码为什么不是一对一

至少有下面六种对应关系：

| 对应类型 | 本例 | 图形含义 |
|---|---|---|
| 一个源码对象 → 多个图元 | `MultiHeadAttention` | 容器、Q/K/V、split、SDPA、merge、Wᴼ 都来自它及其被调用函数 |
| 多条语句 → 一个图元 | `norm1(x + dropout1(attn_out))` | 概览中的一个 Add & Norm |
| 一个函数定义 → 多个调用实例 | `MultiHeadAttention.forward` | Encoder self、Decoder self、Decoder cross 三种实例 |
| 一条重复语句 → 一个代表层和标记 | `for layer in self.layers` | `N×` 是层序列的折叠，不是权重共享 |
| 一个表达式 → 一个非矩形图元 | `x + pe`、`x + sublayer_out` | 带 `+` 的圆、汇合点和旁路线 |
| 无源码算子 → 解释性图元 | 输出概率 Softmax、张量格子、N括号、注释 | 必须记录它是解释/展示，不冒充模型模块 |

因此，一个图元至少应携带：

```json
{
  "semantic_id": "encoder.layers[*].self_attn.q_projection",
  "operation_kind": "Linear",
  "instance_pattern": "encoder.layers[i].self_attn.w_q",
  "source_refs": [
    {"file": "transformer.py", "start": 122, "end": 122},
    {"file": "transformer.py", "start": 156, "end": 156}
  ],
  "inputs": {"x": {"shape": ["B", "S", "D"]}},
  "outputs": {"q_projected": {"shape": ["B", "S", "D"]}},
  "parameter_identity": "encoder.layers[i].self_attn.w_q.weight",
  "display": {"role": "projection", "label": "Linear (W^Q)"},
  "evidence_kind": "static_source"
}
```

这里 `semantic_id`、源位置、参数身份、展示标签各司其职。把标签改成中文不改变源码对象；把同类算子涂成同色也不意味着它们共享参数。JSON 是推荐的数据契约示意，实际示例输出的字段以脚本和生成文件为准。

### 3.1 三种“相同”必须分开

1. **算子类型相同**：Q、K、V 投影都是 Linear，使用同一种矩形轮廓。
2. **结构模板相同**：Encoder self、Decoder self、Decoder cross 都复用 MHA 模板，但端口绑定和 mask 配置不同。
3. **参数对象相同**：只有明确绑定同一权重对象，才标记权重共享。

PyTorch `clones()` 在 23–25 行用 `copy.deepcopy` 产生独立模块，Encoder / Decoder 在 294、372 行使用它。每层拥有独立可训练参数。即使初始副本可能数值相同，也不构成参数对象共享；本模型还会重新初始化矩阵参数。

`encoder.layers[0].self_attn.w_q` 与 `decoder.layers[0].self_attn.w_q` 可以长得一样、颜色相同，却不是同一个权重。反过来，`tie_tgt_embedding_and_generator=True` 时，435 行把 generator 的 weight 指向目标 Embedding 的 weight，才是应当用关联标记表达的共享；默认是 False。

还有一个容易漏掉的事实：该 PyTorch 实现只有一个 `self.position` 对象，encode 和 decode 都调用它，图中却画两枚 PE 波形。两枚图元表达两个调用位置，不表示源码构造了两个独立可学习 PE 模块。它使用固定 buffer，无可学习位置参数。

## 4. 整体结构逐项对应

下面各表中的行号都来自本目录源码副本。P 表示 PyTorch `transformer.py`；T 表示 Tensor2Tensor `models/transformer.py`，其他文件另行标明。

| 图中的图元/连接 | PyTorch 证据 | 为什么这样画 |
|---|---|---|
| Inputs → Input Embedding | P420、236–245、450 | 整数 token id 经查表成为 `[B,S,D]`，并乘 `sqrt(D)` |
| Output Embedding | P421、461 | 消费调用方已经准备的 `[B,T]` 目标输入；和源 Embedding 参数不同 |
| 正弦波 → 加号 | P214–232 | 位置 buffer 按长度截取后逐元素相加，圆加号表达实际加法 |
| Encoder 容器 `N×` | P291–303 | 模块列表顺序执行，输出传给下一层 |
| Encoder self-attention 的三输入 | P278–283 | query/key/value 都绑定同一个 `x`，投影后的 Q/K/V 才不同 |
| Attention → Add & Norm | P284 | 先 attention branch 的 Dropout，再残差和，再 LayerNorm |
| FFN → Add & Norm | P286–287 | 第二个子层及其独立 norm2，不能共用 norm1 |
| Encoder output / memory | P451、489 | 是完整 Encoder stack 最后的输出，不是中间某个 Attention 的输入或权重 |
| Decoder masked self-attention | P345–352 | Q/K/V 来自 Decoder 当前输入；消费 tgt mask 和目标 padding mask |
| Decoder cross-attention | P355–361 | Q 来自 masked self-attention 之后的状态；K/V 来自 memory |
| Decoder FFN + 第三次 Add & Norm | P364–365 | Decoder 每层有三个子层，Encoder 每层只有两个 |
| Linear 输出头 | P430、499 | `[B,T,D] → [B,T,V_tgt]`，不是 MHA 内部的 Wᴼ |
| 输出概率 Softmax | P499 只有 generator 返回值 | 可加入解释边，但应画成虚线/标注 `outside forward` |

对于 Encoder 的一层，可把 `forward` 改写成保持语义的中间表示：

```python
x0 = layer_input
a  = self_attn(query=x0, key=x0, value=x0, padding_mask=src_padding)
x1 = norm1(x0 + dropout1(a))
f  = ffn(x1)
x2 = norm2(x1 + dropout2(f))
layer_output = x2
```

这种带版本的变量比原源码反复赋值 `x` 更适合画图：它能区分“哪一个 x”走旁路，哪一个 x 进入下一子层。对应 Decoder：

```python
t0 = layer_input
a  = self_attn(t0, t0, t0, causal_mask, target_padding)
t1 = norm1(t0 + dropout1(a))
c  = cross_attn(query=t1, key=M, value=M, padding_mask=source_padding)
t2 = norm2(t1 + dropout2(c))
f  = ffn(t2)
t3 = norm3(t2 + dropout3(f))
```

画 cross-attention 时，三端口来源必须是 `Q←t1`、`K←M`、`V←M`，不能只因为三个投影形状相同，就把它们全部接到 Decoder 竖直主干。

## 5. 图3的详细图元：Attention

### 5.1 Q/K/V 三列来自哪里

P122–125 定义了 `w_q / w_k / w_v / w_o` 四个 Linear；P156–158 分别执行前三个投影并分头。因此图3上方的三个并列 Linear 不是装饰，也不是三层串行网络，而是同一 Attention 内的三条角色分支。

```text
Self-attention:
                     X
              ┌──────┼──────┐
             WQ     WK     WV        三个独立参数映射
              │      │      │
              Q      K      V

Cross-attention:
        Decoder state H        Encoder final memory M
                │                  ┌─────┴─────┐
               WQ                 WK           WV
                │                  │            │
                Q                  K            V
```

“并列”表示这些分支没有彼此的数据依赖；并不保证某个运行时一定让它们在三块设备上并行执行。确定的列顺序 Q、K、V 来自注意力角色的阅读约定，不能依赖字典遍历或自动布局随意排序。

在该实现中，每个 Linear 都是一次 `D→D` 的整体投影，然后再把最后维度重排成 h 个头。图3不必画 h 份 `Linear`。按数学式 `XW` 的约定，各头 `W_i^Q` 可以对应整体权重的输出列块；PyTorch 的 `nn.Linear.weight` 实际存储为 `[out,in]` 并计算 `X @ weight.T`，因此对应存储张量的输出行块。“每头有子空间”和“源码显式实例化 h 个 Linear 模块”是两件事。

### 5.2 张量格子分别表示什么

| 阶段 | Self-attention | Cross-attention | 对应代码 |
|---|---|---|---|
| query 输入 | `[B,L,D]` | `[B,T,D]` | P147–158 |
| key/value 输入 | `[B,L,D]` | `[B,S,D]` | 同上；P355–358 |
| 投影后的 Q | `[B,L,D]` | `[B,T,D]` | `w_q(query)` |
| 投影后的 K/V | `[B,L,D]` | `[B,S,D]` | `w_k(key)` / `w_v(value)` |
| 分头后的 Q | `[B,h,L,d_k]` | `[B,h,T,d_k]` | P129–136 |
| 分头后的 K/V | `[B,h,L,d_k]` | `[B,h,S,d_k]` | 同上 |
| `QKᵀ` 分数 | `[B,h,L,L]` | `[B,h,T,S]` | P70 |
| Softmax 权重 A | `[B,h,L,L]` | `[B,h,T,S]` | P92 |
| `A @ V` | `[B,h,L,d_k]` | `[B,h,T,d_k]` | P100 |
| 合并 heads | `[B,L,D]` | `[B,T,D]` | P138–145、169 |
| Wᴼ 输出 | `[B,L,D]` | `[B,T,D]` | P170 |

表中 `L=S` 用于 Encoder，`L=T` 用于 Decoder self-attention。此 PyTorch 实现让每头 Q/K/V 的宽度相同；更一般的模型可能有独立的 `d_k` 和 `d_v`，不能硬编码成永远相等。

格子是张量**示意符号**，不是把真实的 512 列或 8 个头逐格画出来。建议规定“显示第一个 batch 的二维示意切片，格数不代表真实尺寸”，再用文字给出完整 shape。图中画成同样大小的格子，不应让读者误以为 `S=T`。

Q 蓝、K 绿、V 粉是一种角色编码；同一角色在不同 Attention 实例中同色。它不表示 Q/K/V 的值相同，也不表示张量被缓存。Concat 中多色条带若用来表达头，应另给“条带表示 head”的图例，不能把 Q/K/V 三色直接当作三类 head：**合并的是各头的 `A_i @ V_i` 输出，不是把 Q、K、V 拼接起来。**

### 5.3 SDPA 里面为什么是这一顺序

本 PyTorch 实现的核心表达式：

```python
scores = q @ k.transpose(-2, -1) / sqrt(d_k)
scores = scores.masked_fill(causal_mask, -inf)     # 如果提供
scores = scores.masked_fill(padding_mask, -inf)    # 如果提供
A = softmax(scores, dim=-1)
A = nan_to_num(A, nan=0.0)
A = dropout(A)                                  # 训练时非恒等
head_out = A @ v
```

因此最详细的局部模板应是：

```text
Q ──┐
    MatMul(Q,Kᵀ) → Scale(1/√d_k) → Add/Apply mask → Softmax → [Dropout] → MatMul(A,V) → head_out
K ─T┘                                                                            ↑
V ────────────────────────────────────────────────────────────────────────────────┘
```

P70 对应第一个矩阵乘法和缩放；P72–90 对应 mask；P92–100 对应归一化、全遮挡行保护、dropout 和第二个乘法。矩阵乘法建议写 `@` 或 `MatMul`，不要只写圈内 `×`，否则可能被误解为逐元素乘法。

Softmax 沿 key 轴归一化，即每个 query 行在有效 keys 上分配注意力。通常在 Dropout **之前**每行和为 1；本实现遇到全部被 mask 的行会用 `nan_to_num` 把该行清零，因此不能绝对写成“所有行总是和为 1”。训练时 Dropout 后的权重也未必逐行和为 1。

### 5.4 因果 mask 的位置和形状

`make_causal_mask()` 在 P28–38 返回上三角布尔矩阵，主对角线以上为 True，即禁止 `j>i`。P82 将对应分数置为 `-inf`，随后 Softmax 使其权重为 0。

所以 mask 图元应该接到 **scores / logits** 的边或加法节点上，位于 Softmax 之前；不能画成“先 Softmax，再把未来输出删掉”，也不能画成直接遮住 V。

```text
允许关系（行=query i，列=key j）：
        j0 j1 j2 j3
i0       ✓  ×  ×  ×
i1       ✓  ✓  ×  ×
i2       ✓  ✓  ✓  ×
i3       ✓  ✓  ✓  ✓
```

图3对 Decoder 画出了因果 mask，但还应说明：Encoder self 和 cross-attention 也可以有 **source padding mask**；Decoder self 可以同时有 target padding mask。它们不是因果 mask，图中可以以细小控制端口或说明表达，不能从“没有画三角形”推导出它们完全没有 mask。

此 PyTorch `forward` 不会自动保证 causal；程序化绘图应记录 `mask_policy=provided_by_caller`，只有选定 `example.py` 或明确的调用契约后，才把 masked self-attention 画成实际采用的执行场景。

### 5.5 Concat heads 与 Wᴼ

P138–145 的 `transpose → contiguous → view` 对应合并 heads，P169–170 再执行 `w_o`。这使图3中的“拼接条带”和紫色 `Linear(Wᴼ)` 都有明确来源。

`Wᴼ` 是 Attention 内的 `D→D` 投影。图最上方 generator 是 `D→V_tgt` 的词表投影。二者可以同属 Linear 风格，但必须有不同语义身份和维度标签；不能因为都叫 Linear 就合并成同一节点。

## 6. 图3的详细图元：FFN、Add & Norm、Embedding

### 6.1 FFN 横向展开为什么合理

P188–194 给出：

```python
ffn(x) = linear2(dropout(ReLU(linear1(x))))
```

它作用在最后一维，对每个位置使用相同权重：

```text
[B,L,D] → Linear(D→F) → ReLU → Dropout → Linear(F→D) → [B,L,D]
```

因此图3的 FFN 可以画成上排算子、下排三个张量切片：输入 D 宽、中间 F 宽、输出 D 宽。下排是**上排数据状态的示意**，不是第二条独立计算路径。可以通过浅色引导线或统一标签联系，避免读者把两排当成两组串行运算。

FFN 中保留位置轴 L，只有特征轴变化。不能画成 `S→F` 或把它画成沿序列窗口滑动的卷积。每个层有自己的 FFN 参数；同层所有 token 位置复用该 FFN 权重。

图2、图3写了 `ReLU / GELU`，这是泛化教材标签。针对两份给定源码的默认 Transformer，应该写 **ReLU**。如果希望展示可切换架构，可另画配置分支并注明其不是当前选定执行结构。

### 6.2 Add & Norm 要绑定两个输入和一个输出

推荐将它定义成双输入复合图元：

```text
x ────────────────────────────┐
│                             ↓
└→ Sublayer → Dropout ─────→ Add → LayerNorm → z
```

上面的示意只强调两支汇合；实际绘制可让 skip 走容器左侧，保持主线清晰。更精确的边契约是：

```text
residual_input: x ──────────→ Add.left
sublayer_output: u → Dropout → Add.right
Add.out → LayerNorm.in
LayerNorm.out → next_sublayer.in
```

图3局部黄块画了 `X → + → LayerNorm → Z`，但竖直主线与 `+` 的关系较含糊。程序化图应明确规定：**下一模块消费的是 LayerNorm 后的 Z，而不是加法后的未归一化张量。** 可以将 Z 输出用一小段折线接回主干。

残差不是从网络最底层直接跨到所有 Add & Norm。每个旁路都从**对应子层的输入端**起始，止于该子层的 Add。Encoder 一层有两条，Decoder 一层有三条。旁路跳过的是该子层计算，不跳过本次 LayerNorm。

### 6.3 Embedding 和位置相加不应遗漏的语义

P244–245 不仅查表，还乘 `sqrt(D)`。P232–233 不仅加位置编码，还做 Dropout。若维持图1的简洁，可把前者折叠进 Embedding 的副标题，后者折叠进 PE-add 的说明；图3若自称逐算子详细图，则应该单独显示或明确声明折叠范围。

源和目标 Embedding 分别消费 `[B,S]`、`[B,T]` 整数序列，输出 `[B,S,D]`、`[B,T,D]`。画矩阵不表示 token id 本身已经是浮点特征。

“Outputs (shifted right)”表示 teacher forcing 的输入对齐方式，不能误认为已经生成的最终输出反向流入同一次无环前向图。PyTorch 的 `greedy_decode`（503–553 行）是另一个循环过程：从 BOS 开始，不断取最后一步 logits 的 argmax 并追加 token；没有 KV cache，也不调用输出 Softmax。若要画这个流程，应另加循环图，不把它混入三张静态结构图。

## 7. Tensor2Tensor 1.0.14：如何得到相似图形而不伪造实现结构

完整证据见 [t2t_evidence.md](t2t_evidence.md)。该版本同样是 Post-LN，但以下差异必须保留在映射规则中。

### 7.1 不只读 Transformer body

在 Tensor2Tensor 中，Embedding 与词表投影位于 modality。完整边界是：

```text
T2TModel.model_fn
  → input/target modality bottom（Embedding）
  → Transformer.model_fn_body（准备输入 + Encoder/Decoder）
  → target modality top（词表 logits）
```

相关文件：

- [models/transformer.py](sources/tensor2tensor-1.0.14/tensor2tensor/models/transformer.py)：主干、prepare、base 配置。
- [models/common_attention.py](sources/tensor2tensor-1.0.14/tensor2tensor/models/common_attention.py)：投影、分头、SDPA、位置编码和 bias。
- [models/common_layers.py](sources/tensor2tensor-1.0.14/tensor2tensor/models/common_layers.py)：逐位置 FFN、LayerNorm、shift。
- [models/modalities.py](sources/tensor2tensor-1.0.14/tensor2tensor/models/modalities.py)：`SymbolModality` 的 bottom/top。
- [utils/t2t_model.py](sources/tensor2tensor-1.0.14/tensor2tensor/utils/t2t_model.py)：整体调用范围。

只扫描 `Transformer` 的字段或只分析 `model_fn_body`，会漏掉三张图最底部和最顶部的模块。

### 7.2 对应和差异表

| 图形语义 | T2T 1.0.14 源码事实 | 应采用的映射规则 |
|---|---|---|
| Add & Norm | transformer 59–61：`layer_norm(x + dropout(y))` | 与 PyTorch 同属 Post-LN 模板 |
| Self Q/K/V 三投影 | common_attention 393–402：一次 `qkv_transform`，再 split | 三个逻辑投影图元共享一个 `implementation_group`，各自记录参数切片 |
| Cross Q 与 K/V | common_attention 403–411：独立 q_transform、融合 kv_transform | 视觉可三列，来源分组必须是 H / M |
| Scale | common_attention 415–416 先缩放 Q，再在 337 行 matmul | `Scale(Q) → QKᵀ` 是调用视图；`QKᵀ → Scale` 是等价数学视图 |
| FFN | common_layers 1160–1194：默认两次 1×1 Conv，中间 ReLU | 可别名为 position-wise Linear，并标记实际实现为 1×1 Conv |
| 激活与 PE | base：ReLU；`pos="timing"` | 不把其他变体标签合入当前主图 |
| 因果 mask | transformer 121–123；common_attention 180–191 | 实际 bias 是 `-1e9`，图中 `-∞` 是数学简写 |
| Encoder / Cross padding | transformer 96–98、158、217 | 在添加 target-space/PE 前检测 padding；同一 source bias 广播到 Encoder 与 Cross 的 scores |
| Decoder self padding | 此版本 prepare 只构造 causal bias | 不能照抄 PyTorch 的“合并 target padding mask”行为 |
| 右移 | transformer 123 调用 `shift_left_3d` | 函数虽然叫 left，common_layers 209–215 实际是前补零、右移 embedding |
| 额外条件输入 | transformer 99–103 加 target-space embedding | 严格实现图须添加；经典 Transformer 简图可以折叠注明 |
| 最终 shape | body `[B,T,1,D]`；top `[B,T,1,1,V]` | 图3 `[B,T,V]` 属于去除单例轴的逻辑形状，不是原 API 秩 |
| 最终 Softmax | modalities 98–120 的 top 返回 logits | 与 PyTorch 一样，将概率读出标为解释节点 |
| 权重共享 | base 289 打开共享标志，modalities 86–118 按 scope 复用 | 保存实际模态/词表/scope 条件，不从粉色盒子推断所有 Embedding 共享 |

融合投影的数学展开可以记录为：

```text
implementation: fused_qkv = Conv1x1(X, W_QKV)
                Q,K,V = split(fused_qkv)

logical:        Q = Linear(X, slice_Q(W_QKV))
                K = Linear(X, slice_K(W_QKV))
                V = Linear(X, slice_V(W_QKV))
```

这里 `Conv1x1` / `Linear` 表示包含 bias 的仿射映射；融合 bias `b_QKV` 也按 Q/K/V 输出通道切片。这与该版本词表输出头的无 bias matmul 要分开。这是明确的归一化重写，不是发现了三个独立源码调用。静态 IR 应保留原调用和重写依据，方便切换“实现视图”与“数学解释视图”。Conv1x1 到 Linear 的归一化也需要 kernel=1、逐位置共享参数等条件；T2T 的 sepconv FFN 变体使用更大核，不能套用这个默认模板。

T2T 的 key/value 总宽度可分别配置。因此通用合头标签应为 `h·d_v → D`，而不是永远写 `h·d_k → D`。默认 base 两者相等时，参考图的写法才成立。

## 8. 原图有哪些地方可以保留，哪些地方应调整

三张参考图适合作为**视觉设计目标**；它们不能覆盖源码事实。程序化重建时建议采取如下处理。

| 参考图表达 | 保留的视觉价值 | 针对当前源码的处理 |
|---|---|---|
| 双栏、底部输入、顶部输出 | 与 Encoder/Decoder 两条主干一致 | 保留，源/目标分别用 S/T |
| 黄、蓝、橙、粉等结构色 | 快速识别 AddNorm / FFN / Attention / Embedding | 保留类别编码，补充图例；黑白时仍有文字与轮廓区别 |
| Q/K/V 三列 | 明确投影角色和同源/异源关系 | 保留；T2T 注明融合实现 |
| `N×` | 压缩六层重复结构 | 标成 `N_enc×` / `N_dec×`，注释独立权重串联 |
| memory 横线位置接近 cross | 线短、跨栏关系清晰 | 必须从 **Encoder stack 最终输出端口** 引出，允许沿侧通道绕行 |
| AddNorm 内部右侧 Z | 显示后置归一化 | 后继输入明确来自 Z；无源码依据的小框删掉或注明路径符号 |
| `ReLU / GELU`、`sinusoidal / learned` | 教材层面的变体概括 | 当前源图分别写 ReLU、sinusoidal |
| 顶部 Softmax | 便于解释概率 | 主网络实线止于 logits，Softmax 用虚线并注明解释范围 |
| 很小的矩阵格子 | 在有限空间展示张量状态 | 说明是切片示意，真实 shape 由标签表达 |
| mask 的三角图形 | 一眼说明不能看未来 | 接到 scores-before-softmax；padding mask 单独注明 |

我不能从三张位图恢复 GPT Image 当时的真实排版参数、隐藏提示或内部生成过程。后文提供的是一种可以产生相近层次与紧凑感的可解释约束系统；不是声称原图本身由这组坐标或算法生成。

## 9. 程序化绘图应分成四层，避免源码与坐标混在一起

```text
源码与选定配置
    ↓ 静态解析、调用解析、语义适配
语义 IR：算子、张量、端口、实例、重复、证据
    ↓ 选择展示粒度与图元模板
视图 IR：可见子图、别名、glyph、折叠边界、注释
    ↓ 测量、约束布局、端口分配、路由
场景：矩形/路径/文字/图层/z-order
    ↓ 矢量渲染
SVG / PDF / PNG
```

### 9.1 从源码提取什么

静态分析至少需要处理：

1. 构造函数中的字段、实际参数与配置来源，例如 `self.self_attn` 的类型、`num_heads`、层数。
2. 调用点实参绑定，例如 `query=x,key=memory,value=memory`。
3. `forward` 中的函数式表达式，例如残差加法、`matmul`、`softmax`。这些不会全部出现在 `named_modules()` 的模块树里。
4. `view/transpose` 带来的轴变化，及已知的算子 shape 规则。
5. 顺序容器和重复控制流：层列表里的顺序执行与参数独立性。
6. 模型边界：输入预处理、外部调用方 mask、模型返回 logits 与外部概率解释。

普通 AST 给出语法，**不自动给出完整语义**。需要名称解析、字段绑定、调用图、配置选择和算子规则。遇到动态分支、无法解析的外部调用、未知维度时，应留下 opaque/unknown 子图；不能凭函数名把它补成标准 Transformer。

具体到这个模型，适配器可建立以下识别规则。实际匹配应基于解析后的对象、实参和版本化变量，而不是只在字符串里找关键字：

| 已解析的源码模式 | 产生的语义结构 | 需要验证的条件 |
|---|---|---|
| `attention(query=x0,key=x0,value=x0)` | SelfAttention，三路输入共用 producer x0 | 三个实参确实是同一版本的张量，不是恰好同名 |
| `attention(query=t1,key=M,value=M)` | CrossAttention，H 与 M 两来源组 | M 来源为 Encoder stack 最终输出，不能只凭变量名 memory |
| `norm(x0 + dropout(u))` 且 `u=F(x0)` | ResidualPostNorm pair | norm 解析为 LayerNorm，旁路 x0 对应本次子层输入 |
| `linear2(dropout(relu(linear1(x))))` | FFN 复合图元 | 两个 Linear 的宽度 D→F→D，作用最后一轴，中间无 token 混合 |
| `view(B,L,h,Dh).transpose(1,2)` | SplitHeads 张量变换 | D=h·Dh；Q/K/V 三条路径分别保留 |
| `softmax(mask(Q@Kᵀ/sqrt(Dh))) @ V` | SDPA 子图 | softmax 轴为 keys；mask 在归一化前；V 为独立操作数 |
| `for layer in deepcopy_copies: x=layer(x)` | 顺序 repeat，独立参数 | 元素确为独立对象；循环不是同一个模块反复调用 |

识别成功后，模板选择就有依据：例如 SelfAttention 采用同源三叉，CrossAttention 采用一列 H 加两列 M；PostNorm 采用旁路→Add→LN；FFN 采用逐位置宽度扩张/收缩。图例结构来自这些模式，颜色和方向仍由设计规范提供。

运行 trace 可作为另外一种观测证据，但只覆盖指定输入和模式经过的路径，还可能把融合/内联算子变成低层操作。它既不自动恢复设计层级，也不能证明未经过的分支。本文示例不依赖执行模型。

### 9.2 语义节点与边建议字段

| 实体 | 必备信息 | 为什么需要 |
|---|---|---|
| Operation | stable id、kind、source refs、callsite、config | 同一函数多个实例可区分，标签可改而身份稳定 |
| Tensor | producer、consumer ports、shape、dtype、角色 | 确定边来源，防止 M 或 Q/K/V 接错 |
| Parameter | parameter id、owner、是否 alias、融合切片 | 区分同形、同类和共享权重 |
| Container | children、边界 ports、repeat spec | 支持折叠、展开和 N× |
| Edge | source port、target port、tensor/mask/parameter/annotation 类型 | 实线数据流和解释关系不能混淆 |
| Evidence | 文件摘要、符号、行号、静态/观测/推导/数学重写 | 图能回查来源，不把推导伪装成运行事实 |

### 9.3 视觉模板建议字段

```python
MHA_TEMPLATE = {
    "internal_direction": "top_to_bottom",
    "projection_row": {"order": ["q", "k", "v"], "equal_width": True},
    "attention_core": {"direction": "left_to_right"},
    "external_ports": ["query", "key", "value", "mask", "out"],
    "source_grouping": "derive_from_input_bindings",  # self同源；cross分H/M
    "style_role": "attention",
}
```

结构顺序来自语义事实；`internal_direction`、equal_width、色彩和圆角来自设计。二者分开后，既能保持源码忠实，也能调整审美。不能因为 SVG 上某个图元离另一个更近，就自动改变数据边的绑定。

## 10. 图3的排布关系如何计算

### 10.1 先分层布局，再优化局部

把所有细粒度节点丢给 Graphviz/ELK/dagre，通常会得到很长的算子流水线，难以同时保留 Attention 容器、双栏和矩阵小图。更合适的做法是“复合图 + 每类容器自己的布局模板”：

| 层级 | 排布规则 | 与源码的关系 |
|---|---|---|
| 全画布 | Encoder 左、Decoder 右，主计算自下而上 | 两条输入主干与 Encoder→Decoder memory |
| stack / layer | 子层按执行顺序由下向上 | Encoder 两子层，Decoder 三子层 |
| residual pair | 子层在下，AddNorm 在上，旁路走侧通道 | 子层输出和输入在 Add 汇合 |
| MHA 内部 | 输入来源分组；Q/K/V 三列等宽；下方 SDPA | 三条逻辑分支、分头与计算顺序 |
| SDPA 内部 | 左到右流水线，V 独立接到第二个 MatMul | `QKᵀ → Scale → mask → Softmax → AV` |
| FFN 内部 | 左到右算子链，shape 注释放在相应边附近 | 最后一维 D→F→D |
| 单个图元 | 标题、正文、张量示意分别有内容区 | 让字不与线或格子重叠 |

局部方向和全局方向可以不同。关键是容器入口、出口必须有明确端口和转接路线。不能以“纸面整体向上”推断框内所有横排文字都应反向执行。

### 10.2 先测量内容，再求容器大小

对叶子图元，先测文字，再加 padding。设文字行宽为 `t_w`，行高为 `t_h`，则：

```text
w_leaf = max(w_min, t_w + p_left + p_right)
h_leaf = title_h + n_lines·line_h + p_top + p_bottom
```

包含张量格子的叶子还要加入图元高度和标签间距。实际生产环境建议固定字体文件，用浏览器 Canvas `measureText`、Pango、Pillow 等测量真实字宽；中文、数学斜体、上下标和字体回退不能只按字符个数计算。示例采用保守估宽，保留空间并通过导出检查验证；这不是排版引擎的精确字形测量。

横向 row：

```text
w_row = Σ w_i + (n-1)·g_x
h_row = max(h_i)
x_(i+1) = x_i + w_i + g_x
```

竖向 stack：

```text
w_stack = max(w_i)
h_stack = Σ h_i + (n-1)·g_y
```

容器：

```text
w_container = w_content + p_left + p_right + reserved_route_width
h_container = h_content + title_band + p_top + p_bottom
```

从最内部 SDPA 和投影列开始，逐级向外计算；不能先把 Attention 的外框高度固定死，再强行把所有文字缩进去。正确的依赖顺序是：文字/格子 → 算子 → row/stack → Attention/FFN → residual pair → layer → 双栏 → 画布。

### 10.3 双栏为什么不要求顶端和底端都对齐

Decoder 多一个 cross-attention 子层，因此通常更高。参考图底部 Embedding 接近同一水平线，上方 FFN 也接近对齐，Encoder 与 Decoder 的输入竖线长度明显不同。这不是“两个 stack 顶底同时对齐”，而是允许短 Encoder 留出更长的输入 stem。可根据目的选择以下两种策略。

**策略 A：stack 底边对齐，更强调缩短输入 stem。** 在 SVG 的 y 向下坐标中，设两栏 stack 共用底线 `Y_bottom`，它们测得的高度分别为 `H_enc`、`H_dec`：

```text
Y_enc_top = Y_bottom - H_enc
Y_dec_top = Y_bottom - H_dec
Y_bottom = top_margin + max(H_enc, H_dec + H_output_head)
```

这样 Decoder 顶部有足够空间容纳 generator、logits 和概率解释，而 Encoder 可以自然从较低处开始。

**策略 B：上方同类子层对齐，更强调比较。** 两栏共享 stack 顶线 `Y0`，Embedding 仍共用底部基线；较短 Encoder 的输入 stem 自然更长。本次生成器采用这个策略，接近参考图中 FFN 横向可比较的处理：

```text
Y_embedding = Y0 + max(H_enc, H_dec) + input_clearance
H_input_stem_enc = Y_embedding - PE_clearance - (Y0 + H_enc)
H_input_stem_dec = Y_embedding - PE_clearance - (Y0 + H_dec)
```

两种策略都是展示选择，不由源码唯一决定。不要为满足所有对齐要求而在 Encoder **内部**塞入假子层或大间距，也不要单独压缩 Decoder 的子层间距。若希望版面更紧凑，可改用策略 A；若希望逐行比较 FFN、Norm 等同类结构，策略 B 更方便。

栏宽和栏间距离也由内容与通道共同决定：

```text
W_enc = max(encoder_attention_w, encoder_ffn_w, encoder_addnorm_w) + 外层padding/残差通道
W_dec = max(decoder_self_w, decoder_cross_w, decoder_ffn_w) + 外层padding/残差通道
X_dec = X_enc + W_enc + G_between_columns
W_canvas = left_margin + W_enc + G_between_columns + W_dec + right_margin
```

`G_between_columns` 必须容纳 memory 折线、标签宽度和与外框的安全距离。它不是只为美观留一条空隙。

### 10.4 Q/K/V 三列如何保持等宽和对齐

对于可用内容宽度 `W`、两侧 padding `p`、列间距 `g`：

```text
w_col = (W - 2p - 2g) / 3
x_Q = x_container + p
x_K = x_Q + w_col + g
x_V = x_K + w_col + g
```

Q/K/V 各占一列，各列复用同样的局部布局。当前细图把每列内的 Linear 与 tensor 左右并排，以 24 px 水平箭头连接；tensor 再向下直达 Split，Split 的输出沿相应操作数通路直达 SDPA。投影和 tensor 各有自己的对齐线，不再上下堆叠并用短折线相连。即使 K 的标签较短，也不缩小 K 列：这些列的**语义对称性**比节省几像素更重要。

Cross-attention 可以让 H 占 Q 的一列，M 容器覆盖 K/V 两列。两组分别标 `[B,T,D]` 和 `[B,S,D]`，强调来源差别，而仍共享投影行的水平基线。这正是图3中“同结构易识别，不同来源也可区分”的来源。

### 10.5 子层顺序与并列是两类约束

以下是硬约束示例，使用 y 向下坐标：

```text
top(AddNorm_after_MHA) + height(AddNorm_after_MHA) + gap ≤ top(MHA)
top(FFN) + height(FFN) + gap ≤ top(AddNorm_after_MHA)
top(AddNorm_after_FFN) + height(AddNorm_after_FFN) + gap ≤ top(FFN)

center_y(Q_linear) = center_y(K_linear) = center_y(V_linear)
right(Q_linear) + gap ≤ left(K_linear)
right(K_linear) + gap ≤ left(V_linear)
```

第一组表达向上执行顺序；第二组表达无依赖分支的展示并列。前者由数据流决定，后者由同级角色与阅读约定决定。不要把所有 y 相同节点自动当成运行并行，也不要把所有矩形都排成一条链。

### 10.6 残差侧通道如何分配

每个 residual pair 预留一条不放文字的侧通道。设主模块左边界 `x_module`，通道宽 `r`：

```text
x_skip = x_module - r
branch = (sublayer.in.x, sublayer.in.y + gap / 2)
route = [branch, (x_skip, branch.y), (x_skip, y_add), Add.residual_port]
```

当前栈间距 `gap=24 px`，因此分叉点在模块输入下方 12 px 的入边上，以独立 junction 圆点标明。这样旁路不沿模块下边框延伸，也不会把矩形边框误读成计算路径。这个 junction 是同一输入张量的几何分叉，不增加语义算子。在平面图中旁路呈 U 形，不是计算图中的反馈回路；其箭头始终从子层输入走向后面的 Add。

不同 pair 可以复用相同 x 坐标，因为 y 范围互不重叠；只有跨越区间重叠、且需要在同侧走线的旁路，才分配到不同的 lane。可用区间着色思想：按路径 y 范围排序，选择第一个没有冲突的 lane，否则新开 lane。父容器的 padding 应把这些 lane 算进去。

### 10.7 memory 线为什么必须与端口绑定分开

推荐的路线是：

```text
Encoder stack final output
    → 顶部短延伸
    → Encoder 右侧/双栏间 memory 总线
    → 下行到 cross-attention memory 入口高度
    → cross 内部的 M 来源组
    → K、V 投影
```

允许几何上的水平段出现在 Encoder 中部高度，但起点必须仍是 `encoder_stack.out`。如果为了缩短边而把起点改成最近的 Attention 右边框，就破坏了源码对应关系。

Memory 被每个 Decoder 层复用。代表层图上可以只画一条进入 cross 的边，并写 `M → every decoder layer`；语义 IR 仍记录 repeat broadcast，而不是认为只送到第一个 Decoder 层。

应先完成节点布局，再按端口和障碍物路由。层级布局算法可以帮助决定大方向，正交路由器负责避开容器和文字。布局器不能通过“重新猜连接对象”来解决交叉。

### 10.8 间距怎样形成紧凑的节奏

可以使用一个基础单位 `u=8`，为不同关系赋不同尺度。以下是设计起点，不是原位图反推的精确参数：

| 距离用途 | 起始建议 | 含义 |
|---|---:|---|
| 同一图元内部文字/图标 | `0.75u–1u` | 强相关内容 |
| 算子链相邻步骤 | `1.5u–2u` | 同一局部计算过程 |
| 并列分支列间距 | `2u–3u` | 可区分但仍属同一个 Attention |
| 子层与其 AddNorm | `1.5u–2.5u` | 成对结构 |
| 不同 residual pair | `2.5u–4u` | 不同子层 |
| 容器内边距 | `2u–3u` | 内容与语义边界分离 |
| 残差专用通道 | `3u–4u` | 防止边压住正文 |
| 双栏间距 | 由通道与标签测量，常大于 `6u` | 跨分支 memory 连接 |

字体、描边和箭头也应统一 token，例如主标题 24–30、模块标题 20–24、正文 16–20、shape 14–17，描边约 2–3；最终数值应以实际导出尺寸为准。细图内容很多，如果把整个大画布缩到手机宽度，任何字体策略都无法保证全部可读，应提供可放大的 SVG 或局部放大视图。

当前完整生成器使用固定 9 px 长箭头，并设置 SVG `markerUnits="userSpaceOnUse"`，避免箭头随线宽被放大。带箭头的最后一段至少为 18 px，常用 24 px；端口、间距和路由一起计算，避免用只有几像素的末端折线硬接目标。展开面板的内侧通道距边框 18 px，栈内 gap 为 24 px。路径进入端口时可以穿过边界，但不沿圆角框边界长距离重合。这些是当前 Transformer 模板的明确规则，不是通用自动最优排图的保证。

### 10.9 “紧凑”应当是约束下的优化，不是无条件缩小

可把布局写成有硬约束的优化问题。硬约束包括：不覆盖正文、同级图元不重叠、子图在父容器内、端口连接正确、顺序正确、Q/K/V 列宽一致、路由不穿过禁止区域。

满足这些条件后，再优化：

```text
cost = α·画布面积
     + β·边总长度
     + γ·折点数量
     + δ·非连接边交叉数量
     + ε·同类间距偏差
     + ζ·重要对齐线偏差
```

通常把语义错误和正文遮挡设为不可行，把无连接边交叉设较高代价，最后才压缩面积。否则优化器可能为减少面积，让箭头穿过标签，甚至把 Q/K/V 顺序交换。

实际无需一开始就引入复杂求解器。对 Transformer 这种模板明确的图，先用确定性 measure/arrange 规则满足大多数硬约束，再做少量局部调整，通常更稳定。通用模型的未知复合区域才交给层次 DAG 布局器；生成的端口和容器仍由上层约束保护。

### 10.10 同一节点展开后怎样不把整张图打乱

保留稳定 id、父容器、可见粒度和旧局部位置。展开 Attention 时：

1. 根据同一语义子图生成详细内部布局。
2. 保持入口/出口端口的身份；重新计算子图包围盒。
3. 优先在原容器预留空间和所属栏内扩张。
4. 必须扩栏或增加高度时，仅移动受影响的兄弟与祖先。
5. 重算涉及该边界的路由，保留其他无关位置与人工锁定对象。

这是“语义图不变，视图发生变化”。重新从零给所有节点随机排一次，虽然也能得到一张新图，但不利于比较三个粒度、手工微调和后续复用。

## 11. 图例体系怎样区分同类结构与不同结构

颜色不应同时编码太多含义。建议用三个相互独立的通道：

| 视觉通道 | 编码内容 | 本例 |
|---|---|---|
| 外框填充色 + 文字标题 | 模块/复合算子类别 | Attention 橙、FFN 蓝、ResidualPostNorm 黄、Embedding 粉 |
| 内部张量色 + Q/K/V 标签 | 张量角色 | Q 蓝、K 绿、V 粉；必须同时保留字母 |
| 边型、边标签、端口 | 关系类别 | 实线数据、mask 控制边、虚线解释关系、权重 alias 关联 |

形状再提供一层区分：圆 `+` 表示逐元素和，矩形表示变换，网格表示张量，圆角大外框表示包含关系，括号/`N×` 表示重复。图元的颜色或轮廓不应单独承担“共享参数”的表达。

同类型且不同实例：相同主色和模板，不同稳定 id / 参数 scope。不同类型但共同属于 Attention：同一橙色容器，内部用标签和图元形状区分 Linear、MatMul、Softmax。Cross 与 Self：共享 MHA 外观语言，但由来源分组、端口绑定、mask 标记以及 S/T shape 区分。

特别容易误会的两个 Softmax：

- Attention 内 Softmax 沿 key 轴处理 `[B,h,T_q,T_k]`，是源码里的真实操作。
- 顶部概率 Softmax 沿 vocabulary 轴处理 logits `[B,T,V_tgt]`，本实现中是模型外解释。

它们应共享“Softmax 算子”的基本样式，但拥有不同 id、轴标签和来源标记。不能把内部一个 green box 的源码位置拿来证明顶部另一个 green box。

对黑白输出，保留类型文字、容器标题、边型和 Q/K/V 字母；即使颜色消失，仍能认出结构。也尽量避免渐变与手绘纹理作为唯一语义依据，程序化 SVG 使用纯色更容易控制一致性和导出质量。

## 12. 一个最小的、可直接运行的布局例子

下面的示例只画一个竖向子层与它的 Post-LN 残差组合，用来演示**坐标从尺寸、端口和统一 token 计算**。它不是完整 Transformer；完整三图生成器在下一节。

保存为 `mini_residual.py` 后执行 `python3 mini_residual.py`，会产生 `mini_residual.svg`，只依赖 Python 标准库。本目录已经保存并实际运行了这份 [最小示例](mini_residual.py)：

```python
from dataclasses import dataclass
from pathlib import Path
from html import escape

@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    def port(self, side):
        return {
            "in": (self.x + self.w / 2, self.y + self.h),
            "out": (self.x + self.w / 2, self.y),
            "left": (self.x, self.y + self.h / 2),
        }[side]

u = 8
pad, gap, lane = 3*u, 3*u, 4*u
norm_h, sub_h, core_w = 7*u, 17*u, 45*u
margin = 4*u

# 先测量父容器，再摆放子容器；不是给每个图元分别手填坐标。
parent = Box(margin, margin,
             2*pad + lane + core_w,
             2*pad + norm_h + gap + sub_h)
core_x = parent.x + pad + lane
norm = Box(core_x, parent.y + pad, core_w, norm_h)
sub = Box(core_x, norm.y + norm.h + gap, core_w, sub_h)

elements = []
def rect(b, color):
    elements.append(
        f'<rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" '
        f'rx="12" fill="{color}" stroke="#17212b" stroke-width="2"/>')

def label(x, y, s, size=18):
    elements.append(
        f'<text x="{x}" y="{y}" text-anchor="middle" '
        f'font-family="DejaVu Sans,sans-serif" font-size="{size}">{escape(s)}</text>')

def edge(points):
    # 留出至少18px的直线终段，避免在箭头头部附近才转弯。
    a, b = points[-2:]
    assert ((b[0]-a[0])**2+(b[1]-a[1])**2)**.5 >= 18
    data = " ".join(f"{x},{y}" for x, y in points)
    elements.append(
        f'<polyline points="{data}" fill="none" stroke="#17212b" '
        f'stroke-width="2" stroke-linejoin="round" marker-end="url(#arrow)"/>')

rect(parent, "#e5f3fc")
rect(norm, "#fff6bf")
rect(sub, "#ffddb8")
label(norm.x + norm.w/2, norm.y + 24, "Add & Norm (Post-LN)")
label(norm.x + norm.w/2, norm.y + 44, "z = LN(x + Dropout(F(x)))", 14)
label(sub.x + sub.w/2, sub.y + sub.h/2, "F(x): attention or FFN")

# 主边来自F的输出，旁路来自F的输入；两者进入复合图元的不同端口。
edge([sub.port("out"), norm.port("in")])
sx, sy = sub.port("in")
lx, ly = norm.port("left")
skip_x = core_x - lane
tap_y = sy + gap/2  # 输入线上的分叉；距模块底边12px，不沿边框走线。
edge([(sx, sy + pad + margin/2), (sx, sy)])
edge([(sx, tap_y), (skip_x, tap_y), (skip_x, ly), (lx, ly)])
elements.append(f'<circle cx="{sx}" cy="{tap_y}" r="2.5" fill="#17212b"/>')
label(skip_x - 10, (sy+ly)/2, "x", 16)
W, H = parent.x + parent.w + margin, parent.y + parent.h + margin
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">
<defs><marker id="arrow" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="8" refX="9" refY="4"
orient="auto"><path d="M0,0 L9,4 L0,8 Z" fill="#17212b"/></marker></defs>
<rect width="100%" height="100%" fill="white"/>
{"".join(elements)}</svg>'''
Path("mini_residual.svg").write_text(svg, encoding="utf-8")
```

这里有两点刻意保持简单：黄块内部的 Add 和 LN 仍被折叠；字宽没有真实测量。它演示父子尺寸依赖与残差端口来源，不代替完整图3的细节布局；最小示例也使用固定 9 px 箭头、至少 18 px 终段，并把输入 junction 放在模块下方 12 px。换成 MHA 或 FFN 后，只需要更换 `F(x)` 的内部内容测量和绘制模板，残差 pair 的排布规则可以复用。

## 13. 完整可运行示例：同一结构生成三种粒度

完整文件为 [draw_transformer.py](draw_transformer.py)，默认读取同目录 `sources/pytorch_transformer_original/transformer.py`。推荐在本交付目录执行：

```bash
python3 draw_transformer.py --source sources/pytorch_transformer_original/transformer.py --out generated
```

它的职责被限定为：

1. 使用 `ast.parse` 静态读取、定位有关类和函数，记录源码摘要和位置。
2. 使用明确的当前模型适配器描述语义层级、实例角色和连接，而不是从矩形名称猜关系。
3. 同一结构生成 overview、modules、detailed 三个 SVG。
4. 用共享视觉 token 和复合容器规则计算尺寸、位置与路线。
5. 输出语义/来源/布局记录，供检查和后续更换后端使用。

**人工指定的语义规则仍然是程序的一部分**。AST 找到某个符号，不等于已自动证明其函数体符合某种 Transformer 语义。更换为另一个实现、改成 Pre-LN、引入 RoPE/GQA/MQA、改动 mask 或参数绑定时，都应重新核对适配器，不应直接沿用图。

也可以直接静态读取原 zip，不解压、不执行其中代码：

```bash
python3 draw_transformer.py --archive ../pytorch_transformer_original.zip --out generated
```

SVG 生成只需标准库。本文的 PNG 预览由环境中已有的 `rsvg-convert` 转换，例如：

```bash
rsvg-convert generated/figure3_detailed.svg -o generated/figure3_detailed.png
```

### 13.1 生成结果

生成目录的图形文件：

- [图1：概览视图](generated/figure1_overview.svg)
- [图2：模块视图](generated/figure2_modules.svg)
- [图3：细节视图](generated/figure3_detailed.svg)

图3采用与参考图一致的主要视觉语法，但以源码语义为准：memory 来自完整 Encoder 最终输出，ReLU / sinusoidal 是已选结构，Dropout 有折叠说明，网络输出是 logits，概率 Softmax 是模型外解释。

当前细图采用**每个容器分别指定粒度**：Encoder self / Decoder self 展开 SDPA 运算，cross 只展开 Q/K/V 来源与投影，把重复的 SDPA 代数折叠成横条，仍保留 split、merge、Wᴼ 和边界端口。`measure_stack` 为 detailed FFN、cross、self 分别分配 210、438、542 px 高度，栈 gap 为 24 px；这次调整只改变视图与几何，`semantic_ir.json` 的模型结构不变。图3由之前的 `1600×2562` 缩为 `1600×2308`，高度减少约 9.9%。PE 波形、三角 mask、渐变等还可以替换为注册的 SVG glyph；本次示例用文字 PE 和 mask 框表达相应语义，不做原位图的逐像素复刻。

细图 PNG 预览如下；需要查看小字和路径时，打开上面的 SVG 放大：

![程序化生成的 Transformer 细节图](</home/fzg/PycharmProjects/ArchCanvas/Constraint relationship of architecture diagram/transformer_programmatic_guide/generated/figure3_detailed.png>)

具体布局和语义的 JSON 与 SVG 一起保存在 `generated/`。它们用于审查规则产生的结果，而不是把 SVG 像素再反向识别成模型。

| 文件 | 内容 |
|---|---|
| [source_evidence.json](generated/source_evidence.json) | AST 定位的符号、行范围、原文片段和文件摘要 |
| [semantic_ir.json](generated/semantic_ir.json) | 明确适配的算子、层级、端口、参数身份与边 |
| [layout_detailed.json](generated/layout_detailed.json) | 细图包围盒、路径折点与连接记录 |
| [layout_checks.json](generated/layout_checks.json) | 几何/端口检查结果及其覆盖限制 |
| [route_diagnostics.json](generated/route_diagnostics.json) | 独立读取原始 SVG 后的路径、框边界与端口复核回执 |
| [index.html](generated/index.html) | 三个 SVG 的本地查看入口 |

### 13.2 示例实际实现到哪一层

| 能力 | 本次可运行示例 | 完整通用工具还需要 |
|---|---|---|
| 源码读取 | AST 静态定位，少量片段 guard，不执行模型 | 跨文件名称解析、动态配置/分支处理 |
| 语义提取 | 人工编写的当前 Transformer 适配器 | 更广的算子 lowering、未知区域处理和完整绑定证明 |
| 层次与排序 | IR 中的 parent/children/rank 控制子层排布 | 任意 DAG 的复合层次推导 |
| 尺寸测量 | 按粒度预设的内容高度、统一栏宽与间距、保守文字余量 | 固定字体的真实测量、长文本自适应、尺寸向祖先传播 |
| 路由 | Transformer 专用残差 junction、memory、18 px 内侧通道、固定箭头与终段规则 | 完整障碍路由与全部标签避让 |
| 展开 | 一次生成三个粒度；细图单独折叠 cross 的 SDPA | 持久画布中局部展开、人工锁定和增量布局 |
| 证明范围 | 来源记录与有限结构/几何检查 | 不能仅靠这些证明任意改动与原图数值等价 |

这张表很关键：本文第9–10节给出的是完整设计方法，伴随脚本是可阅读、可修改的有限实例。它使用显式模板，不是已经实现了自动理解任意源码、完整字体排版与全局最优布局的系统。

### 13.3 如何把它扩成完整工具

更通用的实现可采用以下接口。伪代码强调职责划分，不是本次归档中的 API：

```python
source = parse_sources(root, entry, config)
facts = resolve_calls_and_parameters(source)
semantic_ir = lower_to_semantic_graph(facts, operator_rules)
validate_tensor_bindings(semantic_ir)

for level in ("overview", "modules", "detailed"):
    view = project_view(semantic_ir, level, glyph_catalog)
    measured = measure_bottom_up(view, font_metrics, style_tokens)
    placed = arrange_hierarchy(measured, constraints)
    routed = route_edges(placed, preserve_port_bindings=True)
    validate_scene(routed)
    export_svg(routed)
```

可扩展之处应在 `operator_rules`、语义适配器、glyph catalog 和布局策略；不要在 renderer 内通过 `if label == "Cross Attention"` 临时决定它应该接哪个输入。也不要把真实算子序列写死在 SVG 字符串里，却对外声称图由源码自动恢复。

如果使用 PyTorch 内置 `nn.Transformer`，需要将所用 PyTorch **确切版本**纳入证据。归档的 `torch_builtin_version.py` 只给调用边界，内部实现在外部依赖；不能给不存在于归档中的内部算子编造源码行号。该文件还与主实现存在 generator bias、输入 Dropout 等差异，不宜作为逐算子完全等价替身。

## 14. 应当怎样验证，才能知道图3可信

验证分为语义和视觉，两者不能相互替代。

### 14.1 语义验证

| 需要确认的问题 | 可以检查的证据 |
|---|---|
| memory 是否来自完整 Encoder 输出？ | `encoder_stack.out` 绑定最终层输出，cross 的 K/V producer 为 M |
| Decoder Q 是否来自正确状态？ | cross.query 绑定 masked self 的 Post-LN 输出 |
| mask 是否作用在正确位置？ | mask 消费者是 scores-before-softmax，而不是 V 或概率输出 |
| 三个 Q/K/V 是否仍独立？ | 三个逻辑端口及对应权重；融合实现保留切片对应 |
| AddNorm 是否 Post-LN？ | add.out → norm.in → next.in，不是 next.in 接 add.out |
| N× 是否独立权重串联？ | repeat spec、实例 scope 与 deepcopy/variable scope 证据 |
| shape 能否相乘/相加？ | QK 末轴匹配，AV key 长度匹配，残差两输入形状一致 |
| 解释节点是否被误当源码？ | 最终概率 Softmax 标记 outside-forward；张量格子是注释 |
| 省略了什么？ | dropout、nan guard、padding、singleton 轴等有显式折叠/省略说明 |

不能用“图像看起来像经典 Transformer”验证这些问题。经典图只提供设计参考，最终绑定必须回到给定实现。

### 14.2 视觉验证

建议自动检查并人工查看：

- 同父兄弟的可见内容不重叠；父容器包含全部子图和所分配的边通道。
- 所有端口有合法坐标；箭头落点不在标题文字或无关张量上。
- 路由不穿正文；必要交叉用桥接或清楚标记，不用交叉误表示汇合。
- 投影列等宽、同类标题和 AddNorm 高度一致；长标签换行后仍有 padding。
- Encoder / Decoder 输入基线符合设计，memory 标签不会挤进栏内正文。
- overview 可辨主结构；detailed 在 100% 或局部放大时可读；黑白下仍可辨类型。
- SVG 导出与 PNG 渲染都检查一次，防止字体回退、上下标和裁切差异。

一个自动几何检查通过，只能证明它实际检查的范围。例如矩形不相交，不代表所有曲线都绕开文字；JSON 边绑定正确，也不代表每个手绘 path 都画到了对应端口。生产工具应尽量让**实际绘制路径直接从同一 edge/port 对象生成**，减少这两者分离的机会。

### 14.3 有意义的失败处理

若一个长标签放不下，优先换行或扩大局部容器，再向祖先传播尺寸；不要独自把这一块字号缩得很小。若跨栏 memory 线冲突，扩大通道或移动标签；不要就近改接 Attention 内部。若源码分支无法解析，画 opaque 节点并附来源；不要从教材模板补出确定结构。

## 15. 对当前需求的实施建议

若目标是持续从已有深度学习源码生成这种图，首先实现一条可审查的窄通路：给定模型入口和配置 → 带证据的层级/端口 IR → 一套 Transformer glyph → 三种粒度 → 约束布局与导出。完成这条通路后再增加其他模型族。

对图3，优先做好的部件是：

1. **语义身份与端口**：Q/K/V 来源、memory 最终输出、mask、残差 Add/LN 顺序，决定图是否正确。
2. **复合 glyph**：`MHA`、`SDPA`、`ResidualPostNorm`、`FFN`、`TensorSlice`，决定细节能否复用并保持一致。
3. **bottom-up measure + top-down arrange**：决定长标题、三列分支和不同高度子层能否自然容纳。
4. **专用侧通道与跨栏路由**：决定紧凑条件下连接是否仍然可读。
5. **同一 IR 的局部展开**：保证图1、图2、图3可以逐层解释、互相核对，而不是三张独立示意图。

源码约束了“有哪些实体、如何计算、谁连接谁、哪些参数相同”；视觉系统决定“采用什么图例、在哪个粒度展开、怎么分配空间”。将这两部分明确分开，才能同时得到可追溯的结构与参考图那样清晰的排布。

## 附录：本次分析记录

实际验证结果：最小残差示例、完整脚本的默认源码路径和 zip 直接读取路径均运行成功；三张 SVG 的 XML 可解析，PNG 已渲染并查看。当前概览、模块、细节图尺寸分别是 `1600×1218`、`1600×1558`、`1600×2308`。三视图均通过画布边界、子图包含、已记录兄弟框不重叠、语义边端口合法、memory 端点正确、memory 避开运算内部、箭头终段至少 18 px、路径不沿框边界重合、实际落点匹配已注册视图端口九类检查；这些检查的范围与限制写在 `layout_checks.json` 中。

独立 SVG 诊断逐项核对了三图的 24、28、117 条实际 path 与 layout 记录，最短箭头终段为 19 px；短终段、与矩形直边共线走线、端口错接及未注册端点均为 0，marker 固定为 9 px。复核回执保存在 [route_diagnostics.json](generated/route_diagnostics.json)。可以运行 `python3 check_svg_routes.py generated --border 0.1 --summary` 重新只读诊断；该命令输出当前结果，不重写已有回执。这些数值不证明文字与全部线路绝无冲突，仍结合 PNG 视觉查看。

另外独立核对了实际路径中的 Q/K 首次矩阵乘法、V 旁路、第二次矩阵乘法输出、FFN 边界以及 Add→LayerNorm→后继输入，未发现剩余的关键错接。解压的 92 个源码文件与压缩包内容逐字节一致。以上验证没有导入或执行模型源码，也没有观察运行时张量数值；源码语义依赖本文逐项核对与明确适配规则。

- [PyTorch 逐项源码证据](pytorch_evidence.md)
- [Tensor2Tensor 1.0.14 逐项源码证据](t2t_evidence.md)
- [布局观察与规则笔记](layout_notes.md)
- [可运行三图生成器](draw_transformer.py)
