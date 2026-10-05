# M4 全范围剩余门审核

审核时间：2026-10-05T00:23:56.220637+00:00 至 2026-10-05T00:23:56.464463+00:00。结论：**M4 partial，有可继续推进的工程工作，真实出版审看与研究者任务仍未运行。** 本次只读正式计划、源码、原始收据和磁盘席位；未操作浏览器、运行模型、重跑大套件、安装依赖或改产品/旧证据。新增本报告与 [JSON](full-gate-audit.json)。

当前构建为 `index-oI5sT67U.js` / SHA256 `2c769087f0765ba47892e9f26f12a19e4336ec12573dce5859ac636e310f446c`。既有层级优化 seal 的 **1872/1872 绑定逐字节复核一致**。所有 1909 审核输入先冻结bytes、同份bytes hash/parse，再重新读取磁盘核无变化；JSON列出完整sourceBindings。历史执行没有重演，哈希一致不证明真人、截图像素或持续服务。

## 计划范围与门槛

§17.2的M4硬范围是MLP/Residual CNN、无模板holdout、shared/repeat准确部分、真浏览器体验和研究使用者任务。§18.1要求正式源码Studio、固定浏览器/硬件/字体/DPR/页规格/数据规模，实际截图/输入、六维人工视觉review，3–5名真实使用者及卡点/时间。§18.5明确是**Beta初始量化目标**：300可见对象input-to-paint p95≤50ms、交互≥50fps；中等展开p95<500ms；锚点≤8px、无关pins位移0；3–5人中≥80%在180秒内完成。不能把这些目标改成从未明订的新M4数值硬门，也不能以DOM变化、CPU时间或降低目标宣布体验收敛。每个新holdout的concrete shape/backward/numerical equivalence与三宿主发行不是静态M4的明文硬出口；相关支持主张仍须独立认证。

| 项目 | 当前证据 | 判定 |
|---|---|---|
| 基础模型与holdout准确部分 | 完整MLP/CNN手写关系oracle与9破坏反例；6家族静态入口＋输出/旁路反例；源码与oracle独立 | 已声明有界范围保留；本审计不重跑，不扩成任意模型 |
| shared/repeat/opaque | sourceFacts五反例及Temporal/Skip/GNN存储重开→publication链；当前tree保留事实 | 已声明有界范围保留；未知不升级proven |
| 正式工程独立性 | sealed Studio85/85、strict TS/build、9独立副本检查 | 当前快照保留，不与旧套件累加 |
| 真浏览器性能 | 当前8889 toggle/pan；6eligible/3matched/1interaction、子集p95=2016ms | 数值目标未达到；完整输入与持续呈现未认证 |
| 展开连续性 | 既有core/旧native与当前pan公共SVG连续；本次raw pins为空 | 当前全面native屏幕锚点/pin证据未齐 |
| 活动取消 | Esc/blur/capture路径和纯函数基础；当前活动窗无取消输入 | 代码存在，活动原生回滚/history未认证 |
| 出版 | 当前36spec＋3edited要求，root正在新采集；旧DPwoy39/234为历史 | 完整新矩阵需独立collect，人审与实际尺寸未认证 |
| 研究者任务 | 当前59实施＋4基线＋5envelope精确；五席pristine、0assignment/collected | 0真人；3–5人任务与独立review不能由agent替代 |

## IAB调度与可见性

从当前冻结raw独立重算native双向唯一匹配，与原validator的6/3/1及2016ms精确一致。3条pan输入缺失保持null；toggle的3离散事件属于同一个interaction，不能称3样本p95或整体INP。Pan真实down→up为8003.8000ms、8可信moves、16个rAF回调，event到capture约966–989.6ms；rAF间隔p95约983.4ms。它们是可信自动化的原始时序与回调，不能换算持续presented FPS、因果连续input-to-paint或人工耗时。文档观测visible，iframe focus true/false、top focus true；font loaded/loadedFaces=[]没有绑定浏览器实际解析字体。

