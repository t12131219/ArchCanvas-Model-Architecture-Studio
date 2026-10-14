# Transformer 源码到架构图原型

2026-10-12 交汇点跟随：分支圆点通过源码张量与注册连线确定归属，按实际共享路径计算位置；移动、Apply、撤销和重做使用同一关系。旧 SVG 中误挂在其他模块里的静态圆点会迁移，普通交叉不会成为语义分支。

2026-10-12 短路径与容器接口跟随：语义字段和物理连接位置分离，普通图元自动选择合法连接侧；短间距优先直线，移动后也优化仍然合法的绕行路径。LayerNorm 等内部算子的原始直通出口可随所属端口移动，保留容器边、层级与穿越次序。Memory 上入下出、分支干线和多字段插槽继续受保护。共享路由器已同步，全部当前示例由 Summary_Merge 的 index 展示。实现、浏览器截图和验证见 [专项证据](../Summary_Merge/verification/shortest-routing/README.md)。

2026-10-12 拖动与文字修订：生成器以 `attachments` / `data-follow-owner` 明确绑定标题、Q/K/V 名称、形状和 hidden 快照；张量标签绑定值别名，模块标题绑定实际模块，hidden 快照绑定 ReLU 的源输出。标签不会成为 IR 算子，`source_owner` 可追到现有 IR 节点或端口。默认版和 compact 版的六张 SVG/PNG、布局与诊断均已更新；交互拖动、撤销/重做及校验见 [专项证据](../Summary_Merge/verification/drag-follow/README.md)。

2026-10-12 参考图修订：恢复 FFN hidden 值快照虚线（说明线，不是新增算子），将 Memory 框绑定到最终编码器输出线上，连线进入其上沿、从下沿继续到 K/V，补充 cross SDPA 的 memory padding mask，并统一箭头线帽为 `butt`。默认版与 compact 版均已刷新 SVG、PNG、布局及检查记录；模型源码未修改。

此次修复已进入源码语义层：[source_semantics.py](source_semantics.py) 从 `EncoderLayer.forward` / `DecoderLayer.forward` 的 AST 读取实际 Q/K/V、mask 参数、状态更新与 Post-LN 残差。`semantic_ir.json` 保存这些契约；实际 SVG 保存源码摘要、IR 摘要、父作用域、参数身份和 mask 元数据。验证器重新读取源码及 AST，比较接口绑定、包含关系、叶端点和实际 SVG，而不是仅比较两份缓存是否一致。

执行 `python3 tests/audit_semantics.py` 可复查 3 个视图和 27 个故意损坏的源码/IR/layout/SVG 负例。跨模型检查见 [Summary_Merge 审查报告](../Summary_Merge/verification/source-semantic-audit/report.json) 和 [说明](../Summary_Merge/verification/reference-refinement/README.md)。验证器负责拒绝不一致；修复由源码适配器重新生成，视觉重接仍作为 draft，不会改写模型。

`transformer_programmatic_guide` 是一个**源码到架构图的研究与实现原型**。它围绕随附的教育版 PyTorch Transformer，演示如何建立源码证据、模块与算子的语义对应、张量端口、三种展示粒度，以及可程序化计算的排布和箭头规则。

本目录既可直接查看已有结果，也可作为后续工具开发的设计参考。当前使用手写的 Transformer 语义适配器和确定性 SVG 模板；`ast.parse` 用于静态取证，模型结构与绑定由适配器显式描述。它不运行模型，也不具备从任意深度学习源码自动恢复架构的能力。

跨模型应用示例见 [时间序列模型扩展原型](../timeseries_programmatic_guide/README.md)：Autoformer、iTransformer、PatchTST、TimeMixer 使用各自源码适配器，并共享分层布局与 SVG 引擎。

本轮端点修订已同步默认版、compact 版和两份 mini 教学图。六张主图按源码接口追到实际可见算子；SVG、JSON、PNG 已一起刷新。详见 [Transformer 专项审查](../arrow_semantic_audit/transformer/README.md) 与 [原型总审查](../arrow_semantic_audit/箭头语义审查报告.md)。历史 `snapshots/` 原样保留，不能将旧图视作本轮已认证结果。

