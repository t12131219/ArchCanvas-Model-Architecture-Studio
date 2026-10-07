# M4 研究者任务记录与复核

## 当前状态：视口尺寸与相机坐标协调（2026-10-06）

本阶段绑定 `index-_KAUBMcR.js` / `index--unhoRTb.css`。Studio **430/430**、fail/skip/cancel 0，strict TypeScript/Vite exit 0；publication **11/11**、skip 0。[统一收据](evidence/m4-viewport-resize-current/checks-final-attempt-2/receipt.json)为 112 源码/测试/配置＋3 dist＝**115**，另 11 publication 输入；18 份兼容测试历史 core 单独冻结，112 不是全部传递依赖清单。见[阶段](m4-viewport-resize.md)、[门状态](evidence/m4-current-gate-audit.json)与[143 项源码变更前归档](evidence/m4-viewport-resize-current/before-change/manifest.json)。只认证对应冻结字节。

新增 live ResizeObserver，在空闲视口变大或变小时保持世界中心和 zoom；相机持久化沿用已协调的坐标框尺寸。active pan、对象拖动、框选与端口输入保留原坐标映射，终止/取消后再协调。有限初始化等待可在可用视口/重新挂载时续行，旧 load/intent 不能覆盖新操作。focused45/45包含21项新增 resize 测试，是实际 App callback/effect harness，未挂载 React，不证明浏览器 paint 或初始零闪动。窗口 fallback 不能感知所有内部元素改尺寸。

[相机133/133](evidence/m4-viewport-resize-current/independent-routing-agent/browser-camera-readback-final/report.json)与[节点154/154](evidence/m4-viewport-resize-current/independent-routing-agent/browser-node-readback-attempt-4/report.json)分别核对有限公共DOM关系，不是功能全部成功。11/12 live resize和16/37重开初始DOM仍旧/默认中心，后续恢复(350,405)；first-paint未认证。相机四向32 CSSpx、Encoder四向24世界单位及各自undo、authoring重挂载返回、保存39/storage6和settled重开已记录。像素28/30的footer滞后一版、42仍100%而DOM已54%；43仅root有限亲看完整figure/legend。稳定DOM不能证明rasterfresh，servedBytesHashVerified=false。

[可读300对象准备](evidence/m4-readable-grid-next-work/README.md)用一条 typed output move 将冻结 workload bounds 从4588×30542缩到4588×1952；658/658是有限 document/中心线路径关系。300叶身份/事实与canonical保持，默认672×711名义字号仍仅1.632 CSSpx；大视口9.362/10.495px只是投影计算，未认证实际字体/可读性/完整连续输入性能。rAF 不是实际呈现 FPS，固定硬件/字体 A/B×3、≤50ms连续输入、medium p95<500ms、pins/anchor及presented≥50FPS仍开放。

memory默认名与原路由保持上一阶段范围；dy14→15 display端口仍令路线49→644.3世界单位，全域交叉/弯折美观未通过。[两份实际UI导出](evidence/m4-viewport-resize-current/actual-export-readback/independent-attempt-2/report.json)407/407关系核对whole180mm PDF/SVG与saved39/storage6 full document2/2 exact，相对31只Canvas revision变化；180×208.285714mm最低名义文字6.56018pt。初401/402的PDF normalized-height oracle失败保留；未新增85mm/detail工件、解析字体/嵌入或真人出版认证。 左库仍17基础模块＋3透明网络起点，未逐种生成/执行认证；历史三个AI角色范围保持，审计者不增参与者，AI 不计真人。

M4 `partial`、M5 `not_started`、真人 0。[新研究准备](evidence/m4-viewport-resize-current/research-readiness-independent/report.json)308/308仅readiness：86 implementation/4 baseline、五个pristine席位43621–43625；旧24包410文件exact，上一caption包正式verify已exit1 stale。未开席位服务/查端口可用性/分配/collect；3–5真人五步任务≤180秒/≥80%与出版人审尚未完成。旧gold、失败、研究包与第二个`##`起历史正文原字节保留。正式工程从头实现、独立于Temp runtime/fallback、无新认证复用，未执行生成模型。下方旧“当前/最终”只按各自冻结版本读取。

