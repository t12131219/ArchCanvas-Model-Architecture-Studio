# M4 真人视觉审看与研究试用交接

当前平移/说明构建 `index-DWpF-img.js` / `index-DK5lov-h.css` 已完成新五席pristine研究包准备，人工结果尚未产生，真实研究者仍0。当前矩阵已封存36/36基础＋三模型各一编辑后，39case/234工件、coverage=complete、人工评分pending/false；旧39项缩放矩阵属于历史build，不能作为当前完整覆盖或人工通过。本文只说明接手方式，不新增门、参与者或通过结论。[当前状态快照](evidence/m4-human-review-handoff-status.json)按其生成时间和build核对，不是人工review。

旧交接正文和旧JSON快照分别原字节保存于 [handoff.md](evidence/m4-human-review-handoff-before-pan-annotation/handoff.md)（SHA256 `84c63468189fb2ed7d38784f4379d0890014c652745e6c7af24681380b9f887d`）及 [status.json](evidence/m4-human-review-handoff-before-pan-annotation/status.json)（SHA256 `b24430c449543dfff641409ad7a6e613fcad978038da8ab1b79ac2d85191d016`）。旧55实施文件/dist、39图/spec/core与五席包另在 [切换归档](evidence/before-pan-annotation-build/manifest.json)保留；旧raw、严格oracle与manifest未回改。

## 使用当前证据

| 接手对象 | 当前入口 | 范围与版本绑定 |
| --- | --- | --- |
| 当前视觉矩阵 | [联系表](evidence/browser-visual-matrix-pan-annotation-full/index.html)、[manifest](evidence/browser-visual-matrix-pan-annotation-full/manifest.json)、[评分模板](evidence/browser-visual-matrix-pan-annotation-full/review-template.json)、[spec](evidence/browser-visual-matrix-spec-pan-annotation/spec.json) | 36/36基础＋Transformer/MLP/CNN各一编辑后，39case/234工件，collector完整Canvas/DOM/SVG核对，coverage=complete、人工pending/false；manifest SHA256 `52d60b4ad50d98bb01c0e19ee48fe627d1588185fbbd7961d8c64ff8c45cdd88` |
| 当前交互代表链 | [UI字段核对](evidence/m4-pan-annotation-work/ui-field-audit.md)、[输入范围](m4-input-observation.md) | +64/+40 pan、说明移动/历史/新增/保存重开及实际SVG重建；两v2session四次pan终点匹配，不认证持续paint、隐藏history、真人或出版 |
| 3–5位实际使用者试用 | `.archcanvas/m4-research-trial-pan-annotation`、[准备manifest](evidence/research-trial/pan-annotation-build/prepared-manifest.json)、[核对收据](evidence/research-trial/pan-annotation-build/preparation-verification.json)、[研究协议](m4-research-protocol.md) | 包manifest SHA256 `4b55d0f5508adf3cc2ee091e43c950718f71e996e3efe6e99f19cf0659135333`；S01–S05端口8881–8885，0分配/0收集/0研究者 |

新研究包绑定57实施文件、当前3个build文件和额外12个helper/observer文件；核对收据只证明pristine基线与工具/build。旧`.archcanvas/m4-research-trial-zoom-final`及其它历史包现在stale，不用于新参与者。当前SVG实际打开，PDF仅生成/文件收据核对；当前Transformer L3/85mm minText2.53093pt、nodeLabel3.29021pt，先前rev23约2.896pt属于独立范围，真实尺寸可读性均待审看。说明正文矩形冲突为0不证明路径、marker、页头和字体塑形无冲突。保存重开保持rev23/SVG，但camera改变、会话history重置。

本轮[独立字段核对](evidence/browser-visual-pixel-observation-pan-annotation-full/field-audit.json)重建39份Canvas/DOM/publication SVG、核234工件；[AI像素观察](evidence/browser-visual-pixel-observation-pan-annotation-full/pixel-review.md)只核可见页头/全纸/图例和无modal，密集fit小字无法可靠逐项阅读，CNN英文说明逐字符断为“skip p / ath.”，均应由人工记录问题。三模型说明编辑后工件带20份[公开journal](evidence/m4-pan-annotation-matrix-corrected/edited-ui-journal.json)：save/reopen SVG一致而camera变化/history reset，之后仍重切preset/width、保存导出，final rev54/22/39（storage18/10/14）不是立即reopen值。编辑后variant分别Transformer/CNN L0paper180、MLP L1paper180，不表示所有36配置都执行编辑。

[工件选取修正账本](evidence/m4-pan-annotation-matrix-corrected/export-copy-correction.json)保留helper旧导出URL造成37项错误副本，38项按完整Canvas/formatSVG唯一匹配实际服务文件后修正。原raw与截图/时间/DOM/Canvas不变，不将修正说成再次读取browser链接或复采。窗口1280×720/DPR1，UA/DPR来自同浏览器先前8880 observer；实际硬件/解析字体仍未知。旧12份current材料已在[完整矩阵前归档](evidence/before-pan-annotation-full-matrix/manifest.json)保留。

## 真人逐图评分

