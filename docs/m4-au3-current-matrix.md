# M4：au3 浏览器矩阵与四向操作

2026-10-06，正式构建仍为 `index-au3IB_0Q.js` / `index-B6WbMowt.css`。本轮没有修改产品源码、重新构建、安装依赖或执行模型。M4 为 partial，M5 未开始。三个子 Agent 分别做绑定收集、独立合同核对和像素审查；实际浏览器输入由主任务执行。AI 不计作真人研究者。

## 当前覆盖

[正式矩阵](evidence/browser-visual-matrix-au3-current/index.html)已完成 collect：Transformer L0–L3、MLP L0–L1、Residual CNN L0–L2，共九个真实 authored frontier，分别采彩色/黑白及 85/180 mm，形成 36 基线；另外每模型一份保留非零移动的编辑后导出，共 39 case、234 工件。不是 36 个不同 frontier，也不是所有规格都执行过编辑。

[收集回执](evidence/m4-au3-visual-matrix-work/collection-attempt-1/attempt-receipt.json)及 [独立末读](evidence/m4-au3-visual-matrix-work/independent-audit/final-readback-attempt-2/receipt.json)核对 actual export UUID、源/IR、可见成员、Canvas 与 SVG、构建资产及文件字节。39 份未 stamp 的 screen receipts 保留原字节，正式 stamp 只加入两项 hash；336 份 collector 输入冻结。`artifactCoverage=complete` 仅表示文件合同覆盖完整，`visualAcceptance=pending-human-review`、`humanAcceptanceCertified=false`。

仅首例 Transformer L0 paper180 未及时冻结保存 envelope：它使用 actual export document 明示 export-only，storageRevision 为 null，不计保存快照认证。后续 38 例都有保存 envelope 与实际导出精确比较。六例只有 derived `heightMm` 的跨语言浮点末位差；SVG 原字节和其余 metadata 严格相同，有限差值与 `1e-10` 容差逐例披露，不声称 metadata 逐字相等。

矩阵的 1280×720 viewport、camera、资产与 SVG 来自本次公开 DOM。screen receipt 的 UA/DPR 明示沿用同 IAB 的历史观测；本轮后续 input harness 实际取得相同 UA/DPR，仍不倒填矩阵为同刻采集，不认证 GPU、刷新率或实际解析字体。

## 交互与像素结果

三模型分别选择 CNN classifier、MLP Linear 4、Transformer output projection，以原生 atomic drag 执行上下左右各 24 CSS px，共 12 个方向。按每次起始 zoom 换算并吸附 4 单位网格，CNN/MLP 为 ±32、Transformer 为 ±28 世界单位。每方向检查撤销和重做，前三方向恢复起点，最后方向保留位移；保存后真实 reload，重开历史为空、camera 重新 fit，文档/SVG 几何保持。独立报告位于 [gestures](evidence/m4-au3-visual-matrix-work/independent-audit/gestures)。这些小幅叶对象操作不代表所有对象、任意位移、祖先拖动或已有非空 pins 的覆盖，也不能测试按住期间 Escape 取消。

[36 张 fit 图审查](evidence/m4-au3-visual-matrix-work/pixel-audit/all-36-fit.receipt.json)亲看全部基线，未见宏观纸页裁切或卡体互压。深层 fit 仅 14–26%，不充分认证文字、端点、弯折与出版尺寸。[局部及编辑后审查](evidence/m4-au3-visual-matrix-work/pixel-audit/gestures/three-model-local-and-edited.receipt.json)亲看 19 张原图，其中 18 张状态匹配。旧 MLP 右移截图显示 rev22/X138，而终点 DOM 为 rev23/X142，原图保留且不计当前像素通过；新 prefix 在已保存 Y648 起点重新右移，rev36/X142 的截图和公开场景匹配，属于独立补采。

具体问题仍保留：

- CNN L0 residual edge9 同横坐标端点之间有扁 U 外绕，超模型右框。独立 [原因分析](evidence/m4-au3-visual-matrix-work/independent-audit/cnn-collapsed-residual-analysis.json)定位到所有 special 路线默认侧路及无障碍 preferred 保留策略。候选修复应保留 residual 的 edge、port、role 与 canonical branch，只在折叠目标且完整障碍检查通过时优先短直路；不能仅因 sameTensor 与 data 合并。
- MLP L1 输入/输出与内部链中心略错开，出现短阶梯折角，是对齐优化候选。
- CNN 左移越父框；上下移留下约 6 世界单位窄缝，选中边框、端口和箭头拥挤。自由拖动保留位置并提示冲突，不自动保证美观。
- Transformer output projection 左移 28 世界单位，edge69 横向折点下跳 566 世界单位，属于路线稳定性候选。上游节点不在局部截图内，不能据该截图断言整条连线可删弯折。

## 当前输入诊断

新独立回环服务以未改正式 Studio 资产运行 full observer v2。实际操作包括展开 4→304 rendered frontier、平移、指定 Linear 1 拖动、撤销和重做；另外一次误填目标 ID 的 no-input 保留，合计六次尝试、五次完成。304 rendered 对象不表示 300 张卡同时处于 viewport。

[原始收据](evidence/m4-au3-visual-matrix-work/input-diagnostic/full-observer-raw-chunked.json)由公开 readonly textarea 分块精确取得。[独立 validator](evidence/m4-au3-visual-matrix-work/input-diagnostic/validation-attempt-1/command-receipt.json) exit0，[另一次只读审查](evidence/m4-au3-visual-matrix-work/independent-audit/input-diagnostic-attempt1/final-readback.json)独立重算统计与关键终点，未重跑 validator。完整缓冲、无 dropped/errors；14 eligible 离散输入中 10 matched，对应四个 interaction，matched-subset p95 为 3000 ms。全会话 rAF cadence 约 1.884 fps、idle 约 2.025 fps，拖动/平移回调间隔约一秒。连续 input→DOM 仍是非因果 paint 代理，不从快速 toggle 的少量帧挑选结果代表总体。实际呈现、总体 INP、固定环境与性能通过均未认证。

计划书 §18.5 的 p95≤50 ms/FPS≥50 是初始 Beta 目标；M4 仍要求真实浏览器性能与固定环境证据，不把这两个数值额外改写成 M4 新硬门。此次数据不证明达到该体验目标；`fonts.status=loaded`、`loadedFaces=[]` 也不建立解析字体认证。

## 保留的失败与下一步

误命名 JPEG、未冻结首例 envelope、REPL 旧闭包误写 JPG、locator 多匹配、首次 reload 尚未加载场景、wrong-target no-input、整份 textarea 传输截断及 reviewer helper 错误均保留。截图纠正只复制真实字节；误写 JPG 被排除；截断原件不冒称完整 raw。正式旧 seal 与末读 supplemental 在当前文档更新前完整归档。

已有 au3 的 Input→Linear→ReLU→Output 4 节点/3 边草稿链、保存重开、静态生成及新工作副本保存保持此前独立证据。17 基础模块与 3 透明组合起点仍是当前搭建范围；逐模块参数/生成、Attention/序列模块与自动训练不由这次 Imported Canvas 矩阵认证。

下一步优先实现与独立验证折叠 residual 短路候选，并检查小幅移动的路线稳定性及边界对齐。真实 85/180 mm 审看、完整路由美观、活动手势取消、固定环境呈现性能、当前研究包及 3–5 位真实使用者任务仍开放。真人分配/记录为 0，不以 Agent 替代，也不重复索要参与者安排。
