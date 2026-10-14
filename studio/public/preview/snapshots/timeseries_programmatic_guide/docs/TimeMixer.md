# TimeMixer：源码对应与基础图修正

绘图入口为 ZIP 内 `TimeMixer-main/models/TimeMixer.py::Model`，展示 `long_term_forecast`、`channel_independence=1`、`moving_avg`、`avg` 四尺度路径。配置参考 ETTh1 脚本第一次调用：L=H=96、N=7、D=16、F=32、PDM=2、下采样三次、窗口2；其余分支配置取 `run.py` 默认。本示例明确选择 `x_mark_enc=None`，不宣称数据加载器必然不提供时间特征。

源码仅作为文本与 AST 读取，图中维度为选定配置的静态推导，未执行模型。

| 源码位置 | 图中对应 | 对应原因 |
|---|---|---|
| `Model.__multi_scale_process_inputs`，288–329 | AvgPool 输入金字塔 | 在原始输入上递归下采样，并保留 x0、x1、x2、x3；不是只返回最后一级 |
| `Model.forecast`，341–360 | 每尺度 Normalize、折叠变量 | 各自归一化，再变为 `(B*N,L_i,1)`；尺度不是 batch 维 |
| `Model.pre_enc`，276–286 | 当前路径透传 | `channel_independence=1` 不调用预分解；不能因构造了 preprocess 就画出执行节点 |
| `Embed.py::DataEmbedding_wo_pos.forward`，187–194 | 共享 Conv1d value embedding | 此 profile 没有时间特征，调用 TokenEmbedding + Dropout；未调用 position_embedding |
| `PastDecomposableMixing.forward`，154–183 | PDM 内部的分解、双分支和残差 | season/trend 是两个输出；混合后逐尺度求和，再 `ori + out_cross_layer(out)` |
| `MultiScaleSeasonMixing`，28–69 | 细尺度→粗尺度链 | `down_sampling_layers[i]` 映射时间长度，并加上目标尺度原始 seasonal |
| `MultiScaleTrendMixing`，72–114 | 粗尺度→细尺度链 | reverse 后逐级上采样，加入目标尺度原始 trend，最后恢复列表顺序 |
| `Model.future_multi_mixing`，385–407 | 四个尺度预测器 | 各自 `Linear(L_i,H)`，共用 `projection_layer: D→1`，恢复变量维 |
| `Model.forecast`，381–383 | 四预测求和、scale0 反归一化 | 实际为 stack 后 sum，不是 concat；反归一化使用 normalize_layers[0] |

基础图中 Short/Mid/Long 三路卷积、常规 Add & Norm、独立第三个 Residual 分量、Concat + Linear 融合、Flatten Head 都不符合这个实现的所选路径，已替换。`PastDecomposableMixing.__init__` 构造了 layer_norm 和 dropout，但 `forward` 没有调用，因此不会仅凭成员声明画出计算步骤。源码注释中的 “CrissCrossAttention” 也不是本路径存在注意力的证据。

三个图共用一份语义 IR。概览折叠金字塔、逐尺度处理和两个 PDM；模块图显示尺度并列与第一个 PDM 的主结构；详细图展开第一个 PDM 的双向尺度递推，并重点展开各方向的第一个递推步骤，其余步骤保留实际独立身份并折叠。第二个 PDM 始终折叠以控制高度，内部独立实例与全部来源仍留在 IR 中。

主链及模块内部均自底向上。`fine→coarse`、`coarse→fine` 指**时间尺度的分辨率**，不要求图像中箭头分别向下和向上；两条计算分支都遵循统一阅读方向。PDM 的原始状态走残差旁路；每次跨尺度 Add 的原始 seasonal/trend 由分解节点的独立侧向绑定供给；金字塔侧线表示保留中间尺度。fork/join 总线表示 tuple/list 收集，真正的算术求和均另有明确节点。

参数身份需要区分：`pdm_blocks.0` 与 `.1` 独立；同一 PDM 内各尺度时间 Linear 独立；`out_cross_layer` 在该 PDM 内被不同尺度复用；`enc_embedding`、最终 `projection_layer` 在尺度与变量间复用；`predict_layers[i]` 与 `normalize_layers[i]` 按尺度独立。反归一化复用尺度0统计与仿射参数，并非所有尺度统计的平均。

未覆盖 `channel_independence=0` 的预分解与输出 residual 回归、DFT 分解、max/conv 下采样、future temporal feature、分类、补全和异常检测路径。特别是源码 DFT 的 `torch.fft.rfft(x)` 未显式指定时间轴，本示例不会凭论文口径替它纠正或宣称其行为正确。若扩展这些路径，必须建立新的配置、证据与绘图结构。