## 历史 D60 研究协议与冻结参数

旧 au3、ancestor-corridors 和更早研究包的准备状态仅按各自冻结时点读取，不能用于 D60 新参与者。旧 seal、失败与研究包原字节继续保留；本轮入口更新前的精确字节见 [归档 manifest](evidence/m4-native-matching-work/before-current-doc-update/manifest.json)。

使用正式 Studio 的 `?study=1` 页面和下述隔离试用包，用匿名代号开始计时。记录器只保存在当前浏览器 sessionStorage，不上传参与者资料；刷新后继续同一记录。`?benchmark=1` 是另一种工程测量，不与任务耗时混算。空白席位和自动化反例都不能算作真实参与者。

## 历史 D60：冻结基线与隔离席位（不可用于 DuFX 开场）

以下命令和“当前包”措辞只记录 D60 的冻结时点。该包现被 verify 拒绝为 stale；不要按本节对后续构建执行 assign/serve/collect，也不要覆盖旧包。旧 DuFX 入口冻结时尚未新准备；此后 DuFX/CC91/B_XH 包先后准备并因实现变化失效，现行 BTw7 准备见上方，真人仍为 0。

当前包已经完成 prepare 与 verify，两个进程均退出 0；[实际准备日志](evidence/research-trial/native-matching-current/process.json)保存准确参数与运行范围。不要再次 prepare、build 或覆盖这个包。开场前执行下面的 verify，并核查实际端口可用性与固定浏览器环境：

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
.venv/bin/python scripts/research_trial.py verify --package .archcanvas/m4-research-trial-native-matching-current
```

包 manifest SHA256 为 `321c1c2c83126f57b2cb96f1debafd07849c946afce60a95e5db73b6778dd13c`；[独立审计](evidence/m4-research-native-matching-independent/README.md)确认 5/5 pristine、0 assignment/collected/researchers。准备时使用 `--slots 5 --first-port 43151`，五席登记为 43151–43155，尚未启动席位服务或检测端口可用性。今后产品字节变化时，保留本包并在一个不存在的新路径另行 prepare；不能编辑旧 manifest 的哈希来延续一轮研究。

`prepare` 拒绝覆盖已有包，生成 `manifest.json`、`baseline/source`、独立分析的 `architecture.json`、正式 core 生成的未编辑 `canvas.json` 和 S01–S05。每个席位的 `participantCode=null`，初始统计为 0 researchers / `not_run`。各席位相同的 Canvas 字节和独立的 `workspace/documents` 都有 SHA256；`workspace/exports`、`incoming` 和空白复核模板各自隔离。服务的 `--data-dir` 指向 **documents 目录**，导出写入其父级 workspace，这也是不共享父目录的原因。

准备 manifest 还冻结正式 Python/Studio 源码、导出/汇总工具和真实 `studio/dist` 的文件哈希。每次开场和收集前检查：

```bash
.venv/bin/python scripts/research_trial.py verify --package .archcanvas/m4-research-trial-native-matching-current
```

源码、Studio 构建或基线有变即停止该包并为新一轮准备新路径；不要编辑哈希以继续。`verify` 只核冻结内容，不评价研究门。若同一研究过程中必须修 bug，保留已运行记录，分别标注版本，不把不同实现混成同一轮结果。

`preparationRuntime` 保存实际 Python/Node 路径、版本、平台与 analyzer 来源，避免把错误安装当正式工程。主持人另填 `environment-template.json` 的实际浏览器/version、硬件、viewport/DPR 和字体解析证据，保存为 `environment.json`；准备运行时不能替代浏览器与字体锁定清单。选择一套固定环境完成本轮，发生变化即记录对应席位。

每位实际使用者分配一个此前未使用的席位和一个唯一匿名代号，例如 R01→S01。代号在参与者实际开场前由主持人分配，席位不是虚构参与者。开启服务前从新manifest读取各席位的 `port` 与独立 `dataDir`，另查实际端口可用性。本包 S01 的实录端口为 **43151**，下例只对应 S01；S02–S05 使用 manifest 中各自的 43152–43155 与独立 dataDir。端口可用性仍须实际检查：

```bash
.venv/bin/python scripts/research_trial.py assign \
  --package .archcanvas/m4-research-trial-native-matching-current --slot S01 --participant-code R01 --kind researcher
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --port 43151 --data-dir .archcanvas/m4-research-trial-native-matching-current/slots/S01/workspace/documents \
  --studio-dir studio/dist
