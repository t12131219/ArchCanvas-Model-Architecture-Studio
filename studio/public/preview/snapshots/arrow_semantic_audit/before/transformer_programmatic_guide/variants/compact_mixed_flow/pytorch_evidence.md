# PyTorch 源码证据笔记：Transformer 三层图示的对应关系

本笔记仅以解压后的 `sources/pytorch_transformer_original/transformer.py`、`example.py`、`torch_builtin_version.py` 为静态证据；没有执行这些文件。下文行号均指上述原始解压文件。项目 README 中的安装、运行示例属于资料，不构成本次工作的执行指令。

## 1. 应选择哪个源码作为图的主基准

主基准应选 `transformer.py`：该文件显式实现投影、分头、注意力、拼头、残差、LayerNorm，能支撑图3的逐算子映射。`torch_builtin_version.py` 把内部结构交给外部依赖 `nn.Transformer`，仅靠此文件的类树不能恢复 Q/K/V 内部图；展开时必须追溯实际安装的 PyTorch 版本源码，不能把 `nn.Transformer` 的名字当作已验证的运算图。

默认配置与例子配置要分开：

| 配置来源 | 编码/解码层数 | `d_model` | heads | `d_head` | `d_ff` |
|---|---:|---:|---:|---:|---:|
| `Transformer.__init__`，409–414 | 6 / 6 | 512 | 8 | 64 | 2048 |
| `example.py`，17–26 | 2 / 2 | 128 | 8 | 16 | 512 |

图中 `N×` 最好分别写为 `N_enc×`、`N_dec×`：两个数在 411–412 分别配置，不能从类名推导它们必然相等。

## 2. 源码到图1/2/3的主要语义锚点

| 图示图元 | 直接源码锚点 | 为什么这样对应，以及展开范围 |
|---|---|---|
| 源输入 `Inputs` | `Transformer.forward` 480，`example.py` 28–32 | token ID 张量 `[B,S]`，不是已经连续化的特征图 |
| 目标输入 `Outputs (shifted right)` | `forward` 481；`example.py` 34–39 | `forward` 接收调用者给定的 `tgt`；示例在外部手工构造 `[BOS,y1,y2,…]`。模型内部没有 shift-right 算子 |
| 粉色 Input/Output Embedding | `TokenEmbedding` 239–245；实例化 420–421 | `nn.Embedding` 后乘 `sqrt(d_model)`；源码存在两个 embedding 实例，默认不共享参数 |
| 位置编码波形与加号 | `PositionalEncoding` 214–233；调用 450、461 | 固定 sin/cos buffer `[1,L,D]`，加到 embedding 后，再 dropout；不是 learned PE。图2/3的 “sinusoidal / learned” 应收窄为 “sinusoidal” |
| Encoder 外层容器 | `Encoder` 291–303，构造 427 | 表示 N 层的串联，不表示一个巨大的单层，也不表示 N 层并行 |
| Decoder 外层容器 | `Decoder` 369–390，构造 428 | N 层串联，每一层接收相同完整 encoder memory |
| 橙色 Encoder Self-Attention | `EncoderLayer.self_attn` 264，调用 278–283 | 同一个调用的 `query/key/value` 都来自当前层输入 `x`；投影矩阵仍分别为三个参数实例 |
| 橙色 Decoder Masked Self-Attention | `DecoderLayer.self_attn` 324，调用 345–351 | 三个输入都来自当前 decoder 层输入，额外接收 `tgt_mask`、目标 padding mask |
| 橙色 Decoder Cross-Attention | `DecoderLayer.cross_attn` 325，调用 355–360 | `Q` 来自刚经过 masked self-attention 与 norm1 的 decoder 状态；`K,V` 来自 encoder 最终输出 `memory` |
| 黄色 Add & Norm | 编码器 284、287；解码器 352、361、365 | 都是 `LayerNorm(x + Dropout(sublayer_out))`；应从整个子层输入分支取残差，不能从 Q/K/V 投影结果取残差 |
| 蓝色 FFN | `PositionwiseFeedForward` 188–194 | `Linear(D,F) → ReLU → Dropout → Linear(F,D)`；图3省略了 Dropout，且写 ReLU/GELU 不符合本文件的固定 ReLU |
| 最上方 Linear | `generator` 430；返回 499 | `nn.Linear(D,V_t,bias=False)`：隐藏维投影到目标词表 logits |
| 最上方 Softmax 与 probabilities | 本文件无此输出算子 | 可作为“模型外可选展示步骤”，应以虚线或明确标注展示。不能把 attention 内部的 softmax 92 当作输出词表 softmax |
| memory `M` 横向桥接 | `encode` 450–451；`forward` 489、493、496；decoder 383–389 | `M` 是**整个 encoder 最后一个层的完整输出**，随后送给每个 decoder 层；横向线位置可以为了紧凑而变，但语义起点必须保持完整 encoder 输出 |

