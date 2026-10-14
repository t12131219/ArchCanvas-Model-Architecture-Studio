# 时间序列模型：源码到架构图的跨模型原型

这是 `transformer_programmatic_guide` 的跨模型扩展，已接入用户提供的 **Autoformer、iTransformer、PatchTST、TimeMixer** 四份源码。每个模型都有独立适配器，四者共用静态取证、语义 IR、分层测量、端口连线和 SVG 导出机制。

**当前仍是显式适配器原型。** 模型结构来自对指定源码与配置的人工审阅；程序负责核对证据并生成图形。基础 PNG 是视觉参考，结构冲突以源码为准。它没有从任意源码自动恢复架构，也没有执行 PyTorch、训练模型或观察真实激活。

## 先查看结果

打开 [四模型交互预览](generated/index.html)，可在概览、模块和详细视图之间切换。每个模型的三张图共用一份语义 IR。

| 模型 | 三种粒度 | 详细 SVG | 源码对应与参考图修正 |
|---|---|---|---|
| Autoformer | [预览](generated/autoformer/index.html) | [详细图](generated/autoformer/figure3_detailed.svg) | [说明](docs/Autoformer.md) · [逐节点映射](generated/autoformer/source_map.md) |
| iTransformer | [预览](generated/itransformer/index.html) | [详细图](generated/itransformer/figure3_detailed.svg) | [说明](docs/iTransformer.md) · [逐节点映射](generated/itransformer/source_map.md) |
| PatchTST | [预览](generated/patchtst/index.html) | [详细图](generated/patchtst/figure3_detailed.svg) | [说明](docs/PatchTST.md) · [逐节点映射](generated/patchtst/source_map.md) |
| TimeMixer | [预览](generated/timemixer/index.html) | [详细图](generated/timemixer/figure3_detailed.svg) | [说明](docs/TimeMixer.md) · [逐节点映射](generated/timemixer/source_map.md) |

原始 Transformer 原型、统一自底向上版和之前保留的紧凑版，仍可从 [Transformer README](../transformer_programmatic_guide/README.md) 进入。本目录采用独立的共享引擎和四个适配器。

## 已纠正的关键结构

| 模型 | 基础图与所选源码的差异 | 新图如何表达 |
|---|---|---|
| Autoformer | 普通 Add & Norm、位置编码、Decoder causal mask、右移 x_dec 数值输入，与实际 forward 不符 | residual 后渐进分解；x_enc 构造 seasonal/trend seed；FFT lag correlation 与独立 V 聚合；三项 trend 投影累计；seasonal+trend 输出 |
| iTransformer | 输出 permute 与 Linear 顺序颠倒，省略协变量 token、最终 Encoder norm 和反归一化 | Linear(D,P)→permute→保留 N 个变量；协变量作为独立外部输入；输入统计复用；Attention 在变量 token 轴上计算 |
| PatchTST | Flatten head 被写成 D→H，默认 norm 被写成 LayerNorm，缺失 RevIN、end padding 与跨层 scores | D*P→H；默认 post-BatchNorm；显式 patch 数量公式；RevIN 还原；Softmax 前 scores 进入下一层，V 独立进入 A@V |
| TimeMixer | 三路卷积混合、常规 Add & Norm、三分量分解、Concat head 不符合该实现 | 输入尺度金字塔→逐尺度处理→season 细到粗 / trend 粗到细的时间 MLP→逐尺度预测→求和→尺度0反归一化 |

这些修正针对**提供的压缩包与下面的选定分支**，不能推广为所有同名实现或所有任务配置的事实。

## 所选配置与折叠边界

