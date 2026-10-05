# 实际源码视觉黄金候选审计

2026-10-04，使用正式 `fixtures/transformer`、`fixtures/mlp`、`fixtures/residual_cnn` 的现场 AST 分析建立 `CanvasDocument`。`scripts/check_visual_golds.py --png` 只调用正式 TypeScript Scene/SVG renderer 和正式 publication converter；没有独立重画或修改模型 fixture。

覆盖 Transformer 总览及 1/2/3 层展开、MLP 总览及全部可恢复层级、Residual CNN 总览及 1/2 层展开；每个 frontier 生成彩色/黑白 × 85/180 mm，共 36 份 SVG 和 300 DPI PNG。PNG 是出版派生产物，不能冒充 Studio 截图。浅模型没有虚构第三层。当前审计完成也不意味着固定浏览器视觉黄金验收或研究者人工评分已通过。

独立几何检查核对全部 canonical edge 覆盖（可见合束与隐藏关系）、路径端点与实际 port、同层对象交叠；独立空间任务核对每次操作锚点、另一个 pinned 输出的全局位置、折回基础 frontier 的几何。先前的 Residual CNN 多级展开有真实缺陷：内部移动后父容器的高度仍使用旧缓存，pool 与第二个 Block 相交。正式修复按目标到祖先逐级重新测量，真实源码回归反例保留在 `studio/tests/visual-fixture.test.ts`。

pin 约束有独立限制：固定的 MLP 输出原来位于 network 下方，展开 network 后，其矩形容器会覆盖输出。保持 network 操作锚点和 output pin 两处位置时，普通矩形容器无法完全避开这个空间。当前保留两处锚点并明确发出 Scene layout warning，提示移动或解除 pin；不把它记为无冲突。黄金候选使用未固定的常规布局，固定任务另外登记。

本页原始候选字号从当时 SVG 的真实 `width`、`viewBox` 和各 `font-size` 测量；下表是保留的历史全文档测量，当前新增渲染标识后的数值以新报告为准：

`字号 pt = 字号 scene units × widthMm / viewBoxWidth × 72 / 25.4`

| 实际场景 | 85 mm 节点标签 / 最小文字 | 180 mm 节点标签 / 最小文字 |
|---|---|---|
| Transformer 总览 | 4.500 / 3.116 pt | 9.530 / 6.598 pt |
| Transformer 三级展开 | 3.290 / 2.531 pt | 6.968 / 5.360 pt |
| MLP 全部展开 | 5.264 / 4.049 pt | 11.148 / 8.575 pt |
| Residual CNN 全部展开 | 4.381 / 3.370 pt | 9.277 / 7.136 pt |

计划 §13.6 的 7–9 pt 与 0.5–1 pt 是可配置起始示例，并非通用期刊规则。但小尺寸整体缩放的文字可读性仍不满足完整出版验收。当前 Export 面板会显示实际最小文字、主线 pt 与建议宽度；**选中已展开容器的详情页已经实现**，由同一 renderer 保留内部几何并显式列出 FROM/TO 边界关系，[独立详情证据](evidence/detail-export/report.json) 覆盖实际 SVG/PDF/PNG 与 85/180 mm。它改善指定详情场景，不意味着完整长文档缩放后的字小问题已消失，也不是任意自由选区导出。完整字体/线宽/留白配置、全套真实浏览器截图与逐图人工审看继续待验；36 份几何工件不能替代这些欠项。

从实际 PNG 审看，彩色和黑白均保留节点文字、glyph、repeat 标签与 mask 虚线；Transformer 总览主路两列可读，展开后画面纵向增长，完整三级页在小宽度下明显密集。黑白提供符号和文字证据，但尚无用户任务证明全部角色可快速辨识；线穿关键节点与复杂路由也仍需逐图人工检查，不能从端点正确推出已满足审美评分。

完整可再生成工件和 JSON 报告由脚本留在 `/tmp/archcanvas-visual-golds-accepted-core`；稳定证据见 `docs/evidence/visual-golds`。首期 I-03 状态为 **partial**，I-04 为 **实际 fixture core 回归通过、浏览器完整多级任务仍待验收**。这与有界 M3 结构连接出口分开；不得宣称整个首期出版产品已完成。