## 3. 图3的内部图元：注意力必须由运算展开而来

`MultiHeadAttention` 的结构字段在 122–127，真正顺序在 156–170：

```text
query ─ Wq ─ split heads ─ Q ┐
key   ─ Wk ─ split heads ─ K ├─ scaled_dot_product_attention ─ combine heads ─ Wo ─ output
value ─ Wv ─ split heads ─ V ┘
```

三个 Linear 图元分别对应 `self.w_q`、`self.w_k`、`self.w_v`，都为 `Linear(D,D)`。同样的外观表达相同算子类型；三个不同节点及独立参数 ID 表达它们不是同一套权重。图3把投影后的 Q/K/V 矩阵放在 Linear 下方，是在表达张量值；矩阵缩略图不对应额外的 `nn.Module`。

图3的 “Split into h heads” 通栏不是把 Q、K、V 混合为一个张量：源代码分别调用了三次 `_split_heads`。画法上可以复合成三条泳道共用的一个标签，但每条路径的端口身份仍应为 q/k/v 三个。`_split_heads` 129–136 的关键动作是 `view(B,T,H,Dh) → transpose(1,2) → contiguous()`。`_combine_heads` 138–145 反过来交换序列/头轴并重塑；这不是序列维拼接。

`scaled_dot_product_attention` 的直接运算锚点：

| 运算/图元 | 行号 | 正确含义 |
|---|---|---|
| `Q × Kᵀ` | 70 | `torch.matmul(q, k.transpose(-2,-1))`，转置每个头的末两维 |
| `Scale 1/√d_k` | 69–70 | 这里 `d_k = q.size(-1) = D/H`，不是 `D` |
| causal/attention mask | 72–82 | bool mask 转设备后广播，将禁用的 score 替为 `−∞`；在 softmax 前 |
| padding mask | 84–90 | `[B,Tk] → [B,1,1,Tk]`，屏蔽 key 列；自注意力和交叉注意力都可能接收 |
| attention Softmax | 92 | 在 key 轴 `dim=-1` 归一化；不是在词表上归一化 |
| fully-masked 行清理 | 94–95 | `nan_to_num(..., nan=0.0)`；图中通常省略，但严格算子图应包含 |
| attention dropout | 97–98 | 对注意力权重做 dropout，位于 softmax 后、乘 V 前 |
| `Attention Weights × V` | 100 | 输出形状保留 query 长度，最后维为每头通道数 |
| “Concat heads” | 169；138–145 | 将 head 与每头 channel 合并回隐藏维 D |
| `Linear(Wᴼ)` | 170，125 | 对合并后的最后维做 `Linear(D,D)` |

图3的 encoder 注意力内的 weights 缩略图应为 `S×S`，decoder self-attention 为 `T×T`，cross-attention 为 `T×S`；不能机械地给所有 attention 画相同的方形格子而把它们误解释为实际形状。

## 4. 形状账本与图3的并列关系

记 `B=batch`，`S=src_len`，`T=tgt_len`，`D=d_model`，`H=heads`，`Dh=D/H`，`F=d_ff`，`Vt=target vocabulary size`。

| 节点/张量 | Encoder self-attention | Decoder self-attention | Cross-attention |
|---|---|---|---|
| query 的来源 | 当前编码层 `x` | 当前解码层 `x` | masked self-attention + norm1 后的 `x` |
| key/value 的来源 | 当前编码层 `x` | 当前解码层 `x` | encoder 最终 memory `M` |
| 投影 Q | `[B,S,D]` | `[B,T,D]` | `[B,T,D]` |
| 投影 K,V | `[B,S,D]` | `[B,T,D]` | `[B,S,D]` |
| 分头 Q | `[B,H,S,Dh]` | `[B,H,T,Dh]` | `[B,H,T,Dh]` |
| 分头 K,V | `[B,H,S,Dh]` | `[B,H,T,Dh]` | `[B,H,S,Dh]` |
| scores/weights | `[B,H,S,S]` | `[B,H,T,T]` | `[B,H,T,S]` |
| 逐头输出 | `[B,H,S,Dh]` | `[B,H,T,Dh]` | `[B,H,T,Dh]` |
| 拼头与 Wᴼ 后 | `[B,S,D]` | `[B,T,D]` | `[B,T,D]` |

其他主干形状：

