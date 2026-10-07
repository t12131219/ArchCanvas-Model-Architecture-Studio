# M4：从空白画布搭建模型

当前（2026-10-06）为 `index-CWqdzert.js` / `index-DEZFMW6R.css`。[新手检查与参数引导](m4-authoring-guidance.md)增加独立“检查模型”、节点定位、声明形状、12px端口提示及34个参数字段中文说明。参数/连接变更使旧结果失效；移动和显示名称保留同一语义的声明。最终专项48/48、Studio284/284、strict TypeScript/Vite退出0；专项为全套子集，计数不相加。本轮未执行模型或安装依赖。

当前浏览器证据是恢复后四节点三边草稿的22组状态：修正参数、Linear四向移动16、缺边检查与定位、重连、保存重开；从空白搭建属于中间DS构建，旧生成/managed/出版工件按原版本读取。17基础模块＋3透明起点没有扩增或逐模块认证。AI亲看22图保留58%小字、100%提示框遮挡少量类型文字与局部裁切；小链无可见交叉不认证复杂CNN/Transformer或出版最优排布。

M4仍partial、M5未开始、真人0。AI审查不计真人；当前Studio A/B、三次矩阵、呈现帧性能与物理尺寸出版未认证。[当前schema15状态](evidence/m4-human-review-handoff-status-followup.json)单独绑定本轮范围；[更新前原字节](evidence/m4-authoring-guidance-work/before-current-doc-update-attempt-1/manifest.json)保留旧入口文档。此前BSA合流路由及ye端口交互仅保留各自冻结范围；下方旧“当前/本轮/最终”只指明确旧版本和时点。

历史版本说明：当前正式构建仍为 `index-au3IB_0Q.js` / `index-B6WbMowt.css`，最新范围见[au3矩阵、四向操作与输入诊断](m4-au3-current-matrix.md)。39例文件已collect，三模型四向/history/save-reopen已独审；像素问题与性能未通过项保留，AI真人0、M4 partial、M5未开始。下方记录保留各自历史构建/时点，不继承为最新浏览器或研究认证。当前au3研究包仍未prepare/verify，旧研究席位不可分配。此前seal与末读原字节见[更新前归档](evidence/before-m4-au3-full-matrix/manifest.json)。

当前（2026-10-05）为 `index-ChS0wIgb.js`（SHA256 `05019f89f0de0c0c622df7a2cc1a13ed58477c456244c97209a0f37db79139c9`）与 `index-CsXMONBp.css`。本轮[显式位置修复与透明网络起点](m4-move-recovery-presets.md)新增预览/应用/取消和17基础模块上的3个可编辑网络起点；最终Studio152/152、strict/build退出0。中间会话与最终build证据分开；最终23组/46图、四向操作及单个pin拒绝范围单列，不宣称新36＋3矩阵；最终独立发行9项通过；磁盘满的前次失败保留。旧Bc矩阵/诊断/五席包不能认证本构建，fresh研究准备待完成、真人0。M4仍partial，未进入M5。

[切换前2894绑定原字节](evidence/before-m4-move-recovery-presets/manifest.json)保留旧Bc seal/status/矩阵/诊断/源码；下方历史记录中的“当前/本轮/最终”仅指其明确旧构建和冻结时点，不计新build浏览器、性能或真人认证。旧raw、seal、manifest和研究包不回写。

本轮已实现独立的“模型搭建”工作区。点击 Studio 顶部的“搭建模型”，即可从左侧常用模块库拖入或点击添加模块，在右侧修改参数，连接端口并生成新的 Python 模型。该能力用于创建新模型；已有源代码导入后的制图文档继续保留原有语义保护。

## 入门操作

1. 点击“搭建模型”，再点击“新建空白模型”。先保存当前需要保留的草稿；新建按钮会切换到新的草稿身份。
2. 加入 `Input`，在右侧设置输入形状与 `dtype`。例如默认 `shape = 1, 16`、`dtype = float32`。
3. 加入 `Linear`、`ReLU` 和 `Output`。默认 Linear 将最后一维从 16 变为 32，因此该例输出形状为 `[1, 32]`。
4. 从模块的输出圆点拖到下一个模块的输入圆点，或依次点击两个端口，建立 `Input → Linear → ReLU → Output`。一条输入端口只能有一个来源；分支可以共享同一个输出。
5. 拖动模块调整位置；选中模块后，方向键每次移动 16 个画布单位。工具栏提供平移、缩放、适合画布和“按连接排版”。选中模块或连线后可删除，`Ctrl+Z` 撤销，`Ctrl+Shift+Z` 重做，`Escape` 取消当前手势。
6. 点击“保存草稿”，以后可“重开已保存”。点击“生成模型与论文图”后，审看实际生成的新源码；再点击“创建新工作副本并打开论文图”，进入制图工作区编辑显示名称、样式和布局，并使用现有导出功能。

左侧可按英文类型或中文名称搜索模块。数组参数使用逗号分隔，例如二维卷积的 `kernel_size = 3, 3`；数值字段提交时会检查类型。模块重叠或连线无法避开模块时，画布会显示提示，可手动移动或重新排版。

