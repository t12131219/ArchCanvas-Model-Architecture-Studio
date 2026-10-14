# Autoformer：源码对应、参考图修正与原型边界

本适配器针对用户提供的 `Autoformer-main.zip`，入口为 `Autoformer-main/models/Autoformer.py::Model`。图形由审核后的手写语义适配器生成，AST 提供符号、源码行号和文件摘要证据；这不等于自动理解任意 Autoformer 实现。参考 PNG 只用于视觉参考，结构以压缩包源码为准。

## 选定配置

采用 `run.py` 的常见默认配置：`seq_len=96`、`label_len=48`、`pred_len=96`、`enc_in=dec_in=c_out=7`、`d_model=512`、`d_ff=2048`、`n_heads=8`、`e_layers=2`、`d_layers=1`、`moving_avg=25`、`factor=1`、`activation='gelu'`、`embed='timeF'`、`freq='h'`、`dropout=0.05`、`output_attention=False`。图表达 `eval()` 下的推理分支，默认三个 mask 为 `None`。

图中采用符号形状：`B` 为 batch，`L=96`，`P=96`，`T=label_len+P=144`，`C=7`，`D=512`，`F=2048`，`H=8`，`E=D/H=64`。小时级 `timeF` 输入为四维时间特征，Encoder/Decoder 分别接收 `B,L,4` / `B,T,4` 的时间标记。保持 `enc_in=dec_in=c_out` 是本图的明确条件；原实现的原始趋势项与最终预测相加要求通道兼容，不能任意换成不同通道数后仍声称图成立。

## 精确源码证据

以下路径均是 ZIP 内部路径，行号对应所提供文件，不是论文中的通用定义。