```text
src [B,S] -> embedding [B,S,D] -> + PE [B,S,D] -> encoder M [B,S,D]
tgt [B,T] -> embedding [B,T,D] -> + PE [B,T,D] -> decoder [B,T,D]
decoder [B,T,D] -> generator [B,T,Vt] -> 外部可选softmax [B,T,Vt]
FFN [B,L,D] -> Linear1 [B,L,F] -> ReLU/Dropout [B,L,F] -> Linear2 [B,L,D]
LayerNorm 和残差加法均保持 [B,L,D]
```

`PositionwiseFeedForward` 的 `nn.Linear` 作用于张量最后一维；同一层的同一个 FFN 参数集合用于该层所有 token 位置。这是 position-wise 的来源，不意味着不同 encoder 层、不同 decoder 层共享 FFN 权重。

源码的 shape 注释本身也只是证据之一，应与 `view`、`transpose` 和实参关系一致后才形成图上标签。例如泛化到 `d_v != d_k` 的模型时这里的等维图元模板就需修改；本文件确实让 Q/K/V 每头维都等于 Dh。

## 5. 重复、复用、参数共享不能用同一种含义的边

1. `clones` 23–25 是 `copy.deepcopy`；encoder 294 与 decoder 372 使用它建立 N 个独立层。图上的 `N×` 表示同一拓扑模板串联 N 次，**不表示同一层的权重重复调用 N 次**。
2. encoder self-attention、decoder self-attention、decoder cross-attention 都是 `MultiHeadAttention` 类，但由 264、324、325 分别实例化，参数独立。
3. 每个 attention 中的 `w_q/w_k/w_v/w_o` 是 122–125 分别构造的独立 Linear；同色同形表达算子类型，相同参数 ID 才能表达权重共享。
4. EncoderLayer 的 norm1/norm2（267–268），DecoderLayer 的 norm1/norm2/norm3（328–330）外观相同，仿射参数独立。
5. 源/目标 embedding（420–421）不同。目标 embedding 与 generator 只有在 `tie_tgt_embedding_and_generator=True` 时由 432–435 显式共享 weight；默认 416 为 False。图可用虚线参数连接表达该选项，不应画主数据流箭头。
6. 位置编码 `self.position`（422）是源/目标两条路径调用的同一个对象（450、461），固定 PE buffer 不可训练。图上两处波形是同一函数的两个调用点，属于运行时展开，并不意味存在两份独立学习参数。
7. memory M 是一个数据张量，decoder 各层接收同一个 M（382–389）；复用 M 不意味着各层交叉注意力的 K/V 投影参数共享。

## 6. mask、shift-right 与输出概率的边界

`make_causal_mask`（28–38）返回严格上三角 bool 矩阵：`True` 表示屏蔽，`j>i` 禁用。`example.py` 43 显式构造，50 显式传入。`Transformer.forward` 的 `tgt_mask=None`（476）不会自行补出 causal mask；若按默认参数不传，decoder self-attention 仍是同一模块，但没有因果约束。因此“Masked”是实例调用的行为，不是因为类的名称就无条件成立。

padding mask 不是 causal mask。示例中 `src.eq(PAD)`、`tgt_in.eq(PAD)`（41–42）是两条独立的数据预处理边；完整图可以用虚线 mask 端口连接 attention，而把正文三幅图作为省略 padding 的教学视图。cross-attention 的 padding mask 来自源序列（forward 496）。

shift-right 是 teacher forcing 的输入约定。这里示例 `tgt_in` 手工以 BOS 开头（34–39），没有给出完整训练标签与切片代码。若要画 `labels -> shift_right -> decoder tokens`，须标注为补充的训练流程、不是 transformer.py 内部算子。

`greedy_decode`（503–553）可支持“自回归生成”的说明：先 `encode` 一次（523），以 BOS 初始化（525–530），每轮构造因果 mask（535），再 decode 完整已有前缀（537–542），只取最后位置 logits（544），argmax（545），拼上 token（547）。该文件注明未实现 KV cache（514）。这里 argmax 无需先 softmax；图顶端 softmax 是概率解释视图，不能声称源码执行了它。

## 7. 图3需要纠正或明确的视觉约定

