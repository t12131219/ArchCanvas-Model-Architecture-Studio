# M4 验收记录：泛化与体验收敛

M4已有多家族静态holdout、事实显示、详情导出与受限视觉/运行流程。当前出版修正构建为 `index-DPwoyNJW.js` / `index-DK5lov-h.css`：词边界换行、完整路径/序号的显式详情选择、自定义宽度25–1000mm/页高5000mm限制、建议宽度按钮和v2 exact-SVG导出缓存已实现。Studio79/79、strict TypeScript/build、纯正式副本发行核对与publication/detail Python10/10通过，各suite分列。旧DWp39矩阵、其字段/AI像素审计和pan五席包属于历史，已在[修正前归档](evidence/before-publication-refinement/manifest.json)保留，不能计当前coverage。8886代表链单列；8887当前39例/234工件已封存并完成受限字段/AI像素末审。M4仍partial，39例人工审看、密集图可读性、固定性能、原生取消和3–5真人任务仍未完成。本阶段不重跑既有79Studio/9独立性日志，Python10仍较早Qpo。

## 当前状态

| 门 | 状态 | 证据与边界 |
|---|---|---|
| M4-01 无模板家族 holdout | 通过（有界） | 6/6 独立手写静态 oracle，覆盖 ViT、LSTM Temporal、U-Net-style skip/repeat、GNN/SSM unknown/dynamic 和 Conv1d 负例。[家族范围](m4-holdout.md) |
| M4-02 shared / repeat / opaque | 通过（已声明样本） | 共享 projection 两次调用保持不同 call identity；对象面板与图内短说明展示共享实例、返回槽位和未知边界，SVG metadata 保留完整 canonical 事实与绘制映射。独立 sourceFacts 5/5 及三入口实际保存/重开/导出链通过；repeat 明示 independent/shared instances。普通 Add 不再按左右位置猜残差；12 项独立源码旁路/opaque/多输出反例通过。[事实显示范围](m4-source-facts.md) |
| M4-03 独立工程回归 | 通过（各自快照） | 既有[Studio79/79](evidence/m4-publication-refinement-work/studio-tests-final.txt)无skip、strict TypeScript/[build](evidence/m4-publication-refinement-work/build-final.txt)/[纯正式副本核对](evidence/m4-publication-refinement-work/independence-final.txt)通过；[publication/detail Python10/10](evidence/m4-publication-refinement-work/publication-detail-python-tests.txt)通过，旧import/socket失败日志保留。旧Python219runtime、collector8、研究链12、sourceFacts5、输入工具32分别保留历史快照，不累加；不执行失败原型。 |
| 独立支持边界：新家族运行 | 未认证，非本阶段静态硬出口 | M3 的运行 profile 是声明输入、CPU、有限样本；新 holdouts 不含独立 concrete shape/backward/numerical equivalence 证据，不能宣称这类运行支持。 |
| M4-05 真浏览器性能 | 历史已测，当前完整门未认证 | 旧DWp v2四pan终点及p95 2008/2024ms仅绑定旧build，持续pointermove为DOM proxy。8886代表链与8887完整矩阵均不新增固定性能或原生取消证据；固定硬件/解析字体、持续presented paint和性能目标未通过。[范围](m4-performance.md) |
| M4-06 空间连续性与出版 | 当前工件齐全；字段/AI像素一致通过，人审待完成 | [当前矩阵](evidence/browser-visual-matrix-publication-final/manifest.json)36基础＋3模型各一编辑后、39例/234工件，missing为空；[独立末审](evidence/m4-publication-matrix-work/independent-final-audit.md)核39DOM/实际SVG/截图/直接links和3组SVGundo/redo/save-reopen，5AX值差异与CNN过渡状态公开保留。artifactCoverage=complete，visualAcceptance=pending-human-review/false。8886详情/预检代表仍另列，旧DWp39不计本次。 |
| M4-07 研究者任务 | 最终出版五席准备就绪，人工未执行 | `.archcanvas/m4-research-trial-publication-final`，[prepare](evidence/m4-publication-refinement-work/research-preparation-final.json)/[verify](evidence/m4-publication-refinement-work/research-verification-final.json)通过，58实施文件、五席8881–8885，0分配/0收集/0真人。旧pan及中间publication包stale。Study五步自报与automation仍不计真人，任务/出版审看未完成。 |

## 当前完整矩阵与已提交编辑的范围

