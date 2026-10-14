# Tensor2Tensor 1.0.14：Transformer 源码证据与三张参考图的对应

本文件只分析用户提供的 `tensor2tensor-1.0.14.tar.gz` 解包副本，未导入、执行或修改源码。版本由 `PKG-INFO:3` 的 `Version: 1.0.14` 确认。下列行号均相对 `sources/tensor2tensor-1.0.14/` 中的原始文件。范围用于说明证据上下文；绘图元数据应同时保存文件、符号名和行号，而不只保存说明文字。

## 1. 最重要的结论

这一版本的 Transformer 是 **Post-LN**：每个子层的输出先经过 residual dropout，再与子层输入相加，最后做 LayerNorm；公式是 `LN(x + Dropout(F(x)))`。直接证据是 `tensor2tensor/models/transformer.py:59–61`，而不是依据论文图片推断。它与图 1–3 的 Add & Norm 顺序一致。

图 3 是优质的**语义展开图**，但不能把每个矩形机械解释为一个源码调用或独立模块：源码自注意力用一次 `qkv_transform` 投影后拆成 Q/K/V，交叉注意力用 `q_transform` 加一次 `kv_transform`；图中的三个 Linear 是数学上的三个投影。源码把缩放放在 Q 上，图把 Scale 放在 QKᵀ 之后，两者数学等价。源码 FFN 使用 `1×1` 卷积表达逐位置仿射变换。最终的 SymbolModality top 返回 logits，图中的最终 Softmax 是额外的概率解释节点。

因此，图的中间表示应分别保存“数学算子”“实现调用”“参数/变量实例”。相同外形代表相同算子类型；只有明确的参数标识相同才表示权重共享。`N×` 是重复拓扑的折叠表示，不是参数共享标记。

## 2. 程序边界与调用顺序

完整翻译模型不是只在 `transformer.py` 里：

```text
T2TModel.model_fn
  ├─ input_modality.bottom_sharded → SymbolModality.bottom → bottom_simple
  ├─ target_modality.targets_bottom_sharded → SymbolModality.targets_bottom
  ├─ Transformer.model_fn_body
  │    ├─ flatten4d3d(inputs/targets)
  │    ├─ transformer_prepare_encoder
  │    ├─ transformer_prepare_decoder
  │    ├─ transformer_encoder: N × [self-attention → residual+norm → FFN → residual+norm]
  │    └─ transformer_decoder: N × [masked self-attention → residual+norm
  │                               → cross-attention → residual+norm
  │                               → FFN → residual+norm]
  └─ target_modality.top_sharded → SymbolModality.top → logits + training loss
```

证据：`tensor2tensor/utils/t2t_model.py:379–393` 输入 bottom；`:401–412` 目标 bottom；`:414–425` body 与 top；`:445–446` 返回 logits、loss。`transformer.py:47–75` 是 body 内的准备和主干调用。只分析 `model_fn_body` 会漏掉图底部 Embedding 和顶部词表投影。

## 3. 默认配置必须锁定

| 项目 | `transformer_base()` 的实际值 | 证据 |
|---|---:|---|
| `d_model` | 512 | `models/transformer.py:272` |
| Encoder 和 Decoder 层数 | 各 6 | `models/transformer.py:282`；循环分别在 `:151` 和 `:197` |
| `d_ff` | 2048 | `models/transformer.py:291` |
| 头数 h | 8 | `models/transformer.py:293` |
| 总 key/value 宽度 | 标志值 0，调用时回退 `hidden_size`，即各 512 | `models/transformer.py:294–295` 及 `:159–161`、`:205–207`、`:218–220` |
| 每头 `d_k` / `d_v` | 各 64 | `models/common_attention.py:412–416`，由上述值推得 |
| FFN 类型 | `conv_hidden_relu` | `models/transformer.py:296` |
| 位置编码 | `timing`，正弦/余弦 | `models/transformer.py:304`；`models/common_attention.py:57–70` |
| attention dropout | 0.0 | `models/transformer.py:301` |
| FFN 激活后 dropout | 0.0 | `models/transformer.py:302` |
| residual/embedding dropout | 0.1，训练时 | `models/transformer.py:303`、`:59–66` |
| embedding 缩放 | 乘 `sqrt(d_model)` | `models/common_hparams.py:68`；`models/modalities.py:81–82` |
| embedding 与输出词表投影共享权重 | 标志为 True；实际 scope/模态关系也要保存 | `models/transformer.py:289`；`models/modalities.py:86–118` |

