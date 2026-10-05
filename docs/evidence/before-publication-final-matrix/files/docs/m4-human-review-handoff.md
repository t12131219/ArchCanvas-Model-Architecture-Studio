# M4 真人视觉审看与研究试用交接

当前出版修正构建 `index-DPwoyNJW.js` / `index-DK5lov-h.css` 已提供五pristine研究席位，真实参与与人工结果仍0。本build只有8886出版代表UI/实际导出链，尚无新36＋3完整矩阵。旧DWp39矩阵/字段/AI像素审计与旧pan包全部历史，不能当当前覆盖或给新人分配。旧正文和状态在[出版修正前归档](evidence/before-publication-refinement/manifest.json)保留，[当前状态快照](evidence/m4-human-review-handoff-status.json)只记录库存，不是人审。

## 使用当前证据

| 接手对象 | 当前入口 | 范围 |
| --- | --- | --- |
| 出版UI代表链 | [最终journal](evidence/m4-publication-refinement-work/browser-journal-final.json) | 默认整图、显式完整路径/序号详情、宽度25–1000mm、页高≤5000mm、字号两位小数和建议宽按钮；不是完整矩阵或人审 |
| 当前视觉矩阵 | 待新构建独立采集 | 旧[pan39](evidence/browser-visual-matrix-pan-annotation-full/manifest.json)及其审计只绑定DWp，0个已封存新build矩阵case；需要36基础＋各模型1编辑后 |
| 3–5位实际使用者试用 | `.archcanvas/m4-research-trial-publication-final`、[prepare](evidence/m4-publication-refinement-work/research-preparation-final.json)、[verify](evidence/m4-publication-refinement-work/research-verification-final.json) | manifest SHA256 `4bf341d0c5848d8591ebec138a3723753c13315a57981a19e4676c07b2678d86`；58实施文件、S01–S05端口8881–8885，0分配/0收集/0真人 |

whole85最小2.53pt/282.7mm高，236mm为7.03pt/784.8mm高；显式第一层FFN85为6.94pt且实际<7，86mm实际SVG/PDF7.03pt、node9.13pt、263.7mm高/3边界。7pt仅起点，需要人工确认实际尺寸、字体、路线和目标版面。导出缓存v2按exact当前SVG比较，旧v1/renderer结果变化不复用旧文件。旧“skip p / ath.”与小字失败结论保留历史，不通过改历史工件来改善结果。

最终journal共11条代表记录，CNN180mm为8.58pt/309.5mm高，当前说明保留“…with its skip”/“path.”两行。v1-cache-rejected无导出链接，当前SVG生成后v2恢复同一链接；[最终文件绑定](evidence/m4-publication-refinement-work/final-export-bindings.json)给出两SVG/一PDF原件。PDF生成/收据不等于实际打开与尺寸审看，11代表记录也不覆盖三模型完整任务。服务中断与恢复保留[运行摘要](evidence/m4-publication-refinement-work/service-lifecycle.json)，未封存失败浏览器状态/原始退出日志，失败不当成功。

[最终独立审计](evidence/m4-publication-refinement-work/independent-final-audit.md)受限通过11主Canvas/实看截图、9预览、5选项、3直接链接工件和2SVG/1PDF页几何，无截图状态滞后。storage envelope原文未封存，renderer改变拒绝是2纯函数反例；Python10仍为既有Qpo范围记录，退出原因未知。审计只支持字段/文件/AI像素一致性，实际复核者仍须打开目标文件并填写自己的人工结论。

## 真人逐图评分

