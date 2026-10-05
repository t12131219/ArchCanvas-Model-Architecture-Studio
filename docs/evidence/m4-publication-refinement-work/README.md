# M4 出版换行、尺寸与缓存收束

最终正式构建为 `index-DPwoyNJW.js`（CSS仍为`index-DK5lov-h.css`）。本轮从正式需求继续实现，没有采用旧工程代码。

英文说明优先整词换行，超长标识符才按Unicode码点回退；Scene和SVG共用换行结果。导出默认整图，详情容器按完整路径和序号显式选择；支持25–1000mm自定义宽度，显示实际页高和字号，7pt只是起点。建议尺寸超出1000mm宽/5000mm高时不提供采用按钮；5000mm高是现有出版器预算，不是期刊标准。v2缓存保留精确Scene SVG，画布版本相同而渲染结果改变仍使旧导出失效。

79/79 Studio、严格TypeScript/build与纯正式副本build通过；10项出版/详情Python专项通过。首个Python调用缺PYTHONPATH及sandbox socket失败日志完整保留，随后按正式路径和必要loopback权限执行通过。Python旧219、旧observer32等保持各自历史范围，不累加。

`browser-journal-final.json`包含11项最终构建的公开DOM/AX及原生浏览器截图。两输入为此前实际保存的Transformer L3 rev33和CNN rev39在新隔离8886目录中的副本，未通过本轮编辑制造新revision。真实UI验证whole85/236、FFN85/86、SVG/PDF实际生成、invalid24禁用、CNN整词两行及v1缓存拒绝/v2缓存恢复。`final-export-bindings.json`按每次实际观察的链接复制3个服务导出，而不是推断服务目录或沿用闭包里的旧URL。

Transformer整图85mm最小字仍2.530934pt。EncoderLayer1的feedforward详情86mm最小字7.025347pt、高263.700288mm，显示3条跨边界绑定；SVG和PDF从同一Scene生成。整图增到236mm需要约784.8mm高，不能把数值过7pt当作普通单页出版通过。CNN说明在实际SVG按“...skip”与“path.”两行呈现。当前代表验证不是新完整39矩阵，也不重做旧编辑任务或认证真人审美/字体/印样。

`initial-*`与原`browser-journal.json`、`actual-exports/`及`independent-audit.*`保留中间构建事实：原journal有3个Dzpr与9个Qpo记录，Qpo有3张截图滞后于对应DOM。它们与`final-*`/`final-actual-exports/`分开，不重新标记为最终构建。最终独立复核另存`independent-final-audit.*`。

服务最初session90378退出143，页面实际failed-fetch；恢复原8886端口和数据目录后重试CNN成功，生命周期记录保留，失败请求不计作成功。用户8765画布和五个真人席位未操作。

新的`.archcanvas/m4-research-trial-publication-final`冻结58个实施绑定，S01–S05 ports8881–8885均pristine、unassigned、uncollected，研究者0。旧pan/annotation与中间publication包保持原件但对新版stale。

M4仍partial。新版完整矩阵、人审、固定硬件/解析字体、连续presented-frame性能、原生取消和3–5实际研究者任务仍待完成；证据边界见verification-summary与最终独立审计。
