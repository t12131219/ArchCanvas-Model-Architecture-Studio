# 首批 Alpha 实际证据

`studio-alpha.jpg` 来自正式 Studio 的真实浏览器截图。`transformer-overview.svg` 与 `transformer-edited.svg` 从浏览器保存的 CanvasDocument 用同一正式 Scene/SVG renderer 导出，分别包含显示别名/颜色/图例，以及展开层级/手动图例/说明文字。对应 receipt 记录 source/IR/SVG digest、视觉 revision 和物理尺寸。

`independence-report.json` 来自正式源码的独立 /tmp 副本，检查 Python -I -S 的实际包来源、三个源码样例、源码字节不变，以及复制正式项目本地 Node 依赖后的独立构建。不是旧项目运行记录，也不是干净网络安装或三宿主认证。

浏览器 SVG 下载事件在当前内置浏览器不可取，因此下载链路保持未认证；本地保存文档导出已验证。PNG/PDF、全套 85/180 mm 黄金图、人类出版审查与性能测量不在这批证据中。