| 模型 | 本次 profile | 视觉上的代表性展开 |
|---|---|---|
| Autoformer | run.py 默认预测配置，L=96、label=48、P=96、C=7、D=512、F=2048、8头、Encoder=2、Decoder=1；timeF/h；eval delay 聚合 | Encoder 使用带独立参数说明的二层实例族模板；详细图重点展开一处 AutoCorrelation、分解及 FFN，Decoder 同类内部折叠 |
| iTransformer | ETTh1 首条脚本配置 + CLI 默认；L=P=96、N=7、协变量 C=4、token T=11、D=F=256、8头、2层 | 第1层展开，第2层保留完整 IR 并折叠；协变量是单独输入；无协变量分支未选 |
| PatchTST | supervised/run_longExp 默认：L=H=96、C=7、p=16、s=8、P=12、D=512、F=2048、8头、2层；RevIN、共享 head、res_attention 开启 | 第1层展开，第2层折叠但保留独立权重与 score 输入；不展示 self-supervised、分解双 backbone 或 individual head 分支 |
| TimeMixer | ETTh1 首条脚本 + CLI 默认，显式选择 x_mark_enc=None；L=H=96、N=7、D=16、F=32、2个PDM、avg四尺度、CI=1、moving_avg=25 | 第1个PDM展开，第2个折叠；详细图展开双向尺度递推中的代表步骤，其余步骤保留实际独立身份并折叠 |

形状均为源码及 profile 下的静态推导。不同模型符号口径不同，图下方提供各自图例。尺寸不是运行时观测值；配置 JSON 保存在各模型输出目录。

为减少重复，独立 Dropout 和 iTransformer FFN 的内部 transpose 在视觉上折叠，源码节点保留在 IR；组合框中的 `Add + dropout`、`GELU + dropout` 会保留其主要运算。SVG 悬停信息包含完整说明和参数身份。所有折叠选择都能在生成脚本和 `layout_*.json` 中核对。

## 重新生成

生成器和验收器只需 **Python 3.9+ 标准库**；本文命令在 Python 3.11.5 下验证。生成 PNG 另需 `rsvg-convert`。字体采用 DejaVu Sans / Arial / sans-serif；跨环境字体回退可能改变外观，需要重新查看导出。

从本目录运行：

```bash
cd "/home/fzg/PycharmProjects/ArchCanvas/prototype/timeseries_programmatic_guide"
python3 generate.py --out /tmp/timeseries-preview --png
python3 verify.py /tmp/timeseries-preview --png
```

查看 `/tmp/timeseries-preview/index.html`。也可以只生成一个模型：

```bash
python3 generate.py --model autoformer --out /tmp/autoformer-preview --png
```

| 参数 | 行为 |
|---|---|
| `--model all/autoformer/itransformer/patchtst/timemixer` | 默认 all；只生成/刷新所选模型，已有其他模型目录不会删除；总览和 validation_summary 只记录本次生成项 |
| `--archive-dir DIR` | 默认脚本目录上一级，需要相应的原始 ZIP；读取所需文件并保存证据副本，不导入或执行模型项目 |
| `--out DIR` | 默认脚本旁的 generated；显式相对路径按当前工作目录解释 |
| `--png` | 使用 rsvg-convert 生成同名 PNG；省略时只更新 SVG、JSON、HTML、映射 Markdown 和源码副本 |

将整套目录迁移时，携带上一级的四个 ZIP，或使用 `--archive-dir` 指向它们。`reviewed_archives.json` 绑定本次审阅的原始 ZIP 摘要；压缩包变化时生成器会拒绝继续，避免旧适配器悄悄解释新源码。修改模型版本需要重新审阅适配器并有意识地更新摘要；不能把更新摘要当作兼容性验证。

`generate.py` 会生成文件后检查，布局失败时返回非零；失败输出供诊断，不代表可交付。省略 `--png` 后，已有 PNG 可能仍是旧结果，建议开发期间始终输出到新的草稿目录。

`verify.py` 默认验收完整四模型、每个三视图的交付目录，缺模型或缺图都会失败；单模型草稿可先使用生成时的布局检查。`export_checks.json` 需要单独运行验收器更新，生成器不会刷新它。

## 目录结构与证据

