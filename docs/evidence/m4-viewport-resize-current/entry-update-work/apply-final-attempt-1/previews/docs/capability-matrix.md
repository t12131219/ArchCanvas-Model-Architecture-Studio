# 首批真实能力矩阵

## 当前状态：视口尺寸与相机坐标协调（2026-10-06）

本阶段绑定 `index-_KAUBMcR.js` / `index--unhoRTb.css`。Studio **430/430**、fail/skip/cancel 0，strict TypeScript/Vite exit 0；publication **11/11**、skip 0。[统一收据](evidence/m4-viewport-resize-current/checks-final-attempt-2/receipt.json)为 112 源码/测试/配置＋3 dist＝**115**，另 11 publication 输入；18 份兼容测试历史 core 单独冻结，112 不是全部传递依赖清单。见[阶段](m4-viewport-resize.md)、[门状态](evidence/m4-current-gate-audit.json)与[143 项源码变更前归档](evidence/m4-viewport-resize-current/before-change/manifest.json)。只认证对应冻结字节。

新增 live ResizeObserver，在空闲视口变大或变小时保持世界中心和 zoom；相机持久化沿用已协调的坐标框尺寸。active pan、对象拖动、框选与端口输入保留原坐标映射，终止/取消后再协调。有限初始化等待可在可用视口/重新挂载时续行，旧 load/intent 不能覆盖新操作。focused45/45包含21项新增 resize 测试，是实际 App callback/effect harness，未挂载 React，不证明浏览器 paint 或初始零闪动。窗口 fallback 不能感知所有内部元素改尺寸。

[相机133/133](evidence/m4-viewport-resize-current/independent-routing-agent/browser-camera-readback-final/report.json)与[节点154/154](evidence/m4-viewport-resize-current/independent-routing-agent/browser-node-readback-attempt-4/report.json)分别核对有限公共DOM关系，不是功能全部成功。11/12 live resize和16/37重开初始DOM仍旧/默认中心，后续恢复(350,405)；first-paint未认证。相机四向32 CSSpx、Encoder四向24世界单位及各自undo、authoring重挂载返回、保存39/storage6和settled重开已记录。像素28/30的footer滞后一版、42仍100%而DOM已54%；43仅root有限亲看完整figure/legend。稳定DOM不能证明rasterfresh，servedBytesHashVerified=false。

[可读300对象准备](evidence/m4-readable-grid-next-work/README.md)用一条 typed output move 将冻结 workload bounds 从4588×30542缩到4588×1952；658/658是有限 document/中心线路径关系。300叶身份/事实与canonical保持，默认672×711名义字号仍仅1.632 CSSpx；大视口9.362/10.495px只是投影计算，未认证实际字体/可读性/完整连续输入性能。rAF 不是实际呈现 FPS，固定硬件/字体 A/B×3、≤50ms连续输入、medium p95<500ms、pins/anchor及presented≥50FPS仍开放。

memory默认名与原路由保持上一阶段范围；dy14→15 display端口仍令路线49→644.3世界单位，全域交叉/弯折美观未通过。[两份实际UI导出](evidence/m4-viewport-resize-current/actual-export-readback/independent-attempt-2/report.json)407/407关系核对whole180mm PDF/SVG与saved39/storage6 full document2/2 exact，相对31只Canvas revision变化；180×208.285714mm最低名义文字6.56018pt。初401/402的PDF normalized-height oracle失败保留；未新增85mm/detail工件、解析字体/嵌入或真人出版认证。 左库仍17基础模块＋3透明网络起点，未逐种生成/执行认证；历史三个AI角色范围保持，审计者不增参与者，AI 不计真人。

M4 `partial`、M5 `not_started`、真人 0。[新研究准备](evidence/m4-viewport-resize-current/research-readiness-independent/report.json)308/308仅readiness：86 implementation/4 baseline、五个pristine席位43621–43625；旧24包410文件exact，上一caption包正式verify已exit1 stale。未开席位服务/查端口可用性/分配/collect；3–5真人五步任务≤180秒/≥80%与出版人审尚未完成。旧gold、失败、研究包与第二个`##`起历史正文原字节保留。正式工程从头实现、独立于Temp runtime/fallback、无新认证复用，未执行生成模型。下方旧“当前/最终”只按各自冻结版本读取。

