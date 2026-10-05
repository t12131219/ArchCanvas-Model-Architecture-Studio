# 本轮 UI 字段独立核对

本核对使用十份实际 UI JSON、隔离服务保存 envelope 和两份实际导出，独立解析 XML/JSON、计算 SHA256，并调用正式 pure core 和 SVG 出版导出器重建；不读取隐藏 React/history 状态，不以字段或截图摘要认证原生性能、真人完成或出版质量。详见 [ui-field-audit.json](ui-field-audit.json)。

pan 公开相机从 `(293.262,46,z0.230606)` 到 `(357.262,86,z0.230606)`，恰为 `+64/+40`；SVG、rev18、四展开对象、一个固定对象、公开选择记录及 undo/redo 按钮状态完全不变。十份 viewport 均为 `(230,115,783,526)`，本组没有 viewport drift。

旧说明 `(0,1445,380,35)` 与 `Add:7d8cbbfd96` 正文矩形重叠。移到 `(50,1885,380,35)` 后正文冲突为0；undo 恢复旧位置和旧冲突，redo 恢复新位置，重复执行仍 rev21 和相同位置。新增说明位于 `(50,1944)`，编辑后高度50；最终两说明正文冲突为0。此检查不覆盖路径、marker、容器页头或实际字体塑形边界。

隔离服务保存为 document rev23/storage rev3，与初始化 rev18 完整文档相比只改变 `revision` 和 `annotations`；全 source/IR、49事实节点、71事实边和其它视觉字段保持精确相同，source/IR 摘要另行重算匹配。两导出输入都精确等于保存文档；实际 SVG 由正式 core+publisher 重建逐字节匹配，PDF 核实际字节/签名/收据和源 Scene，但不重转 PDF。七份实际工件字节副本在 [export-files](export-files)，衍生重建明确放在 [ui-field-reconstruction](ui-field-reconstruction)。

save/reopen 的公开 SVG 和 rev23 精确相同，但相机从 `(336.155,-189.333,z0.230606)` 改为 `(301.856,46,z0.215492)`，undo 按钮重置为 disabled；因此不宣称跨重开保留相机或历史。撤销说明时相机保留移动后聚焦值，viewBox x 回到 -20；据公开变换推算，模型屏幕 x 较移后增加约4.612px，撤销也不等于回到操作前屏幕视图。记录的 selection 数组始终为空，而部分 status 写“1 个已选”，不据此认证隐藏选择状态。

85mm 导出的 minText≈2.896pt、nodeLabel≈3.765pt；字体嵌入与 shaping 未认证，实际物理可读性仍需复核。旧严格报告的 failed 结论及旧39图历史范围保持原样，本轮只是一个自动化实际 UI 代表序列。
