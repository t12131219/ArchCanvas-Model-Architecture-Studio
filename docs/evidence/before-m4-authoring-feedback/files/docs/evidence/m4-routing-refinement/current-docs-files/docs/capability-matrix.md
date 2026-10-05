# 首批真实能力矩阵

当前（2026-10-05）构建为 `index-CVO3JbfE.js`（SHA256 `0516dc07309a95196c403fd822b3daf474ced88ec9c0ab7a8c0de85cfd0e26e9`）。[共享连线路由收敛与代理探索](m4-routing-refinement.md)已接入主画布、详情导出和模型搭建；独立几何 73/73、公共测试 13/13、15 个污染反例拒绝，Studio **126/126**、相关 Python **40/40**、strict/build 与独立发行核验通过。此前 Python 完整 300/300 保留历史范围，本轮未完整重跑。Transformer L3 重叠对 25→19，交叉仍 20 对/23 点，路长增加 48；实际浏览器与服务 SVG 的 49 节点/59 连线/106 端口核对通过。当前矩阵已准备但采集仍 0/36＋0/3，五个真人席位已准备但真人 0；代理测试不计真人。出版人审、持续呈现性能和原生活动取消尚未认证，M4 保持 partial，未进入 M5。

本构建切换前的搭建 327 个封印绑定原字节见[归档](evidence/before-m4-routing-refinement/manifest.json)。更早 904 个绑定继续通过此前归档解析。下方旧记录中的“当前/最终”仅指其绑定版本，旧浏览器矩阵与研究包不继承为本构建证据。

[边界修正前原字节](evidence/before-m4-boundary-corrections/manifest.json)保留165文件、旧verification原件与3188历史绑定解析；旧seal/manifest/raw和研究包不改。下方历史记录中的“当前/本轮”只指其明确绑定的旧版本和冻结时点，不计新构建覆盖或真人门。

状态以2026-10-05正式目录代码及各自版本绑定的命令/工件为准。`通过` 表示有独立实现和可复核检查；`未认证` 表示不能作为支持承诺。

| 能力面 | 当前状态 | 真实边界与证据 |
|---|---|---|
| 线间重叠/交叉收敛 | 有预算的有界改进 | 主画布/详情/草稿共享批路由，保护端点/事实/布局；73场景无受保护指标增加，L3重叠25→19，交叉20对仍保留，无全局最优或美观认证。见[m4-routing-refinement](m4-routing-refinement.md)。 |
| 从零可视化模型搭建 | 有界通过 | 17种模块库，独立草稿与typed tensor DAG、参数/shape/dtype校验、草稿history/CAS，生成全新Python并静态精确核对；创建独立工作副本，无导入模型结构写回或运行认证。见[m4-authoring](m4-authoring.md)。 |
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
| 层级展开 | Alpha有界；当前Studio126/126通过 | canonical children、alias/repeat/pin/ARIA与history保留；Transformer L3/CNN L2代表实查属于历史 C7，当前完整新矩阵未collect，旧Cr39/234亦不继承。 |
| 连线避障/布局提示 | 有预算的几何修复 | 整图/详情共用正交路由；无关body、端点body和祖先标题避障。重叠/预算失败保留手工位置并提示；未优化所有线间交叉或弯折。 |
| 复合预制模型与扩展模块库 | 未实现 | 当前搭建库提供17种单模块，已有模型左树继续用于源层级查看；Attention/LSTM与复合网络预制尚未实现。旧[缺口清单](evidence/m4-ai-usability-next/novice/module-palette-backlog.md)记录补齐前的 C7 状态。 |
| 拖动预览路径 | 实现与CPU反例通过，体验未认证 | 开场校验/冻结gesture snapshot，每帧共用Scene/SVG；松开经guarded history，版本切换使旧gesture失效。旧路由300层CPU专项14.32→5.75ms仅属历史；当前避障候选有额外CPU成本，完整Scene/SVG/commit/undo/redo回归通过，不替代native输入/DOM/FPS，见[本轮边界](m4-ai-usability-audit.md) |
| 画布缩放与实际手势 | 当前搭建代表四方向通过；完整原生门未认证 | 同Linear±16、左向单独undo/redo、其他方向最终整体恢复；相机四向±40及恢复，图形不变。25份当前DOM独立审查，第一次左向中断排除，第二轮通过。旧源模型±32证据只属C7；活动cancel、presented性能未认证。 |
| 保存与冲突 | 通过 | loopback server JSON CAS；storage revision 与 document revision 分离；immutable architecture/source binding；root 允许 loopback 环境 HTTP tests 通过，浏览器 alias 保存与刷新重开已实测 |
| SVG | 同一scene，当前搭建代表实际导出；完整新版矩阵待采 | 当前16→48新模型的论文SVG实际生成，保存重开交互SVG逐字节一致；浏览器与导出SVG几何/绑定/meta一致但字节不同。未交付用户目录下载或认证出版人审。MLP rev21属于历史C7。 |
| PNG / PDF | M2 本地通过 | 正式 `.venv` CairoSVG 2.8.2 仅从当前 SVG 派生；85/180 mm PDF MediaBox、PNG 像素与 300 DPI/pHYs 通过；receipt 绑定 scene hash、实际依赖来源和 Cairo glyph coverage。共享 Scene font 首选 Noto Sans CJK SC，字体仍依赖宿主；跨机器排字/嵌入未认证 |
| 参数审核与提交 | M2/M3 本地通过 | 显式 float literal Dropout.p/MHA.dropout，或唯一 module-top-level float 且全部读者为已注册概率参数；单 token 保格式改动，完整影响列表、独立 Expected/Observed、具体 review/HMAC approval、全 corpus/staged freshness、single-file journal/recovery。HTTP 只改受管理副本，CLI 写显式绑定 root |
| 局部连接事务 | M3 本地通过 | 保留同-base pure unary 条件式静态 API，G6 为 not_run；新 `structural-verified` 支持 entry-root 直线 unary/MHA 的 positional/keyword Name、具名 q/key/value/mask、明确 input specs、冻结独立整图 oracle、实际 producer/shape/dtype/梯度/状态核对，运行必需门失败不进入 ReviewReady。CLI/HTTP/Python prepare→review→approve→commit 共用守卫；异步 HTTP 可取消，不改原导入目录 |
| 激活替换 | M3 本地通过 | 无参 ReLU↔GELU constructor、完整影响作用域与独立结构 oracle；Studio/CLI 必须显式 CPU profile，保留实际 forward/backward/replay/state receipt；in-place/functional/带参/未知影响拒绝 |
| 动态连接 / 派生配置 / 多文件事务 | 未实现 | in-place、unknown call/state、控制流、nested/shared authored scope、alias/reassignment、未证明端口/type/shape 路径拒绝；派生/歧义配置和整数源概率 literal 拒绝；不承诺多文件原子提交、全程序执行或数学等价 |
| MCP adapter | 未实现 | Skill 文档描述合同，不存在可调用 MCP 工具 |
| Codex / Claude Code / DeepSeek Harness | 未认证 | Skill 指令包与引用已整理；三宿主 discovery/open/edit/save/export E2E 尚未实测 |
| Publication quality / performance | M4partial；当前完整矩阵待采 | 当前CVO不继承旧Cr39/C7矩阵或性能；新矩阵和69实施绑定/4基线五席包已prepare/verify、0真人。代表L3实际SVG尺寸180×598.61mm、minText5.36pt；持续presented/font/hardware、active cancel、出版人审和3–5真实任务待完成。 |