## 历史版本记录

当前（2026-10-06）为 `index-BV-fWDiR.js` / `index-QPVAzYp6.css`。[模块库可发现性与预制起点](m4-module-library.md)增加“基础模块 17 / 网络起点 3”入口；默认直达 Input、Output、Linear 与激活模块，搜索词会跨两类结果。最终专项48/48、Studio284/284、strict TypeScript/Vite退出0；本轮未执行模型或安装依赖。

实际浏览器复核保留待连接状态、草稿4节点3连线、跨类搜索、未支持 Attention 说明、Identity/MLP/Input 添加后撤销，以及保存重开。入口切换只改列表视图，不改草稿、历史、选择、相机或连接。15组新BV状态/JPEG绑定在 [模块库浏览证据](evidence/m4-module-library-work/browser-attempt-1/manifest.json)；此前CW22组静态检查/四向移动/参数引导保留原范围。

M4仍partial、M5未开始、真人0。AI审查不计真人；复杂图路由、逐模块生成、出版尺寸、呈现性能与真人任务仍未认证。[当前schema16状态](evidence/m4-human-review-handoff-status-followup.json)单独绑定本轮；schema15与CW/BSA旧证据保留各自归档，不继承为BV浏览器认证。

历史版本说明：当前（2026-10-06）构建仍为 `index-au3IB_0Q.js` / `index-B6WbMowt.css`。本轮[au3 浏览器矩阵与四向操作](m4-au3-current-matrix.md)已 collect 36 基线＋3 编辑后视图、234 工件；三个模型共12方向的实际拖动、撤销重做、保存重开有独立核对。36张fit及19张局部/编辑图分别AI审查，旧MLP右移失配保留，新起点补采单列。CNN外绕残差、窄缝拥挤、MLP边界折角和Transformer小移大改线仍是具体问题；文件完整不认证美观或出版。当前full observer保留6尝试/5完成、14eligible/10matched/4interactions、matched子集p95 3000ms；约1秒rAF间隔不是呈现帧认证。产品源码/build未改，沿用源码精确绑定的179/179、strict/build exit0；此前发行9/9是其209源码/654依赖/5symlink冻结副本范围，后续Skill文档改动不称同一完整发行字节。已有au3 4节点3边搭建链保存重开、静态生成及新工作副本保存保持独立证据；17模块＋3起点不等于逐模块完整验收。M4 partial、M5未开始，当前研究包未prepare/verify、0分配/收集/真人；AI不能替代真人。[文档更新前归档](evidence/before-m4-au3-full-matrix/manifest.json)保存此前4233绑定、24末读supplemental及两个原receipt；下方旧“当前/本轮/最终”只指各自版本和冻结时点。

历史ChS（2026-10-05）为 `index-ChS0wIgb.js`（SHA256 `05019f89f0de0c0c622df7a2cc1a13ed58477c456244c97209a0f37db79139c9`）与 `index-CsXMONBp.css`。[ChS浏览器矩阵](m4-chs-current-matrix.md)已通过正式collect：36基础＋三模型各一编辑后，共39例/234工件，artifactCoverage=complete；人工审看仍pending、真人0。17基础模块＋3透明网络起点及位置修复继续使用同一产品，既有Studio152/152、strict/build0、独立发行9项保持版本范围，本轮未重跑产品套件。新五席研究包72实施绑定、4baseline、8991–8995仅登记，0分配/收集/真人。不同tensor交叉/重叠、repeat背景叠片、说明空白和密集图字号仍是问题；presented性能/活动取消/物理出版未认证，M4 partial、未进入M5。此前799绑定加原seal共800文件已在[文档更新前归档](evidence/before-m4-chs-browser-matrix/manifest.json)逐字保留；以下历史记录只按各自版本/时点读取。

