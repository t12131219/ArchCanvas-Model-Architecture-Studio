# M4 真人视觉审看与研究试用交接

当前准备已完成，人工结果尚未产生：最终矩阵有 36 基线 + 3 编辑后工件，39 个评分项全部待审；当前研究包有五个未分配席位，真实研究者为 0。本文只说明接手方式，不新增验收门、参与者或通过结论。[只读状态快照](evidence/m4-human-review-handoff-status.json)记录本次核查时间、文件摘要、空白评分数量和各席位实际库存；它也不是人工 review。

## 使用当前证据

| 接手对象 | 当前入口 | 版本绑定 |
| --- | --- | --- |
| 39 图视觉审看 | [联系表](evidence/browser-visual-matrix-zoom-full/index.html)、[manifest](evidence/browser-visual-matrix-zoom-full/manifest.json)、[现有空白评分模板](evidence/browser-visual-matrix-zoom-full/review-template.json) | manifest SHA256 `eff1558d5acf2c07724af352d3ac7b1169c550048fab10b10084efed729db516` |
| 3–5 位实际使用者试用 | `.archcanvas/m4-research-trial-zoom-final`、[准备 manifest 副本](evidence/research-trial/current-zoom-build/prepared-manifest.json)、[原有研究协议](m4-research-protocol.md) | 包 manifest SHA256 `daeaec0137a0950ca93ca904574987e298f68eb45e6990fd3326d9be37f365b0` |

二者都绑定当前 `assets/index-oH4Ot2L9.js` / `assets/index-BO7yZQLO.css`。矩阵 spec digest 是 `a7baa207f7806526256da3737b41d339ec25a4fee5aed7ebcab062e9c0f42ea5`；评分模板 SHA256 是 `860261ef96ee5e7e4182f465b219a6134654a184f88d973424aea956d5ad2a36`。完整 build 与各基线 source/IR 绑定保存在相应 manifest 和状态快照。

`browser-visual-matrix-before-intrusion-fix` 是历史 build 的 39 图；`browser-visual-matrix-zoom-current` 是当前 build 的代表四样本；名称不能代替版本核对。旧 current/ready/ready-final/intrusion-final 研究包保留但不适用于当前实现，见[失效包记录](evidence/research-trial/current-zoom-build/stale-packages.json)。

## 真人逐图评分

