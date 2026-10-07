# 实际保存草稿与静态生成物独立核对

本记录由 AI 子 Agent 独立完成，真人参与者为 0。最终 observer 只读取已冻结的公开 DOM/AX、匹配的服务持久化文件、正式源码和当前 clone 中两份既有 managed model 源码。未操作浏览器、修改服务状态、调用生成器、导入或执行模型、安装依赖或访问旧 prototype。

`report.json` 的 21 个输入均有精确快照与 SHA-256。浏览器 attempt-2 manifest 的全部 60 个原始工件在核对前后保持字节一致。

实际草稿位于 `.archcanvas/m4-authoring-preview-20261006-attempt-1/drafts/draft-7c9ff26a-8ab1-4d90-8bb7-a65e26728a7f.json`，名称为“M4 · 合并路由复核”。草稿 revision 为 33，保存 envelope revision 为 1。它与公开 reopen 记录的全部 5 个节点身份、标签、位置及 5 个边身份匹配。

11 个公开 SVG 几何记录（基线、四方向 Add 移动、恢复基线、四方向相机平移、保存后重开）均包含 5 节点、5 边。10 个端点逐一与实际公开端口圆心精确相等；路径没有零长段或斜线，也没有穿过卡片内部或不同源端口之间的线段交叉、接触及重叠。同一精确源端口共享的起始段/接点明确允许。四方向相机平移 ±40 保留边路径与节点世界位置，四方向 Add 移动 ±16 保留其余节点位置与所有身份。

530 字节 `generated-source.py` 与生成弹窗的公开文本在折叠空白后相等。独立 AST 核对确认两个 Input、Add 的 left/right、Concat 的 a/b 与 dim=1、命名 Output 均与持久化草稿的精确绑定一致。两路输入 [1,16]、Add [1,16]、Concat/输出 [1,32] 都是静态声明，没有运行或数值正确性证据。

当前 clone 中两个 managed project 的 `source/model.py` 都是旧的 Linear/GELU 链，均不等于本次 merge 生成文本。因此本记录证明草稿持久化及弹窗静态生成物对应，不能证明已创建或打开本次 merge 的 managed model。

几何通过仅针对这些记录。外侧 fanout 仍有 7 段、6 个折点，不能据此认可美观或最少弯折；SVG 核对也不能修复已知像素旧帧、剪裁或缩放标注与像素不一致问题。没有真人小白体验、实体出版或实际呈现帧率认证。

`../saved-artifact-audit-attempt-1/failed-attempt.json` 保留 observer 首次错误：公开 SVG outerHTML 无 xmlns，初版脚本错误假设了 XML 命名空间，造成空元素提取。最终 attempt-2 按实际 root tag 读取命名空间；初版脚本、输入快照和失败说明未覆盖。
