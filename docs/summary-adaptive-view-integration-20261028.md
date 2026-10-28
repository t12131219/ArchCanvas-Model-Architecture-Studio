# Summary 原生画布的测量驱动局部细化

日期：2026-10-28。Summary 为候选、语义规则、图元和路由的唯一 authority；Studio 保留面板形式。本阶段将此前仅原样迁入、尚未调用的 `adaptive-frontier/5` 接到当前原生画布。

## 来源与替换范围

`semantic_studio/adaptive-frontier.js`、`expression-goals.js`、`summary-goals.js` 和其余 32 个原版模块继续逐字节保留。新增 `studio-adaptive.js` 改编 Summary `publication-renderer.js` 中 `prepareAdaptive` 的有限候选比较流程，但布局、文字、物理端口与路径来自现有 `SummaryNativeSemantic` 和原生 router。没有引入旧 publication renderer、第二份可见图或 React 侧自动规划。

候选仍只来自当前真实证书的角色引用和已有局部关系，保留完整角色键数组；不按模型名、案例 ID、源码哈希或特定角色名称分支。每次最多 36 次投影、3 个实际布线候选；结构策略可比较同一边界的整体与局部路径。计数上限不保证墙钟耗时上限，Worker 的原有取消和过期回复门禁继续生效。

## Studio 面板衔接

右侧原有“Summary 语义切面”折叠面板增加“局部自适应细化”开关、细节/结构策略和可折叠测量记录。仅角色粒度、自动语义切面可开启；F1 的显式认证配方及手动源码层级保留各自语义，用户切换到角色粒度后可开启自适应。

面板只发送 `semantic-view` patch，唯一 Worker 计算当前图。采用、拒绝、无候选均发布同一个 child snapshot，使用现有 undo/redo、相机、保存及层级树路径。测量记录显示每个机会、收益、资源及拒绝原因；没有新增可兑现关系时保留原切面，不能用“新增了节点”替代绑定检查。

手动展开/收起认证边界保留其他已选边界；手动角色路径编辑保留已选细节并关闭自动规划。新增明确的“收起所选边界的认证角色”和“收起路径”入口。F0/F1、全部展开和局部源码展开清理当前自动基线；返回切面仍恢复原请求。面板折叠继续属于 Studio UI session，不写入语义状态。

## 实际几何与证据

测量适配器从原生 glyph 的实际 `<text>` 读取已打印标题与说明；完整但未打印或截断的语义 captions 不能满足展示目标。Studio 的显示别名参与实际打印证据，受压缩的别名按有效水平字号保守评估。字号、文字边界、当前 canvas 尺寸、实际路径的交叉/内部接触/异值重叠和完整 native validator 共同进入评估。

每条可兑现的 canonical 输入绑定必须来自实际成功的原生物理路径：同时检查 binding 的生产者、结果槽、消费操作数、条件及证据。pending、failed、无效端口或被删路径不能获得收益。原版规则继续拒绝丢失已表达目标、摘要、角色、未知/控制边界、归属重复/丢失、额外约束冲突、退化字号与资源超限。增加细节允许的有限交叉成本仍由 Summary 规则计算；接触和异值重叠没有该例外。

Worker 中的文字宽度沿用原版 `SemanticPublication.width` 估算，真实浏览器的字体边界另以 SVG getBBox/CTM 检查；Worker 数值不等同于浏览器字体排版的全域证明。

这里测量的是选择时的原生图元与路径；用户之后的手动编辑不把旧测量记录升级为当前几何合格证。Studio 注释/图例与页面排版不是自动规划目标；不宣称全局最优、整体可读性理想或模型已经执行。

## 状态、保存与还原

`generic.state` 保存实际有效的角色/关系请求，并用私有 `nativeAdaptiveBase` 保留用户开启前的三组原请求。该字段不接受外部 `semantic-view` patch。关闭开关从基线恢复；切换策略从原请求重新比较，避免将上次自动细节误当永久手动输入。

编辑 JSON 保存完整 IR、实际有效切面、原请求和 nativeLayout。重开使用这些实际请求重新生成并独立校验语义/几何，保留手动布局，不重跑昂贵候选搜索；面板明确标记为“已恢复保存的请求”。外部回执不能认证 binding，也不能绕过 `G.read/restore/validate`。所有布局、草线、样式和正式源码/CAS/事务边界保持原合同。

## 自主验证与限制

新专项覆盖实际采用、关闭还原、确定性重开、独立回执反例、缺失输入路径、隐藏 captions、文字越界、路径冲突、零预算、未知/控制结构、手动收起与策略切换。真实浏览器专项通过面板开关、策略、撤销/重做、保存刷新和 JSON 往返，并监测是否产生源码、CPU 或事务写入。当前验证结果另记本阶段 `evidence/summary-adaptive-view-20261028/validation.json`；执行完成前不把待运行的检查写成通过。

诊断中 SameSource 的角色图由 11 图元/10 边变为 17/17；新增目标使用实际输入路径复核。UnknownFusion、BrokenCell、ConditionalResidual、LoopWithBoundary 保持已有边界。不同 renderer 的几何成本不同，不直接继承原型旧 SVG 的采用结果或性能结论。

本阶段不提高 480 节点/3600 依赖/16 MB 导入限制。3 个大图的完整传输/持久化/多切面历史/取消压力、新 CPU 隔离执行与正式 receipt 接入、D1 正式依赖拆分继续属于整体迁移；整体仍未完成。

自主浏览器验证发现两处测试假设不符现有合同：受控 checkbox 等待异步 Worker 提交后才变为 checked，故使用真实 click 后等待 snapshot 并断言最终 checked；原版 compact layout 明确省略可再生 sourcePort/targetPort 缓存，往返比较继续严格核对 route、physicalSource/Target、fixed ports、binding 和其余字段，仅排除这两个派生缓存。两次失败 JSON、日志和截图均保留，未改产品规则或放宽实际几何/绑定检查。

实际浏览器 JSON 往返进一步发现：完整编辑 wrapper 原会保留外部提供的旧 nativeAdaptive 回执。现于 openCase 的来源、渲染和 native validator 全部通过之后，丢弃传入回执并按实际有效请求与当前几何重建 restored 记录；不重新宣称已采用某个自动候选。新增反例覆盖伪造 gain/attempts 的 wrapper。此前完整前端运行因这项生产修复主动停止，最终结果只采用修复后的完整运行。

真实浏览器文字检查包含编辑器的展开按钮；其 text 的 getBBox 是按钮局部坐标，原断言忽略祖先 transform。原生 owner 外组保留世界坐标，最终使用 SVG/text 的 CTM 逆矩阵将四角统一换算到世界坐标，与节点 x/y/w/h 逐项检查包含。失败记录保留；未排除按钮文字或提高边界容差。


本阶段最终验证：完整前端 946 项（945 通过、0 失败、1 沙箱 Chromium 跳过）；最终专项 41 项（含新增自适应 12 项）和独立副本专项 94 项通过。真实 Chromium：自适应 8、手势 5、原生 16、证据 9、组装 12，共 50 项通过；实际 36 处文字按 CTM 换算世界坐标检查包含。主/独立构建、110 HTTP 资源、32 原版模块及 45 目录资产逐字节核验通过。独立副本核对当前生产字节、69 个 Python 文件、8 个实际模块来源及 5 个纯静态 fixture。详见[本阶段验证](evidence/summary-adaptive-view-20261028/validation.json)。新 CPU、大图完整压力和 D1 仍待继续，整体移植未完成。
