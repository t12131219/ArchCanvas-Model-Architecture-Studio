# iTransformer：源码、语义与程序化图形的对应

本适配器面向用户提供的 `iTransformer.zip`，入口是 `iTransformer/model/iTransformer.py::Model`。它将已核对的 `forecast` 路径显式写成统一语义树，再由共享绘图器生成概览、模块、细节三种视图。模型源码不会被导入或执行；该结果不是对任意 Python 模型的自动理解。

## 本次选择的配置

以压缩包内 `scripts/multivariate_forecasting/ETT/iTransformer_ETTh1.sh` 第 5–22 行的第一个命令为准，并补齐 `run.py` 的未覆盖默认值。

| 符号 / 参数 | 取值 | 来源及含义 |
| --- | --- | --- |
| `L=seq_len` | 96 | 脚本第 13 行，输入时间长度 |
| `P=pred_len` | 96 | 脚本第 14 行，预测时间长度 |
| `N` | 7 | ETTh1 多变量配置，脚本第 12、16–18 行；运行时来自 `x_enc.shape[-1]` |
| `D=d_model` | 256 | 脚本第 20 行 |
| `F=d_ff` | 256 | 脚本第 21 行 |
| `e_layers` | 2 | 脚本第 15 行，两个独立 EncoderLayer |
| `H=n_heads` | 8 | `run.py:43` 默认值；每头宽度 `d=D/H=32` |
| `activation` | GELU | `run.py:55` 默认值；EncoderLayer 根据该参数选择函数 |
| `dropout` | 0.1 | `run.py:52` 默认值，训练时生效 |
| `use_norm` | True | `run.py:86` 默认值；本次画出归一化和反归一化 |
| `embed / freq` | timeF / h | `run.py:53–54`、`:29–30` 默认值 |
| `C` | 4 | 本次保留外部 `x_mark_enc`。小时级 timeF 对应四个时间特征；`T=N+C=11` |
| `output_attention` | False | `run.py:56` 未启用该开关；注意力仍计算，前向不返回其矩阵 |

`C=4` 的依据是 `data_provider/data_factory.py:18` 选择 `timeenc=1`，`data_provider/data_loader.py:73–75` 取得时间特征，`utils/timefeatures.py:106` 对小时频率选择 HourOfDay、DayOfWeek、DayOfMonth、DayOfYear。若调用方传入 `x_mark_enc=None`，源码走无协变量分支，此时 `C=0,T=N`。图中的时间协变量是外部独立输入，不能画成由数值序列派生的中间量。

## 源码对应表

以下路径均为压缩包内部路径，行号直接对应原始文件。

| 图形 / 语义节点 | 源码位置 | 为什么这样对应 |
| --- | --- | --- |
| 输入 `[B,L,N]` | `model/iTransformer.py:42–50` | `forecast` 读取 `x_enc`，变量数量 `N` 由当前输入确定，而不是固定使用 `enc_in` |
| Series normalize | `model/iTransformer.py:43–48` | 对每个样本、每个变量沿时间轴计算 mean/std；mean 被 detach，方差 `unbiased=False`，加 `1e-5` |
| Invert axes | `layers/Embed.py:133–135` | `permute(0,2,1)` 把 `[B,L,N]` 改为 `[B,N,L]`，因此变量是 token，整段时间是该 token 的输入特征 |
| 时间协变量旁路 + concat | `layers/Embed.py:136–140` | 将 `[B,L,C]` 变为 `[B,C,L]` 后在 token 轴拼接；使用 tuple/独立旁路表达额外输入，不隐式求和 |
| Temporal projection + dropout | `layers/Embed.py:128–142` | `value_embedding=Linear(L,D)`，随后 dropout；该类没有位置编码成员 |
| Encoder × 2 | `model/iTransformer.py:26–39`；`layers/Transformer_EncDec.py:53–79` | 列表推导每次新建 EncoderLayer，再由 ModuleList 逐层调用；图中第 1 层展开，第 2 层折叠，IR 保留两层 |
| Q、K、V 三个投影 | `layers/SelfAttention_Family.py:266–300` | 三个独立 Linear 和三次 `view(B,T,H,-1)`；相同颜色只表示同类操作，不表示权重共享 |
| QK contraction → scale → Softmax → dropout | `layers/SelfAttention_Family.py:142–155` | Q/K 生成 `[B,H,T,T]` 权重；`FullAttention(False)` 不进入 causal-mask 条件 |
| V 独立分支 → A×V | `layers/SelfAttention_Family.py:156` | V 是权重汇聚的第二个操作数，不能穿过 Softmax，也不能将 Q/K/V 三分支相加 |
| Merge heads + output projection | `layers/SelfAttention_Family.py:298–300` | 将各头结果 view 回 `[B,T,D]` 后应用 `out_projection` |
| Attention dropout、Add、LayerNorm 1 | `layers/Transformer_EncDec.py:38–46` | 残差精确汇入 `x + dropout(new_x)`，然后执行 norm1；旁路不能跨到 FFN 之后 |
| Pointwise FFN | `layers/Transformer_EncDec.py:27–36,47–48` | 两个 kernel=1 Conv1d；先转为 `[B,D,T]`，执行 Conv1d→GELU→dropout→Conv1d，再转回并 dropout |
| Add、LayerNorm 2 | `layers/Transformer_EncDec.py:46–50` | 第二条残差来自 norm1 的输出，和 FFN 输出相加后执行 norm2 |
| Encoder final LayerNorm | `model/iTransformer.py:38`；`layers/Transformer_EncDec.py:76–77` | 在所有层完成后还执行一次额外 LayerNorm，不能与最后一层 norm2 合并 |
| Linear D→P | `model/iTransformer.py:40,64` | 对每个 token 将 D 个隐藏特征投影为 P 个预测时间步，先得到 `[B,T,P]` |
| Restore time axis | `model/iTransformer.py:64` | 投影之后才 permute，得到 `[B,P,T]` |
| Keep N variates | `model/iTransformer.py:64` | `[:, :, :N]` 丢弃协变量 token 的预测，保留原始变量 |
| Restore series scale | `model/iTransformer.py:66–69` | 用输入阶段保存的 std、mean 进行 `forecast*std+mean`，图中保留统计量长旁路 |
| Forecast `[B,P,N]` | `model/iTransformer.py:74–80` | 再取最后 P 步；所选配置只返回预测张量 |