[manifest](evidence/browser-visual-matrix-publication-final/manifest.json) SHA256 `55df9000f42857bca9dc8ce2f75fe097b99ea90fae94ad077810225e05162593`，[spec](../.archcanvas/browser-visual-matrix-publication-final/spec.json) SHA256 `847b40ea74b474c2853263abd9557971af9cf386ef1f51c8f3194e1ee1d45625`，九源码frontier×85/180mm×彩色/黑白为36基线，另三模型各一编辑后，不表示36配置都执行编辑。[独立末审JSON](evidence/m4-publication-matrix-work/independent-final-audit.json) SHA256 `8fe586a4e531d74b63baeb963875e8ff12e8bb151834d742411bb16710ae50e2`为passed-with-explicit-observations：39XML/转换字节/直接服务文件精确，39截图实际重看无明显状态不一致；352raw＋352映射、313不变＋39receipt只加两hash、234sealed一致。仅4处metadata.heightMm JSON浮点用1e−9窄容差，XML仍精确。

19[编辑UI记录](evidence/m4-publication-matrix-work/edited-ui-journal.json)支持3undo/3redo除revision整XML一致、3save/reopen＋3reopen/finalraw字节一致。CNN/MLP/Transformer最终paper180 rev32/18/41、storage14/10/18；CNN最终L0、MLP L1、Transformer L0。CNN第一added的latent子flags不组成L2；5AX输入值与SVG不同原因未知，未认证输入同步。Save处理中footer不认完成，随后reopen才有持久化证据；临时wrapper在正式39stamp/collect已exit0之后异常保留。

viewport来自8887DOM，UA/DPR来自同IAB旧8880observer；字体/硬件未知。36基线10项最小字≥7pt、0满足组合示例；深图14–26%fit不认证细字/端点，旧wholeL3/85≈2.53pt结论不由详情页取代。下一门是39例六维人工review与实际尺寸/密集图可读性、固定持续paint/FPS、活动手势原生cancel和3–5真人任务。[取消只读审计](evidence/m4-publication-matrix-work/gesture-cancellation-audit.md)只有代码/既有测试，hidden-only为增强建议，没有现存明文合同。

[矩阵前15原件归档](evidence/before-publication-final-matrix/README.md)保留旧11docs＋4收据；旧publication-refinement manifest current-doc paths在更新后通过files/<原路径>核旧bytes，不修改原manifest。末审后的5次输入诊断与服务恢复单列在[work说明](evidence/m4-publication-matrix-work/README.md)，不解释旧5AX、不计矩阵/性能或独立末审结果。

## 较早同构建的出版行为与代表证据

英文词/标识符在能容纳时保持整体，超长token仍逐字符拆分；不会声称全部字体/排字正确。导出默认整图，详情按展开容器的完整层级路径和序号显式选，不自动收缩范围或改Canvas展开。宽度25–1000mm、页高≤5000mm，低于7pt可采用建议宽，但建议页高也须核目标版面。UI数字为两位小数，FFN85显示6.94pt且真实值6.943656539772626<7；86mm真实值7.02534661553473显示7.03，页高263.700288184438mm，不能沿用旧renderer257.69mm。整图236mm高784.8mm，不等于适合目标期刊。

导出缓存v2 envelope保留生成scene SVG字节并在复用时与当前渲染精确比较；旧v1、同revision但不同renderer/Scene结果均失效。旧包/39矩阵因产品改变stale；新publication-final包仅核冻结基线/58实施文件/build，零真人。旧initial/12条中间journal与最终journal分别阅读，不将中间截图或代表UI当当前矩阵/出版通过。

最终journal精确11条，全绑定DPwoy；范围为Transformer/CNN两份基线Canvas与三次实际导出。CNN rev39整图180mm最小8.58pt、node11.15pt、高309.5mm（receipt实际309.47899159663865mm），说明两行保持“…with its skip”/“path.”；当前SVG正文相同。v1缓存初始无links，重新生成当前SVG后v2恢复同一链接。[最终文件绑定](evidence/m4-publication-refinement-work/final-export-bindings.json)保留两SVG/一PDF；PDF生成不证明已在浏览器打开或实际尺寸阅读。[生命周期摘要](evidence/m4-publication-refinement-work/service-lifecycle.json)记录服务failed fetch/退出143和同端口/数据目录恢复；未封存失败浏览器状态/原始退出日志，失败不计成功。