[切换前2894绑定原字节](evidence/before-m4-move-recovery-presets/manifest.json)保留旧Bc seal/status/矩阵/诊断/源码；下方历史记录中的“当前/本轮/最终”仅指其明确旧构建和冻结时点，不计新build浏览器、性能或真人认证。旧raw、seal、manifest和研究包不回写。

本轮文档更新前的478个封印绑定和旧seal原字节已[逐字节归档](evidence/before-m4-bcf-browser-matrix/manifest.json)；下方历史记录按其明确构建/时点阅读，旧失败和seal不回写。

本构建切换前的 **1277** 个封印绑定及旧seal原字节见[归档](evidence/before-m4-authoring-feedback/manifest.json)；更早327/904绑定继续通过此前归档解析。下方旧记录中的“当前/最终”仅指其绑定版本，旧浏览器矩阵、研究包和UI中间构建不继承为最终Bc证据。

[边界修正前原字节](evidence/before-m4-boundary-corrections/manifest.json)保留165文件、旧verification原件与3188历史绑定解析；旧seal/manifest/raw和研究包不改。下方历史记录中的“当前/本轮”只指其明确绑定的旧版本和冻结时点，不计新构建覆盖或真人门。

当前能力表以2026-10-06正式au3目录代码及各自版本绑定的命令/工件为准。`通过` 表示有独立实现和可复核检查；`未认证` 表示不能作为支持承诺。后续历史表不继承为当前浏览器或人工覆盖。