本机插件[visibility指导](/home/fzg/.codex/plugins/cache/openai-bundled/browser/26.930.31428/docs/visibility.md)及[能力契约](/home/fzg/.codex/plugins/cache/openai-bundled/browser/26.930.31428/docs/capabilities/browser/visibility.md)明确`set(true)`请求视觉呈现，`get()`读取是否向用户呈现。此审核只读这些文档，**未在当前CUA重验证有效API或操作浏览器**，root仍需用选定IAB的现行文档执行。历史set(true)前后false的原件保留；第三simple control的前后两次true包围20秒40rAF窗口，但末读比窗口结束晚54.5637秒，不能证明连续呈现。当前root `visibility-attempt.json`为00:15:08.263Z false、立即set后false、00:15:33.615Z可见tab后true；只证明三个离散读数，不建立修复因果。

简单页面没有React/SVG/模型却也慢，因此环境/调度是应检查的假设。非随机窗口、不同viewport、有限observer成本和capability读数**不能排除完整Studio/telemetry/React/拖动全SVG替换成本**，也不能解释事件延迟的具体来源。不能用这份simple控制或tree属性读取归零证明产品≥50fps。当前raw仍无连续宿主presented-frame证据与已解析字体/硬件锁定。

## 活动取消与能做的下一步

当前App共同取消先清gesture/port ownership，再取消pending rAF、清preview/box/portDraft，pan回基准camera后release capture；window blur和Esc调用该路径，Esc受editingTarget/modal guard。没有visibilitychange取消监听，hidden-only仍是增强提议，不是已存在明文合同。observer/validator标记cancelled并拒绝将其当成功drag/pan，但不含rollback/history成功验证。当前raw的lostcapture在pointerup之后，不是活动取消。

下一次必须先核当前文档是否支持**保持down→移动→Esc/失焦→同pointer release**。若只有atomic drag，结束后按Esc不满足，不能用dispatchEvent或隐藏API造原生样本。可推进纯适配层的pending-frame/late-reply反例，但仍不能升级原生门。有效原生试次须先有sentinel操作、观察到临时几何、取消早于up，之后保存核实际document/store；Undo只撤销sentinel一次、Redo恢复它，再save/reopen与普通新drag核无迟到提交。不同pointercancel/blur/lostcapture分别按实际事件命名；hidden+blur组合不当hidden-only。

## 出版和真人交接

当前新matrix final manifest存在情况：`{"docs/evidence/browser-visual-matrix-hierarchy-final/manifest.json": false}`；这是审核时刻的库存，root后续采集可改变，**本审核不填最终collection数量**。当前spec为36基线＋三模型各一edited；36candidate SVG逐字一致只是renderer不变，旧39截图不继承。root可继续独立storage实际UI采集、核每张像素与DOM/Canvas/实际导出，再正式collect。六维审美、85/180mm真实尺寸与dense可读性须真实reviewer记录；old matrix的人审仍pending/false。

新五席8891–8895的59实施文件、4基线与5envelope本次重新hash/size核全相同；actual assignment=0、collected=0、incoming/export文件为空，reviewer=null。环境模板硬件/浏览器/DPR/fontResolutionEvidence均未填写。准备/verify不是开场，不给不存在的人assign，不邀请或发送消息。实际参与者开场才分配匿名代码；保留start/final、checkpoints、undo/redo、reload和实际export-open工件以及超时/放弃。自报、collector一致性和人工判定分别记录；3人需3/3、4人需4/4、5人需4/5才达≥80%，分母包含失败。

当前可继续：完成新matrix；用已记录的选定浏览器API核可见性及固定环境；测实际产品原生窗口并保留缺失项；若有效native能力允许则采活动cancel；准备最终人审交接。实际人审与3–5使用者是外部参与依赖，不能伪造。若继续改产品，须先归档当前source/build并宣布当前matrix/研究包stale，再重新绑定；调度疑点不是免除完整产品测试的理由。

JSON SHA256 `a7211b3df001c919b3a98b9ecb59dfa6c1dacbef542eb4e36587a7b8890d1236`，468916bytes。本报告不能证明M4完成、持续服务在线、真人成功、可见性导致/修复调度或原生取消回滚。