[最终独立审计](evidence/m4-publication-refinement-work/independent-final-audit.md)受限通过：11主Canvas与实看截图、9预览、5详情选项、3直接链接工件精确相符，无截图状态滞后；2SVG转换字节和1PDF真实单页尺寸通过。它读取既有79Studio/build/独立性记录，不重跑套件；Python10记录仍属较早Qpo范围，发布runtime/core未变，无最终JS轮次重跑。缓存原始envelope未封存，renderer改变拒绝仅2纯函数反例，服务失败历史为根工具响应事后摘要、退出原因未知。上述8886字段/文件/AI像素核对不替代单独的8887矩阵、人工或性能验收。

以下从“历史UI改善”开始保留旧pan/annotation及更早快照，旧“当前/本轮”均指其当时DWp或旧build。

## 历史 UI 改善的边界

四次v2 hand pan从普通图区、展开控件与输入端口开始，最终camera分别+80/+48、+32/+20、+24/+16、+20/+12，公开SVG/frontier/pins保持一致；选择模式端口仍proposal。Transformer代表pan另核+64/+40、十快照viewport固定，公开字段一致，但选择记录与status文案不完全一致，不据此认证隐藏selection/history。观测器/独立validator[32/32详细反例](evidence/m4-pan-annotation-work/observer-tests-expanded.txt)与Studio68项分开；模态guard取得实际按键证据；进行中gesture取消目前只有pure tests/代码证据，没有原生cancel样本。

说明从(0,1445)移到(50,1885)，正文冲突由1变0；undo/redo、重复执行不新增revision、新说明(50,1944)和保存重开rev23有实际链。保存文档相较基线只改revision/annotations，source/IR与其它视觉字段精确不变。此处正文矩形检查不含连线/marker/页头/字体塑形；reopen改变camera且清空会话history。当前SVG已实际打开，PDF仅生成和文件绑定验证；85mm minText≈2.896pt仍待真实尺寸审看。

当前[研究包收据](evidence/research-trial/pan-annotation-build/preparation-verification.json)核57实施文件、3build文件和12额外helper/observer绑定，只证明五席pristine未分配。当前矩阵36/36基础＋3/3模型编辑后工件完整，39case/234准则人工pending；它与零真人五席准备分开，automation不能补成人类完成门。

[20份公开编辑journal](evidence/m4-pan-annotation-matrix-corrected/edited-ui-journal.json)记录三模型说明文本undo/redo、save/reopen，Transformer/CNN回L0放置说明，MLP为L1，最终paper180 rev54/22/39（storage18/10/14另计）。保存重开的SVG/revision对应当时状态；随后配色/页宽重切、再次保存导出，final工件不等于立即reopen快照。采集helper旧URL复制错37项，修正按38项完整Canvas/formatSVG唯一匹配实际服务导出；[账本](evidence/m4-pan-annotation-matrix-corrected/export-copy-correction.json)和原raw保留，截图/时间/DOM/Canvas不变，不称浏览器链接复读或复采。UA/DPR来自同浏览器先前8880 observer，1280×720/DPR1；硬件/解析字体未知。AI像素观察报告密集fit小字不可可靠逐项阅读，人工门仍未通过。

以下按段保留此前源码/详情/性能/缩放build时间范围；其中“当前”“最终”指当时的绑定快照。

## 模型事实与独立性

[`m4-holdout-report.json`](evidence/m4-holdout-report.json) 以 `-I -S` 执行独立手写关系预期，无模型导入/执行。当前报告包含 6 个家族、10 个输出槽位/反例和 12 个旁路合同/反例，另有独立 Studio 3 项合同校验。ViT 为 17 节点/21 边，Temporal 为 9/8，U-Net-style 为 16/15，GraphForecast 为 7/8，DynamicStateSpace 为 5/5，UnsupportedVision 为 5/4。各结构已覆盖的 opaque 数与限制见家族报告。嵌套 dict/tuple 现在保留 key/index 的 `outputPath`；重复 producer 的不同输出身份与槽位也保留。动态键、unpack 或不可移植键将整个字典保守标为 OpaqueDictionary，不静默丢项或猜路径。该字段进入 IR digest；旧报告存档在 `evidence/before-output-path/`，旧浏览器收据仍绑定其实际历史 IR，未重写为当前分析结果。

额外 [`m4-stress-report.json`](evidence/m4-stress-report.json) 从纯正式副本静态分析 300 个显式 Linear/ReLU 声明，默认 4 节点/2 边；展开非根 network 为 304 canonical 可见节点/302 scene 边，其中 300 个是真实层对象。此压力图是测量数据规模，不是模型性能或科学合理性证明。[场景说明](m4-stress-scenario.md)

