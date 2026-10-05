# 新构建完整矩阵字段独立审计

[字段审计 JSON](field-audit.json) 核对新矩阵36基础组合、三模型各1份编辑后，共39case/234实际文件。所有manifest SHA256/bytes、corrected输入与collection副本精确匹配。21source、3dist、72core候选、core report及12supplementary绑定在审计前后均匹配；此报告不声称审查后续current文档更新。

三份 browser-observation 的 `heightMm` 与源 SVG metadata 相差最多约 `5.69e-14`，仅该字段按 `1e-9` 浮点序列化容差记录，其它 metadata 字段精确相同，未改输入字节。

39份Canvas通过正式pure core校验与独立Scene重建，全部实际浏览器SVG与重建interactive SVG按XML语义精确相同；全部实际出版SVG经正式publisher重建逐字节匹配。36baseline相对core只允许revision不同，三个edited实际新增说明（Transformer/CNN另有layout）；完整source/IR/Architecture、完整前沿/page均匹配。

原raw保留38份首项导出副本，其中首MLP85mm本来正确，另37份完整导出文档不符。修正ledger按“format=SVG且完整实际Canvas精确相同”的唯一服务工件解析38份，实际figure/receipt/document各37份改变。截图、Canvas、DOM、browser-observation字节和screen receipt事实字段（时间、环境、相机、资源、文档绑定）保持；38份screen receipt仅追加limitations说明，不能声称其整个文件字节未变。修正URL来自服务文件系统匹配，原stale URL保留且不当作正确路径证据，没有新browserlink读取认证。

20条journal覆盖三模型说明改文、undo恢复默认文本、redo恢复已编辑文本；模型node/edge/port/legend组保持。保存与重开记录的SVG字节一致，最终journal与实际edited case一致，当前服务保存的完整Canvas也匹配；仅认证这些公开记录与实际工件，不认证隐藏history或真人任务。

各格viewport1280×720/DPR1；UA/DPR来自绑定的同IAB8880先前observer，不能伪称每tab新读取。字体文件、硬件及实际browserVersion仍未知。此字段审计不逐图审像素、不认证原生性能、人工审美或85/180mm物理可读性；CNN说明断词“skip p / ath.”按实际SVG如实记录。旧严格failed报告与历史矩阵范围保持。