```

本五席包只在真实使用者实际开场时调用 `assign --kind researcher`；AI 工程检查使用独立的隔离数据或自动化包并明确 `--kind automation`，不消耗此包的未分配研究席位。此步先核对当前席位仍是原始 baseline envelope 且没有旧导出/项目/事务，再独占写入 `assignment.json` 的 code→slot→baseline 哈希绑定。它不开始计时、不证明真实身份；已分配席位和重复代号拒绝再次分配。收集要求 task 的 code/type 与该 assignment 相同，防止任务结束后才给已编辑数据补填一个“初始基线”。

打开对应S01实录端口的 `http://127.0.0.1:43151/?study=1`，使用单独浏览器 session，加载 Transformer 总览，核对初始 revision=0、没有别名/样式覆盖或 pin。先保存实际开场截图，再开始计时。端口登记不证明可用或服务已经在线；以新包manifest和实际启动结果为准。每目录只运行一个服务进程；下一位换新席位、端口和浏览器 session。**“开始下一份记录”只清 sessionStorage，不清服务端文档，不能用它复用同一席位。** 停止服务也不会重置基线；包不提供覆盖/清除旧参与者数据的自动操作。

## 任务与评判

邀请 3–5 位实际模型制图使用者，每位从未编辑的 Transformer fixture 开始，在 3 分钟内完成五步：

1. 展开 Encoder 和第一层，找到 self attention。
2. 修改 Encoder 的显示别名/填充、一条图例和说明文字。
3. 移动一个对象、固定另一个对象，撤销并重做一次。
4. 保存并刷新，核对别名、样式、图例与固定位置。
5. 导出 SVG/PDF，打开并检查文字、连接与最终尺寸。

每一步的“记录此步已完成”是参与者自报，记录当时 documentId、source/IR digest、视觉 revision、可见节点和展开身份。卡点、错误与审看意见可记在面板；退出时使用“结束并记录未完成”。下载 JSON 到该席位的 `incoming`，并保存实际截图。主持人保留 start/final、各 checkpoint、撤销前后/重做后、刷新后、实际打开导出的截图；截图要显示操作对象或文件尺寸，不能用 SVG 转 PNG 充当 Studio 截图。撤销历史不跨刷新保留，这是当前能力边界。

复核者逐项检查工件后再认定成功；小于等于 180 秒且全部五步确实完成才计入成功。放弃和超时都留在分母。不要只挑成功者，也不要把自动化代号改成研究使用者。目标是至少 80% 完成；这项人工门不能由脚本或 agent 自测认证。

## 收集实际工件链

完成最后一个视觉编辑后保存最终 Canvas。第 5 步导出此同一文档，打开文件检查，再记录 checkpoint；若在导出后修改文档，必须重新保存并导出后再记录。否则脚本会拒绝旧导出与最终 Canvas 的不一致。未完成者也下载 ended/abandoned 记录并保留 start/final 截图；没有完成导出时可以不传 `--export-id`，仍保留在自报分母。

SVG/PDF 实际目录是 `slots/S01/workspace/exports/<artifactId>`。导出面板链接中 `/api/exports/<artifactId>/figure.svg` 给出 identity；面板关闭后可从此席位自己的 exports 目录找到。不要把别的席位或历史证据文件复制过来作本次结果。服务保存的 `document.json` 是导出器实际输入，与最终保存文档逐字段对照，而非仅比较 sourceDigest 或 revision。

示例收集命令使用 **实际 artifactId 和实际截图路径**，不可原样把占位文字当证据：