对象事实的独立证据见 [`source-facts/report.json`](evidence/source-facts/report.json)：Temporal 两个 Linear 调用按 instance identity 分组，四个完整 outputPath 明示；Skip 的两个 repeat 成员保持独立，GNN 名称/任意显示别名不提升 opaque。当前 Scene/SVG 增加整个源架构的 `sourceFacts` 与本页 `renderedNodes`/`renderedBindings`；源/IR digest 和 Architecture/Canvas schema 不变，Scene/SVG 字节改变。旧原生、详情和黄金图收据只证明它们记录的历史 renderer/build，不冒充当前版本绑定。

[`m4-python-tests.txt`](evidence/m4-python-tests.txt) 记录全套 166/166、285.507 秒；[`m4-detail-tests.txt`](evidence/m4-detail-tests.txt) 和 [`m4-server-tests.txt`](evidence/m4-server-tests.txt) 记录新增/更新的 3/3 与 7/7，无 skip。默认沙盒不支持 loopback/namespace 的尝试不当作产品回归，最终证据使用正式 `.venv` 与实际隔离可用的宿主运行。

## 详情页与尺寸预检

[`detail-export/report.json`](evidence/detail-export/report.json) 记录独立副本、模块来源、共享渲染器摘要，以及 MLP/Transformer feedforward 在 85/180 mm 的 SVG/PDF/PNG 和收据。跨边界数据保留原始 tensor/role/port 身份；隐藏 adapter、无关边与区域外 annotation 明确列入 metadata。宽度只影响导出工件，不改 CanvasDocument 或源码。

样本 85 mm 最小文字 6.94 pt，180 mm 为 14.70 pt。7 pt 是可调整的建议值；界面说明并不代表期刊通用规则。真实浏览器额外测试了较大的 Encoder 详情：85 mm 最小文字 5.6 pt，建议至少 106 mm，12 条 crossing 全部保留。已验证显示别名/填充保存刷新保留与 SVG 生成，截图为 [`m4-detail-studio-final.jpg`](evidence/m4-detail-studio-final.jpg)；实际浏览器生成的 [SVG](evidence/m4-browser-encoder-detail.svg)、[CanvasDocument](evidence/m4-browser-encoder.canvas.json) 与 [收据](evidence/m4-browser-encoder-detail.svg.receipt.json) 已保存在正式证据目录，独立核对 revision 4、source/IR、SVG digest 和 12 条 crossing 一致。

## 性能与人工门

原始采样有 source/IR/revision 绑定，最终两份诊断还各有操作前 2 秒 idle frame baseline；两帧延迟从 typed handler 入口计时，排除事件队列，因此不是 INP 或计划要求的完整 input-to-paint。synthetic 点击与独立 Event Timing entries 分开，未用空 entries 声称 native 输入达标。帧统计同时覆盖展开/收起序列，不是静止画布的空闲 FPS。

全套测试并发时的小前沿记录为展开 p95 126.5 ms、28.07 FPS；另一轮约 1 秒帧间隔。新增 visibility 后，页面 start/end 均 visible/focused、无 changes，仍观察到约 990 ms 和 2.5 FPS，故暂不能将原因简单归为后台节流。全部结果保留，具体环境和限制见性能页。最终主收据不能用更早较快的一轮替换。

最终诊断比较了 8→10→8 的小前沿和 4→304→4 的源码压力前沿：空闲 FPS 分别约 1.01/1.02，idle frame p95 都为 1000 ms；操作 FPS 约 1.68/1.33，展开 proxy p95 为 996.4/1005.4 ms，压力收起 proxy p95 为 1955.2 ms。handler 同步耗时 p95 小前沿展开/收起为 1.8/1.9 ms、压力为 44.1/40.0 ms；此值只测 typed operation 的同步处理，排除 React render/SVG commit 和 frame 等待。压力最大 long task 为 101 ms。空闲同样有一秒节律说明环境/调度限制参与测量，不能单凭这条证据排除产品渲染开销或认证目标。原始 JSON 保留全部 trial、事件与实际路径。

早期研究任务 smoke 只验证了部分流程，标记 automation/abandoned，汇总正确输出 0 位研究者与 `not_run`；后续完整 automation 链见末节，两者均排除真人分母。完整 M4 出口仍需固定目标浏览器/机器的实际输入与屏幕连续性测量、真实用户研究、完整视觉黄金矩阵及出版工件人工审看。计划 §18.5 的 300 对象 ≤50 ms/≥50 FPS、展开 <500 ms、锚点 ≤8 px、无关 pin 0 和 ≥80%/3 分钟明确是 Beta 目标；本阶段继续按原阈值测量，不降低数值或额外发明运行硬门。M5 三宿主和发行认证没有被本阶段自动通过。