| 能力面 | 当前状态 | 真实边界与证据 |
|---|---|---|
| 线间重叠/交叉收敛 | 精确memory家族有界改进；非零冲突保留 | 祖先侧候选在原caps内保留4/2额度；L3不同tensor overlap19→17、strict20/23不升、disjoint overlap13不升，具体交叉对可交换。same-tensor逐pair保护只作用新增family阶段，generic保留旧评分；12独立视图无退化。见[当前报告](m4-ancestor-corridors.md)。 |
| 从零可视化模型搭建 | 静态有界；不同build UI范围单列 | 17基础模块＋3透明起点，typed DAG/参数/shape/dtype、history/CAS与新Python静态round-trip。旧BG AI试用17逐click、Input/CNN原生drag、四节点空白连线/排版、残差MLP生成不继承为au3或真人；当前au3 role/native文字端口命中、4/3草稿保存重开、静态source review、新工作副本打开与论文图保存独审通过；仅该链，不执行模型。 |
| 运行入口与来源 | 通过 | `archcanvas_cli` / `archcanvas_python` 从正式目录 `src` 解析；`check_independence.py --build` 的 `/tmp` 报告检查 module origin、capability receipt 和发行源字节 |
| 静态源码分析 | Alpha 通过 | stdlib AST 子集；显式本地模块、字面量构造、模块层级、producer/consumer、具名 MHA 端口、固定tuple/list/dict输出路径、获证张量依赖旁路、bounded repeat/shared identity |
| Transformer gold | 通过 | 独立人工 oracle；多输入、self/cross attention、mask、7 个残差、2 个独立 Encoder layer、无源码 Softmax |
| MLP / Residual CNN / Vision holdout gold | 通过（有界） | MLP/CNN完整手写源码oracle独立11/11（含9项腐坏反例），家族holdout6项加output/bypass22项独立28/28；未知 Conv1d 保留 opaque。没有把 fixture 快照当作任意模型泛化保证，详见 [M4 验收](m4-completion.md) |
| 未知与动态结构 | 有界 | 动态控制、反射、未知 constructor、继承 forward、预算截断保留 opaque/diagnostic；不伪造 proven 关系 |
| Runtime execution / concrete shape | Linux CPU 本地通过 | 静态分析仍不执行模型；独立显式 `runtime` / `verify_structural` 使用冻结具名 shape/dtype/fill/seed/modes 和源码默认构造。真实 MHA Lq≠Lk、Q/K/V/mask 绑定、forward/backward、同种子结构/输出/梯度/state replay 已验收，均限于声明样本 |
| 执行隔离与环境绑定 | Linux x86-64 本地通过 | Mandatory Bubblewrap namespaces＋kernel seccomp，源 generation 只读，私有 scratch；Python exe/标准库/ELF closure 为私有只读字节副本，不暴露整 Conda/宿主目录；全部 venv 字节、依赖锁、解释器/adapter 摘要与执行后 freshness。真实越界文件/源码写、宿主 listener、子进程、CPU/timeout/cancel 和大内存分配反例通过；缺能力禁用 profile，无普通 subprocess fallback。内存为 per-process RLIMIT_AS，未配置 cgroup 聚合 RSS/tmpfs 总配额 |
| 模型状态观察 | 样本本地通过 | state_dict keys/shape/dtype、parameter/buffer、对象/存储共享组、train/eval 状态变化有独立手写测试；不加载或迁移 checkpoint，optimizer/scheduler/progress/random training state 分别列为未提供/未迁移 |
| CanvasDocument | 通过 | source/IR digest、canonical identity、display alias、节点/边样式、图例、注释、页规格、layout、pin、expanded frontier |
| 对象来源与共享/输出事实 | 有界通过 | inspector展示同instance不同call、repeat independent/shared instances、完整outputPath、opaque和source location；SVG metadata分开保存whole-source-architecture事实与实际rendered对象/bindings。sourceFacts独立5/5及Temporal/Skip/GNN真实存储重开→publication SVG链通过；source/IR与Canvas schema不变，Scene/SVG字节变，旧renderer收据不冒充当前 |
| Visual history | 通过 | 手势和当前局部确定性视觉指令共用 VisualOperation、undo/redo 和 document revision；没有通用 LLM 语言解析 |
| 层级展开 | Alpha有界；179/179与当前矩阵 | 九真实authored frontiers×四规格已采36基线；不造MLP/CNN深层级。canonical对象/端口/sourceIR与实际SVG保持，真实尺寸人审未认证。 |
| 连线避障/布局提示与位置修复 | nominal union避障与显式局部方案 | 折叠Repeat三rect同owner、端口沿外法向投影；body/header/containment冲突真实报告。现有最多64候选preview/apply/cancel/history/pin拒绝继续有界；不隐式clamp或认证全局布局。见[Repeat报告](m4-repeat-outline.md)、[位置修复历史范围](m4-move-recovery-presets.md)。 |
| 复合预制模型与扩展模块库 | 17基础＋3透明起点 | MLP/CNN/残差MLP是可编辑普通草稿图，不新增模块种类。旧BG有三起点逐click/Input与CNNdrag/残差静态生成试用，各自范围明示；17模块参数/生成逐项和全部原生拖入未验。Attention/LSTM/训练未支持。 |
| 拖动预览路径 | 实现与CPU反例通过，体验未认证 | 开场校验/冻结gesture snapshot，每帧共用Scene/SVG；松开经guarded history，版本切换使旧gesture失效。旧路由300层CPU专项14.32→5.75ms仅属历史；当前避障候选有额外CPU成本，完整Scene/SVG/commit/undo/redo回归通过，不替代native输入/DOM/FPS，见[本轮边界](m4-ai-usability-audit.md) |
| 画布缩放与实际手势 | 三模型小幅叶对象四向/history通过 | 12方向实际native drag、undo/redo及保存重开；非所有对象/位移/pins覆盖。held-pointer cancel/presented FPS/font/hardware仍开放。 |
| 保存与冲突 | CAS有界；当前三模型移动保存重开独审 | storage/visual revision分离；三模型SVG/几何和envelope一致，reopen清history/fit相机。au3 authored4/3链另证；imported alias刷新未复验。 |
| SVG | 当前36基线＋3编辑后工件通过 | 39case×6文件与actual UUID/源IR/Canvas/Scene精确绑定；首例export-only、6height末位容差披露。PDF/PNG/物理阅读守各自范围，artifactCoverage不认证美观。 |
| PNG / PDF | PDF当前单L3字节/尺寸独审；PNG为M2历史范围 | 当前单L3实际PDF单页180×605.611052mm及绑定字节精确，glyph/pixel未认证。M2历史PNG/PDF由正式 `.venv` CairoSVG 2.8.2 从同scene SVG派生；85/180 mm PDF MediaBox、PNG 像素与 300 DPI/pHYs 通过；receipt 绑定 scene hash、实际依赖来源和 Cairo glyph coverage。共享 Scene font 首选 Noto Sans CJK SC，字体仍依赖宿主；跨机器排字/嵌入未认证 |
| 参数审核与提交 | M2/M3 本地通过 | 显式 float literal Dropout.p/MHA.dropout，或唯一 module-top-level float 且全部读者为已注册概率参数；单 token 保格式改动，完整影响列表、独立 Expected/Observed、具体 review/HMAC approval、全 corpus/staged freshness、single-file journal/recovery。HTTP 只改受管理副本，CLI 写显式绑定 root |
| 局部连接事务 | M3 本地通过 | 保留同-base pure unary 条件式静态 API，G6 为 not_run；新 `structural-verified` 支持 entry-root 直线 unary/MHA 的 positional/keyword Name、具名 q/key/value/mask、明确 input specs、冻结独立整图 oracle、实际 producer/shape/dtype/梯度/状态核对，运行必需门失败不进入 ReviewReady。CLI/HTTP/Python prepare→review→approve→commit 共用守卫；异步 HTTP 可取消，不改原导入目录 |
| 激活替换 | M3 本地通过 | 无参 ReLU↔GELU constructor、完整影响作用域与独立结构 oracle；Studio/CLI 必须显式 CPU profile，保留实际 forward/backward/replay/state receipt；in-place/functional/带参/未知影响拒绝 |
| 动态连接 / 派生配置 / 多文件事务 | 未实现 | in-place、unknown call/state、控制流、nested/shared authored scope、alias/reassignment、未证明端口/type/shape 路径拒绝；派生/歧义配置和整数源概率 literal 拒绝；不承诺多文件原子提交、全程序执行或数学等价 |
| MCP adapter | 未实现 | Skill 文档描述合同，不存在可调用 MCP 工具 |
| Codex / Claude Code / DeepSeek Harness | 未认证 | Skill 指令包与引用已整理；三宿主 discovery/open/edit/save/export E2E 尚未实测 |
| Publication quality / performance | M4 partial；0真人 | 当前39工件已collect，AI局部/fit审查发现路径及拥挤问题。新full observer仅工程诊断，物理印样/presented/fonts/hardware/activecancel未认证；研究包未准备。 |
## 历史ChS能力表原行