“生成”先返回新源码和静态核对结果，不创建源项目。打开论文图的后续操作才注册新的 managed 工作副本；显示别名来自草稿标签。搭建坐标属于草稿，制图工作区使用其自己的布局，当前没有承诺两种工作区的坐标完全一致或持续同步。

## 当前 17 种模块

| 类型 | 中文用途 | 主要输入要求与效果 |
| --- | --- | --- |
| `Input` | 输入 | 声明正整数形状及 `float32`、`float64` 或 `int64` 类型；无输入端口。 |
| `Output` | 输出 | 一个输入端口，可添加多个命名输出；无输出端口。 |
| `Linear` | 全连接 | `float32`，最后一维须等于 `in_features`，输出最后一维为 `out_features`。 |
| `ReLU` | ReLU 激活 | 浮点张量，逐元素激活，保留形状；无原地修改参数。 |
| `GELU` | GELU 激活 | 浮点张量，`approximate` 可选 `none` 或 `tanh`。 |
| `SiLU` | SiLU 激活 | 浮点张量，保留形状；无原地修改参数。 |
| `Identity` | 恒等映射 | 保留形状与类型。 |
| `Dropout` | 随机失活 | 浮点张量，`p` 在 `[0, 1]`；训练与评估行为不同。 |
| `Flatten` | 展平 | 合并 `start_dim` 到 `end_dim` 的维度，默认保留批次维度。 |
| `Conv2d` | 二维卷积 | CHW/NCHW 的 `float32` 输入；通道须匹配，分组须同时整除输入与输出通道。 |
| `MaxPool2d` | 二维最大池化 | CHW/NCHW 浮点输入，支持步长、填充、膨胀和 `ceil_mode`；只返回池化张量。 |
| `AdaptiveAvgPool2d` | 自适应平均池化 | CHW/NCHW 浮点输入，空间输出尺寸为指定的两个正整数。 |
| `BatchNorm2d` | 二维批归一化 | NCHW 的 `float32` 输入，通道数匹配，当前要求每通道不止一个值。 |
| `LayerNorm` | 层归一化 | `float32`，末尾维度须与 `normalized_shape` 完全匹配。 |
| `Embedding` | 词嵌入 | `int64` 索引输入，输出为 `float32`，增加末尾嵌入维度。 |
| `Add` | 张量相加 | `left` 与 `right` 必须形状、类型相同；当前不允许隐式广播。 |
| `Concat` | 张量拼接 | `a` 与 `b` 类型和秩相同，除指定轴外其他维度相同；只支持两路输入。 |

卷积、池化的空间参数使用长度为 2 的整数数组。构造带权重的 Linear、Conv2d、BatchNorm2d、LayerNorm 和 Embedding 时，生成源码显式指定 `dtype=torch.float32`。负数 Concat 轴按照已声明的输入秩转成等价非负轴，草稿仍保留原值，核对结果记录 `scalarNormalizations`。

`Sigmoid`、`Tanh`、`Conv1d`、`AvgPool2d`、`BatchNorm1d`、`MultiheadAttention` 和 `LSTM` 尚未进入搭建库。现有静态分析器能识别某些模块，不代表搭建工作区已经支持其构造与完整核对。当前也不提供任意 Python、自定义代码节点、循环、共享权重实例、动态形状、自动广播或三路以上拼接。左侧已有最小MLP、小型CNN、残差MLP三个透明网络起点；插入后仍是上述普通节点，可独立编辑，不新增模块类型。

## 草稿、校验与新源码

搭建草稿使用独立 `authored-draft` schema，节点只有身份、类型、标签、参数和位置，连接使用明确的节点与端口身份。草稿没有源文件路径、source digest 或伪造的 source binding；导入的 CanvasDocument 不能替代它。单份草稿最多 128 个模块、384 条连接；声明张量最多 8 维、十亿个元素。这些是编辑器的校验预算，不代表相应张量已分配或可以在当前硬件运行。

保存允许未接线的合法草稿，例如只有 Input、尚未连接 Output 的网络。已有连接仍须满足端口方向与归属、单输入单生产者、无环、参数合法等约束；已能从声明推导的形状与类型冲突会拒绝。非法值、重复身份、未知字段、布尔值冒充整数或非有限数值不会写入保存文件，Studio 会保留编辑并显示错误。

生成要求至少一个 Input 和 Output，所有必需输入端口完整绑定，每个节点都贡献到某个输出。后端从声明形状与类型推导张量规格，再生成全新 `model.py` / `AuthoredModel`，由正式 AST frontend 静态重分析。核对覆盖完整节点与端口清单、构造参数、实例与调用身份、父子关系、输出键、tensor 的唯一生产者和全部消费绑定。相同标签不合并模块，同一张量分支不拆成伪造的独立 tensor。