追加浏览器视觉矩阵时，原 `visual-golds` 目录及报告保留。新的实际 IR/core 候选已写 `visual-golds-current`，当时准备浏览器采集的 Studio 版本使用 `visual-golds-browser-build` 单列，避免新 renderer/源码事实标识修改旧证据。 [浏览器采集协议](browser-visual-matrix-protocol.md) 从实际 containment 推导九前沿 × 彩色/黑白 × 85/180 mm=36，并单列三个模型编辑后证据；MLP 仅 L0/L1、CNN 仅 L0/L1/L2，没有伪造第三层。

`browser_visual_matrix.py` 冻结 build/core 来源，校验实际 Canvas 的 source/IR/完整前沿/page、不同 UI revision、实际 DOM interactive SVG、同源规范化 publication SVG 和截图/采集收据摘要，输出联系表与人工评分模板。采集数量以收集 manifest 为准；此处不提前宣称36张实际截图或三份编辑后证据已取得。即使文件齐全，`humanAcceptanceCertified=false`、`visualAcceptance=pending-human-review` 保持不变，截图内容、字体/硬件锁定与六维评分仍需独立复核。

2026-10-04追加的 [布局修复前浏览器联系表](evidence/browser-visual-matrix-before-intrusion-fix/index.html) 已正式收集 **36基础组合+3模型各一份编辑后工件，共39份**；[manifest](evidence/browser-visual-matrix-before-intrusion-fix/manifest.json) 的 artifactCoverage=complete，没有缺失variant。它绑定历史 `index-D1WyCZV8.js` / `index-BO7yZQLO.css`，**不是后续布局修复版的视觉认证**。编辑后三份实际Canvas均改变alias与fill，由同source/IR重建DOM和实际publication SVG验证；不声称所有36配置均执行了编辑，也不将三份样本当成完整undo/save/reload或真人任务。

首次浏览器采集出现真实绘制滞后：DOM已更新，截图仍显示上一宽度/配色或尚未关闭的弹窗。 [旧paint诊断](evidence/browser-visual-paint-diagnostics/README.md) 保留24张明确错图与绑定摘要；37份旧文件即使通过DOM/Canvas/SVG检查也不能证明正确画面。完整重拍在独立服务重新打开实际UI导出Canvas，fit、取得AX状态、丢弃首次capture，再独立call保存第二次；窗口变化的MLP裁切项又用新case重拍。旧图/不统一窗口记录保留在superseded/excluded证据，不计最终39份。

最终39份的 [AI像素观察](evidence/browser-visual-pixel-observation-before-intrusion-fix/report.json) 对可见页头width/preset、frontier整体形态、无弹窗、整页与图例进入窗口逐图核查；全部1280×720、DPR1，实际图像尺寸与收据一致，没有完全相同字节的截图。它没有认证每个tiny label/参数或每条路由，报告保留此前MLP小字参数误读的更正。真人六维评分模板仍为空，`humanAcceptanceCertified=false`、`visualAcceptance=pending-human-review`。 [环境来源快照](evidence/browser-visual-pixel-observation-before-intrusion-fix/README.md) 给出主机查询、旧同build resource inventory与同IAB先前native receipt UA的真实字节摘要；这些不能推定浏览器resolved字体已锁定。

下面按最终actualUI publication receipt记录物理字号，不能用窗口Fit百分比替代印样：

| 实际UI场景 | 85 mm节点标签 / 最小文字 | 180 mm节点标签 / 最小文字 | 180 mm整页高度 |
|---|---|---|---|
| Transformer总览 | 4.500 / 3.116 pt | 9.530 / 6.598 pt | 208.4 mm |
| Transformer三级展开 | 3.290 / 2.531 pt | 6.968 / 5.360 pt | 805.1 mm |
| MLP全部展开 | 5.264 / 4.049 pt | 11.148 / 8.575 pt | 285.0 mm |
| Residual CNN全部展开 | 5.264 / 4.049 pt | 11.148 / 8.575 pt | 764.2 mm |

完整fit使页面边界可见，但Transformer L2/L3约12%/10%的窗口比例仍很小，实际UI布局下半页有大块留白、output下移。它是明确的layout/whitespace/readability限制；基础黄金布局也不覆盖pin intruding parent那类冲突场景。后续修复需重新freeze和新浏览器证据，不能沿用此历史39份宣称当前出版质量或全部首期交互已验收。

