# M4 研究者任务记录与复核

当前（2026-10-05）为边界修正构建 `index-Cr_xKW9U.js`，SHA256 `1f4f51f9818e523916dacea184a7005fa7459bd3f2c4c8bfe6bfc83006e5be29`。[修正说明](m4-boundary-corrections.md)与[本轮收据](evidence/m4-boundary-corrections-work/verification.json)记录 unknown initializer/container/loop 边界、world-camera 负 bounds 和连线检查器样式修正；Studio 88/88、TypeScript/build、最终Python 62/62及额外21/21已记录（18个新增边界反例，计数单列）。旧 oI5 构建的39例/234工件矩阵、59实施绑定研究包和原生诊断只保留历史范围，对本构建 stale；新构建完成一例Transformer坐标/样式浏览器核对（11项）并有最终IR/全SVG回放14项；fresh36静态候选/9frontier与新spec已准备，但浏览器collect仍0。当前五席包61实施绑定、0真人；性能、活动取消和人工出版门未认证。M4仍partial，未进入M5。

使用正式 Studio 的 `?study=1` 页面和下述隔离试用包，用匿名代号开始计时。记录器只保存在当前浏览器 sessionStorage，不上传参与者资料；刷新后继续同一记录。`?benchmark=1` 是另一种工程测量，不与任务耗时混算。空白席位和自动化反例都不能算作真实参与者。

## 准备同一基线与独立席位

正式工程运行以下命令；不要使用旧目录、旧解释器或全局 entry。旧hierarchy-final五席包对Cr_xKW9U源码/build stale，不能分配新人。当前新包已prepare/verify：`.archcanvas/m4-research-trial-boundary-final`，61实施绑定、4baseline、五席8901–8905、0分配/收集/真人。应先verify当前包，不重新prepare覆盖；以下prepare命令仅示范未来再次修改源码/build时的新目录：

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
npm --prefix studio run build
.venv/bin/python scripts/research_trial.py prepare --output .archcanvas/m4-research-trial-NEW-BUILD --slots 5
```

`prepare` 拒绝覆盖已有包，生成 `manifest.json`、`baseline/source`、独立分析的 `architecture.json`、正式 core 生成的未编辑 `canvas.json` 和 S01–S05。每个席位的 `participantCode=null`，初始统计为 0 researchers / `not_run`。各席位相同的 Canvas 字节和独立的 `workspace/documents` 都有 SHA256；`workspace/exports`、`incoming` 和空白复核模板各自隔离。服务的 `--data-dir` 指向 **documents 目录**，导出写入其父级 workspace，这也是不共享父目录的原因。

准备 manifest 还冻结正式 Python/Studio 源码、导出/汇总工具和真实 `studio/dist` 的文件哈希。每次开场和收集前检查：

```bash
.venv/bin/python scripts/research_trial.py verify --package .archcanvas/m4-research-trial-boundary-final
```

源码、Studio 构建或基线有变即停止该包并为新一轮准备新路径；不要编辑哈希以继续。`verify` 只核冻结内容，不评价研究门。若同一研究过程中必须修 bug，保留已运行记录，分别标注版本，不把不同实现混成同一轮结果。

`preparationRuntime` 保存实际 Python/Node 路径、版本、平台与 analyzer 来源，避免把错误安装当正式工程。主持人另填 `environment-template.json` 的实际浏览器/version、硬件、viewport/DPR 和字体解析证据，保存为 `environment.json`；准备运行时不能替代浏览器与字体锁定清单。选择一套固定环境完成本轮，发生变化即记录对应席位。

每位实际使用者分配一个此前未使用的席位和一个唯一匿名代号，例如 R01→S01。代号在参与者实际开场前由主持人分配，席位不是虚构参与者。开启服务；S02–S05 使用新 manifest 中相应的独立目录和8902–8905端口：

```bash
.venv/bin/python scripts/research_trial.py assign \
  --package .archcanvas/m4-research-trial-boundary-final --slot S01 --participant-code R01 --kind researcher
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --port 8901 --data-dir .archcanvas/m4-research-trial-boundary-final/slots/S01/workspace/documents \
  --studio-dir studio/dist