按[原有视觉协议](browser-visual-matrix-protocol.md#独立人工审看)复制现有评分模板为一份独立 review，保留原始模板与 manifest。由实际复核者填写 reviewer、实际审看时间、采用的接受标准与观察结论。为避免复制后失去版本归属，在独立 review 中记录所审 manifest 的路径及 SHA256、spec digest、build 文件绑定；这些是审看来源说明，当前脚本没有解析或强制这些附加字段。

联系表基线卡标题是 `variantId`，模板键是 `caseId`。用 manifest 的 `captures` 对照二者，例如 `transformer-level0-paper-85` 对应 `transformer-level0-paper-85-final-ui`。从同一 capture 的 `files.screenshot` 和 `files.svg` 打开原截图与出版 SVG；`variants` 中的候选 gold 路径不能替代该 capture 的实际出版文件。三份 edited case 也按其准确 caseId 审看。

逐项记录现有六准则：布局、层级阅读、留白、色彩与黑白含义、字体与真实尺寸可读性、连线路由。填写 `browserPixelContentReviewed` 要以实际打开截图的观察为依据；填写 `physicalSizeViewed` 要说明实际尺寸审看方法。例如按 SVG 指定的 85/180 mm 宽度、关闭“适应页面”打印并用尺确认，或记录经过校准的屏幕显示方法。浏览器 fit、100% 缩放或联系表缩略图本身不证明物理尺寸。没有采用可确认的方法时保留未核实结论。

记录字体缺字、实际字体环境、dense 展开与小字问题；`fonts.status=loaded` 和零外部字体请求不能证明解析到哪份字体。7 pt 是可调整的建议，接受标准由实际审看者说明，不能从脚本数值自动得到审美通过。39 case、234 个六准则及真实尺寸/像素字段目前全部 pending。

当前采集器只生成空白评分模板，没有读取人工 review、检查完整性或升级验收门的命令。完成独立 review 后，将其路径和结论交回维护者；保留原矩阵的 `pending-human-review`、`humanAcceptanceCertified=false`，另记录人工报告的范围和发现。AI 像素观察和工件覆盖仍保留各自原范围。

## 实际研究者开场与复核

准备好的 S01–S05 对应 8871–8875；五席均只有一份原始 document，没有 assignment、collected、输入文件、导出、项目或事务。包级 `environment.json` 尚不存在，[现有环境模板](../.archcanvas/m4-research-trial-zoom-final/environment-template.json)仍为空白。实际外部输入是 3–5 位模型制图使用者、主持人的实际环境记录，以及独立复核者对任务工件的观察。

开场前在正式工程核对冻结内容；当前包无需再次 prepare 或 rebuild：

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
.venv/bin/python scripts/research_trial.py verify \
  --package .archcanvas/m4-research-trial-zoom-final
```

只在真实使用者实际开场时分配唯一匿名代号。以下 R01 是协议示例，不是已存在的参与者；S02–S05 更换对应席位、端口和独立浏览器 session：

```bash
.venv/bin/python scripts/research_trial.py assign \
  --package .archcanvas/m4-research-trial-zoom-final \
  --slot S01 --participant-code R01 --kind researcher
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --port 8871 \
  --data-dir .archcanvas/m4-research-trial-zoom-final/slots/S01/workspace/documents \
  --studio-dir studio/dist
```

服务启动后打开 `http://127.0.0.1:8871/?study=1`，按[原有五步及收集命令](m4-research-protocol.md#任务与评判)执行。下一份记录仅清 sessionStorage，不能复用已编辑席位。保留超时与放弃者；自动化记录不计入研究者分母。第五步的当前 UI 和收集器接受 SVG 或 PDF 实际导出，也可记录两种格式；逐一标明真正打开检查的格式，不声称检查了未查看的文件。

由主持人实际填写浏览器/版本、硬件、viewport/DPR 和字体解析依据到包级 `environment.json`。当前收集器允许缺少此文件，且存在时只检查它是 JSON object；收集成功不能证明环境记录完整。环境变化、缺项及无法核实的字体事实需如实注明。

`--study` 与 `--screenshot` 是主持人选择的文件路径，CLI 不限制它们必须来自 slot 的 incoming。按协议将本人的下载与截图放在对应 incoming 并注明来源；收集器验证选定字节的类型与绑定，不证明捕获时间、操作人身份或截图的席位来源。workspace 中的 Canvas 与导出则受席位路径和文档一致性校验约束。SVG 有独立重构比较，PDF 仅核本地可编辑 receipt，人工仍需打开实际文件。

收集后复制该席位 `collected/review-template.json` 为独立 `review.json`。收集器原样复制模板，因此 `participantCode` 仍为 null；复核者需对照实际 assignment、task 和 collected manifest 填入真实匿名代码、自己的 reviewer、审看时间和所审 manifest SHA256，再填写各任务证据路径、sourceUnchanged、publicationReadability 与 overallOutcome。没有看到的撤销、重做、刷新或导出行为填写 missing/unverified，不能用脚本一致性通过代替观察。

现有[汇总器](../scripts/summarize_research_tasks.py)仅统计自报，3–5 位与至少 80% 在 180 秒内完成是原协议目标；没有自动处理 review 或生成 reviewed-success 的接口。独立人工报告与自报汇总分别保存，不改写采集器的 `humanSuccessCertified=false`。当前[汇总](evidence/m4-study-summary.json)仍为 0 researchers / `not_run`，排除唯一 automation 冒烟记录。

若复核发现需要修改实现，保留本轮工件及失败结论，修改后按原协议准备新路径并重新采集；不改冻结哈希来延续旧包。
