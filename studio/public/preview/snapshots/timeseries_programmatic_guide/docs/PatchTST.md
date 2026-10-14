# PatchTST：源码到图形的适配说明

本适配器解释附件 `PatchTST.zip` 中 **supervised forecasting** 的 `Model.forward`。它按实际调用关系手写语义树，再交给共享绘图引擎生成不同粒度的 SVG；没有导入 PyTorch、执行模型或读取训练权重。附件中的基础图仅作版式参考，结构以此压缩包的源码为准。

## 入口、配置与范围

下面的路径均为 zip 内的准确路径；简写 `S/` 表示 `PatchTST/PatchTST_supervised/`。

- 入口：`S/models/PatchTST.py::Model`，类定义第 15 行；`forward` 第 80–92 行。
- Backbone：`S/layers/PatchTST_backbone.py::PatchTST_backbone`，第 16 行；`forward` 第 60–82 行。
- 配置来源：`S/run_longExp.py` 第 31–70 行的默认值，加上 `Model.__init__` 第 16–18 行没有由配置覆盖的默认参数。

适配器选择 `decomposition=False`、`pretrain_head=False`、`head_type='flatten'` 的监督预测路径。配置中的 `model` 参数需要选择 `PatchTST`；这里借用运行脚本的结构配置默认值，不表示不加参数即可启动该脚本。

| 符号/参数 | 本次配置 | 依据 |
| --- | --- | --- |
| `L, H, C` | `96, 96, 7` | `run_longExp.py:31–33,54` |
| `p, s` | `16, 8` | `run_longExp.py:42–43` |
| `padding_patch` | `'end'` | `run_longExp.py:44` |
| `P` | `floor((L-p)/s)+2 = 12` | `PatchTST_backbone.py:35–38` |
| `D, F, h, N` | `512, 2048, 8, 2` | `run_longExp.py:57–61` |
| RevIN | 开启；`affine=False`，`subtract_last=False` | `run_longExp.py:45–47` |
| head | `individual=False`，共享 Flatten Head | `run_longExp.py:50`；`PatchTST_backbone.py:97–108` |
| normalization | `BatchNorm`；`pre_norm=False` | `Model.__init__:16–18` |
| attention | `res_attention=True`；`attn_dropout=0` | `Model.__init__:16–18` |
| 位置参数 | `pe='zeros'`；`learn_pe=True` | `Model.__init__:18` |
| dropout | embedding / projection / FFN / residual 为 `0.05`；head 为 `0` | `run_longExp.py:41,67`；各调用点 |

这些数值用于确定所画分支与维度公式；图中保留 `B,L,C,P,D…` 符号，以便比较结构。`fc_dropout=0.05` 只影响未选中的 pretrain head，不能把它误画成当前 forecast head 的 dropout。推理时非零 dropout 也成为恒等操作。

## 主数据流与图元对应

所有流程自底向上；同一条链中的顺序来自 `forward`，横向并列仅表示同级分支。分组边框属于绘图层级，不额外增加模型算子。