```text
timeseries_programmatic_guide/
├── README.md
├── spec.py                     显式模型描述契约
├── evidence.py                 ZIP/AST 静态取证、摘要绑定、语义 IR
├── theme.py                    Transformer 风格的色板、字体、节点视觉角色
├── layout.py                   共享测量、嵌套布局、端口、折线路由、SVG、几何检查
├── generate.py                 profile、三种粒度、预览与导出入口
├── verify.py                   实际导出核验、源码片段与模型事实验收
├── reviewed_archives.json      已审阅 ZIP 的 SHA256
├── adapters/                   四个模型专用的 build()
├── docs/                       四份中文源码对应和修正说明
└── generated/
    ├── index.html              四模型可切换预览
    ├── validation_summary.json 生成时的检查结果
    ├── export_checks.json      独立验收记录
    └── <model>/
        ├── figure1_overview.svg/.png
        ├── figure2_modules.svg/.png
        ├── figure3_detailed.svg/.png
        ├── index.html
        ├── profile.json
        ├── source_evidence.json
        ├── semantic_ir.json
        ├── source_map.md
        ├── layout_overview.json / layout_modules.json / layout_detailed.json
        ├── layout_checks.json
        └── sources/            实际引用的源码及配置文件副本
```

图框上的 `E###` 来自 `source_evidence.json`，编号在**单个模型**中有效。悬停图框可查文件、起始行、符号、参数身份与补充说明。`source_map.md` 将稳定节点 ID、shape、证据编号和参数身份逐项列出；完整函数片段、行范围与文件摘要留在 JSON 中。复制的源码保留 ZIP 内的相对路径，不需要导入模型项目即可核对。

## 与 Transformer 原型一致的视觉样式

`theme.py` 集中定义 `transformer-paper` 样式。采用与 Transformer 图相同的 DejaVu Sans 字体栈和主要色值，通过明确的模块角色扩大颜色覆盖面积，并使用实色边框增强层级对比。

| 视觉角色 | 颜色与用途 |
|---|---|
| Attention / AutoCorrelation | 橙色 `#ffddb3` 的主要模块框 |
| FFN / 时间与特征 MLP | 青蓝 `#c8ebfb` |
| Norm / Add / Sum | 淡黄 `#fff6bd`；同色不代表这些操作数学等价 |
| 输入 / Embedding | 粉色 `#f8d4e1`；输入框表示外部数据，本身不执行 Embedding |
| Linear / 预测投影 / 输出 | 淡紫 `#dfdff8`；输出框标记预测结果 |
| Softmax | 绿色 `#c9f1cd`；GELU、Dropout 使用浅灰，避免混同 |
| 序列分解 | 浅绿 `#d6f0df`；AvgPool 构造尺度金字塔使用张量蓝 |
| 路径和层级容器 | Encoder 浅蓝、Decoder 浅粉；TimeMixer 的 season/trend 路径也以浅蓝/浅粉分栏；内部 tuple/list 组织框采用中性色 |

字体层级为主标题 30px、主要模块标题 22–24px 加粗、内部组织标题 20px 加粗、算子标签 20px 常规、shape 16px、说明 14px、证据编号 12px。正文 `#172336`，边框 `#263348`；主要外框 2.5px、普通框 2px、内部组织框 1.6px，均不降低透明度。改变字号后会重新测量节点并计算布局，避免文字变大后挤出原框。

同一层的主要 Attention、FFN、分解与归一化框采用一致宽度，内部算子保持居中；这些展示选择由 `FILL_WIDTH` 显式指定。这样较窄的 FFN 不会缩成一根小柱，主模块的色块和横向边界更接近 Transformer 示例。标题区域同步按新字号重新换行。

视觉角色以稳定节点 ID 显式绑定，记录在布局 JSON 的 `boxes[].style`；总样式参数记录在 `visual_style` 和 SVG 的 `diagram-style` metadata 中。它们属于展示层，不修改语义 IR 的 `kind`、来源证据或参数身份。新增模型时需补齐其容器视觉角色；未注册的容器默认中性色，不根据标题猜测其算法类别。

## 语义如何变成排布

```text
已审阅 ZIP + profile
    → AST 符号与文件/压缩包摘要
    → 模型适配器：chain / parallel / 显式侧向绑定
    → 同一份语义 IR
    → 选展示粒度、折叠重复与次要操作
    → 递归测量、分配位置、注册几何端口
    → 内部连接 + 避障侧向路由
    → SVG / 布局记录 / 检查 / PNG / 预览
```

