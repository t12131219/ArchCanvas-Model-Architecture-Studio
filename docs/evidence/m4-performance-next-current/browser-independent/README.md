# B_XH 浏览器诊断独立核验

2026-10-06，独立 AI 审查。此报告只读核验 B_XH 的三次原生操作、视口正文矩形与两张 Transformer 截图；它不计作真人验收，也不宣布性能门通过。

使用正式 `.venv/bin/python` 执行 [手写审查脚本](audit.py)，未导入产品代码或复用产品统计验证器。[报告](report.json) 的 **358/358** 条断言通过，其中 304 条逐节点重算视口标志；该计数不是 Studio 测试数，也不能与其他测试相加。另有 121 个既有冻结输入逐个验证，全部 160 个审查输入的字节在审查前后保持一致，见 [输入绑定](input-receipt.json)。已核封存的 21 份性能与 15 份视觉材料，以及性能 manifest 的 7 个外部绑定。

[完整原始记录](../bxh-before-drain-browser/native-raw.json) 是三次 expand / collapse / expand，版本为 `index-B_XHk-wz.js` / `index--unhoRTb.css`。静态资产名称来自各次 DOM，冻结 JS 字节 SHA-256 为 `7ac90aa9607a1a2004c2d3e6ada03602f34884039945be01d16f7cd5a01a0e8e`；这不是新构建的测量。首次截断读取仍保存在 [原始失败尝试](../bxh-before-drain-browser/native-raw-truncated-attempt-1.txt)。

独立先建立完整事件与操作候选关系，再要求双方度数均为 1。三次均唯一关联原生 click，interactionId 分别为 4046、4053、4060；事件耗时为 **224、72、160 ms**，最近秩 p95 为 **224 ms**。文档、源摘要、IR 摘要保持一致，revision 为 0→1→2→3，目标展开状态逐次翻转，DOM frontier 为 4→304→4→304。目标屏幕锚点位移为 0；没有无关固定对象样本。64 条 Event Timing 记录包含其他事件及开始采样控件的事件，不能当作 64 次完整输入验收。

记录有两条 Long Task（171、127 ms），分别在第一次和第三次原生事件时窗内相交。这个时间关系不能分离布局开销、DOM 读取开销与审查器开销。4906 个 rAF 回调组成 4905 个正间隔，跨度 82580 ms，回调频率 **59.3969 Hz**，间隔 p95 16.7 ms、最长 233.3 ms；5 个间隔超过 50 ms。rAF 是回调调度，**没有实际呈现 FPS**。页面记录的开始与结束 visibility 均为 visible / hasFocus=true，期间无变化；这不绑定宿主可见性、硬件或字体字节，也不是可见性 A/B。

[视口覆盖记录](../bxh-before-drain-browser/02-viewport-coverage.json) 针对各 canonical group 的直接正文 `rect[stroke-width]`，由采集者说明使用 `getBoundingClientRect`，不是 group 外包矩形。独立重算全部矩形与 783×526 CSS px 视口的相交关系，得到 **6 个相交、4 个完整进入**。benchmark 浮层还会遮挡视口，这只是正文矩形的几何覆盖上界，并不证明 6 个对象实际无遮挡可见，更不证明 300 个视口对象。

四个 public SVG 字符串保留采集结果；展开态字符串在 `[Truncated]` 处中断，`02-stress-expanded.json` 中字符串长度为 200011，XML 解析失败。不能用它认证完整 SVG 几何或导出一致性。完整 native raw 内的 scene/provenance 与单独矩形数组可核验；该限制未通过补造 SVG 消除。

已亲看 [54% 普通概览](../../m4-visual-next-current/bxh-browser-before/02-transformer-normal-overview.jpg) 和 [100% memory 局部图](../../m4-visual-next-current/bxh-browser-before/03-transformer-memory-local-100.jpg)。memory 在两图中仍可辨认，位于 encoder 和 decoder 的拥挤间隙。由 [标签边界记录](../../m4-visual-next-current/bxh-browser-before/memory-label-bounds.json) 独立算出，与 encoder 最后背板横向重叠 **0.269226 CSS px**、与 decoder 前板横向重叠 **0.194519 CSS px**，纵向都为 7 CSS px。`getBBox()` 不可用的失败记录保留。矩形相交不证明实际文字墨迹被圆角填充遮住；这些图片也不构成实体出版尺寸的人审。

当前诊断范围为 3 次自动化操作，无完整输入分母、重复固定环境、无关固定对象操作或实际呈现帧记录。该 B_XH observer 的采样结束没有 `takeRecords()` 排空，队列末尾条目可能遗漏；缓冲的采样前条目虽存在，本轮三次唯一关联已通过目标与时间窗排除它们。上述数据不能用于宣布 300 可见对象性能门通过。AI 参与者为 AI，真人数仍为 0。