以下行记录修复前的构建与待冻结状态，不作为au3当前覆盖。原字节亦保存在修复前归档。

| 能力面 | 当时状态 | 当时范围 |
|---|---|---|
| 线间重叠/交叉收敛 | 有预算的有界改进；历史指标单列 | 主画布/详情/草稿共享批路由；旧73场景与L3重叠25→19/交叉20对保留冻结范围，当前Scene变更不直接继承13core证据，无全局最优或美观认证。见[m4-routing-refinement](m4-routing-refinement.md)。 |
| 从零可视化模型搭建 | 有界通过 | 17种基础模块＋3透明网络起点，独立草稿与typed tensor DAG、参数/shape/dtype校验、草稿history/CAS，生成全新Python并静态核对；实际三起点草稿/source共19节点17连接单列。最终build浏览器范围待冻结，无模型执行或导入结构任意写回认证。见[本轮说明](m4-move-recovery-presets.md)。 |
| 层级展开 | Alpha有界；最终Studio152/152通过 | canonical children、alias/repeat/pin/ARIA与history保留；旧Bc9前沿/36＋3矩阵属于历史范围，新build完整矩阵尚未认证，真人与深层阅读尺寸未认证。 |
| 连线避障/布局提示与位置修复 | 显式局部方案，有界通过 | 新增父容器越界提示；手工位置不隐式clamp。最多64候选的preview/apply/cancel保护无关对象与既有冲突程度，应用一次move history，pins/内部冲突/无方案时拒绝；不认证全部交叉或美观。见[本轮说明](m4-move-recovery-presets.md)。 |
| 复合预制模型与扩展模块库 | 3网络起点静态有界通过 | 最小MLP、小型CNN、残差MLP仍是普通可编辑节点；17基础模块数不增加，一次插入一次history，真实三草稿AST单列。Attention/LSTM/训练仍未支持，最终CNN两行坐标浏览器补采待冻结。旧[缺口清单](evidence/m4-ai-usability-next/novice/module-palette-backlog.md)保留补齐前状态。 |
| 画布缩放与实际手势 | 当前代表补采待冻结；完整原生门未认证 | 本轮中间build源MLP四向冲突与显式修复、草稿起点操作单列；最终ChS0wIgb浏览器范围待冻结。Bc/CIVB/C7手势只属历史；active cancel/presented性能未认证。 |
| SVG | 同一scene；代表链与完整矩阵分开 | 本轮源MLP修复后保存/重开完整SVG20691字符相同，实际SVG/PDF副本单列；该中间build链不证明新36＋3矩阵。最终build补采待冻结；旧Bc39几何/保存重开链只属历史。 |
| Publication quality / performance | M4partial；新完整矩阵、人审/性能未认证 | 当前Scene字节已变，旧13core不变/旧Bc39截图与四原生诊断不能继承；只保留历史范围。新build矩阵未认证，旧70绑定研究包stale、fresh准备pending、0真人；深图与真实尺寸、持续presented/font/hardware、active cancel、3–5真人任务待完成。 |

