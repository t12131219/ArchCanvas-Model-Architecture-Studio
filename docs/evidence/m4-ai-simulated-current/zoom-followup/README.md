# 缩放修复的独立读回

新资产为 `index-CC91IvNz.js` / `index--unhoRTb.css`。本子 Agent 的浏览器在尝试reload时不可用，公开inventory为空；`browser-unavailable-attempt-1.json`保留失败。本次11组真实新页面操作由root通过其可用CUA完成，原始文件位于相邻`browser-fixes/`。本Agent只读取冻结公开DOM/SVG、原尺寸图片并独立计算，真人参与者仍为0。

两种实际源图是展开Residual CNN和折叠MLP。覆盖fit→100%、100%→120%→100%，CNN另先相机向右下平移20CSS再放大。每组实际资产均一致；缩放前后同一document/revision。

`independent-root-geometry-readback.json`使用公开CSS translate/scale、SVG viewBox和viewport反推中心world。7/7转换在0.002world界限内，最大0.0012783076475102462；0.001CSS界限仅6/7，CNN fit→100%的0.0012783076475102462CSS超界。六位CSS序列化可能造成残差，但该失败保留，没有倒推抹零或加大界限。

`independent-bbox-geometry-readback.json`另从SVG直接绝对rect和同id的公开native group bbox宽/高独立求X/Y scale、translation。选择无transform且内部内容不超出body的conv1与features，不使用有shadow/Repeat外延的network。该独立方法在相同0.002world和0.001CSS界限7/7通过：maxWorld0.0002059117172166225，maxCSS0.00024709393892408116；X/Y scale差最大8.423541684177138e-7。这是公开渲染DOM几何，不是compositor或像素一致性证据。

原conv1实际“聚焦这个对象”恢复后，公开bbox中心为(621.5000152587891,378.0000305175781)，viewport中心为(621.5,378)，整个节点在视窗中。中心锚点缩放不承诺任意偏离中心的选中对象不会出界。

本Agent亲看11原尺寸截图与一张派生contact：**9有界匹配、2一步滞后失败**，详见`independent-pixel-review.json`。03-cnn-plus公开scale1.2但截图badge100%、card宽194，显示前一02帧；04-cnn-minus公开scale1但截图badge120%、card约233，显示前一03帧。其他9帧在zoom badge、card宽和位置的审查范围与DOM一致。两个失败不被7/7几何通过覆盖，不将其解读为新代码的实际缩放失效或全帧呈现正确性。

本次没有新增模型执行、源文件改写、真人小白/研究者记录、出版尺寸审看、全局箭头最少交叉认证或presented FPS结论。