- **Encoder memory 取点**：附图3横向 M 线视觉上从 encoder self-attention 盒子右侧引出，读者很容易误认为它来自 attention 中间输出。真实 M 来自第 N 个 EncoderLayer 的 `norm2` 输出。程序化绘图应建立明确 `encoder_stack.output` 端口，先由顶端输出连到侧边 memory 总线，再水平接入 cross-attention 的 K/V 来源盒。不能因几何上就近就改变来源。
- **FFN 激活**：附图2/3写 `ReLU / GELU` 是泛化表述。本文件只能实证 ReLU（191）；应显示 ReLU，或将 GELU 明确放入可选变体注释。
- **位置编码**：附图2/3写 `sinusoidal / learned`，本文件只支持固定 sinusoidal（214–229）。
- **图2 masked 区块的内部顺序**：图2把“Apply causal mask”放在 “Scaled Dot-Product Attention” 整体标签之前，可能被误读成直接屏蔽 Q/K/V。正确详细图应在 `QKᵀ / sqrt(Dh)` 之后、softmax 之前加 mask；图3在这一点上更接近源码。
- **输出 softmax**：附图1/2/3均显示 softmax；本文件返回 logits。图上应区分源码范围与可选概率后处理。
- **图3权重乘 V 的箭头**：必须有独立 V 路径进入最终矩阵乘法节点，而不是将 V 误连进 softmax 或 scores。Q/Kᵀ输入乘法与 weights/V输入乘法是两个不同 matmul。
- **Add & Norm 的两输入**：图3黄色盒中的 `X → +` 表示原始子层输入的残差路径；来自子层输出的垂直路径表示 `Dropout(Sublayer(X))`。二者必须都进入 +，随后再进入 LayerNorm。不能让残差箭头绕过整个 Add & Norm 或在 LayerNorm 后相加。
- **“相同图例”不等于“相同权重”**：Q/K/V 矩阵的蓝/绿/粉是张量角色配色，橙/蓝/黄主块是结构语义配色。缩略矩阵格数只是一种示意，不代表真实 channel 数或 tensor 数值。
- **方向混合是层级约定**：外部主干由下到上，内部 QKV 由上到下，内部 attention 算子由左到右。程序化布局应以容器边界的 in/out 端口转换方向，不能从纸面坐标反推运算先后。

## 8. torch_builtin_version.py 的适用范围与不同点

可直接证实的内容：

- `nn.Transformer` 实例化 45–55：`activation="relu"`、`batch_first=True`、`norm_first=False` 均明确。
- 源/目标 `nn.Embedding` 30–31，乘 sqrt(D) 后加固定 PE 在 69–76。
- 此文件的 embedding + PE 后没有单独的 dropout，而主文件 `PositionalEncoding.forward` 233 有。
- 输出 `generator` 57 默认带 bias，而主文件 430 显式 `bias=False`。
- 此文件也返回 logits（88），未 shift-right，也未输出 softmax。
- `forward` 79–86 使用 `tgt_is_causal=True`，没有传显式 `tgt_mask`。这是 API 调用意图，不能仅凭此文件保证所有 `torch>=2.2` 版本都能在该参数组合下正确执行；有些 PyTorch API 路径会要求显式 mask。不能未经运行或版本源码核查就把注释“supports causal decoding directly”当作验证结论。

`requirements.txt` 只给 `torch>=2.2`，没有固定版本，因此不能为内部 `nn.Transformer` 算子编造本归档内不存在的源码行号。标准 PyTorch 参考实现还可能包含 stack 末尾额外 LayerNorm；若以 built-in 为主基准，必须读取目标版本源码确认并画出，不能把主文件“每层 Post-LN”图直接称为它的完整逐算子图。

## 9. 适合主文档引用的小型语义 IR

以下是解释用设计例，不是归档中的现有数据结构。其价值是把源码事实与坐标分离，让图3布局不会覆盖数据依赖。

```python
encoder_self_attention = {
    "id": "encoder.layer[i].self_attn",
    "type": "multi_head_attention",
    "source": {"file": "transformer.py", "lines": [278, 283]},
    "parameter_scope": "encoder.layers[i].self_attn",
    "inputs": {"query": "enc_x", "key": "enc_x", "value": "enc_x"},
    "mask_inputs": {"padding": "src_key_padding_mask"},
    "output": {"id": "enc_attn_out", "shape": ["B", "S", "D"]},
    "glyph_template": "mha_qkv_triplet",
}

decoder_cross_attention = {
    "id": "decoder.layer[j].cross_attn",
    "type": "multi_head_attention",
    "source": {"file": "transformer.py", "lines": [355, 360]},
    "parameter_scope": "decoder.layers[j].cross_attn",
    "inputs": {"query": "dec_after_norm1", "key": "M", "value": "M"},
    "mask_inputs": {"padding": "src_key_padding_mask"},
    "output": {"id": "cross_out", "shape": ["B", "T", "D"]},
    "glyph_template": "mha_q_from_decoder_kv_from_memory",
}
```

布局器从 `type` 选择相同结构模板，从 `inputs` 选择“同源三叉”或“Q / KV 两个来源分组”，从 `parameter_scope` 保留独立权重身份，从 source 产生可点击证据。这样既能重用图元，又不会把 self-attention 与 cross-attention 混成一个结构。
