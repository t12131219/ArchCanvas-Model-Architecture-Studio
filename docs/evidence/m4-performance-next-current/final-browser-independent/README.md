# BTw 最终浏览器独立只读核验

2026-10-06，独立 AI 核验。正式 `.venv/bin/python` 执行 [手写脚本](audit.py)，没有导入产品实现、调用产品验证器或重跑产品套件。[报告](report.json) **90/90** 条关系断言通过，375 份审查输入前后字节一致，见 [输入绑定](input-receipt.json)。这不是 90 个 Studio 测试，也不能累加到已有测试总数。

两个新 browser manifest 的 30/51 份材料、各自相同的 107 个当前源码/构建/验证脚本绑定全部逐字节核对。版本为 `index-BTw7OHsD.js` / `index--unhoRTb.css`。既有 121 个 before 快照、旧 B_XH 的 21/15 份 browser 材料及先前六份独立报告仍完全匹配原 seal；association-followup 的新 seal 和旧 seal 也未变。

[最终原生记录](../final-native-browser/native-raw.json) 三次操作均在完整候选关系中双方唯一关联 click：160、72、160 ms，最近秩 p95 **160 ms**；interactionId 7958、7965、7972，revision 4→5→6→7，frontier 4→304→4→304。source/IR/document 不变，目标屏幕锚点为 0，无无关固定对象样本。45 条 Event Timing 包括非目标事件，不是完整输入分母。无输入的首次 setup 原样保留，不能当作成功操作。

2350 个 rAF 回调构成 2349 个正间隔，回调频率 **58.6054 Hz**，间隔 p95 16.8 ms、最长 216.6 ms，6 个间隔超过 50 ms。它不是实际呈现 FPS。页面记录 visible/hasFocus=true，无 visibility 变化；宿主可见性、硬件和字体字节没有绑定。当前源码的 snapshot 排空已入队 observer 记录，不能强制未来异步 Event Timing 已生成或已投递；200 条保留上限仍存在。

[展开覆盖](../final-native-browser/expanded-body-coverage.json) 304 个正文矩形只有 **6 个与画布相交、4 个全入**，浮层可能遮挡，仍是几何覆盖上界。BTw 窗口 1102×835、画布 672×641；B_XH 窗口 1280×720、画布 783×526，无法据 p95 的数值差异认定修复带来性能改善。三样本 p95 高于 50 ms 目标，但这不是完整 300 个可见对象验收运行，也没有完整连续输入、配对重复固定环境或实际呈现帧数据。

[重开序列](../final-browser/receipt.json) 的首次 reload 实际选中共享 last-active 的 DenseStress300，05 标签为空且 documentId 不同，这次结果被保留。06 显式重选原 Transformer 后，才恢复同 documentId/revision 0，memory XML 仍为 `(280.5,388.1)`。保存前后镜头不同，未宣称镜头持久化。03 的 DOM 已是 100%，截图仍旧；使用亲看且稳定的 [07 图](../final-browser/07-transformer-reopened-100-settled.jpg)。另已亲看 [09 自然概览](../final-browser/09-final-natural-overview.jpg)：全图进入画布，memory 可辨但小，100% 时标签清晰且离所属短箭头较远。两图只构成 AI 的有限画面审查。

由完整 [整图 SVG](../final-browser/exports/whole-180mm/figure.svg) 和 [详情 SVG](../final-browser/exports/detail-180mm/figure.svg) 独立解析，两者均有 12 个当前 node groups / 12 个 rendered edge groups。整图 memory 为 `(280.5,388.1)`，详情为 `(265.5,400.1)`；对应边 `edge:44` 的短水平箭头分别为 y=444.1 / 456.1，**标签基线距所属边均为 56 世界单位**。当前完整 SVG 使用 `data-edge-id`；根观察器错误使用不存在的属性得到 `routes=[]` 的原件保留，这不能证明没有连线冲突。标签的实际屏幕外包矩形与卡片正文、重复背板、根标题条均无正相交；它不证明 actual glyph mask、圆角填充和字体解析正确。关联距离诊断或引导线仍未实现。

三份导出的保存 CanvasDocument 完全相同，源码内容逐字节等于正式 Transformer 的 `blocks.py` / `model.py`，sourceDigest、irDigest、49 个 sourceFacts 和 renderedBindings 与旧 B_XH 的同模型一致。各 SVG 文件 digest/bytes 与收据一致，完整 XML 可解析。整图最小字号 **6.5979 pt**、详情 **7.4186 pt** 由 viewBox/180 mm/9 世界单位字体独立重算；它们是名义尺寸，不是视觉字号或真人 85/180 mm 人审通过。

[PDF](../final-browser/exports/pdf-attempt-1/figure.pdf) 为实际文件，23164 字节、digest 与收据一致；系统 `/usr/bin/pdfinfo` 读到单页 510.236×590.877 pt，匹配 180×208.4483 mm。环境默认的 bundled pdfinfo 因 GLIBC_2.38 不可用失败，完整错误与成功系统回读均保存在 [诊断](pdf-inspection.txt)，没有安装环境或替换产物。PDF 像素、字体嵌入和实际可读性没有额外认证。

M4 仍为 partial，真人为 0。这次审查不增加模型执行、真实研究者记录、完整 300 可见对象性能或实体出版质量证据。
