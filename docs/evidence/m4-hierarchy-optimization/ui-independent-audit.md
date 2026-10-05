# 层级树优化 UI 独立审计

12 个实际 DOM journal 观察已核对，25 个输入从同一冻结 bytes 解析与哈希，审计前后 bytes / SHA256 均一致。早期 11 项 journal 仍是 final journal 的完全相同前缀。本审计只写自己的脚本和两个结果文件。

实际观察绑定新 `index-oI5sT67U.js`（SHA256 `2c769087f0765ba47892e9f26f12a19e4336ec12573dce5859ac636e310f446c`）；所有 journal 的 script URL 与当前 bound HTML/JS 一致。原始浏览器 HTTP 响应正文没有由本审计重新捕获或认证。

MLP 的展开、指定 Linear1 选择、`Projection α` 显示别名、pin、undo、redo、收起、再展开、保存与重开均通过。11 个 MLP 快照 source/IR digest 及完整 8 条 sourceFacts 一致；独立 Python 映射 metadata 与保存 architecture 相同，included source 与正式 fixture 字节相同。CNN 切换清除旧 MLP tree ID、alias、selection 与 pin。

保留采集限制：早期 `treeitem.querySelector('.tree-row > svg')` 递归扫描 descendant rows，把 Linear1 的 pin 误记到 MLP root 和 network。`mlp-pinned` 原始三个 true 原样保留；V2 改为 `firstElementChild` 直接行范围，真实 pinned IDs 及 store 均只有 Linear1。SVG 本身不显示 pin 状态，不能据 normalized pin-stage SVG 推断 pin 数量。

完整 SVG 比对只排除实际 SVG attribute / metadata 两个 revision 标量：undo 恢复 alias-stage、redo 恢复 pin-stage、collapse 恢复原始 frontier、re-expand 恢复布局及 alias 均精确。save/reopen 的完整 SVG 甚至原字节相同，SHA256 `62f83f6db697d38d6713cd7c50cc832a327844930a6bbe732988749c771962ee`。封存 envelope 与当前隔离 store 字节相同，visual revision 7、storage revision 1。

Fresh formal core 从冻结模块 bytes 的临时副本导入，完整 visual-operation replay 重建保存 document 的所有字段；11 个完整 SVG 的 XML 内容与对应 journal 精确。只规范化 browser empty-element serialization 与 XML attribute 顺序，fresh replay 不去掉 revision。此项是相同引擎的一致性复核，不是第二个独立渲染算法正确性或新源码分析。

`mlp-reopened.jpg` 原文件已通过 `view_image(high)` 实际查看，编码 1280×720，与 journal viewport 相同。画面显示已保存、Projection α、该行 pin、无选择、46% 相机、重开 footer / rev7；undo / redo 图标看起来 disabled。图片不用来认证 CSS 几何、采集时间或物理出版可读性。

重开清空 selection 并改变相机，场景 body 几何不变。当前 App 明确 createHistory(document)，fresh core 检查返回空 past/future；journal 没有记录原生按钮 disabled 属性。历史与相机持久化均未认证。

本审计是 agent 验证，human participants 为 0，不替代人工 publication review、研究者任务、native cancel、固定字体/硬件或持续呈现 FPS / input-to-paint 性能验收。

复现：`python3 docs/evidence/m4-hierarchy-optimization/audit_ui.py`。需要已有 Node 24 和正式 core 文件，不安装依赖，不操作服务或浏览器。