## 历史 DPwoy 与更早代表记录

同一DPwoy构建新增[8888原生输入诊断](evidence/m4-current-native-diagnostic/README.md)：stress300五项与MLP三项目标补采通过、MLP pilot仅pan覆盖成功；错误命中与三项请求缺口保留。两个全SVG撤销/重做及保存重开链精确，三个独立matched子集p95为2016/2008/2016ms。无pins；持续presented FPS、活动取消、font/hardware和真人门仍未认证，服务已exit143原因未知。原39工件矩阵、人审状态和研究包仍原样，旧文档hash按[新归档](evidence/before-current-native-diagnostic/README.md)解析。

较早8886[代表审计](evidence/m4-publication-refinement-work/independent-final-audit.md)受限通过11Canvas/实看截图、9preview、5选项、3直接链接工件、2SVG转换字节和1PDF单页尺寸，无最终截图状态滞后。Python10仍为较早Qpo范围、runtime/core未变；未重跑最终JS轮次。storage envelope未捕获，renderer改变拒绝是2纯函数反例，服务历史是事后根工具摘要。审计不升级上表人工/出版/性能门。

历史DPwoy[manifest](evidence/browser-visual-matrix-publication-final/manifest.json) SHA256 `55df9000f42857bca9dc8ce2f75fe097b99ea90fae94ad077810225e05162593`，[矩阵末审](evidence/m4-publication-matrix-work/independent-final-audit.md)受限passed-with-explicit-observations；4处DOMheightMm JSON窄浮点差保留，XML精确。352raw不变，313stamped不变＋39receipt两hash，234sealedexact。36baseline10minText≥7pt/0组合示例不是期刊门；viewport8887、UA/DPR旧同IAB8880，hardware/font未知。[取消审计](evidence/m4-publication-matrix-work/gesture-cancellation-audit.md)只读、不计nativecancel；[旧文档解析归档](evidence/before-publication-final-matrix/README.md)支持旧manifest current路径恢复原bytes。后续root诊断/服务恢复不属矩阵finalaudit。

静态分析通过只说明支持子集的源码事实可恢复；样本运行通过只说明声明的 CPU 输入、模式和样本观测。两者均不把 opaque 区域变成可编辑源码。执行安装与命令见 [README](../README.md)，逐项阶段状态见 [完整 M3 出口](m3-completion.md)、[source oracle](source-oracle.md) 和 [acceptance ledger](acceptance.md)。
