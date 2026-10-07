# M4 缩放按钮原生点击修复

主流程在 8771 的真实浏览器中点击缩放百分比按钮后，DOM 仍显示 14%，未回到按钮声明的 100%。缩放按钮位于 canvas viewport 内；原 `pointerDown` 仅排除 input/textarea 等编辑对象，因此普通按钮冒泡到 viewport 后启动 box gesture、调用 `setPointerCapture` 并 `preventDefault`，干扰后续原生 click。

`studio/src/App.tsx` 的 `zoom-control` wrapper 现用 `onPointerDown={event => event.stopPropagation()}` 隔离指针起点。没有 preventDefault，缩小、百分比重置、放大和适合画布按钮继续使用现有 onClick。键盘按钮激活仍使用默认事件路径。

pointerup 没有新 canvas gesture 时直接返回；原来从画布开始并已经捕获的拖动仍由 viewport 结束。wheel 未被拦截，继续使用既有 viewport 滚轮缩放合同。这次修复不改 core、source、document/history、pin 或 publication export。

源码前后 SHA256 及具体故障保存在 `docs/evidence/m4-zoom-control-fix.json`，TypeScript 检查日志为 `m4-zoom-control-typescript-check.txt`。构建后的原生按钮点击、显示百分比和浏览器截图由主流程单独验证；源码修复记录不代替实际浏览器结果。


最终生产构建 `index-oH4Ot2L9.js` 的真实按钮复核已完成：放大14%→16%、100%按钮及缩小100%→83%都能提交相机状态。[实际手势记录](evidence/m4-actual-gesture-zoom-current.json)明确保留并标记修复前无效的zoom尝试；修复后 `encoder.0.feedforward.expand` 从(170,996)拖至(202,1016)，undo恢复、redo/reexpand恢复，save/reopen保持。pin在100%视口外，不将这份记录宣传为可见pin体验通过；没有drag原生延迟或过程FPS认证。[最终39项视觉封包](evidence/browser-visual-matrix-zoom-full/manifest.json)绑定此构建并通过文件一致性，人工验收仍待执行。当前core54/54无skip，后续此一行UI事件修复通过strict TypeScript/build和actualUI，未增加镜像测试。