所有名字以 `dropout` 结尾的超参数在非训练模式被置 0，证据 `utils/t2t_model.py:88–92`。图若选择推理视图，可以隐藏 Dropout，但必须在图注声明；若选择训练视图，应显示或折叠注明。

`transformer_big` 等变体会覆盖维度和 dropout；`transformer_ffn_layer` 还有 parameter attention、带较大卷积核的 sepconv、none 等分支（`transformer.py:239–265`）。一张声称对应源码的图需要注明选中的配置，而不能同时画互斥的默认/备选分支。

## 4. 图 1 / 图 2 / 图 3 的共同主干映射

| 参考图图例 | 实际源码 | 为什么对应；绘图应保存什么 |
|---|---|---|
| Input Embedding / Output Embedding | `models/modalities.py:75–96` | `tf.gather` 从 token id 查向量；这是特征变换而非 attention 主干。保留 source 与 target 的不同实例 id，以及可能共享的 parameter id。 |
| Positional Encoding + 圆形加号 | `transformer.py:104–105`、`:124–125`；`common_attention.py:57–70` | 生成 `[1,L,D]` 的信号后广播相加。正弦波 glyph 是无训练参数的编码算法，不是一个可学习网络层。 |
| Encoder 大容器 `N×` | `transformer_encoder`，`transformer.py:129–167` | 这是包含两个子层的重复层类型；`layer_%d` 为每层独立命名空间。 |
| Encoder Multi-Head Self-Attention | `transformer.py:153–165` | query 为 x，memory 为 None；该条件在 attention 实现中使 Q/K/V 都来自 x。 |
| Encoder Feed Forward | `transformer.py:166`、`:229–244` | 该子层接收 attention residual+norm 后的 x；宽度先扩张再收缩。 |
| Decoder 大容器 `N×` | `transformer_decoder`，`transformer.py:170–226` | 每层包含三子层，与 Encoder 拓扑不同；不应共用同一个完整层模板。 |
| Masked Multi-Head Self-Attention | `transformer.py:199–211` | query=x，memory=None，bias=decoder causal bias。与 Encoder self-attention 的算子主体同型，但输入域、mask、参数实例不同。 |
| Multi-Head Cross-Attention | `transformer.py:212–224` | query 来自当前 decoder x；memory 明确传入 `encoder_output`。这是两种长度的输入端口，不是“再一次 self-attention”。 |
| Encoder output / memory 跨列线 | `transformer.py:67–72`、`:215–217` | Encoder 最后一层结果传到每个 Decoder 层的 cross-attention；不是只接 Decoder 首层，也不是由 Encoder 某一中间层接过去。折叠图应注记 `memory → every decoder layer`。 |
| Add & Norm | `transformer.py:59–61`，调用在 `:153`、`:166`、`:199`、`:212`、`:225` | 与子层成对出现：保存子层输入 x 的旁路、子层输出 y 的主路、逐元素 add 和后置 norm。 |
| Linear → vocabulary logits | `models/modalities.py:98–120` | hidden 向量与词表矩阵转置相乘，生成 vocab 维度；它位于 Transformer body 之外。 |
| 顶部 Softmax / Output Probabilities | `SymbolModality.top` 没有执行 softmax；训练调用见 `utils/modality.py:149–158` 与 `common_layers.py:1422–1423` | 概率 `softmax(logits)` 是数学展示层。用标记区分“源码实现节点”与“数学解释节点”；不可把最终 Softmax 算入 body 的源码子模块。 |