`index-oH4Ot2L9.js` / `index-BO7yZQLO.css` 缩放修复版先保留了 [代表联系表](evidence/browser-visual-matrix-zoom-current/index.html) 与 [manifest](evidence/browser-visual-matrix-zoom-current/manifest.json) 四份：**2基础**（MLP L1、CNN L2，均180mm彩色）和**2 edited**（Transformer L3手排保存重开、规定L2前沿）。该代表快照基础覆盖2/36、缺34组合，编辑后仅Transformer，artifactCoverage=incomplete；完整复采另列下文。 [代表AI像素/DOM观察](evidence/browser-visual-pixel-observation-zoom-current/README.md)核四图页头、整体层级、无弹窗、整页和图例完整，以及全部24份工件的字节摘要。人工仍pending，没有逐字或字体锁定认证。

当前规定Transformer L2 actual DOM全局projection y2086、encoder bottom2048、间距38；独立XML解析的viewBox为 **892×2382**，41可见对象，完整6项expandedIds包括decoder.feedforward。此前同前沿实际UI图是892×3474、projection y3178；这两份具体采集中的下方空白缩短1092Scene单位。额外纯collapse样本未展开decoder.feedforward，虽保存832宽的DOM和截图，已单列additional-frontier，**不计规定L2覆盖**。当前L2整页高480.7mm、最小文字5.720pt；手排后L3整页高598.6mm、最小文字5.360pt，fit约18%/14%，真实小字可读性仍待印样/详情页与人工审看。

 [当前实际UI手势原收据](evidence/m4-actual-gesture-zoom-current-raw-final.json)保留旧失效缩放状态及修后scale1、zoom-out scale0.833333。独立比较实际drag把encoder.0.feedforward.expand从(170,996)移到(202,1016)，undo恢复全部Canvas rect，redo、折回重展开、save/reopen保留手排。pin memory_mask Canvas坐标不变，但100%时screen y=-536处于窗口外，此样本不能认证可见pin体验。它只证已提交几何与保存恢复，没有native拖动延迟/中间帧率，也不能升级真人任务或整个浏览器空间门。

最终相同 `index-oH4Ot2L9.js` build已在独立8772服务通过真实source UI逐层展开、切page、UI导出与下一call稳定截图，封存 [完整构建矩阵](evidence/browser-visual-matrix-zoom-full/index.html) 和 [manifest](evidence/browser-visual-matrix-zoom-full/manifest.json)：**36基础组合+3模型各一份edited/save/reopen，共39份**，missingBaselineVariants为空，artifactCoverage=complete。 [最终AI像素与字节核查](evidence/browser-visual-pixel-observation-zoom-full/README.md)绑定234份artifact的SHA/字节长度，freeze verify仍unchanged；39图全1280×720/DPR1、无字节duplicate、页头/整体frontier/整页/图例/无modal正确。36基础page active控件可见且匹配，3edited重开是object inspector，没有假称读到了page控件。历史39、代表4与进行中记录均保留。

最终实际paper180基线L2/L3 viewBox分别892×2382、952×3166，projection y2086/2870、encoder bottom2048/2832，两处间距38；规定L2包含decoder.feedforward，L3增加两个encoder feedforward，当前没有把遗漏容器的additional前沿冒充matrix覆盖。下面按最终实际UI export receipt量测，补足两个宽度与当前build的全文大小；不是85/180mm校准印样：

| 最终实际UI场景 | 85 mm节点标签 / 最小文字 | 180 mm节点标签 / 最小文字 | 180 mm整页高度 |
|---|---|---|---|
| Transformer总览 | 4.500 / 3.116 pt | 9.530 / 6.598 pt | 208.4 mm |
| Transformer二级展开 | 3.512 / 2.701 pt | 7.436 / 5.720 pt | 480.7 mm |
| Transformer三级展开 | 3.290 / 2.531 pt | 6.968 / 5.360 pt | 598.6 mm |
| MLP全部展开 | 5.264 / 4.049 pt | 11.148 / 8.575 pt | 285.0 mm |
| Residual CNN全部展开 | 5.264 / 4.049 pt | 11.148 / 8.575 pt | 764.2 mm |

完整工件覆盖补齐浏览器文件门，但**不是人工视觉验收通过**。六维评分仍pending、`humanAcceptanceCertified=false`；85mm整体字号与Transformer180mm最小字号仍小，复杂路由、黑白角色辨识和resolved字体待独立审看。UA仅来自同IAB此前8771native实际收据，来源字节已快照绑定，不能当本轮8772 navigator读取或计时；fontloaded/零external资源不能推定fallback字体已锁。三份编辑后证据也不能推出每个36配置都执行了编辑流程、3–5位研究者完成任务或所有M4出口已通过。