## 1. 从哪里开始

| 目的 | 入口 |
|---|---|
| 直接比较两种版式 | [版本选择页](版本选择.html) / [版本说明与运行命令](版本选择.md) |
| 查看当前默认的三层图 | [三图预览](generated/index.html) / [图3 SVG](generated/figure3_detailed.svg) |
| 查看上次保留的紧凑版 | [紧凑版三图预览](variants/compact_mixed_flow/generated/index.html) / [图3 SVG](variants/compact_mixed_flow/generated/figure3_detailed.svg) |
| 理解源码、图元和排布为何对应 | [完整中文说明](源码到Transformer三层架构图_对应关系与程序化布局.md) |
| 快速查阅布局设计 | [布局笔记](layout_notes.md) |
| 逐项核对实现依据 | [PyTorch 证据](pytorch_evidence.md) / [Tensor2Tensor 证据](t2t_evidence.md) |
| 从最小程序理解残差与端口 | [mini_residual.py](mini_residual.py) / [生成结果](mini_residual.svg) |

三个粒度分别是 **overview（概览）→ modules（模块操作）→ detailed（算子与张量细节）**，共用同一份语义 IR。展示细节可以折叠，数据依赖与参数身份应保持一致。

## 2. 两个可选版式

| 版本 | 内部阅读方向 | 图1 / 图2 / 图3尺寸 | 生成脚本 |
|---|---|---|---|
| **统一自底向上版，当前默认** | Attention / SDPA、FFN、Add & Norm 的主计算链均自底向上 | 1600×1218 / 1600×1718 / 1600×2742 | [draw_transformer.py](draw_transformer.py) |
| **紧凑混合方向版，上次结果** | 整体向上，Attention 内部向下；SDPA / FFN 横排，Linear→Q/K/V 张量横向连接 | 1600×1218 / 1600×1606 / 1600×2308 | [可选版生成器](variants/compact_mixed_flow/draw_transformer.py) |

两版的源码语义相同，各自保存图像、脚本、布局与说明。当前版的 self-attention 列序为 Q/K/V，cross-attention 使用 K/V｜Q 来源分组，使 memory 总线避开 Q 的输入；角色绑定与参数身份不因列序调整而改变。跨栏 memory 传输可向下，模块内部的主依赖线保持向上或水平。

可选版保存在 `variants/compact_mixed_flow/`，含源码副本，可独立重新生成。`snapshots/` 是修改前的历史恢复材料，部分快照未包含源码依赖；日常查看与运行应使用根目录或 `variants/` 中的正式可选目录。

## 3. 目录与产物

```text
transformer_programmatic_guide/
├── README.md                    使用入口与原型定位
├── draw_transformer.py          默认版：取证、语义适配、布局、SVG、检查
├── semantic_routes.py          源码接口投影、叶端点绑定、张量别名与语义检查
├── check_svg_routes.py          读取实际 SVG 的只读语义/路线诊断
├── mini_residual.py/.svg/.png    最小残差布局示例
├── 源码到Transformer三层架构图_对应关系与程序化布局.md
├── layout_notes.md              布局规则与观察
├── pytorch_evidence.md          PyTorch 源码对应依据
├── t2t_evidence.md              Tensor2Tensor 对照依据
├── 版本选择.html / 版本选择.md   两版入口
├── sources/                     整理后的源码参考
├── generated/                   当前默认版输出
├── variants/compact_mixed_flow/  上次紧凑版的完整可选副本
└── snapshots/                   历史快照
```

每个版本的 `generated/` 包含：

