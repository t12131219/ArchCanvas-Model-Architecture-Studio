# 导出可见文字几何差异补充纠正

原完成报告保持原样。本补充单独标明其已列出的可见文字变化：network 容器中的 `4× · independent` 在 saved/reopened public SVG 的坐标为 x=339、y=281，在导出 SVG 为 x=369、y=281，向右移动 30 个 SVG user units。文字内容、其余属性相同，但可见文字位置不同；这项变化不能仅归入 wrapper/interaction。

原 `export.nodeBodyChecks` 只核对节点主体 rect 属性相等，并记录 aria-label 字符串，未核对所有 text/tspan 坐标、字形几何或完整节点像素。因此不能由这些检查宣称全节点主体文字几何或导出图完全一致。rect/aria-label、edge groups、可见端口圆的有限对应结论保留。

whole-export bytes 不一致、receipt input/scene digest 不匹配 captured public SVG 的差异均保留。绑定原 JSON/Markdown、两个 public 文件及导出 SVG，共 5 个输入；末复核全部未变。没有浏览器/服务/产品操作或图片查看，不认证字体、采集方法、runtime 或人类验收。