## 5. 图 3 的注意力展开：逐步证据

### 5.1 Q/K/V 逻辑分支与融合调用

`models/common_attention.py:393–402`：当 `memory_antecedent is None`，实现只调用一次 `conv1d(query, 2*D_k + D_v, 1, name="qkv_transform")`，再沿通道维 split 为 q、k、v。

因此“一个源张量 X 分成三支 → 三个 Linear → Q、K、V”是合法的数学展开：

```text
combined = X @ W_QKV + b_QKV
Q, K, V = split(combined)
W_QKV = [W_Q | W_K | W_V]  （沿输出通道拼接）
```

这三个逻辑 Linear 的 `implementation_group` 应相同，指向 `qkv_transform`；它们的 `logical_parameter_slice` 应不同。不要为图中的三个矩形伪造三个源码类或函数位置。

`models/common_attention.py:403–411`：cross-attention 有一次 Q 投影 `q_transform`，memory M 经一次 `kv_transform` 后拆为 K 和 V。因此图 3 把 decoder states H 与 encoder memory M 放在两个相邻浅色子容器是有代码依据的：它表达张量来源的分组，而不是任意视觉装饰。

`models/common_layers.py:354–360` 表明 `conv1d` 先增添单例空间维、调用 `tf.layers.conv2d` 再 squeeze；卷积核大小 1 时，不混合相邻 token，等价于每个位置共用同一仿射映射。图可以标 `Linear (implemented as 1×1 Conv)`；这是语义命名与实现命名的明确对应。

### 5.2 分头不是 h 个新建模块

`models/common_attention.py:412–414` 分别对 Q/K/V 调用 `split_heads`。其定义 `:244–254` 用 reshape+transpose 得到 `[B,h,L,D/h]`，reshape 实现在 `:207–224`。

图 3 的 `Split into h heads` 横条应接收三条输入与三条输出，表示三路张量均做布局变换；它不应被画成只分 Q，或者一个会把 Q/K/V 合起来的计算层。头维是张量轴，attention 通过批量矩阵乘法一起处理各头，没有 Python 循环为每个 head 新建一个完整 multihead 模块。

默认 self-attention：

```text
X:       [B,L,512]
Q/K/V:   [B,L,512]
split:   [B,8,L,64]
scores:  [B,8,L,L]
context: [B,8,L,64]
combine: [B,L,512]
output:  [B,L,512]
```

cross-attention 以 S 为源长度、T 为目标长度：

```text
H → Q: [B,T,512] → [B,8,T,64]
M → K: [B,S,512] → [B,8,S,64]
M → V: [B,S,512] → [B,8,S,64]
QKᵀ:   [B,8,T,S]
AV:    [B,8,T,64]
output:[B,T,512]
```

图上写 `seq` 可用于自注意力的通用模板；cross-attention 必须分别标 `src` 与 `tgt`，因为 S 与 T 无需相等。张量网格小图应是结构示意符号，不能把示意列数解释为实际 64、512 或序列长度；每个网格保留正式 shape 标签。

### 5.3 Scale、bias/mask、Softmax 和 V 的先后

实际顺序是：

```text
q *= d_k**(-0.5)                       # common_attention.py:415–416
logits = matmul(q, k, transpose_b=True) # :337
logits += bias                        # :338–339
weights = softmax(logits)              # :340
weights = dropout(weights)             # :342
context = matmul(weights, v)           # :345
```

图 3 用 `QKᵀ → Scale 1/sqrt(d_k) → Mask → Softmax → ×V` 的数学顺序正确，因为 `(Q/sqrt(d_k))Kᵀ = QKᵀ/sqrt(d_k)`；但如目标是严格的调用追踪图，Scale 应放在 Q 的边上。两种布局可以由同一个语义 IR 的 `equivalent_rewrite="scale_q_to_scores"` 控制。

