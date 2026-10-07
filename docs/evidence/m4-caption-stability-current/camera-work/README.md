# Camera view-state implementation work

本目录记录正式 Studio 的相机恢复实现、独立数值检查和 App callback 集成检查。当前源文件见 [最终快照](final-attempt-3/source-snapshot/)，验收范围见 [report.json](report.json)。本任务未操作浏览器，未更新 current 入口文档，也未构建 dist。

## 最终检查

- [focused attempt 3](final-attempt-3/final-attempt-3-focused.process.json)：24/24 通过、fail/skip/cancel 均 0。包括 11 项新视图状态用例、3 项实际 App callback harness、原 projection 2 和 gesture 8。
- [strict attempt 3](final-attempt-3/final-attempt-3-strict.process.json)：严格 TypeScript 退出 0。
- [root scoped diff check](final-attempt-3/scoped-diff-check-root.process.json)：退出 0；[三文件全文空白检查](final-attempt-3/all-owned-file-whitespace.json)补核 untracked 新文件。
- [App 最终 diff](final-attempt-3/app-camera-final.diff)相对138原件归档中的 App，只改变相机身份、存储、初始化与既有加载/操作的相机调用。
- attempt 1 的 21/21、attempt 2 的 25/25与原始日志均保留。attempt 2 含中间 gate 单测，不能代替当前24项。首次 attempt 3 diff 命令在 studio cwd 使用错误 pathspec，不能计源检查；上述 root scoped 收据已纠正。

## 实现边界

sessionStorage key 按 document/source binding/IR 隔离，内容精确绑定 visualRevision。状态保存世界中心、缩放、捕获 viewport；重开时以当前 viewport 重算平移，保持世界中心和缩放。版本、身份、数值与 storage 异常均拒绝并安全回退。

App 使用 document object、revision、load sequence 和 intent sequence 防止过期初始化覆盖新文档或显式 fit/zoom/focus/pan。persistCamera 明确拒绝 active pan，终止拖动和取消回滚才保存。已有语义提交在其既有路径采用新身份并保留数值视图；本任务未创建或执行语义源码修改。

3项 callback harness 从实际 App.tsx 读取身份函数与 persist/claim/commit/initialize 回调本体，并经 TypeScript 转换后运行受控 storage/rAF；期望数值和访问顺序为手工独立断言。检查了初始读先于写、preview 拒写、终端/回滚写入、过期 intent/load/revision 拒绝和 tiny viewport 有限重试。它没有挂载 React，也不能证明 effect、原生 pointer capture 或实际绘制时序。

没有自动 ResizeObserver。不同 viewport 的世界中心保持只在初始化/重开应用；最多4帧无可用 viewport 后等待显式操作。关闭标签或跨标签持久化不在 sessionStorage 范围内。不同 visualRevision 拒绝旧视图；初始化前的新视觉编辑也会取消旧 ticket。

## 待主任务验收

主任务继续正式 build 与实际 CUA：同 viewport reload、不同 viewport 重开、显式 fit 优先级、四向 pan/zoom、取消/终止拖动、保存重开和 source/history/export 不变性。本目录没有新的实际性能样本或真人记录；M4 保持 partial，M5未开始。