适配器只声明结构和关系，不为每个图框写绝对 x/y。核心约定如下：

1. **顺序先于位置。** `chain.items` 按源码输入→输出声明；布局从底部逐项向上放置。串联相邻节点之间保留统一间距，父容器高度由子节点高度之和计算。
2. **并列有明确语义。** `parallel` 为独立分支分配横向列，底部输入对齐；顶部收集 tuple/list。`dispatch` 与 `input_selector` 指明选择哪些分量。真正的 Add、A@V 或预测求和另设节点，汇流总线本身不代表加法，也不代表权重共享或运行时并发。
3. **尺寸由内容与层级分配。** 叶节点按标签、shape、证据行测量；chain 宽度取最宽子节点再加两侧空间，parallel 宽度累加各列宽度与列间距；头部高度根据标题/shape 行数计算。标题与 shape 放在顶部两侧，中央留出向上输出通道。
4. **残差与保留操作数不同。** `residual=True` 将组输入送到末端 Add；`retained_input=True` 将分解原始 x 送到末端减法。这些边在 IR 中区分，不能仅靠画一条相似旁路表示同一数学操作。
5. **侧向来源单独绑定。** memory、趋势、统计量、跨层 raw scores、外部协变量以命名边声明。折叠后投影到最近可见祖先；记录同时保留原始语义端点、语义端口、可见祖先及实际几何端口。若两端都折入同一图框，则不另画自环。
6. **路由使用实际障碍。** 内部主链保持向上；侧向连接采用基于框边界坐标的正交 A*，避开叶框、与端点无关的模块组和已测文字，并拒绝沿矩形直边走线。箭头末段保留至少18px，侧线强制24px接入段；箭头采用固定 userSpaceOnUse 尺寸。跨栏辅助边允许必要的向下绕行，不改变源码依赖方向。

当前字宽是保守估算，尚未使用真实字体逐字测量；A* 在有限障碍坐标网格上寻路，也不保证全局最短或所有边彼此无重叠。实际路径同时写入 SVG 和布局 JSON，便于复核和后续替换更精确的测量/路由器。

## 验证能说明什么

生成时检查画布边界、父子包含、同级框不重叠、注册端点、箭头末段、正交路径、主计算向上、不沿边框走线、不穿越叶框、侧线不穿越无关模块组，以及估算文字不越出画布。

验收器再从**实际 SVG**读取矩形、路径、marker，与布局记录逐项比对；核对冻结源码 SHA、AST 范围和片段、三视图相同 IR 摘要，检查几个核心模型绑定。`--png` 还检查 PNG 尺寸。检查失败返回非零，并保存具体问题。它复用几何规则，同时独立核对导出与记录的一致性；不能把这称为独立数学等价证明。

这些检查不会证明任意源码语义恢复、完整的运行时 tensor producer、所有循环/多状态边界的逐算子数值等价，或任意打印缩放下的可读性。Decoder trend 更新、TimeMixer 递推保留列表等仍有明确复合边界，具体范围见模型说明。图像必须再人工查看标题、文字、线与框的实际关系。

## 如何继续增加模型

新增 `adapters/<name>.py`，以 `build()` 返回入口、archive、profile、tree、aux_inputs、extra_edges、facts、corrections、symbols、legend。先定位真实 forward、构造配置、训练/推理分支，再声明 chain 与分支选择，写对应说明和关键验收样例。更新生成器模型注册表及已审阅摘要后，复用共享引擎生成三个粒度并验证。

不要通过复制一个 Transformer 图、换模型名称和 `--source` 路径来宣称适配完成。适配器负责回答“有哪些模块、张量从哪里来、哪些参数相同”；布局引擎负责回答“怎样紧凑排列、怎样连接与折叠”。当前四个实例验证了这种分工可以跨模型复用；自动分析更广泛 Python 动态结构仍是后续工作。

本扩展交付独立 SVG/PNG/HTML 和程序脚本，尚未连接 ArchCanvas Studio 的持久 CanvasDocument、拖拽历史或源码写回接口。