```bash
.venv/bin/python scripts/research_trial.py collect \
  --package .archcanvas/m4-research-trial-native-matching-current --slot S01 --participant-code R01 \
  --study .archcanvas/m4-research-trial-native-matching-current/slots/S01/incoming/m4-study-R01.json \
  --export-id ACTUAL_32_HEX_ARTIFACT_ID \
  --screenshot start=.archcanvas/m4-research-trial-native-matching-current/slots/S01/incoming/start.png \
  --screenshot final=.archcanvas/m4-research-trial-native-matching-current/slots/S01/incoming/final.png \
  --screenshot undo-before=.archcanvas/m4-research-trial-native-matching-current/slots/S01/incoming/undo-before.png \
  --screenshot undo-after=.archcanvas/m4-research-trial-native-matching-current/slots/S01/incoming/undo-after.png \
  --screenshot redo-after=.archcanvas/m4-research-trial-native-matching-current/slots/S01/incoming/redo-after.png \
  --screenshot reloaded=.archcanvas/m4-research-trial-native-matching-current/slots/S01/incoming/reloaded.png \
  --screenshot export-open=.archcanvas/m4-research-trial-native-matching-current/slots/S01/incoming/export-open.png
```

可重复 `--export-id` 绑定 SVG/PDF；可增加 `--screenshot step1=...` 至 step5。成功收集的 `slots/S01/collected/manifest.json` 绑定匿名代码、开场 assignment、task JSON、基线/最终 Canvas、服务 storage envelope、实际导出输入/文件/receipt 和截图的字节 SHA256。它核对所有 checkpoint 的 document/source/IR，末步 revision、slot 内路径、导出文件 digest/size，以及正式 `buildExportScene`/`renderSvg` 从最终文档重算的 Scene digest。代码重复、已收集席位、同 revision 的另一份 Canvas、旧/错 source/IR、错文件摘要、缺 start/final 图和已完成但无 SVG/PDF 都会拒绝，失败不会留下半份 collected 包。

这些是一致性校验，不是人类成功认证。manifest 固定为 `self-report-pending-independent-review`、`humanSuccessCertified=false`；automation 排除研究者分母。图像签名和哈希不能证明截图内容、捕获时间或参与者身份，逐图仍需人工检查。`changedVisualFields` 仅帮助找别名、样式、图例、说明、layout/pin 的差异，不证明撤销/重做、保存刷新或出版可读性。

导出的 Scene 由最终 Canvas 独立重算。SVG 再由已冻结的正式 publication `export_svg(format='svg')` 重做 XML/物理尺寸规范化，与实际缓存 SVG 字节精确比较；同步改 SVG 可见文字及 receipt 的 output/svgDigest/bytes 仍会被拒绝。renderSvg 原文和规范化 SVG 的摘要通常不同，不能直接等同。PDF 转换后的字节仅和本地 receipt 的 outputDigest/bytes 对照，没有再次执行 PDF converter；同步改 PDF 与可编辑 receipt 仍可能通过。因此工件链不证明真实身份/操作或任意文件不可伪造来源；复核者仍要打开实际导出，核对文字、连接、尺寸和可读性，不能仅凭 manifest 认定人工任务成功。

收集器先读入并验证 Canvas/storage、assignment、导出输入/文件/receipt 和截图的字节快照，再写这些相同字节到 collected。等待正式 core 时服务的后续保存或文件变化不会混入这份包；包对应已核对的 checkpoint 文档快照，不宣称包含收集期间之后的编辑。并发变化反例验证此关系。

复制 `collected/review-template.json` 为独立 `review.json`，真实复核者填自己的匿名 reviewer 代码、各步骤证据路径/事实与结论，记录源码未变、字体/连线/尺寸审看和 overallOutcome。没有看到的行为填 missing 或 unverified；不能把脚本通过填成真人通过。包不自动合并人工结论，也不自动生成 reviewed-success；人工判定和自报汇总分别保存。

## 汇总

```bash
.venv/bin/python scripts/summarize_research_tasks.py \
  .archcanvas/m4-research-trial-native-matching-current/slots/S01/collected/task.json \
  .archcanvas/m4-research-trial-native-matching-current/slots/S02/collected/task.json \
  .archcanvas/m4-research-trial-native-matching-current/slots/S03/collected/task.json --output study-summary.json
```