`Kᵀ` 来自 `transpose_b=True`，不是额外学习层。图中 `×` 表示矩阵乘法；Add & Norm 中圆形 `+` 表示逐元素相加。绘图 DSL 应给这两类 glyph 不同的 operation kind，避免统一成无语义的“圆形算子”。

### 5.4 三种 attention 的 mask 不能混为一谈

| 位置 | bias 构造与传递 | 数值和 shape | 图 3 需要补充的事实 |
|---|---|---|---|
| Encoder self-attention | `transformer.py:96–98` → `:158` | `attention_bias_ignore_padding`：padding 位置加 `-1e9`，shape `[B,1,1,S]`；`common_attention.py:194–204` | Encoder 也有 padding mask，只是没有 causal mask。 |
| Decoder masked self-attention | `transformer.py:121–123` → `:204` | `attention_bias_lower_triangle`：上三角加 `-1e9`，shape `[1,1,T,T]`；`common_attention.py:180–191` | 图上的“−∞ above diagonal”是数学极限描述；实际常量为 `-1e9`，不是浮点 `-inf`。这一版本该函数只构造 causal bias，不能擅自声称它还合并了 target padding mask。 |
| Decoder cross-attention | 同一个 encoder bias 经 `transformer.py:71–72` → `:217` | memory/source padding bias `[B,1,1,S]`，广播到 `[B,h,T,S]` | cross-attention 不使用 Decoder 的 causal triangle，但仍应屏蔽 encoder padding。 |

构造 encoder padding 时先检测 embedding 是否全零（`common_attention.py:166–177`），而 SymbolModality 会让 id 0 的 embedding 为零（`modalities.py:83`）。然后 encoder 才加 target-space embedding 与 timing，因此不能把 padding 检测放到它们之后。

### 5.5 合头与输出投影

`models/common_attention.py:419–420` 为 `combine_heads(x)` 后 `output_transform`。`combine_heads` 在 `:257–266` 先 transpose 回 `[B,L,h,d_v]`，再合并最后两维为 `[B,L,h*d_v]`。图中 Concat heads 是通道拼接，不是把序列长度拼成 h 倍。

当 `D_v=h*d_v` 时输出投影是 `W^O: D_v → D_model`。默认 `D_v=D_model=512`，所以图 3 中 `h·d_k → d_model` 在默认 `d_v=d_k` 时成立；通用绘图器应写 `h·d_v → d_model`，因为源码允许 key/value 总宽度不同（参数检查 `common_attention.py:382–387`）。

## 6. 图 3 的 FFN 与 Add & Norm

### 6.1 FFN

`transformer.py:239–244` 选择默认 `conv_hidden_relu(x, filter_size, hidden_size, dropout=relu_dropout)`。实现 `common_layers.py:1160–1194`：

1. 默认第一与第二卷积核都为 `(1,1)`（`:1163–1164`）。
2. 第一层将通道数 D 扩到 F，激活 `tf.nn.relu`（`:1177–1183`）。
3. 可选 dropout 位于激活之后（`:1184–1185`），默认率 0。
4. 第二层线性投影把 F 缩回 D（`:1190–1193`）。

故图 3 的横向 `Linear D→F → ReLU → Linear F→D` 与下方蓝/绿/粉网格表达的是同一个逐位置函数的两种注释层。网格可作为 tensor-edge annotation，不应被计为三个额外算子。

图中的 `ReLU / GELU` 对这个归档应改为 **ReLU**。源码没有选择 GELU 的分支。`Position-wise` 来自 kernel 1 不跨 token 混合，且同一层参数对各位置共用；它并非每个 token 一套权重。

### 6.2 残差

`residual_fn(x,y)` 在 `transformer.py:59–61`。展开图应把旁路的起点精确接在该子层输入：

```text
x ───────────────────┐
│                    ↓
└→ F → Dropout → [Add] → LayerNorm → z
```