| 图中实体/绑定 | 源码位置 | 为什么这样对应 |
|---|---|---|
| 根输入、最终求和、截取预测区间 | `Autoformer-main/models/Autoformer.py::Model.forward`，74–96 行 | 91 行将 `trend_part + seasonal_part` 相加；94/96 行只返回最后 `pred_len` 步。 |
| 初始分解与两条 Decoder seed | 同上，77–82 行 | `x_enc` 分解得到 seasonal/trend；seasonal 取最后 `label_len` 步并补未来零，trend 取同长度历史并补输入序列均值。 |
| `x_dec` 的实际作用 | 同上，78 行 | 只读取 batch/channel shape 来创建零张量，其数值没有进入预测计算；不能画成普通 Transformer 的右移 token 输入。 |
| Encoder 输入/最终 memory | 同上，84–85 行；`Autoformer-main/layers/Autoformer_EncDec.py::Encoder.forward`，92–109 行 | Encoder 对原始 `x_enc` 的 embedding 计算；最终 seasonal norm 后输出供 cross K/V 使用。 |
| 两套独立 embedding | `Autoformer-main/models/Autoformer.py::Model.__init__`，27–30 行 | `enc_embedding` 与 `dec_embedding` 是分别实例化的模块，不共享参数。 |
| 无位置编码的实际 embedding | `Autoformer-main/layers/Embed.py::DataEmbedding_wo_pos.forward`，153–155 行 | 只相加 value 与 temporal embedding，然后 dropout。虽然 `__init__` 的147行创建 position embedding，但 forward 没有调用。 |
| Value embedding | `Autoformer-main/layers/Embed.py::TokenEmbedding`，49–61 行 | 是核宽 3、circular padding 的 `Conv1d(C,D)`，而非参考图的逐时刻 Linear。 |
| 时间标记 embedding | `Autoformer-main/layers/Embed.py::TimeFeatureEmbedding`，114–123 行 | `timeF`、`h` 配置选择 `Linear(4,D,bias=False)`。其他 embed/freq 分支未画。 |
| Encoder：AutoCorr→分解1→FFN→分解2 | `Autoformer-main/layers/Autoformer_EncDec.py::EncoderLayer.forward`，68–79 行 | 73行 attention 残差相加；74行分解并丢弃趋势；76–77行 Conv1d FFN；78行第二次分解并丢弃趋势。 |
| Decoder：self→分解1→cross→分解2→FFN→分解3 | 同文件 `DecoderLayer.forward`，132–146 行 | 顺序与三次分解逐条对应；每个分解输出的 seasonal 继续主通道，trend 另存。 |
| Cross Q/K/V 的来源 | 同上，138–140 行；`Autoformer-main/models/Autoformer.py::Model.forward`，88–89 行 | Q 为当前 Decoder seasonal state，K/V 均为 Encoder `enc_out`，不能将 seasonal/trend seed 误作 memory。 |
| 残差 FFN | 同文件 `EncoderLayer.__init__/forward`，61–66、75–78 行；`DecoderLayer.__init__/forward`，122–130、143–146 行 | 两个核宽1的 Conv1d，在时间轴各位置执行 `D→F→D`；本配置为 GELU，两个 dropout 仍在源码结构中，eval 时为恒等。 |
| 三个 trend 的投影 | 同文件 `DecoderLayer.forward`，148–150 行；`DecoderLayer.__init__`，128–129 行 | `trend1+trend2+trend3` 经独立的核宽3 circular Conv1d `D→C`，不是 seasonal forecast 的 Linear。 |
| 累计趋势状态 | 同文件 `Decoder.forward`，163–173 行 | 每层将 `residual_trend` 加到上一层 trend；本配置只有1层，初始 trend 直接与该层残差趋势相加。 |
| 堆叠后的特殊 norm 与 seasonal Linear | 同文件 `my_Layernorm.forward`，14–17 行；`Decoder.forward`，168–172 行；模型构造70–71行 | `LayerNorm(D)` 后减去时间均值；Decoder seasonal 再经 `Linear(D,C)`。norm 不在每个残差后，而在整组 Encoder/Decoder 的末尾。 |
| Q/K/V 与输出投影 | `Autoformer-main/layers/AutoCorrelation.py::AutoCorrelationLayer`，127–159 行 | 三个不同的 Linear 投影后分头；最终合头并经第四个 Linear。self、cross、不同层分别有自己的权重。 |
| FFT 的操作数与 lag correlation | 同文件 `AutoCorrelation.forward`，98–113 行 | K/V 对齐到 Q 长度，随后只对 Q/K 做 rFFT、乘共轭、irFFT。V 不经过 FFT 相关计算。 |
| 推理的 delay 聚合 | 同文件 `AutoCorrelation.time_delay_agg_inference`，45–71 行 | 每个样本选择 `floor(factor*log(Lq))` 个 delay，对相关强度 Softmax，再 gather 对应位移的 V 并加权求和。 |
| 训练分支差异 | 同文件 `AutoCorrelation.time_delay_agg_training`，21–43 行；`forward`，115–119 行 | 训练通过 batch 平均选共享 delay 索引，使用 roll 聚合；图只画 inference，但保留该差异说明。 |
| mask 没有生效 | 同文件 `AutoCorrelation.__init__`，13–19 行；`AutoCorrelation.forward`，98–124 行 | 虽接收 `mask_flag` 和 `attn_mask`，forward 没有读取它们执行遮挡；构造 self block 时的 `True` 不足以证明 causal mask。 |
| 分解的具体含义 | `Autoformer-main/layers/Autoformer_EncDec.py::moving_avg.forward`，29–36 行；`series_decomp.forward`，47–50 行 | 端点重复填充后移动平均为 trend，`x-trend` 为 seasonal。不是额外的第三个 residual 分量。 |

## 三种视图与真实状态流

概览折叠 preparation、Decoder layer、final parts，重点保留“原始序列→准备 tuple→Decoder→seasonal/trend→相加→预测区间”。模块图展开 Encoder 与 Decoder 的实际次序，明确 Decoder 中三次分解；详细图重点展开 Encoder 侧的 embedding、一处 AutoCorrelation、残差、FFN 和第一次分解。重复的 Decoder 同类算子、其余分解及两端特殊 norm 保留源码绑定并折叠，具体选择记录在布局 JSON 的 presentation_overrides 中。

全图与内部模块均从下到上计算。并列容器表示 fork / 命名 tuple 的收集，不隐含求和：embedding 的两项相加、三项 trend 相加、seasonal 与 trend 相加均显式标出。Encoder 与 Decoder preparation 的并列意味着它们从同一原始 `x_enc` 各自取输入，不能据此推断两者一定在运行时同时执行。