## 对参考框架图的修正

1. **先投影，后 permute。** 参考图主干把 Permute 放在 Encoder 与 Linear Projection 之间；实际代码是 `projector(enc_out).permute(0,2,1)`。如果先 permute，会把 Linear 的末维从 D 改成 token 数，与 `Linear(D,P)` 不匹配。
2. **补全时间 token、截取和反归一化。** 参考图省略了可选时间协变量 token；代码在同一个 embedding Linear 中处理它们，预测后截取原始 N 个变量，再恢复输入统计尺度。
3. **补全 Encoder 最终 norm。** 两个层各有 norm1/norm2；整个 Encoder 还带有独立 final LayerNorm。
4. **将 FFN 标成真实 Conv1d。** kernel=1 Conv1d 在功能上相当于对每个 token 做相同 Linear，但原型需要追踪具体源码成员，因此明确标记 `conv1/conv2` 和转置。
5. **调整注意力内部方向。** 三个 Q/K/V 投影位于计算下游的起点，Q/K 共同生成权重；V 通过独立分支进入 A×V。所有模块内部遵循整体的自底向上方向。

## 图元、参数身份与排布

颜色按算子语义分类：线性投影、注意力、归一化、激活、张量变换和输入输出分别使用共享图元；嵌套框用于表示真实源码模块和可展开的计算组合。颜色相同不承诺权重相同。

`enc_embedding.value_embedding` 对各变量和时间 token 共享；`projector` 对各 token 共享。一个 AttentionLayer 内的 query/key/value/out projection 分别有自己的参数。两个 EncoderLayer 来自两次构造，参数彼此独立；同一层两个 LayerNorm 以及 Encoder 的 final norm 也都是独立成员。

适配器的 `chain.items` 以源码执行顺序写成输入→输出，绘图器将其翻译为从下往上的几何顺序。注意力细节中的 `parallel` 明确产生 `(A,V)`，随后才调用 A×V；它不表示求和。两个残差组合各自单独设置旁路，终点是各自的 Add。跨越整条主干的 mean/std 复用使用独立外侧通道；协变量输入也使用独立旁路。尺寸、留白和折线路径由共享绘图器统一计算，适配器不硬编码各个 SVG 图元坐标。

概览折叠内部算子；模块视图展开 embedding、Encoder、预测头；细节视图再展开第 1 层 attention/FFN。第 2 层始终折叠是为了减少同构图元的重复，不意味着省略其执行或共享第一层权重；它的内部节点和独立参数作用域仍在语义 IR 中。

## 边界

- 当前适配器只覆盖此压缩包的 `Model.forecast`，不覆盖 iInformer、iFlowformer、iReformer、iFlashformer 或部分变量训练实验。
- 该模型虽接受 `x_dec`、`x_mark_dec` 和 `mask` 参数，所画 forecast 路径并未使用它们；不能据此添加 Decoder 或交叉注意力。
- 图中的 `T` 是变量和协变量 token 数，不能误标为输入时间 L。注意力矩阵大小是 `[B,H,T,T]`。
- `use_norm=False`、不提供协变量、改变激活或层数都需要同步选择配置与语义树，不能只改图中标签。
- Series normalization/denormalization 不等同于 Dataset_ETT_hour 使用训练集拟合的 StandardScaler；后者属于模型调用前的数据处理，本图不将其混入模型 forward。
- 形状为静态配置下的符号推导，未运行模型进行 shape tracing；AST 证据验证说明节点有源码依据，不等于证明任意输入或任意代码改动仍然兼容。