按[原有视觉协议](browser-visual-matrix-protocol.md#独立人工审看)复制现有评分模板为一份独立 review，保留原始模板与 manifest。由实际复核者填写 reviewer、实际审看时间、采用的接受标准与观察结论。为避免复制后失去版本归属，在独立 review 中记录所审 manifest 的路径及 SHA256、spec digest、build 文件绑定；这些是审看来源说明，当前脚本没有解析或强制这些附加字段。

联系表基线卡标题是 `variantId`，模板键是 `caseId`。用 manifest 的 `captures` 对照二者，准确caseId由本轮manifest给出，不沿用旧矩阵的caseId。从同一 capture 的 `files.screenshot` 和 `files.svg` 打开原截图与出版 SVG；`variants` 中的候选 gold 路径不能替代该 capture 的实际出版文件。实际已采集的edited case也按其准确caseId审看；缺项保留missing，不补成已审。

逐项记录现有六准则：布局、层级阅读、留白、色彩与黑白含义、字体与真实尺寸可读性、连线路由。填写 `browserPixelContentReviewed` 要以实际打开截图的观察为依据；填写 `physicalSizeViewed` 要说明实际尺寸审看方法。例如按 SVG 指定的 85/180 mm 宽度、关闭“适应页面”打印并用尺确认，或记录经过校准的屏幕显示方法。浏览器 fit、100% 缩放或联系表缩略图本身不证明物理尺寸。没有采用可确认的方法时保留未核实结论。

记录字体缺字、实际字体环境、dense 展开与小字问题；`fonts.status=loaded` 和零外部字体请求不能证明解析到哪份字体。7 pt 是可调整的建议，接受标准由实际审看者说明，不能从脚本数值自动得到审美通过。当前矩阵39case/234准则、真实尺寸/像素字段全部待人工审看。旧1case先导保留其原模板，旧zoom39也仅历史；不能将AI像素观察或旧review移作本轮人审结果。

当前采集器只生成空白评分模板，没有读取人工 review、检查完整性或升级验收门的命令。完成独立 review 后，将其路径和结论交回维护者；保留原矩阵的 `pending-human-review`、`humanAcceptanceCertified=false`，另记录人工报告的范围和发现。AI 像素观察和工件覆盖仍保留各自原范围。

## 实际研究者开场与复核

准备好的 S01–S05 对应 8881–8885；五席均只有一份原始 document，没有 assignment、collected、输入文件、导出、项目或事务。包级 `environment.json` 尚不存在，[现有环境模板](../.archcanvas/m4-research-trial-pan-annotation/environment-template.json)仍为空白。实际外部输入是 3–5 位模型制图使用者、主持人的实际环境记录，以及独立复核者对任务工件的观察。

开场前在正式工程执行以下freeze verify；若实际源码/build已改变，准备新的路径，不改旧manifest延续认证：

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
.venv/bin/python scripts/research_trial.py verify \
  --package .archcanvas/m4-research-trial-pan-annotation
```

只在真实使用者实际开场时分配唯一匿名代号。以下 R01 是协议示例，不是已存在的参与者；S02–S05 更换对应席位、端口和独立浏览器 session：

```bash
.venv/bin/python scripts/research_trial.py assign \
  --package .archcanvas/m4-research-trial-pan-annotation \
  --slot S01 --participant-code R01 --kind researcher
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --port 8881 \
  --data-dir .archcanvas/m4-research-trial-pan-annotation/slots/S01/workspace/documents \
  --studio-dir studio/dist
```

服务启动后打开 `http://127.0.0.1:8881/?study=1`，按[原有五步及收集命令](m4-research-protocol.md#任务与评判)执行。下一份记录仅清 sessionStorage，不能复用已编辑席位。保留超时与放弃者；自动化记录不计入研究者分母。第五步的当前 UI 和收集器接受 SVG 或 PDF 实际导出，也可记录两种格式；逐一标明真正打开检查的格式，不声称检查了未查看的文件。

由主持人实际填写浏览器/版本、硬件、viewport/DPR 和字体解析依据到包级 `environment.json`。当前收集器允许缺少此文件，且存在时只检查它是 JSON object；收集成功不能证明环境记录完整。环境变化、缺项及无法核实的字体事实需如实注明。

`--study` 与 `--screenshot` 是主持人选择的文件路径，CLI 不限制它们必须来自 slot 的 incoming。按协议将本人的下载与截图放在对应 incoming 并注明来源；收集器验证选定字节的类型与绑定，不证明捕获时间、操作人身份或截图的席位来源。workspace 中的 Canvas 与导出则受席位路径和文档一致性校验约束。SVG 有独立重构比较，PDF 仅核本地可编辑 receipt，人工仍需打开实际文件。

收集后复制该席位 `collected/review-template.json` 为独立 `review.json`。收集器原样复制模板，因此 `participantCode` 仍为 null；复核者需对照实际 assignment、task 和 collected manifest 填入真实匿名代码、自己的 reviewer、审看时间和所审 manifest SHA256，再填写各任务证据路径、sourceUnchanged、publicationReadability 与 overallOutcome。没有看到的撤销、重做、刷新或导出行为填写 missing/unverified，不能用脚本一致性通过代替观察。

现有[汇总器](../scripts/summarize_research_tasks.py)仅统计自报，3–5 位与至少 80% 在 180 秒内完成是原协议目标；没有自动处理 review 或生成 reviewed-success 的接口。独立人工报告与自报汇总分别保存，不改写采集器的 `humanSuccessCertified=false`。当前[汇总](evidence/m4-study-summary.json)仍为 0 researchers / `not_run`，排除唯一 automation 冒烟记录。

若复核发现需要修改实现，保留本轮工件及失败结论，修改后按原协议准备新路径并重新采集；不改冻结哈希来延续旧包。