Decoder 层内部的自动主链标记为 `flow_role='seasonal'`：各 decomp 的 seasonal 输出继续上行；单独的 trend 边进入 `Trend update; carry seasonal` 复合边界。该边界明确执行 `trend1+trend2+trend3 → Conv1d(D,C,k=3) → trend += residual_trend`，seasonal 在此保持不变，并以 `(seasonal, trend)` tuple 输出。此处保留复合边界，避免将两个不同状态错误排成一条普通张量流水线。展开后外侧的 memory 边绑定 Cross AutoCorrelation 的 K/V；初始 trend 边绑定累计状态，不能解读为 attention 输入。

详细 AutoCorrelation 内部单独分出 `V: align + bypass FFT` 支路；Q/K 经 FFT 相关，最后以 `(corr,V)` 两个操作数进入 delay aggregation。因此图没有将 V 错画成相关矩阵的输入。`Q/K/V projections` 仍是带明确信息来源的复合投影框，未为每个 head、FFT 张量轴换位、单次 delay 循环各画一个图元。

分解详细组中的移动平均结果是减法的一个操作数；`Seasonal = x - mean` 的另一个操作数是该组保留的原始输入 x。`retained_input=True` 让引擎在组内画出输入 x 到减法的旁路。该小组整体对应 `series_decomp.forward`，不能把其中的箭头读成“只靠 moving mean 就能计算 seasonal”。

选择不同 tuple 分量的并列组明确标记 `dispatch=True`，分支的 `input_selector` 分别指定 Q/K、V 或 seasonal/trend，而不是把完整 tuple 原样复制到各分支。两套 embedding 的时间标记由独立的 `aux_inputs` 图元和 covariate 边送入对应的 time-feature Linear，不从时间序列数值伪派生。初始 trend 分支还使用 `Model.forward` 保留的原始输入均值。

## 参考图的主要修正

1. **删除普通 Add & Norm 模板。** 本实现是 residual 后分解，Encoder 两次、Decoder 三次；特殊 seasonal LayerNorm 仅在各层堆叠完成后执行。
2. **删除位置编码和 causal mask 的运行主张。** 位置编码对象虽被创建但不参与 `DataEmbedding_wo_pos.forward`；AutoCorrelation 不执行 mask。
3. **修正 embedding 和计算顺序。** Token embedding 是 circular Conv1d；Encoder 是 autocorrelation 在前、FFN 在后，Decoder 是 self→cross→FFN。
4. **修正 Decoder 输入。** 来自 `x_enc` 的分解初始化，不使用 `x_dec` 的数值。时间标记仍来自独立的 `x_mark_dec`。
5. **把趋势画成独立状态。** 初始 raw-channel trend 加上每层三次分解的投影趋势；最后与 seasonal Linear 的输出相加。参考图缺失这一核心累计路径。
6. **区分 FFT lag correlation 与普通点积注意力。** V 是 delay aggregation 的独立操作数；输入/输出 shape 中的 `D` 也不能替代实际分头后的 `H,E`。

## 参数身份与可复用部分

同色只表示同类算子，不表示共享权重。Encoder 的两层由列表推导分别构造，`encoder.attn_layers[0]` 与 `[1]` 独立；适配器以 `repeat={count:2,index:'i',independent_parameters:True}` 标识代表层是两个实例的结构模板。本配置 Decoder 为一层，其 self/cross AutoCorrelation 投影各自独立。两套 embedding、Decoder trend Conv1d、seasonal Linear 也分别独立。移动平均没有可训练权重，多个 decomposition 实例使用相同 window 仍不能与可训练权重共享混为一谈。

`adapters/autoformer.py` 的 `build()` 返回显式树、非主链绑定、profile、事实、修正记录与 AST 符号清单。源码路径与符号绑定可复用作证据定位；本模型专属部分包括初始化规则、渐进分解、FFT delay 聚合和 trend 状态。不要把本适配器只换 ZIP 路径就当作支持其他 Autoformer 分支。

当前未运行 PyTorch、未观测真实激活、未自动推导所有 shape，也未逐层展开两层 Encoder 的全部实例。形状来自选定配置下的静态阅读；图将同构重复层折叠为带层数和独立权重说明的代表层。训练模式、非 timeF embedding、其他频率、`output_attention=True` 的额外返回值和不同任务接口，需要独立扩展适配器。几何验证通过只说明绘图约束满足，不能证明所有数值计算等价。