本轮追加 scene 索引优化保留完整 baseline 文档/历史/场景/SVG 一致性，独立 core 展开 p95 38.78→20.07 ms，不能替代浏览器延迟。原生采样新增目标身份/展开状态、Event Timing 和屏幕/画布双坐标；初轮工程冒烟与硬化前后证据分开保存，详见 [性能页](m4-performance.md)。研究试用包补齐每席位独立服务目录、冻结相同基线和实际工件 hash 链，包准备不算真人任务通过。

拖动预览把文档校验/clone放在gesture开始，每帧保留同一 scene/serializer，正式松开仍通过guarded history；版本变化取消旧gesture。300层独立CPU对比中，frame→scene p95 14.32→5.75 ms，SVG serializer未优化，完整Scene/SVG及commit/undo/redo等价核对通过。这是CPU阶段数据，不是native latency、FPS或性能门通过，详见 [拖动证据](m4-drag-preview.md)。

[浏览器矩阵 collector 的独立8项检查](evidence/browser-visual-matrix-tests/report.json)只核文件/source/DOM/export/build/字节快照合同，其测试真实截图数为0，不能替代另行采集的浏览器画面。实际[修复前39项矩阵](evidence/browser-visual-matrix-before-intrusion-fix/manifest.json)已封存（36基础＋三模型各一编辑后），绑定`index-D1WyCZV8.js`；artifactCoverage=complete，humanAcceptanceCertified=false、visualAcceptance=pending-human-review。它不表示36个配置都执行了编辑或真人任务。

[展开空白修复](m4-expansion-intrusion.md)仅让已有空位先吸收container增长，剩余实际侵入才推动邻居；新序列中Transformer二级projection前空白1130→38px、scene高3474→2382px，属独立core数据。已有保存布局/cache不会自动压缩或迁移。当时54项core回归绑定prezoom `index-CkE1Vwsy.js`。随后App在zoom-control停止pointerdown冒泡、保留按钮click，当时`index-oH4Ot2L9.js`通过strict TypeScript与生产build（CSS `index-BO7yZQLO.css`不变）。[实际UI记录](evidence/m4-actual-gesture-zoom-current.json)验证14→16%、100%复位、100→83%，节点移动+32/+20、undo/redo、收起/重展开同位置恢复；[先导代表保存/重开截图](evidence/browser-visual-zoom-current/transformer-gesture-saved-reopened/screenshot.jpg)保留实际Canvas/SVG链。该缩放版本全部基础前沿/配色/尺寸36组合与三模型各一编辑后已复采封存，字体与出版人工审看仍待完成。

[缩放修复前原生收据](evidence/m4-native-performance-intrusion-current.json)及[独立一致性核对](evidence/m4-native-performance-intrusion-current-validation.json)为9次采样、8次Event Timing匹配，p95 3024ms、约2.01FPS、screen/pin位移0；其环境/build保持历史，不认证当前缩放版本。实际UI已提交位置核对也不测中间drag帧率或native drag input-to-paint。

[历史缩放39项浏览器矩阵](evidence/browser-visual-matrix-zoom-full/manifest.json)绑定`index-oH4Ot2L9.js`：capturedBaselineCount=36/36，Transformer/MLP/CNN各一编辑后，两个missing列表为空，artifactCoverage=complete、humanAcceptanceCertified=false、visualAcceptance=pending-human-review。它来自实际独立复采，不表示36配置全部经过编辑/undo/保存任务，也不自动认证字体、物理出版或真人任务。[先导4项封包](evidence/browser-visual-matrix-zoom-current/manifest.json)保留原2/36基础覆盖和两Transformer编辑后范围，修复前39项保持历史绑定。先导L2实际projection y2086、Encoder底2048、gap38px、viewBox892×2382。

基础 MLP/CNN 另有 [完整手写源码 oracle](m4-base-models.md)：11/11（两模型和九项腐坏反例）在正式独立副本通过，覆盖全部端口、producer/tensor、containment、repeat 与 instance/call。它推动发现并修复 CNN `x + residual` 中右侧旁路错标；当前证据 frontend hash 与正式源码一致。holdout 最终副本为 Python 28/28（家族 6、输出槽位 10、旁路 12）及 Studio 输出路径 3/3。试用包已生成五个未分配席位；[历史公开准备收据](evidence/research-trial/current-zoom-build/preparation-verification.json)明确assignments=0、researcherCount=0。工件链工具最终独立12/12，通过不产生人工结论；采集只复制已验证字节快照，SVG从当前文档重建并按正式规则规范化后精确核对，拒绝图与收据同步篡改。