| 图中图元 | 实际张量变化与含义 | 精确源码位置 |
| --- | --- | --- |
| Input → Permute | `Model` 输入 `(B,L,C)`，转换为 `(B,C,L)` | `S/models/PatchTST.py:80,89–90` |
| RevIN normalize | 内部转为 `(B,L,C)`，按样本、变量计算时间均值和标准差，再转回 | `S/layers/PatchTST_backbone.py:62–65`；`S/layers/RevIN.py:33–49` |
| End padding | 在时间轴末尾复制 `s` 个末值，长度变为 `L+s` | `S/layers/PatchTST_backbone.py:35–38,68–69` |
| Unfold | `unfold(-1,p,s)` 得到 `(B,C,P,p)`；随后换为 `(B,C,p,P)` | `S/layers/PatchTST_backbone.py:70–71` |
| Patch Linear | 再转回 `(B,C,P,p)`，`W_P: p→D` 得到 `(B,C,P,D)` | `S/layers/PatchTST_backbone.py:143,161–162` |
| Fold B and C | `(B,C,P,D)→(BC,P,D)`；每个变量的 patches 单独形成一个序列 | `S/layers/PatchTST_backbone.py:164` |
| Position + dropout | 对每个序列加同一 `W_pos:(P,D)` 后 dropout | `S/layers/PatchTST_backbone.py:147,165` |
| Encoder layers 1/2 | 两个独立实例依次处理 `(BC,P,D)`，同时逐层传递 attention scores | `S/layers/PatchTST_backbone.py:183–196` |
| Restore channels | `(BC,P,D)→(B,C,P,D)→(B,C,D,P)` | `S/layers/PatchTST_backbone.py:169–170` |
| Flatten Head | 展平最后两维，`(B,C,D*P)→Linear(D*P,H)→(B,C,H)` | `S/layers/PatchTST_backbone.py:48,106–108,119–122` |
| RevIN denormalize | 用输入阶段缓存的统计量还原预测尺度 | `S/layers/PatchTST_backbone.py:78–81`；`S/layers/RevIN.py:52–60` |
| Permute → Forecast | `Model` 对外输出 `(B,H,C)` | `S/models/PatchTST.py:91–92` |

`P` 的公式适用于 `L≥p`、`s>0` 的本次有效配置。`padding_patch=None` 时没有末端补值，公式为 `floor((L-p)/s)+1`。本次 `s=8<p=16`，patches 存在重叠；基础图中“通常 stride=patch_len”的说明不能决定当前配置。

`pe='zeros'` 这个名称容易误解。`S/layers/PatchTST_layers.py:105–107,121` 实际创建 `(P,D)` 的矩阵，用 `Uniform(-0.02,0.02)` 初始化，并返回可训练参数；它不是全零编码，也不是固定正弦位置编码。

## Encoder 内部为什么这样画

`TSTEncoderLayer.forward` 第 237–267 行确定本次 post-norm 的顺序：

```text
x -> SelfAttention -> residual dropout -> Add(x) -> BatchNorm
  -> Linear(D,F) -> GELU -> dropout -> Linear(F,D)
  -> residual dropout -> Add(previous normalized state) -> BatchNorm
```

每个 `Add` 的旁路只连到加法图元，然后再进入 BatchNorm；不能把旁路直接接到归一化输出。两个残差分别属于 attention 和 FFN，不是整个 encoder 的一个总旁路。`pre_norm=True` 会改变顺序，未包含在当前所画配置。

默认 `norm='BatchNorm'` 在 `TSTEncoderLayer.__init__:215–218,228–231` 进入 `Transpose(1,2) → BatchNorm1d(D) → Transpose(1,2)`。BN 的输入是 `(BC,D,P)`，训练时统计量在 `BC` 与 `P` 维上聚合。因此 channel-independent 指 attention/FFN 不把不同变量当作同一个 token 序列，不能扩大解释为“不同变量之间绝无统计耦合”。

Attention 中 Q/K/V 横向并列，因为三次投影消费同一个 layer input，彼此没有先后依赖。代码为 `S/layers/PatchTST_backbone.py:286–288,306–308`：

```text
Q: (BC,h,P,d)     K: (BC,h,d,P)     V: (BC,h,P,d), d=D/h
S_i = Q_i @ K_i / sqrt(d) + S_(i-1)        # 第一层没有 S_(i-1)
A_i = Dropout(softmax(S_i, dim=-1))
Z_i = A_i @ V_i
concat_heads(Z_i) -> Linear(h*d,D) -> projection dropout
```

公式依据 `_ScaledDotProductAttention.forward:354–377`。Q/K/V 并列组输出的是 tuple，SDPA 消费其全部分量；并列组不表示相加。详细图将 SDPA 再展开为两条并列支路：Q/K 进入 `QK / sqrt(d) + prev → Softmax → attention dropout`；V 单独绕过这条权重计算链。两条支路汇集为 `tuple(A,V)` 后，才进入显式的 `A @ V` 图元。它们是矩阵乘法的两个独立操作数，不能把 V 串接到 QK 或 Softmax 前面。