## 历史 DPwoy 与更早代表记录

同一DPwoy构建新增[8888原生输入诊断](evidence/m4-current-native-diagnostic/README.md)：stress300五项与MLP三项目标补采通过、MLP pilot仅pan覆盖成功；错误命中与三项请求缺口保留。两个全SVG撤销/重做及保存重开链精确，三个独立matched子集p95为2016/2008/2016ms。无pins；持续presented FPS、活动取消、font/hardware和真人门仍未认证，服务已exit143原因未知。原39工件矩阵、人审状态和研究包仍原样，旧文档hash按[新归档](evidence/before-current-native-diagnostic/README.md)解析。

较早8886[代表审计](evidence/m4-publication-refinement-work/independent-final-audit.md)受限通过11Canvas/实看截图、9preview、5选项、3直接链接工件、2SVG转换字节和1PDF单页尺寸，无最终截图状态滞后。Python10仍为较早Qpo范围、runtime/core未变；未重跑最终JS轮次。storage envelope未捕获，renderer改变拒绝是2纯函数反例，服务历史是事后根工具摘要。审计不升级上表人工/出版/性能门。

历史DPwoy[manifest](evidence/browser-visual-matrix-publication-final/manifest.json) SHA256 `55df9000f42857bca9dc8ce2f75fe097b99ea90fae94ad077810225e05162593`，[矩阵末审](evidence/m4-publication-matrix-work/independent-final-audit.md)受限passed-with-explicit-observations；4处DOMheightMm JSON窄浮点差保留，XML精确。352raw不变，313stamped不变＋39receipt两hash，234sealedexact。36baseline10minText≥7pt/0组合示例不是期刊门；viewport8887、UA/DPR旧同IAB8880，hardware/font未知。[取消审计](evidence/m4-publication-matrix-work/gesture-cancellation-audit.md)只读、不计nativecancel；[旧文档解析归档](evidence/before-publication-final-matrix/README.md)支持旧manifest current路径恢复原bytes。后续root诊断/服务恢复不属矩阵finalaudit。

静态分析通过只说明支持子集的源码事实可恢复；样本运行通过只说明声明的 CPU 输入、模式和样本观测。两者均不把 opaque 区域变成可编辑源码。执行安装与命令见 [README](../README.md)，逐项阶段状态见 [完整 M3 出口](m3-completion.md)、[source oracle](source-oracle.md) 和 [acceptance ledger](acceptance.md)。