```

只在实际使用者开场时调用 `assign`；自动化选择 `--kind automation`。此步先核对当前席位仍是原始 baseline envelope 且没有旧导出/项目/事务，再独占写入 `assignment.json` 的 code→slot→baseline 哈希绑定。它不开始计时、不证明真实身份；已分配席位和重复代号拒绝再次分配。收集要求 task 的 code/type 与该 assignment 相同，防止任务结束后才给已编辑数据补填一个“初始基线”。

打开 `http://127.0.0.1:8901/?study=1`，使用单独浏览器 session，加载 Transformer 总览，核对初始 revision=0、没有别名/样式覆盖或 pin。先保存实际开场截图，再开始计时。8901–8905来自当前manifest；以下8901是S01端口，以新包manifest和实际端口可用性为准。每目录只运行一个服务进程；下一位换新席位、端口和浏览器 session。**“开始下一份记录”只清 sessionStorage，不清服务端文档，不能用它复用同一席位。** 停止服务也不会重置基线；包不提供覆盖/清除旧参与者数据的自动操作。

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
  --package .archcanvas/m4-research-trial-boundary-final --slot S01 --participant-code R01 \
  --study .archcanvas/m4-research-trial-boundary-final/slots/S01/incoming/m4-study-R01.json \
  --export-id ACTUAL_32_HEX_ARTIFACT_ID \
  --screenshot start=.archcanvas/m4-research-trial-boundary-final/slots/S01/incoming/start.png \
  --screenshot final=.archcanvas/m4-research-trial-boundary-final/slots/S01/incoming/final.png \
  --screenshot undo-before=.archcanvas/m4-research-trial-boundary-final/slots/S01/incoming/undo-before.png \
  --screenshot undo-after=.archcanvas/m4-research-trial-boundary-final/slots/S01/incoming/undo-after.png \
  --screenshot redo-after=.archcanvas/m4-research-trial-boundary-final/slots/S01/incoming/redo-after.png \
  --screenshot reloaded=.archcanvas/m4-research-trial-boundary-final/slots/S01/incoming/reloaded.png \
  --screenshot export-open=.archcanvas/m4-research-trial-boundary-final/slots/S01/incoming/export-open.png
```

可重复 `--export-id` 绑定 SVG/PDF；可增加 `--screenshot step1=...` 至 step5。成功收集的 `slots/S01/collected/manifest.json` 绑定匿名代码、开场 assignment、task JSON、基线/最终 Canvas、服务 storage envelope、实际导出输入/文件/receipt 和截图的字节 SHA256。它核对所有 checkpoint 的 document/source/IR，末步 revision、slot 内路径、导出文件 digest/size，以及正式 `buildExportScene`/`renderSvg` 从最终文档重算的 Scene digest。代码重复、已收集席位、同 revision 的另一份 Canvas、旧/错 source/IR、错文件摘要、缺 start/final 图和已完成但无 SVG/PDF 都会拒绝，失败不会留下半份 collected 包。

这些是一致性校验，不是人类成功认证。manifest 固定为 `self-report-pending-independent-review`、`humanSuccessCertified=false`；automation 排除研究者分母。图像签名和哈希不能证明截图内容、捕获时间或参与者身份，逐图仍需人工检查。`changedVisualFields` 仅帮助找别名、样式、图例、说明、layout/pin 的差异，不证明撤销/重做、保存刷新或出版可读性。

导出的 Scene 由最终 Canvas 独立重算。SVG 再由已冻结的正式 publication `export_svg(format='svg')` 重做 XML/物理尺寸规范化，与实际缓存 SVG 字节精确比较；同步改 SVG 可见文字及 receipt 的 output/svgDigest/bytes 仍会被拒绝。renderSvg 原文和规范化 SVG 的摘要通常不同，不能直接等同。PDF 转换后的字节仅和本地 receipt 的 outputDigest/bytes 对照，没有再次执行 PDF converter；同步改 PDF 与可编辑 receipt 仍可能通过。因此工件链不证明真实身份/操作或任意文件不可伪造来源；复核者仍要打开实际导出，核对文字、连接、尺寸和可读性，不能仅凭 manifest 认定人工任务成功。

收集器先读入并验证 Canvas/storage、assignment、导出输入/文件/receipt 和截图的字节快照，再写这些相同字节到 collected。等待正式 core 时服务的后续保存或文件变化不会混入这份包；包对应已核对的 checkpoint 文档快照，不宣称包含收集期间之后的编辑。并发变化反例验证此关系。

复制 `collected/review-template.json` 为独立 `review.json`，真实复核者填自己的匿名 reviewer 代码、各步骤证据路径/事实与结论，记录源码未变、字体/连线/尺寸审看和 overallOutcome。没有看到的行为填 missing 或 unverified；不能把脚本通过填成真人通过。包不自动合并人工结论，也不自动生成 reviewed-success；人工判定和自报汇总分别保存。

## 汇总

```bash
.venv/bin/python scripts/summarize_research_tasks.py \
  .archcanvas/m4-research-trial-boundary-final/slots/S01/collected/task.json \
  .archcanvas/m4-research-trial-boundary-final/slots/S02/collected/task.json \
  .archcanvas/m4-research-trial-boundary-final/slots/S03/collected/task.json --output study-summary.json