外侧 `S1: pre-softmax scores` 连线直接绑定第一层的 raw-score 图元，并进入第二层的 raw-score 图元，对应 `TSTEncoder.forward:191–194` 与 SDPA 第 357 行。它传递的是 Softmax **之前**的 score 张量，不是归一化后的 attention weights，也不是 hidden-state residual。第一层 raw-score 图元记录 `prev=None`；第二层记录 `prev=S1`。一般带 mask 的分支会返回应用 mask 后的 raw scores；本次没有 mask，因此不引入额外 mask 算子。所选 `TSTiEncoder.forward:168` 调用没有传 mask，故不画因果 mask；函数签名里存在 `attn_mask` 不代表实际路径中自动启用。

详细图展开第一层；第二层保持折叠以控制高度。IR 仍保留第二层的完整算子及独立参数身份，score 连线在折叠时连接到该层边界。两层串联的顺序和 score side dependency 均保留。

## 相同结构与相同参数的区别

| 对象 | 参数身份 |
| --- | --- |
| 不同变量 | 共享同一个 `W_P`、`W_pos` 与 encoder，不为每个变量复制一套 Transformer |
| 不同 patch 位置 | 共享投影与 encoder；位置由 `W_pos` 的不同行区分 |
| 不同 encoder 层 | `ModuleList` 由两次构造得到，参数独立；图元颜色相同只表示算子种类相同 |
| 同层 Q/K/V | 三个独立 `Linear`，不是同一个 Linear 的三次重复显示 |
| 预测 head | 本次 `individual=False`，一个 `Linear(D*P,H)` 应用于所有变量；`individual=True` 才逐变量建独立 head |
| RevIN | 本次关闭可训练 affine；输入均值/标准差是每次前向产生的缓存统计量，不是训练参数 |

这些身份在适配器的 `param_identity` 中记录；例如 `encoder.layers.0.W_Q` 与 `encoder.layers.1.W_Q` 不同。位置参数与共享 head 各自仅有一个身份。外侧 RevIN 连线标示保存与复用统计量，不能画成 learned projection。

## 对基础图的修正

1. 将对外输入/输出改为 `(B,L,C)/(B,H,C)`，在内部保留 `(B,C,L)/(B,C,H)`；这是所选 `Model` 包装器的真实接口。
2. 将 Flatten Head 的输入改为 `D*P`，恢复变量维度后的张量改为 `(B,C,D,P)`，避免丢失 patch 维。
3. 将默认 LayerNorm 改为 post BatchNorm，补齐 RevIN 及输出还原。
4. 补齐 end replication padding 与准确 patch 数，展示重叠 patch 的配置。
5. 补齐跨层 residual attention scores，区分它与两个普通残差。
6. 位置编码采用当前可训练矩阵，并说明 `'zeros'` 的实际初始化行为。

## 未展开的分支与适配边界

- `decomposition=True`：`S/models/PatchTST.py:51–68,81–87` 先分解 residual/trend，使用两套 **独立** PatchTST backbone 后相加。当前图没有启用这条路径；不能只在现图加一个 decomposition 方框就认为支持了它。
- `individual=True`：`Flatten_Head:97–104,111–118` 为每个变量创建独立预测 head；需要改变参数身份和分支表示。
- `pre_norm=True`、`norm='LayerNorm'`、不同 PE、mask、`store_attn=True`、pretraining head 等可选设置均未作为第二套 profile 生成。
- `PatchTST/PatchTST_self_supervised/` 是另一套实现与训练接口，不由当前入口适配器覆盖。
- 本适配器只提取静态结构。维度为依据代码与选定配置推导的符号结果，没有用运行时 tracing 验证训练状态、随机 dropout、设备或数值输出。

后续适配新配置，应先修改 `profile` 与语义树，再核对每个分支、shape 和 `param_identity`；单独替换 zip 或模型名称不会自动获得正确图形。