脚本规范代号并去重，拒绝错误对象、未结束记录、伪摘要、负数/非有限时间、源码绑定变化和错误 checkpoint/时区顺序；研究使用者的放弃/超时计入分母，automation 排除。输出 `selfReportedCompletionRate` 与样本数，不自动把自报提升为通过，`researchGate` 始终等待独立工件复核。

## 当前搭建与位置修复探索

原五步绑定同一 Transformer document/source/IR。17 基础模块＋3 透明起点的草稿搭建会生成另一份 source/document；位置修复的 preview/cancel/apply 也不能从原五步结果推导。先结束并收集原五步，再使用另一个独立草稿/画布探索从零搭建、模块库搜索/点击/拖入、节点及相机上下左右移动、撤销重做、保存重开和箭头交叉/弯折。计时、工件与卡点单列，不改变原 180 秒分母。

[AI 体验覆盖核对](evidence/m4-ai-usability-current-review/README.md)保留已核对历史证据与缺口；[新手与视图任务卡](evidence/m4-research-handoff-audit-attempt-1/novice-and-view-task-card.md)及[八项空白探索表](evidence/m4-research-handoff-audit-attempt-1/exploration-template.json)用于逐项记录实际完成、失败或未运行。D60 新增工程检查以 [本轮阶段记录](m4-native-matching.md)为准。AI 角色始终标 automation/AI，不计 researcher 或出版人审；真实参与者尚未开场。

## 历史缩放构建与工程冒烟范围

以下只证明其原版本的准备/工件，不是当前可分配包，也不是研究者结果。

历史工程冒烟 [`m4-study-automation.json`](evidence/m4-study-automation.json)：已定位 attention、编辑 Encoder 别名/填充、验证保存刷新、生成 85 mm 详情 SVG；其他步骤未执行，记录为 abandoned。汇总 [`m4-study-summary.json`](evidence/m4-study-summary.json) 正确排除此记录，研究者人数为 0，任务验收为 `not_run`。

历史缩放build当时的空白正式包位于 `.archcanvas/m4-research-trial-zoom-final`：S01–S05、8871–8875，已prepare/verify，没有 assignment、collected 或参与者结果，各席位exports/projects/transactions为空。该旧包不用于 D60 新人；当时的准备与核验结果仅保留历史范围。可审阅[历史准备 manifest](evidence/research-trial/current-zoom-build/prepared-manifest.json)与[准备核对收据](evidence/research-trial/current-zoom-build/preparation-verification.json)；它们只证明基线/工具/build冻结、五个空白席位和研究者数0，包manifest SHA256为`daeaec0137a0950ca93ca904574987e298f68eb45e6990fd3326d9be37f365b0`。旧current、ready、ready-final、intrusion-final四包完整保留，但[当前实际verify失败](evidence/research-trial/current-zoom-build/stale-packages.json)，不用于新研究。历史公开收据保留其原范围，不替代当前准备或真人任务验收。

同一历史缩放build的[最终浏览器矩阵](evidence/browser-visual-matrix-zoom-full/manifest.json)已封存36基础组合＋三模型各一编辑后，共39项、artifactCoverage=complete；humanAcceptanceCertified=false、visualAcceptance=pending-human-review。这是独立自动化工件覆盖，未新增参与者，不能填入本协议的真实研究者样本、任务完成率或出版人工结论。该旧试用包在当时 verify unchanged，研究者为0；这不证明它可用于当前构建。

汇总是本地原始审看报告，包含备注原文与工件绝对路径；分享前需另行选择可公开内容。`m4-research-tests.txt` 保存9项独立反例/分母检查，测试输入不作为真实参与者工件。

`tests/test_research_trial.py` 使用明确命名的 automation 测试数据，12 项验证独立席位、拒绝覆盖、participant/document/source/IR/revision 绑定、同 revision 不同 Canvas、导出与 Scene 错摘要、缺实际工件、冻结内容变化、跨席位 symlink、abandoned、验证期间并发修改仍保留同一快照，以及同步改 SVG 和收据仍被独立重构拒绝。任何这些单元测试都不证明真人完成五步。