| 文件 | 用途与更新方式 |
|---|---|
| `figure1_overview.svg`、`figure2_modules.svg`、`figure3_detailed.svg` | 三种粒度的矢量图；生成器更新 |
| `source_evidence.json` | 源码摘要、符号、行范围与原文片段；生成器更新 |
| `semantic_ir.json` | 节点、层级、端口、连接和参数身份；生成器更新 |
| `layout_overview.json`、`layout_modules.json`、`layout_detailed.json` | 画布、图元框、端口及实际路径；生成器更新 |
| `layout_checks.json` | 生成时的结构与有限几何检查；生成器更新 |
| `index.html` | 三张 SVG 的查看入口；生成器更新 |
| 三张同名 `.png` | SVG 的栅格预览；需要单独转换 |
| `figure3_attention_detail.png` | Attention 局部预览；需要单独裁剪 |
| `route_diagnostics.json` | 已保存的独立审查记录；不会随生成器自动更新 |

**SVG 是布局结果的主要依据。** 重画后若 PNG、局部图或审查记录尚未刷新，它们仍可能对应旧版本。可选版的 `preservation_manifest.json` 是保存时的文件摘要清单，也不会随重新生成自动更新。

## 4. 运行与重新生成

生成 SVG 和运行路线诊断只需 **Python 3.9+ 标准库**；本文生成与诊断命令已在 Python 3.11.5 下验证。绘图无需安装 PyTorch、TensorFlow 或 `sources/` 中模型项目的依赖。PNG 转换示例另需 `rsvg-convert`；字体采用 DejaVu Sans / Arial / sans-serif 回退，换环境后应查看实际渲染。

以下命令从本目录运行。在当前工作区可先进入：

```bash
cd "/home/fzg/PycharmProjects/ArchCanvas/prototype/transformer_programmatic_guide"
```

### 4.1 生成一个新草稿

建议修改原型时先将结果写入临时目录，便于和已保存版本比较：

```bash
python3 draw_transformer.py --out /tmp/transformer-bottom-up-preview
```

```bash
python3 variants/compact_mixed_flow/draw_transformer.py --out /tmp/transformer-compact-preview
```

输出目录中的 `index.html` 可查看三张 SVG。省略 `--out` 时，各脚本默认写入**脚本所在目录**的 `generated/`；两个版本互不覆盖，但会覆盖各自已有的 SVG、JSON 和 HTML。

### 4.2 输入与参数

| 参数 | 行为 |
|---|---|
| `--source PATH` | 读取指定 Python 文件；默认读取脚本旁的 `sources/pytorch_transformer_original/transformer.py` |
| `--archive PATH` | 直接读取 zip 中唯一的 `*/transformer.py`，不解压、不执行源码；同时传入 `--source` 时以 archive 为准 |
| `--out DIR` | 指定输出目录；显式相对路径按当前工作目录解析 |

查看实际 CLI：

```bash
python3 draw_transformer.py --help
```

原压缩包位于本目录上一级时，可以直接读取：

```bash
python3 draw_transformer.py --archive ../pytorch_transformer_original.zip --out /tmp/transformer-from-zip
```

`--source` 只是输入路径选项，不代表自动支持任意模型。源码变为 Pre-LN、RoPE、GQA，或改动 mask、FFN、参数共享时，需要相应修改并核对适配器。Tensor2Tensor 1.0.14 在这里用于文档对照，尚未实现对应的绘图适配器。

### 4.3 刷新 PNG 与最小示例

转换上述默认版草稿的三张图：

```bash
rsvg-convert /tmp/transformer-bottom-up-preview/figure1_overview.svg -o /tmp/transformer-bottom-up-preview/figure1_overview.png
rsvg-convert /tmp/transformer-bottom-up-preview/figure2_modules.svg -o /tmp/transformer-bottom-up-preview/figure2_modules.png
rsvg-convert /tmp/transformer-bottom-up-preview/figure3_detailed.svg -o /tmp/transformer-bottom-up-preview/figure3_detailed.png
```

紧凑版使用其对应输出目录执行同样的转换。`figure3_attention_detail.png` 是人工选定范围的裁剪图，当前没有自动裁剪命令。

最小残差示例可单独运行：

```bash
python3 mini_residual.py
```

该示例将 `mini_residual.svg` 写到**当前工作目录**，与完整生成器按脚本位置确定默认输出的方式不同。