每个 Encoder 层有两个该结构，每个 Decoder 层有三个。图 3 的黄色横条可以作为组合图例 `ResidualPostNorm`，其内部 `Add`、`LayerNorm` 和旁路线通过模板固定。`LayerNorm` 在最后一个维度统计均值和方差（`common_layers.py:406–411`），并带 scale 与 bias 变量（`:429–443`）；它不是沿 batch 或整个序列做归一化。

图中黄色条旁路若画一个无标签小圆角框，源码没有相应独立算子；应删掉，或明确把它标为 residual branch 的路径符号。灰色小框 `LayerNorm` 才有可识别的函数和参数。

## 7. 图底部与顶部的精确修正

### 7.1 右移发生在哪里

该版本函数名是 `shift_left_3d`，但 docstring 明确写 “Shift ... right by one”，实现向第二维开头 pad 一位再去掉最后一位，见 `common_layers.py:209–215`。`transformer_prepare_decoder` 在 `transformer.py:123` 对**已经 embedding 且 flatten 的 targets** 执行它。形式为：

```text
[e(y0), e(y1), ..., e(yT-1)]
      → [0, e(y0), ..., e(yT-2)]
      → + positional timing
```

因此图 3 `Outputs (shifted right) → Output Embedding` 是常见数学叙述，但严格源码调用顺序应为 `target ids → Target Embedding → shift-right embeddings → +PE`。padding id 0 被嵌入为全零，使其可用“移位 token”解释，但图注应区分语义视图和实现视图。不要凭函数名把它画成向左移位。

### 7.2 源码还有参考图没有的 target-space embedding

`transformer.py:99–103` 从 `target_space_id` 创建 32 类、宽度 D 的学习 embedding，并广播加到 encoder 输入，然后才加 timing（`:104–105`）。图 1–3 均省略了它。若声称严格复现该 T2T 归档，需要增加该支路，或者在“省略的任务条件信息”中注明。它和位置编码来源不同、含义不同、是否学习也不同，不应共用正弦波 glyph。

### 7.3 顶部 shape 与概率

Transformer body 在 `transformer.py:73` 加一个维度后返回 `[B,T,1,D]`。SymbolModality top 最终又在 `modalities.py:120` 插入 channels 维度，返回 `[B,T,1,1,Vocab]`。已有测试 `models/transformer_test.py:56` 的断言也写明这个 shape（仅阅读测试，未执行）。

图 3 的 `[B,seq_len,vocab_size]` 是隐藏两个 singleton 维度的**逻辑 shape**，并且对于 Decoder 应使用 `T`/`tgt`。图注需声明 logical tensor shape，而不冒充实际 API 返回秩。

`SymbolModality` 类 docstring 的 “Linear transformation + softmax” (`modalities.py:39–40`) 不能覆盖函数体证据：`top` 明确声明 “Generate logits” (`:98–105`)，只 matmul+reshape (`:117–120`)。训练损失直接调用 `softmax_cross_entropy_with_logits`（`common_layers.py:1422–1423`）；采样默认直接对 logits argmax（`t2t_model.py:330–339`）。若最终仍画 Softmax，则给它 `origin="mathematical/readout"`，从 logits 节点以清楚的解释关系连上。

## 8. N×、同型模块与共享权重

Encoder 在 `transformer.py:150–152` 使用 `encoder/layer_0 ... layer_5`；Decoder 在 `:196–198` 使用 `decoder/layer_0 ... layer_5`。每层 namespace 不同，attention 的内部变量和 FFN、LayerNorm 随之不同。**可重复同一个图例模板，但不可复用同一个参数实例 id**。

同样，Encoder self-attention、Decoder self-attention、cross-attention 都调用 `multihead_attention`，意味着相同实现/算子族；调用位置、scope、输入来源、bias 不同，意味着不同实例。建议每个图形保留：