按[原有视觉协议](browser-visual-matrix-protocol.md#独立人工审看)对已有历史build审看可复制其原评分模板；当前build须等待新实际矩阵与模板，随后复制为独立review，保留原始模板与 manifest。由实际复核者填写 reviewer、实际审看时间、采用的接受标准与观察结论。为避免复制后失去版本归属，在独立 review 中记录所审 manifest 的路径及 SHA256、spec digest、build 文件绑定；这些是审看来源说明，当前脚本没有解析或强制这些附加字段。

联系表基线卡标题是 `variantId`，模板键是 `caseId`。用 manifest 的 `captures` 对照二者，准确caseId由所审实际manifest给出，不沿用其它矩阵的caseId。从同一 capture 的 `files.screenshot` 和 `files.svg` 打开原截图与出版 SVG；`variants` 中的候选 gold 路径不能替代该 capture 的实际出版文件。实际已采集的edited case也按其准确caseId审看；缺项保留missing，不补成已审。

逐项记录现有六准则：布局、层级阅读、留白、色彩与黑白含义、字体与真实尺寸可读性、连线路由。填写 `browserPixelContentReviewed` 要以实际打开截图的观察为依据；填写 `physicalSizeViewed` 要说明实际尺寸审看方法。例如按 SVG 指定的 85/180 mm 宽度、关闭“适应页面”打印并用尺确认，或记录经过校准的屏幕显示方法。浏览器 fit、100% 缩放或联系表缩略图本身不证明物理尺寸。没有采用可确认的方法时保留未核实结论。

记录字体缺字、实际字体环境、dense 展开与小字问题；`fonts.status=loaded` 和零外部字体请求不能证明解析到哪份字体。7 pt 是可调整的建议，接受标准由实际审看者说明，不能从脚本数值自动得到审美通过。旧DWp39case/234准则仍可按历史build审看；当前出版build尚无新39矩阵模板。新采集必须独立生成模板，不能将旧矩阵、AI像素观察或旧review移作本build人审结果。

当前采集器只生成空白评分模板，没有读取人工 review、检查完整性或升级验收门的命令。完成独立 review 后，将其路径和结论交回维护者；保留原矩阵的 `pending-human-review`、`humanAcceptanceCertified=false`，另记录人工报告的范围和发现。AI 像素观察和工件覆盖仍保留各自原范围。

## 实际研究者开场与复核

准备好的 S01–S05 对应 8881–8885；五席均只有一份原始 document，没有 assignment、collected、输入文件、导出、项目或事务。包级 `environment.json` 尚不存在，[现有环境模板](../.archcanvas/m4-research-trial-publication-final/environment-template.json)仍为空白。实际外部输入是 3–5 位模型制图使用者、主持人的实际环境记录，以及独立复核者对任务工件的观察。

开场前在正式工程执行以下freeze verify；若实际源码/build已改变，准备新的路径，不改旧manifest延续认证：

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
.venv/bin/python scripts/research_trial.py verify \
  --package .archcanvas/m4-research-trial-publication-final
```

只在真实使用者实际开场时分配唯一匿名代号。以下 R01 是协议示例，不是已存在的参与者；S02–S05 更换对应席位、端口和独立浏览器 session：

```bash
.venv/bin/python scripts/research_trial.py assign \
  --package .archcanvas/m4-research-trial-publication-final \
  --slot S01 --participant-code R01 --kind researcher
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --port 8881 \
  --data-dir .archcanvas/m4-research-trial-publication-final/slots/S01/workspace/documents \
  --studio-dir studio/dist
```

服务启动后打开 `http://127.0.0.1:8881/?study=1`，按[原有五步及收集命令](m4-research-protocol.md#任务与评判)执行。下一份记录仅清 sessionStorage，不能复用已编辑席位。保留超时与放弃者；自动化记录不计入研究者分母。第五步的当前 UI 和收集器接受 SVG 或 PDF 实际导出，也可记录两种格式；逐一标明真正打开检查的格式，不声称检查了未查看的文件。

由主持人实际填写浏览器/版本、硬件、viewport/DPR 和字体解析依据到包级 `environment.json`。当前收集器允许缺少此文件，且存在时只检查它是 JSON object；收集成功不能证明环境记录完整。环境变化、缺项及无法核实的字体事实需如实注明。

`--study` 与 `--screenshot` 是主持人选择的文件路径，CLI 不限制它们必须来自 slot 的 incoming。按协议将本人的下载与截图放在对应 incoming 并注明来源；收集器验证选定字节的类型与绑定，不证明捕获时间、操作人身份或截图的席位来源。workspace 中的 Canvas 与导出则受席位路径和文档一致性校验约束。SVG 有独立重构比较，PDF 仅核本地可编辑 receipt，人工仍需打开实际文件。

收集后复制该席位 `collected/review-template.json` 为独立 `review.json`。收集器原样复制模板，因此 `participantCode` 仍为 null；复核者需对照实际 assignment、task 和 collected manifest 填入真实匿名代码、自己的 reviewer、审看时间和所审 manifest SHA256，再填写各任务证据路径、sourceUnchanged、publicationReadability 与 overallOutcome。没有看到的撤销、重做、刷新或导出行为填写 missing/unverified，不能用脚本一致性通过代替观察。

现有[汇总器](../scripts/summarize_research_tasks.py)仅统计自报，3–5 位与至少 80% 在 180 秒内完成是原协议目标；没有自动处理 review 或生成 reviewed-success 的接口。独立人工报告与自报汇总分别保存，不改写采集器的 `humanSuccessCertified=false`。当前[汇总](evidence/m4-study-summary.json)仍为 0 researchers / `not_run`，排除唯一 automation 冒烟记录。

若复核发现需要修改实现，保留本轮工件及失败结论，修改后按原协议准备新路径并重新采集；不改冻结哈希来延续旧包。
