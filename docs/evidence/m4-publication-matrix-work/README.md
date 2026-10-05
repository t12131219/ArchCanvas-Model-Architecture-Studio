# M4 当前出版构建的完整浏览器矩阵

本轮保持正式 `index-DPwoyNJW.js` / `index-DK5lov-h.css` 不变，按源码的九个真实前沿，使用独立8887服务与真实CUA UI重新采集36个基础组合，再为Transformer、MLP、Residual CNN各补一份说明编辑后的保存重开与SVG。没有复用旧截图、core候选或旧导出充当新浏览器证据；旧DWp39矩阵和8886代表链保留各自原范围。

采集的原文件在 [raw](../m4-publication-matrix-raw/captures.json)，每项含实际DocumentStore envelope、DOM、AX、原生截图、明确观察到的导出链接及实际服务导出输入/文件/收据；`matrixCapture`显式接收当前链接，在复制前核同Canvas，未通过推测ID或旧闭包URL复制工件。截图前关闭modal、fit、读状态并丢弃一次截图，下一tool call保存第二次；最终像素内容仍需独立逐图核对。

[公开UI journal](browser-journal.json)有39条；[编辑journal](edited-ui-journal.json)有19条，三个模型文本change→undo→redo→Save→reload。Save之后立即记录的footer仍为“正在处理”，但随后实际重开、同版本DOM和再次Save后的服务工件确认成功；不能只凭点击Save认定保存完成。CNN先收起repeat时保留hidden子层级状态，后通过真实控件收起两block再收起repeat，最终准确L0。编辑样本为CNN L0/paper180 rev32、MLP L1/paper180 rev18、Transformer L0/paper180 rev41；对应最终storage14/10/18含生成最终导出前的再次Save，并非三份新建人类任务。

[准备摘要](preparation-summary.md)核对前版80local+94linked和175current绑定没有漂移，重新生成36份gold候选并冻结/verify新版spec；gold派生PNG不是浏览器截图。正式产品/测试/build均未更改，本轮不重复跑既有79项Studio测试，也不把既有较早Qpo的10项Python日志称为新JS重跑。

截图视口均为当前DOM观察的1280×720；UA/DPR明确绑定早先同IAB8880observer的原收据，非本次直接重测。硬件、实际解析字体、校准物理尺寸及持续presented FPS仍未知。[手势取消只读审计](gesture-cancellation-audit.md)确认四类已有取消路径，但未采活动手势原生取消；hidden-only是增强建议，没有现存明文合同。

M4仍partial：工件覆盖/字段/像素一致不等于独立人工出版审看，三个代理编辑样本不等于3–5位研究者；研究包五席仍0分配/0采集/0人。深层Transformer85mm整图文字仍过小，显式详情页不改变整图范围的结论。

本目录服务记录是根任务工具响应转录及session轮询，不冒称原始PTY startup日志；sandbox中ps没有可见匹配进程，不表示宿主服务停止。原用户8765与研究者8881–8885未被本轮改动。

本轮[联系表](../browser-visual-matrix-publication-final/index.html)与[矩阵清单](../browser-visual-matrix-publication-final/manifest.json)已正式收集36＋3／234工件，人工review-template保持空白。派生stamped目录保留原raw全部浏览器事实，仅39份screenReceipt经正式CLI补两项文件摘要；313份其余文件字节不变，绑定见 [raw-to-stamped-bindings.json](raw-to-stamped-bindings.json)。临时编排脚本在39次stamp与collect全部exit0之后打印return-code时变量遮蔽导致wrapper报错，原错误及命令exit日志保留于[说明](stamp-collect-orchestration-note.json)，不冒称产品或collect失败。

[当前交付预检截图](delivery-preflight.jpg)另有公开DOM与AX，只展示rev41整图180mm的现有缓存与字号预检，不额外计矩阵、导出或缓存试验。独立末审仅认证其明确scope的39项；机器可读验证摘要将冻结末审和当前文档绑定。

编辑中间记录另有五条AX输入值与同条已提交SVG内容不一致：CNN redo、MLP undo/redo、Transformer undo/redo。未采后续DOM input.value与对应像素，不推断是工具缓存、React draft还是异步绘制，也不声明19条AX输入值都同步。文本撤销/重做结论按3对undo与3对redo的SVG除revision结构相等，以及3对保存重开字节相等确认。原AX与journal保持不变。

CNN第一条note-added仅root与两个block的latent展开flags，repeat父已收起，实际renderedNodes为L0八节点，说明尚在L2遗留坐标。它属于过渡UI状态，不能称L2矩阵样本；后续真实控件清latent状态并放置note，最终L0矩阵输入root-only，已分别保留。

矩阵封存后另做[有界输入诊断](input-draft-diagnostic.json)：Transformer当前文本、临时提交、Undo、下一tool-call Undo、Redo五次DOM input.value/attribute与实际SVG内容一致；只证明这五个当前样本，不能解释旧五条AX差异，也不额外算矩阵/任务。临时编辑未保存。初次reload时服务已确认exit143，原因未知；同端口/data-dir重启后新同IAB tab恢复rev41，[恢复收据](input-draft-diagnostic-restore.json)确认保存envelope原字节未变。重启[raw startup日志](service-restart-raw.txt)单独保留。旧错误页的导航/关闭被浏览器URL策略限制，没有绕过策略；它不改变已封存证据。

[最终独立审计](independent-final-audit.md)状态为passed-with-explicit-observations，39DOM／实际出版字节／明确服务链接工件／39截图均匹配；352raw／352派生映射／234sealed完整，19编辑记录的3对undo、redo、save/reopen及finalraw对照均通过。审计输入1472个唯一文件写前写后绑定一致；五条AX、CNN过渡latent flags、四处JSON页高末位差、临时wrapper收尾错误皆保留。真实DOM XML与SVG导出字节仍exact，1e−9mm容差仅用于独立metadata.heightMm观察比较。

当前构建既有79Studio测试、strict TypeScript/build、9独立副本检查及58研究包绑定日志另保持原范围，未在矩阵阶段重复测试或认证真人。最终根[验证摘要](verification-summary.json)、[封存清单](manifest.json)与[root复核](root-final-recheck.json)冻结当前文档/工件字节；旧linked当前文档的原bytes到[上一版归档](../before-publication-final-matrix/manifest.json)解析，禁止以改hash重标旧记录。
