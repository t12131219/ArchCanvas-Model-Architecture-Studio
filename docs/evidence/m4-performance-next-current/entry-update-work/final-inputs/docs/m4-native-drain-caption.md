# M4：观测队列边界与派生连线标签

2026-10-06。当前构建 `index-BTw7OHsD.js` / `index--unhoRTb.css`。本阶段修复性能观测队列的结束／重置边界，并让派生标签避开局部障碍。M4 **partial**，M5 **not_started**，真人参与者 **0**。上一阶段的三个 AI 模拟角色保持原版本限定，不计入真人验收。正式工程独立运行，没有采用旧版 runtime 或代码片段。

`PerformanceObserver` 的 callback 与 `takeRecords()` 共用入口；snapshot 收取已入队的 event/longtask，reset 丢弃旧队列并过滤开始于重置之前的迟到条目。结束时不再漏掉已经入队但尚未回调的数据，也不会把前一轮记录混入下一轮。这不保证未来异步 Event Timing 全部送达，也没有建立完整连续输入分母。[独立边界回归](evidence/m4-performance-next-current/contract-review/receipt.json)保存旧实现0/4失败和修复后的24/24相关检查。

派生连线标签使用9单位字高的名义包围盒，在±64世界单位内避开卡片／重复背板、展开标题、说明、其他标签及无关连线。已有安全标签保留，无法找到局部位置时保留原位置并提示 `layout-edge-label-blocked`。同一逻辑应用于画布和详情导出；不改节点坐标、路径、端口绑定、源码、IR或CanvasDocument。[源码支持的独立检查](evidence/m4-visual-next-current/review/README.md)覆盖三种模型与36种Scene／SVG组合，相关34项测试包含7项新回归。

Transformer L0 的 `memory` 从(280.5,436.1)移至(280.5,388.1)，所属路径保持 `M281444.1 H316`。实际浏览器100%文字框没有与卡片／背板／展开标题相交；保存后重选原文档，标签坐标和文档身份保持。但它距所属短箭头56世界单位，关联偏弱。[独立视觉复核](evidence/m4-visual-next-current/review/association-followup/README.md)确认，仅换候选排序仍不足以解决；所属连线距离约束／明确引导线是后续工作，22个安全缩短路径候选也尚未实现。标签避障不是全局视觉通过。

统一验证为 **Studio358/358、零跳过，严格TypeScript／Vite构建退出0，出版边界9/9**，绑定103份源码／测试／配置和3份构建产物。[最终收据](evidence/m4-performance-next-current/checks-final-attempt-2/receipt.json)与[首轮357/358失败](evidence/m4-performance-next-current/checks-final-attempt-1/receipt.json)均保留。首轮仅旧整Scene金样冻结了此次有意改变的memory标签Y；测试现在只归一化这一字段后比较其余Scene，并另用源码回归检查标签安全，没有重写金样。

新构建的三次原生展开／收起耗时160、72、160 ms，3/3有源码／版本绑定和一对一Event Timing匹配，p95 **160 ms**。[完整原始值和收据](evidence/m4-performance-next-current/final-native-browser/README.md)保留无输入setup尝试。窗口1102×835、实际画布672×641，304正文仅6个与画布视口相交、4个全入；浮层可能进一步遮挡。rAF回调58.605 Hz不是实际呈现帧率，45条Event Timing不是全输入分母，零pins不能认证无关固定对象。旧B_XH诊断224/72/160 ms用不同窗口／视口，不形成A/B或性能改善证据。

[实际浏览器与完整导出](evidence/m4-performance-next-current/final-browser/README.md)包含同文档整图180 mm SVG和根详情180 mm SVG，分别最小6.60 pt／7.42 pt；尺寸算术不等于真人出版审看。03截图像素滞后于DOM，05 reload重开了共用last-active stress工程，首次默认PDF生成后等待自动下载的观察超时均原样保留。06显式重选Transformer、07实际100%和09自然视口为后续准确观察；临时视口已复原。模型未执行。

新研究包 `.archcanvas/m4-research-trial-btw-current` 的manifest SHA256为 `8a8be05f0ebbfde11e4fa208bee1b7e12a5a49f7e7cc74529e5215d4416b3a96`。[独立准备核验](evidence/m4-performance-next-current/research-final-preparation/report.json)280/280，5个未分配席位注册43551–43555，没有启动席位服务或收集真人记录。20个旧包342文件保留；B_XH包现在过期。左侧模块库仍为17基础类型／3透明预制起点，上轮三个AI角色的四方向操作、从零搭建与预制使用记录保留，不宣称覆盖真人小白或任意模块执行。

下一步应解决标签与所属连线的明确关联、审查并实现必要路径简化，再取得300个实际可见对象的连续输入／呈现帧率证据。固定硬件字体与三轮配对、无关pins、真实研究者五步任务和85／180 mm真人审看仍开放。入口[当前验收状态](evidence/m4-current-gate-audit.json)保持这些边界。

本轮变更前121份精确快照见[档案](evidence/m4-performance-next-current/before-change/manifest.json)。旧收据／manifest不回写；旧可变入口／源码绑定通过对应精确快照解析。阶段证据入口见[索引](evidence/m4-performance-next-current/README.md)。