形状与类型是用户声明下的静态合同；整个搭建、生成与注册过程**不导入或执行模型**。没有数值、训练、梯度、内存、权重加载、Embedding 索引范围或 checkpoint 兼容性验证；执行结果记为 `modelExecution: not_run`。生成源码成功与“可以训练”是不同证据。

草稿保存有独立的存储版本检查。多个客户端并发保存同一版本时只有一个成功，陈旧客户端收到冲突且其编辑保留；服务重新启动后可重开原草稿。草稿撤销属于草稿历史，论文图视觉撤销属于 CanvasDocument 历史，两者均不能替代已提交源码变更的审核事务。

注册新模型使用现有 managed-copy 服务，重新分析新源码并检查 source/IR digest。该操作不重写导入模型的原目录或已注册副本；已导入模型的语义编辑仍受原有 intent、具体审核、审批和提交保护约束。继续修改搭建草稿再生成，会得到另一份新源码；当前没有把该草稿自动写回此前打开的源项目。

## 搭建证据版本

以下搭建浏览器与113/300回归记录绑定此前 CIVB 构建，327个原始绑定保存在 `before-m4-routing-refinement`。此前 CVO 构建仅新增共享路由收敛，当前测试/CPU/实际SVG与代理探索范围见 [m4-routing-refinement](m4-routing-refinement.md)；不继承历史浏览器矩阵或任务通过。

## 历史 CIVB 证据与未完成验收

独立证据位于 [independent/manifest.json](evidence/m4-authoring-next/independent/manifest.json)，范围说明见 [independent/README.md](evidence/m4-authoring-next/independent/README.md)。该组实际通过 8 个手算网络正例、50 个无效草稿反例和 21 个故意恶化的源码/IR 独立 oracle 控制；实际随机端口 HTTP 检查为 7/7，通过记录没有跳过项。最初受限 socket 的跳过日志另行保留，不计作通过。

正例覆盖 17 种已启用模块、MLP、CNN、Embedding→LayerNorm、残差分支、不同 Concat 轴、分组与膨胀卷积、ceil pooling，以及同表达式的独立 Add 调用。独立 oracle 不调用产品的 registry、形状推导、生成器或 verifier 来决定期望；它检查实际 Python AST、静态 IR、手算张量形状和精确连线。HTTP 证据覆盖 mutation session/origin、保存冲突、并发、重开、模式隔离、文本生成、fresh managed 注册及原件字节保留。

Studio 全套检查本轮通过 113/113，严格 TypeScript 与构建通过；获准环境中的 Python 全套检查通过 300/300、零跳过。受限环境首次运行的失败和跳过日志另行保留，不能计为通过。

实际浏览器从空白开始拖入 Input、Linear、ReLU、Output，连线后保存，修改 Linear 输出宽度为 48，再重开、审看新源码、创建新工作副本并生成 PDF 和 SVG。[浏览器独立报告](evidence/m4-authoring-next/browser-audit/README.md)核对 25 份当前构建公开 DOM 记录和 11 个实际服务工件；21 个浏览器几何污染反例及 17 个服务/出版工件污染反例全部被拒绝。原始失败记录保留，未继承此前构建的完整视觉矩阵。

同一个 Linear 的左、右、上、下原生按键移动各为 16 个画布单位；左移另有单独撤销、重做记录，其他三向只认证移动状态与最终整体恢复。四向原生拖动平移各为 40 CSS 像素并恢复，图形未改变；第一轮左向返回曾中断，该链排除，左向通过范围是完整第二轮。简单搭建链的 25 份几何状态均无模块重叠、路径穿框、严格交叉或线段重合；上下移动后的折线在当时端点位置下为最短曼哈顿路径。

保存的 DraftStore 存储版本为 2、草稿历史版本为 19；CanvasStore 存储版本为 1、CanvasDocument 内层版本为 0。实际保存稿、生成 Python AST、静态架构及论文图中的 Linear 均为 16→48。论文图保存重开后的完整交互 SVG 逐字节相同；浏览器 SVG 与导出 SVG 的几何、绑定和元数据一致，二者并非同一份字节。PDF 实际页面约为 180×196.63866 mm，仅证明工件尺寸与文件绑定，没有物理纸面或字体保真人审证据。

论文图有两处节点中心错位，分别产生两个折点，总计 4 个真实弯折；无严格交叉、线段重合或叶节点穿框。进一步对齐仍可改善视觉，不能把简单链通过扩大为复杂模型连线美观认证。原始草稿存储版本 1 的参数字节、浏览器生成 HTTP receipt、摄像机持久化、用户目录下载交付、持续 presented performance 和按住手势时取消均不在本轮通过范围。

AI 子 Agent 可以模拟新手、审查者并提出缺陷，但不能充当真实研究使用者或出版审看者。M4 当前继续保持 partial：3–5 位真实研究使用者的五步任务与真人出版尺寸审看尚未完成，当前构建的完整新视觉矩阵、持续 presented performance 和 active cancellation 证据仍需分别完成；路由不必要交叉与弯折的美观优化也没有完整通过证据。本轮搭建能力补齐了可操作的产品入口，未据此宣布 M4 完成或进入 M5。