## 5. 验证结果如何阅读

完整生成器会写出 `layout_checks.json` 并打印结果；检查不通过时以非零状态退出。SVG 在检查之前已写出，因此不能仅凭“文件生成了”判断检查通过。

当前默认版检查原有十类内容，并增加源码投影的实际叶端点及全量依赖覆盖、张量别名来源与物理续线检查。原有十类为：画布边界、子节点包含、兄弟框不重叠、语义边端口合法、memory 来源与目标、memory 避开运算内部、箭头末段至少 18px、不沿矩形直边走线、实际落点匹配注册端口，以及依赖路径逐段向上。方向检查豁免所有 `semantic_kind=memory` 的实际跨栏分支；水平分叉、残差与说明线仍纳入检查。紧凑版执行相同语义与几何检查，并明确声明内部混合方向，故不执行逐段向上断言。

独立读取实际 SVG 复查：

```bash
python3 check_svg_routes.py /tmp/transformer-bottom-up-preview --border 0.1 --summary --strict
```

```bash
python3 variants/compact_mixed_flow/check_svg_routes.py /tmp/transformer-compact-preview --border 0.1 --summary --strict
```

诊断器接受多个目录或 SVG 文件；目录中扫描 `figure*.svg`。`--terminal` 默认 18px；`--border` 默认只报告重合长度至少 18px 的边框共线，示例显式使用 0.1px 以发现更短的共线段。端口检查需要 SVG 同目录的 `layout_*.json`；当前版只有在布局记录声明向上规则时才执行方向检查，结果中的 `upward_check_applied` 表示该项是否执行。

诊断命令默认打印 JSON，使用 `--strict` 可在发现任何问题或输入为空时非零退出。检查 `short_terminal`、`border_collinear`、`endpoint_errors`、`endpoint_unregistered`、`semantic_errors`、`svg_layout_errors` 及默认版 `downward_dependency_segments`，期望计数均为 0。缺少配套布局或 IR 会报告错误，不再静默跳过。`semantic_errors` 包括：非法 leaf 绑定、错用其他 Q/K/V 网格、source edge 未处置、物理链断裂；`svg_layout_errors` 核对实际 XML 路径、端点、trace 与 JSON。

如需保存本次命令结果，可使用独立文件名：

```bash
python3 check_svg_routes.py /tmp/transformer-bottom-up-preview --border 0.1 --summary --strict > /tmp/transformer-bottom-up-preview/route_check_current.json
```

本轮 `generated/route_diagnostics.json` 已刷新为严格诊断器的六项/方向项计数。旧记录保存在审查前备份及历史 snapshots 中。完整审计另见 [actual_transformer_audit.json](../arrow_semantic_audit/transformer/actual_transformer_audit.json)：包括实际 SVG、layout、IR、PNG 的 SHA256，以及 PNG 与当前 SVG 新鲜栅格渲染的逐字节对照。

### 5.1 端点元数据与最小残差例

实际箭头携带 `data-src` / `data-dst`（落到的可见图元端口）、`data-canonical-src` / `data-canonical-dst`（对应源码叶接口）及 `data-semantic-edges`（完整 IR trace）。例如详细图 memory 从 `enc.norm2.layernorm:out` 分别进入 `dec.cross.k:in`、`dec.cross.v:in`；Q 从 decoder 当前状态进入。`layout.semantic_projection.edge_dispositions` 逐条记录 134 条 IR 边的处置：实际连接、声明的源码接口别名，或同一可见源码范围内部的折叠；不得将外部真实依赖假称为内部折叠。

Q/K/V 与 FFN X/Z 网格是 `tensor_value_alias`，不是新增 Python 算子。每个网格有 `owner`、真实入/出端口；箭头穿过网格时拆成两段，仍保留同一源码关系与可核对的续线。几何网络只选择走线通道，不能决定张量身份。