Python全套历史快照日志为 [`m4-python-tests-final.txt`](evidence/m4-python-tests-final.txt)。sourceFacts/拖动版本46项日志保留于[`m4-drag-studio-tests.txt`](evidence/m4-drag-studio-tests.txt)，追加布局8项的独立54项core回归见[布局修复记录](m4-expansion-intrusion.md)。随后App缩放修复的actual UI与strict TypeScript/build为独立验证，该缩放生产build记录于[`m4-studio-build-zoom-current.txt`](evidence/m4-studio-build-zoom-current.txt)。此前166/195项Python全套和26/35/46项Studio记录保留其历史范围，不拼接成当前全套数字。

全套219项运行之后，研究工件链追加快照/规范化SVG核对（独立12/12），矩阵collector追加独立8/8，Studio追加sourceFacts、拖动、展开布局和最小App缩放修复；没有重新宣称Python全套新总数。当时已冻结并verify `.archcanvas/m4-research-trial-zoom-final` 五个独立未分配席位（S01–S05、8871–8875），相同pristine rev0 envelope，exports/projects/transactions为空，assignment/collected/researcher均为0。[历史准备收据](evidence/research-trial/current-zoom-build/preparation-verification.json)只核基线/工具/build，包manifest SHA256为`daeaec0137a0950ca93ca904574987e298f68eb45e6990fd3326d9be37f365b0`。current、ready、ready-final、intrusion-final四旧包实际verify失败，完整保留并[单列stale](evidence/research-trial/current-zoom-build/stale-packages.json)，不能分配新参与者。

2026-10-05 较早追加[独立输入观测](m4-input-observation.md)：当时未修改 production build 在隔离测量服务完成 MLP 六操作、304 对象展开/拖动/undo/redo 与可信滚轮；源绑定、完整所选事实的历史恢复和 Save/重开分别验证。离散匹配 p95 2016ms，rAF 回调仍慢，连续手势只给 DOM proxy；简单页面也有一秒停顿，因果尚不明确。测量工具24项独立反例通过，不累加历史产品suite、不宣称性能认证。当时pan尚未覆盖；当前已有终点证据，固定原生环境、持续呈现、真人审看和3–5研究者仍待完成（当前工件矩阵已完整）；[真人交接](m4-human-review-handoff.md)已具备，实际参与0。

## 同文档完整任务与后续对照（2026-10-05 Asia/Shanghai）

[独立 automation 任务包](evidence/automation-full-task/README.md)从 pristine Transformer 开始，以实际 UI 连续完成展开、显示别名/填充、图例、说明、边样式、85 mm 黑白页、固定、节点 +32/+20、undo/redo、保存刷新重开，以及 SVG/PDF 生成。最终 revision 18；两个导出输入与保存 Canvas 相同。S01 明确 `AUTOMATION_M4_FULL`/automation，五步自报完成，末 checkpoint 1,230,519 ms、wall-clock/collector 1,230,520 ms，含等待，不构成三分钟真人成功。checkpoint2 后才追加 FFN/edge 等增强，未回写原记录时间。

目标位移与 canvas 历史恢复通过，严格“其它几何全不变”预期未通过：四个祖先容器宽各增长 32，三条非直接目标连线改道；undo 恢复原几何。视口变化也使全体 screen rect 比较失败，不能当固定环境连续性认证。固定对象 canvas 位置未变，但 focused100% 时在屏幕外。说明创建前的 viewBox 未采，初始位置公式与 native trusted 输入链仍未知。SVG 实际打开后观察到 85 mm 最小文字约 2.8 pt，以及说明跨过 Add/残差区；PDF 实际 URL 打开为空白，浏览器可读性未验证。独立工具和收集字节校验不替代出版通过。

[后续简单页面控制](evidence/m4-visible-host-control/README.md)前后宿主 capability 返回 true，20 秒仍仅 40 次 rAF、匹配交互 1016 ms；后读数晚于窗口结束 54.5637 秒，非连续呈现证据。原 validator 的 unconfirmed 结果保持原样，因果诊断未完成。该控制诊断时产品源码/dist、原39矩阵和五个真人席位冻结不变；真实研究者仍 0，M4 仍 partial。