```

脚本规范代号并去重，拒绝错误对象、未结束记录、伪摘要、负数/非有限时间、源码绑定变化和错误 checkpoint/时区顺序；研究使用者的放弃/超时计入分母，automation 排除。输出 `selfReportedCompletionRate` 与样本数，不自动把自报提升为通过，`researchGate` 始终等待独立工件复核。

## 历史缩放构建与工程冒烟范围

以下只证明其原版本的准备/工件，不是当前可分配包，也不是研究者结果。

历史工程冒烟 [`m4-study-automation.json`](evidence/m4-study-automation.json)：已定位 attention、编辑 Encoder 别名/填充、验证保存刷新、生成 85 mm 详情 SVG；其他步骤未执行，记录为 abandoned。汇总 [`m4-study-summary.json`](evidence/m4-study-summary.json) 正确排除此记录，研究者人数为 0，任务验收为 `not_run`。

历史缩放build当时的空白正式包位于 `.archcanvas/m4-research-trial-zoom-final`：S01–S05、8871–8875，已prepare/verify，没有 assignment、collected 或参与者结果，各席位exports/projects/transactions为空。使用此包时，将上文命令的 `.archcanvas/m4-research-trial` 替换为 `.archcanvas/m4-research-trial-zoom-final`，先执行 verify，无需再次 prepare。可审阅[当前准备 manifest](evidence/research-trial/current-zoom-build/prepared-manifest.json)与[准备核对收据](evidence/research-trial/current-zoom-build/preparation-verification.json)；它们只证明基线/工具/build冻结、五个空白席位和研究者数0，包manifest SHA256为`daeaec0137a0950ca93ca904574987e298f68eb45e6990fd3326d9be37f365b0`。旧current、ready、ready-final、intrusion-final四包完整保留，但[当前实际verify失败](evidence/research-trial/current-zoom-build/stale-packages.json)，不用于新研究。历史公开收据保留其原范围，不替代当前准备或真人任务验收。

同一历史缩放build的[最终浏览器矩阵](evidence/browser-visual-matrix-zoom-full/manifest.json)已封存36基础组合＋三模型各一编辑后，共39项、artifactCoverage=complete；humanAcceptanceCertified=false、visualAcceptance=pending-human-review。这是独立自动化工件覆盖，未新增参与者，不能填入本协议的真实研究者样本、任务完成率或出版人工结论。试用包仍verify unchanged，研究者为0。

汇总是本地原始审看报告，包含备注原文与工件绝对路径；分享前需另行选择可公开内容。`m4-research-tests.txt` 保存9项独立反例/分母检查，测试输入不作为真实参与者工件。

`tests/test_research_trial.py` 使用明确命名的 automation 测试数据，12 项验证独立席位、拒绝覆盖、participant/document/source/IR/revision 绑定、同 revision 不同 Canvas、导出与 Scene 错摘要、缺实际工件、冻结内容变化、跨席位 symlink、abandoned、验证期间并发修改仍保留同一快照，以及同步改 SVG 和收据仍被独立重构拒绝。任何这些单元测试都不证明真人完成五步。