```json
{
  "id": "decoder.layer_0.cross_attention",
  "kind": "multihead_attention",
  "template": "mha",
  "implementation": "common_attention.multihead_attention",
  "callsite": "tensor2tensor/models/transformer.py:214",
  "scope": "body/decoder/layer_0/encdec_attention",
  "parameter_group": "decoder.layer_0.encdec_attention.*",
  "q_source": "decoder.layer_0.self_postnorm",
  "kv_source": "encoder.output",
  "mask": "source_padding"
}
```

源码另有有意共享的 embedding/输出词表权重：base 开 `shared_embedding_and_softmax_weights`，bottom、targets_bottom、top 对 `shared` scope 的创建/复用逻辑在 `modalities.py:86–118`。源与目标是否属于兼容的同一 symbol modality namespace，还取决于问题配置和 vocab/模态，`SymbolModality.name` 由 vocab 与 D 决定（`:43–45`），完整模型按模态名设置 scope（`t2t_model.py:383–412`）。不能从两个相同粉色 Embedding 盒子直接推断“源目标永远共享”。

## 9. 三张图的可追溯折叠规则

同一 source-backed IR 可以导出三个 view，而不是分别画三张没有关系的图：

- 图 1：把 `qkv/projections + split + scaled dot product + combine + output projection` 折成 MHA，把 FFN 折成一个盒子，把 `dropout + add + layernorm` 折成 Add & Norm。
- 图 2：展开 FFN 的三步与 MHA 的逻辑步骤，继续折叠所有 tensor reshape、矩阵操作细节；给 causal mask 独立注释。
- 图 3：展开 Q/K/V 来源和投影、tensor shape、头维变换、attention 运算；保留多头的批量运算解释，并明确 fused implementation group。Cross 可共享相同 attention-core 图例，但不能隐藏 S/T 的不同。

折叠必须保持入口/出口和边来源：特别是 residual 旁路仍接同一个子层输入，memory 仍从 encoder.output 接到 cross 的 K/V，mask 仍接 scores-before-softmax，V 仍只接权重乘法。这些是真正由源码决定的结构约束；边拐弯、间距、box 坐标等审美布局是布局器根据约束计算的表现选择。

## 10. 对图 3 的源码忠实性检查清单

| 图 3 表达 | 对该归档的判定 | 程序化图建议 |
|---|---|---|
| Add → LayerNorm | 准确，Post-LN | 保留；训练视图补 residual dropout。 |
| ReLU / GELU | 默认只支持此处 ReLU | 改 ReLU。 |
| sinusoidal / learned PE | 默认 `pos=timing`；该 prepare 分支没选择 learned | 改 sinusoidal；不要把库中其他函数存在当成被此模型调用。 |
| 三个 self Q/K/V Linear | 逻辑正确，实现 fused | 加 fused QKV group 元数据或注记。 |
| Cross K/V 两 Linear | 逻辑正确，实现 fused KV | 加 fused KV group。 |
| QKᵀ 后 Scale | 数学等价，实现缩放 Q | 明示 semantic view 或改真实调用位置。 |
| causal mask −∞ | 数学表示，实际 -1e9 | 标签写 `mask bias (−1e9)`，可旁注数学极限。 |
| Encoder / Cross 省略 mask | 缺 source padding mask | 在 scores 添加 padding-bias 端口或折叠注记。 |
| 输出已右移再 Embedding | 语义简写，实际 shift embedding | 实现视图重排；语义视图注明。 |
| 顶部 Softmax | 数学读出节点 | 标记为 probability interpretation。 |
| logits 三维 shape | 去除单例维的逻辑 shape | 明确 `[B,T,V] (logical)`，附实际 `[B,T,1,1,V]`。 |
| attention 输出 `h·d_k` | 默认 d_k=d_v 时正确 | 通用模板写 `h·d_v`。 |
| N× 相同图例 | 拓扑复用正确 | 独立层参数；不得用同一个 parameter instance。 |
| 省略 target-space embedding | 经典论文视图的省略 | T2T 完整实现图要增加或列明省略。 |