两份 `mini_residual` 新增实际 `Input x` 图元和 `mini_residual_layout.json`：`x→F.in`、`F.out→Add&Norm.in`、`x→Add&Norm.skip`。它们明确属于残差教学 annotation，不被当成指定模型的源码 forward。最小例独立检查见 [mini 审计](../arrow_semantic_audit/transformer/mini/actual_mini_residual_audit.json)。

## 6. 作为原型参考，应该复用什么

当前程序的职责可按下面的链路阅读：

```text
源码文件 / zip
  → read_source / extract_evidence：静态定位、摘要、符号与片段 guard
  → make_ir：手写的模型语义、来源、层级与参数身份
  → measure_stack / render：粒度选择、模板尺寸与双栏排布
  → attention / ffn / norm / Scene：图元、端口、路径与 SVG
  → checks：有限结构与几何检查
```

| 后续想修改的内容 | 主要参考位置 | 应保留的关系 |
|---|---|---|
| 源码证据与模型结构 | `extract_evidence()`、`make_ir()` | 符号依据、实例身份、计算顺序、参数与张量绑定 |
| 展示粒度与子层顺序 | `measure_stack()`、`render()` | 同一 IR 的边界端口与执行顺序 |
| Attention / FFN / Norm 内部图例 | `attention()`、`ffn()`、`norm()` | 类型可识别、来源可区分、输入输出可追踪 |
| 箭头与几何记录 | `Scene.line()`、`Scene.layout()`、`checks()` | 实际绘制路径与记录一致、端点合法、末段与边框间隔 |
| 字体、颜色与页边距 | `COLORS`、`FONT`、模板参数 | 相同角色一致，不用同色暗示参数共享 |

值得复用的是**语义与视觉分离、稳定节点身份、显式端口、来源分组、并列与顺序的区分、同一结构的多粒度视图，以及可审查的布局记录**。仅调整版式时，应比较修改前后的 `semantic_ir.json`，确认模型事实未改变；源码证据的文件位置字段则可能随目录迁移而变化。

修改图像时优先改生成器，再重新生成与检查。直接编辑导出的 SVG 会与布局 JSON 和程序脱节，也会在下一次生成时被覆盖。保留另一种版式时，参考现有 `variants/`：保存脚本、图像、说明和证据，并提供明确选择入口。

## 7. 原型目前的边界

当前已实现的是特定 Transformer 的可阅读适配器和有限布局实例。以下事实应在扩展时继续明确：

- **取证不等于语义恢复。** AST 定位和片段 guard 没有证明整个函数的行为；没有跨文件调用解析、动态配置恢复或运行时张量追踪。
- **布局仍包含显式模板。** 容器高度、列宽、局部坐标和部分路由由模型专用规则给定；文字采用保守余量，没有完整字体测量、通用障碍路由或全局最优布局求解。
- **展示节点不等于完整运算清单。** Dropout / NaN guard 在 IR 保留、图中折叠；cross-attention 的 SDPA 在细图中仍折叠。张量网格表示符号状态，不是真实矩阵尺寸或激活值。
- **模型口径固定且有来源。** 使用 Post-LN、ReLU、固定正弦 PE；层重复表示独立参数的串联实例。memory 来自完整 Encoder 最终输出，Decoder 的因果 mask 由调用方提供，最终概率 Softmax 是 forward 之外的解释步骤。
- **检查有覆盖范围。** 通过有限几何检查不代表所有文字与路线都无碰撞，也不证明模型数值等价、任意源码改动正确或打印尺寸可读。
- **两个版本目前是两份生成器。** 尚未抽象成一个可配置的布局策略，也没有持久交互画布、局部展开、拖拽锁定、撤销/重做或源码写回。

后续工具可先沿三个方向推进：把源码适配与语义 IR 接口独立出来；把图例测量、粒度和布局方向做成共享策略；让真实字体测量、端口约束、路径检查和导出使用同一个场景模型。新增模型族时应建立对应证据与有限验收样例，避免把当前手写坐标当成通用源码分析能力。

详细的源码对应、数学依据和约束推导见 [完整中文说明](源码到Transformer三层架构图_对应关系与程序化布局.md)。
