# Bc 浏览器矩阵最终文件核对

正式 `scripts/browser_visual_matrix.py collect` 已于 2026-10-05 执行成功，输出为 `docs/evidence/browser-visual-matrix-bcf-full/`。`captures-039.json` 包含36个唯一baseline和Transformer、MLP、Residual CNN各1个edited-after；missing列表为空，artifactCoverage为complete。`humanAcceptanceCertified=false`、`visualAcceptance=pending-human-review` 保留原值，人审模板未填写。

索引SHA-256为 `f45b9f4055979024e3c3c6feaa4fbff588620af913c211a28abd0f1647fe74f2`；正式collection manifest为 `114dd31605ed08e4c7a2498212e0442c746d2acda5142b3106fb08a90a86fad2`。执行命令、exit0和时间保存在 `full-collection-execution.json`，完整stdout保存在 `full-collection-log.txt`。

`full-collection-byte-audit.json` 完成39个索引case的raw→bound/package→collection核对、234份最终collection文件字节核对、39张原生JPEG header与记录的1280×720/DPR1核对，以及全部index input bindings、当前build/worker guard和既有89份sealed文件核对。SHA-256为 `b2db7ade35eadef87d594e603ccb1e1786f23844eed75eac7c7bd7e22a7ade85`。该报告在byte阶段通过后写入；同一 `audit_full_collection.py` 在后续journal阶段的旧before假设上exit1。因此它的完整执行不能写成exit0，byte阶段与后续失败receipt均保留。

`edited-journal-svg-audit.json` 由新的只读 `audit_edited_journals.py` 执行exit0得到，SHA-256为 `b2f0c6121328d9adbf2bc15cffe244bae80cd335ba194a78377df00df8620754`。15份公开SVG journal的实际结果如下：

| 模型 | before时点 | undo→redo | redo→saved→reopened | 最终capture |
| --- | --- | --- | --- | --- |
| Residual CNN | rev30，确为edit前 | rev32→33，1个注释tspan改变 | SVG原字节相等 | rev35，除revision元数据外相等 |
| MLP | rev20，已包含edit | rev21→22，1个注释tspan改变 | SVG原字节相等 | rev24，除revision元数据外相等 |
| Transformer | rev42，已包含edit | rev43→44，1个注释tspan改变 | SVG原字节相等 | rev46，除revision元数据外相等 |

MLP和Transformer的早期before不能用作pre-edit证据。真实undo→redo和后续save/reopen效果依据实际SVG比较成立。比较只去除root的 `data-revision` 和metadata JSON的 `revision`；其余XML tag/attribute/tail/child-count完全核对，文字差异逐条记录。相机在reopen时改变，不影响SVG内容等价。

早期15份journal JSON的 `visibleNodes=0` 来自过时选择器。原JSON均保留，新审计从实际SVG的唯一 `data-node-id` 派生24/8/49个可见节点，没有改写raw。旧Transformer85mm stale-href raw仍保留且未进入index；使用单独recapture。前2个case由直接helper执行，后37个由bound-only worker执行；先前把所有case都计为worker的内存审计断言失败，尚未写文件时即终止，最终审计改用39例固定index范围。

`audit-full-collection-attempt1-failure.json` 与 `audit_full_collection_attempt1.py` 保留首次审计build路径错误；`audit-full-collection-attempt2-journal-failure.json` 保留旧before断言失败。没有将失败记录替换为通过，也没有覆盖旧prepared/independent/pixel seal。

本辅助代理仅处理主代理已发布的bound快照与局部文件；本阶段未操作浏览器、未重读live store、未触发export、未填写真人席位或人审评分。本代理之前实现过routing和capture helper，以上为对主代理冻结观察的独立文件比较，不声称独立于全部产品实现。截图像素审查另由proxy_novice完成；本报告不认证当前UA身份、字体解析、出版实际尺寸可读性或真人任务完成。
