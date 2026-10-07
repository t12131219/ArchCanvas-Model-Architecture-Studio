# 三黄金模型浏览器视觉矩阵采集

当前（2026-10-06）构建仍为 `index-au3IB_0Q.js` / `index-B6WbMowt.css`。本轮[au3 浏览器矩阵与四向操作](m4-au3-current-matrix.md)已 collect 36 基线＋3 编辑后视图、234 工件；三个模型共12方向的实际拖动、撤销重做、保存重开有独立核对。36张fit及19张局部/编辑图分别AI审查，旧MLP右移失配保留，新起点补采单列。CNN外绕残差、窄缝拥挤、MLP边界折角和Transformer小移大改线仍是具体问题；文件完整不认证美观或出版。当前full observer保留6尝试/5完成、14eligible/10matched/4interactions、matched子集p95 3000ms；约1秒rAF间隔不是呈现帧认证。产品源码/build未改，沿用源码精确绑定的179/179、strict/build exit0；此前发行9/9是其209源码/654依赖/5symlink冻结副本范围，后续Skill文档改动不称同一完整发行字节。已有au3 4节点3边搭建链保存重开、静态生成及新工作副本保存保持独立证据；17模块＋3起点不等于逐模块完整验收。M4 partial、M5未开始，当前研究包未prepare/verify、0分配/收集/真人；AI不能替代真人。[文档更新前归档](evidence/before-m4-au3-full-matrix/manifest.json)保存此前4233绑定、24末读supplemental及两个原receipt；下方旧“当前/本轮/最终”只指各自版本和冻结时点。

历史ChS（2026-10-05）为 `index-ChS0wIgb.js`（SHA256 `05019f89f0de0c0c622df7a2cc1a13ed58477c456244c97209a0f37db79139c9`）与 `index-CsXMONBp.css`。[ChS浏览器矩阵](m4-chs-current-matrix.md)已通过正式collect：36基础＋三模型各一编辑后，共39例/234工件，artifactCoverage=complete；人工审看仍pending、真人0。17基础模块＋3透明网络起点及位置修复继续使用同一产品，既有Studio152/152、strict/build0、独立发行9项保持版本范围，本轮未重跑产品套件。新五席研究包72实施绑定、4baseline、8991–8995仅登记，0分配/收集/真人。不同tensor交叉/重叠、repeat背景叠片、说明空白和密集图字号仍是问题；presented性能/活动取消/物理出版未认证，M4 partial、未进入M5。此前799绑定加原seal共800文件已在[文档更新前归档](evidence/before-m4-chs-browser-matrix/manifest.json)逐字保留；以下历史记录只按各自版本/时点读取。

[切换前2894绑定原字节](evidence/before-m4-move-recovery-presets/manifest.json)保留旧Bc seal/status/矩阵/诊断/源码；下方历史记录中的“当前/本轮/最终”仅指其明确旧构建和冻结时点，不计新build浏览器、性能或真人认证。旧raw、seal、manifest和研究包不回写。

本轮文档更新前的478个封印绑定和旧seal原字节已[逐字节归档](evidence/before-m4-bcf-browser-matrix/manifest.json)；下方历史记录按其明确构建/时点阅读，旧失败和seal不回写。

本构建切换前的 **1277** 个封印绑定及旧seal原字节见[归档](evidence/before-m4-authoring-feedback/manifest.json)；更早327/904绑定继续通过此前归档解析。下方旧记录中的“当前/最终”仅指其绑定版本，旧浏览器矩阵、研究包和UI中间构建不继承为最终Bc证据。

[边界修正前原字节](evidence/before-m4-boundary-corrections/manifest.json)保留旧文档与3188历史绑定；下方旧版本记录不计当前构建覆盖。

计划 §13.2、§18.1 的矩阵是实际源码前沿 × 彩色/黑白 × 85/180 mm，并独立保留编辑后导出与人工审看。当前三模型有九个可恢复前沿、36 个基础组合。MLP/CNN 的浅层不能伪造到三级。

| 模型 | 总览 L0 | L1 | L2 | L3 |
|---|---|---|---|---|
| Transformer | 模型 root 展开，12 节点 | Encoder 与 Decoder，23 节点 | 两个 EncoderLayer 与 Decoder FF，41 节点 | 两个 Encoder FF，49 节点 |
| MLP | 模型 root，4 节点 | Sequential network，8 节点 | 无真实层级 | 无真实层级 |
| Residual CNN | 模型 root，8 节点 | blocks repeat，10 节点 | 两个 ResidualBlock，24 节点 | 无真实层级 |

每级包含所有此前展开容器；不是只展开一个代表 layer/block。`capture-tasks.md` 和 `spec.json` 列出完整 canonical expandedIds。九前沿 × 两预设 × 两宽度=36。至少为每个模型另留一份编辑后实际 Canvas、浏览器画面和同 revision SVG；它是额外证据，不把36份基础截图充当已编辑矩阵，不声称仅三份编辑样本就是所有配置的编辑覆盖。

## 冻结实际版本

先完成正式 Studio 源码/build，再重新生成 core 候选到新目录，保留旧目录和报告。core PNG 是出版派生物，不是 Studio 截图：

```bash
.venv/bin/python scripts/check_visual_golds.py --output docs/evidence/visual-golds-current
.venv/bin/python scripts/browser_visual_matrix.py prepare \
  --core-dir docs/evidence/visual-golds-current --output .archcanvas/browser-visual-matrix
.venv/bin/python scripts/browser_visual_matrix.py verify --matrix .archcanvas/browser-visual-matrix
```

`prepare` 从实际 Architecture 的 container parent depth 推导前沿，核对36份 Canvas 的源码/IR/展开/page，冻结 core文件、正式renderer/analyzer/publication来源和真实dist所有文件。后续源码/build有变即重新生成新路径；不得改manifest哈希以继续。它不创建浏览器截图或通过结论。

## 保存当前浏览器工件

在独立服务 data-dir 用真实 UI 打开 fixture、逐层展开全部容器、切预设/物理宽度，完成后点击保存。服务 `--data-dir` 的 `<documentId>.json` 是真实 DocumentStore envelope；复制这个文件即可取当前 Canvas，不需要依赖浏览器下载路径。每variant实际revision可以不同于core候选：检查器核source/IR/structure/frontier/page并从实际Canvas重新生成Scene，允许UI展开顺序导致的layout差异，但基础矩阵不能额外改别名/样式/图例/说明/pin。

在 UI 导出整页 SVG 后，按链接 `/api/exports/<artifactId>/figure.svg` 取得该服务workspace下 `exports/<artifactId>/figure.svg` 和 `figure.svg.receipt.json`。复制导出器实际文件/receipt；需要时额外保存此目录的 `document.json` 用于追溯。不要用 core 候选SVG替代实际服务导出。

使用实际浏览器 CUA 截图，并读取 `.publication-scene svg.outerHTML` 保存为 `browser-scene.svg`。浏览器中的SVG包含展开按钮、port hitbox，不能与publicationSVG直接字节比较。检查器独立调用正式 `renderSvg(scene,{interactive:true})`，按XML节点/属性/文本规范化比较DOM；另从同一Canvas重做publicationXML/物理尺寸规范化并逐字节核实际SVG。

截图还需核可见像素，而不是只核 DOM metadata。本次实际采集发现 DOM 已更新而截图仍显示上一状态，甚至导出弹窗尚未消失；[绘制诊断](evidence/browser-visual-paint-diagnostics/README.md) 保留24张错图的摘要与观察。每次切换模型/frontier/page后，关闭弹窗并 fit，取得 AX/DOM 状态，先请求一次截图后丢弃，再在独立 tool call 保存第二次截图；操作员随后逐图检查可见模型、展开层级、页头宽度/PAPER COLOR 或 MONOCHROME、可见时对应 inspector active 控件和整页是否入 viewport。这个顺序只是一种已观察到有效的采集办法，不能代替逐图检查。错图移入 superseded/excluded 清单，保留原工件，新 caseId 重新绑定实际 Canvas/DOM/导出/截图收据。禁止仅更新旧截图的 receipt 来掩盖像素不一致。

读取浏览器事实：SVG metadata 的 documentId/revision/source/IR/widthMm，wrapper `data-expanded-ids`，viewport/DPR/userAgent，`.paper` 的 computed transform，publicationSVG `getBoundingClientRect()`，实际载入script/link或Resource Timing assetURL。buildAsset sha256来自相应冻结dist文件并保存URL。若浏览器工具不开放 navigator/performance，保存真实 pageAssets inventory，并将UA等可用测量来自哪份同浏览器收据及其时间另写 provenance；不能伪称本次DOM读取取得。字体/硬件/具体浏览器version不能观察时留null并登记缺口，不能从UA或可见截图推定已锁定字体环境。

## 采集格式

每项目录包含 `canvas.json`、`figure.svg`、`export-receipt.json`、`screenshot.jpg`、`browser-scene.svg`、`screen-receipt.json`。36项基础记录的列表：

```json
{
  "schemaVersion": 1,
  "protocol": "archcanvas-browser-visual-matrix/1",
  "captures": [
    {
      "caseId": "transformer-level0-paper-180",
      "variantId": "transformer-level0-paper-180",
      "state": "baseline",
      "canvas": "transformer-level0-paper-180/canvas.json",
      "svg": "transformer-level0-paper-180/figure.svg",
      "exportReceipt": "transformer-level0-paper-180/export-receipt.json",
      "screenshot": "transformer-level0-paper-180/screenshot.jpg",
      "browserScene": "transformer-level0-paper-180/browser-scene.svg",
      "screenReceipt": "transformer-level0-paper-180/screen-receipt.json"
    }
  ]
}
```

路径相对列表文件所在目录。`caseId` 唯一；`variantId` 必须是spec声明的真实组合。编辑后记录使用另一caseId、`state="edited"`，variantId仍指其实际frontier/preset/width；需存在真实视觉差异。保存同源模型/不同revision可接受。重复基础组合不能覆盖先前工件。

`screen-receipt-template.json` 给出最低字段。填写实际caseId/variantId/state/capturedAt（带时区）、`captureKind="studio-browser"`、documentBinding、pageSpec、expandedIds、环境viewport/DPR/userAgent、相机transform/Scene屏幕矩形、加载JS/CSS的path/url/sha256和captureScope。filehash可用工具填入实际文件摘要，不生成任何浏览器事实：

```bash
.venv/bin/python scripts/browser_visual_matrix.py stamp-hashes \
  --receipt capture/screen-receipt.json --screenshot capture/screenshot.jpg \
  --browser-scene capture/browser-scene.svg
```

`browserSceneDigest` 是检查器的XML语义摘要，非outerHTML原始SHA256；收集manifest另外绑定原始字节。用以下命令产出不可覆盖的证据快照、36格联系表和评分模板：

```bash
.venv/bin/python scripts/browser_visual_matrix.py collect \
  --matrix .archcanvas/browser-visual-matrix --captures capture/captures.json \
  --output docs/evidence/browser-visual-matrix
```

空列表也可生成36格缺图索引；所有卡明确写“缺浏览器截图 · 正式core候选”，capturedBaselineCount=0。每份实际图展示真实截图、SVG、Canvas与采集收据，并保留source/IR/rev/build/DOM/文件摘要。验证前缓存所有工件bytes，正式core运行之后只保存同一快照，避免service后续save混包。

## 独立人工审看

manifest始终 `visualAcceptance=pending-human-review`、`humanAcceptanceCertified=false`，即使36基础和3编辑后工件全部齐全。artifactCoverage只报告文件覆盖，不能升级人工门。截图哈希和operator收据不证明图像内容、捕获时间或实际浏览器请求；截图与SVG仍必须打开逐图复核。

`index.html` 联系表便于比较9前沿 ×4配置；缺图预览、实际浏览器图和额外编辑后图明确标识。复核者复制review-template为独立review，填写真实reviewer、逐图布局/层级阅读/留白/色彩及黑白/字体与真实尺寸可读性/连接路由。窗口fit缩放图不是校准的85/180mm印样，必须另看SVG真实尺寸；字体缺字、最小字号建议未达和dense展开须如实登记。几何/DOM/字节一致不能代替审美评分，截图集合也不能代替真人任务/性能认证。

## 已封存的历史采集

`docs/evidence/browser-visual-matrix-before-intrusion-fix` 是 `index-D1WyCZV8.js` / `index-BO7yZQLO.css` 的36基础+3编辑后工件快照；collect的artifactCoverage=complete，人工仍pending。最终统一1280×720、DPR1，并逐图核像素，原绘制滞后和窗口裁切证据另保留。 [AI像素观察与环境来源](evidence/browser-visual-pixel-observation-before-intrusion-fix/README.md) 绑定最终manifest、每张截图和ancillary来源。它明确只适用于修复前版本；后续renderer/layout/source/build改变必须重新prepare到新目录、再采新截图，不能改历史hash或用旧矩阵认证新版本。

此前相同协议重新采集历史 `index-oH4Ot2L9.js` build，正式快照在 `docs/evidence/browser-visual-matrix-zoom-full`：36基础+3模型各一份edited/save/reopen，artifactCoverage=complete、人工pending。 [最终AI像素观察](evidence/browser-visual-pixel-observation-zoom-full/README.md)独立核234artifact字节/摘要、39真实截图可见页头和整页范围；它仍不认证字体、真实印样或六维审美。当时代表4样本、进行中观察和历史修复前39均保留，不能通过目录名推定completion。UA来源已如实改为同IAB先前8771native receipt并绑定source SHA，未伪称8772navigator读取。后续build改变仍须再freeze/重采。

## 历史手工具构建的完整采集

此前 `index-DWpF-img.js` / `index-DK5lov-h.css` 的[不可变矩阵](evidence/browser-visual-matrix-pan-annotation-full/manifest.json)已封存36/36基础组合和三模型各一编辑后，39case/234工件，manifest SHA256 `52d60b4ad50d98bb01c0e19ee48fe627d1588185fbbd7961d8c64ff8c45cdd88`。两个missing列表为空、artifactCoverage=complete；visualAcceptance仍pending-human-review、humanAcceptanceCertified=false。该历史build的[1case先导](evidence/browser-visual-matrix-pan-annotation-current/manifest.json)保留自己的原范围；历史zoom39不计入该次覆盖；后续出版renderer/build已变化，此39矩阵与其字段/像素审计不计入新构建覆盖。

本轮截图统一1280×720/DPR1，UA/DPR来自同IAB先前8880observer并标注来源，硬件/解析字体仍未知。三份edited分别Transformer/CNN L0paper180、MLP L1paper180，说明文本undo/redo与save/reopen记录在20份[公开journal](evidence/m4-pan-annotation-matrix-corrected/edited-ui-journal.json)。三对SVG/revision保存重开一致，camera改变/history reset；重开后还重切preset/width再保存/导出，final rev54/22/39（storage18/10/14）不冒称立即reopen全部状态。

采集helper闭包保留旧exportURL，导致37项复制错实际导出。[修正账本](evidence/m4-pan-annotation-matrix-corrected/export-copy-correction.json)对38项按完整exported Canvas及formatSVG唯一匹配真实服务文件，另1项沿用先导，原错误raw在`m4-pan-annotation-matrix-raw`保留。修正采集在`m4-pan-annotation-matrix-corrected`；截图/时间/DOM/Canvas与观察事实不变，仅screen限制说明追加。这是实际工件选取修正，不是重新读取浏览器链接或复采；collect随后精确核实际Canvas→interactive DOM→publicationSVG。

[独立字段核对](evidence/browser-visual-pixel-observation-pan-annotation-full/field-audit.json)重建全部39Canvas/interactive DOM/publication SVG并精确匹配；[AI像素观察](evidence/browser-visual-pixel-observation-pan-annotation-full/pixel-review.md)独立核234工件字节及39截图可见页头/全纸/图例、无modal。CNN L2与Transformer深层fit文字无法可靠逐项读，不能把轮廓可见当作canonical端点、字体或真实印样认证。TransformerL3/85mm receipt minText2.53093pt、nodeLabel3.29021pt与先前rev23约2.896pt不同范围，均无出版通过。CNN说明英文逐字符换行为“skip p / ath.”，仍是待修可读性问题。39case/234准则仍待实际人审；性能、固定环境和五席研究者0人的门保持未认证。

## 历史 DPwoy 出版修正构建的范围

当前JS `index-DPwoyNJW.js`，CSS`index-DK5lov-h.css`；wordwrap/详情选项/页宽/预检与缓存改变后，旧DWp39矩阵和字段/AI像素报告均保持历史，不计算新coverage。8886whole/FFN/CNN代表链单列；随后8887重新freeze/prepare、逐variant实际采集并collect新36＋3矩阵，见末节。不得改旧manifest哈希或沿用旧截图。旧版[77文件/6链接归档](evidence/before-publication-refinement/manifest.json)是provenance，不是覆盖数量。

导出默认整图，显式详情选项按完整层级路径/序号；宽25–1000mm、高≤5000mm，预检显示两位小数字号与实际页高，7pt只是起点。新实际FFN85为6.94pt且raw<7；86为7.03pt、263.7mm高/3boundaries，不沿用旧renderer高度。低字号采用建议宽可形成很高页面，whole236为784.8mm高，仍需目标版面人工审看。保存/导出缓存v2比较当前exactSVG，同revision不同renderer不复用旧artifact，缓存通过不证明实际内容/人类结果。固定字体/硬件、持续性能、原生cancel和人审/研究者任务未认证。

最终journal有11条代表记录，CNN180mm为8.58pt/309.5mm高，说明“…with its skip”/“path.”两行与当前SVG一致；v1初始无links，v2恢复当前重新生成的链接。三次导出是两SVG/一PDF、仅两份基线Canvas，不计36＋3覆盖或三模型完整任务；PDF生成不证明本次浏览器打开/物理尺寸人审。采集期间failed fetch与退出143保留，恢复同端口/数据目录后新生成才计成功。

[最终独立审计](evidence/m4-publication-refinement-work/independent-final-audit.md)受限通过11Canvas/实看截图、9preview、5选项、3直接链接工件与2SVG/1PDF页几何，最终截图无状态滞后；截图可见切片之外的精确字/links由DOM和实际文件支持。该结果不填写人工评分、不补新matrix cases。storage envelope未封存；renderer升级拒绝是2纯函数反例；Python10仍属较早Qpo范围记录。服务过程是根工具响应事后摘要，退出原因未知。

## 历史 DPwoy 出版最终39例封存

[新manifest](evidence/browser-visual-matrix-publication-final/manifest.json) SHA256 `55df9000f42857bca9dc8ce2f75fe097b99ea90fae94ad077810225e05162593`，[spec](../.archcanvas/browser-visual-matrix-publication-final/spec.json) SHA256 `847b40ea74b474c2853263abd9557971af9cf386ef1f51c8f3194e1ee1d45625`；36基础、3edited、39例234工件，missing两empty、coveragecomplete；[联系表](evidence/browser-visual-matrix-publication-final/index.html)/[空白review-template](evidence/browser-visual-matrix-publication-final/review-template.json)pending-human-review/false。按manifest captures的caseId打开其实际截图/SVG；新gold候选不替代实际浏览器工件，3edited不代表36配置皆有编辑任务。

[独立末审](evidence/m4-publication-matrix-work/independent-final-audit.md)及[JSON](evidence/m4-publication-matrix-work/independent-final-audit.json) SHA256 `8fe586a4e531d74b63baeb963875e8ff12e8bb151834d742411bb16710ae50e2`在明确观察范围通过39DOM/publication/directlinkSVG与39实看截图；352raw/352mapping、313不变＋39receipt仅补两hash、234sealedexact。4处heightMm JSON微差限定1e−9、XML其余精确，正式stamp/collect0后的wrapper异常公开保留。

19UI支持3SVGundo/redo除revision相等、3save/reopen＋3finalraw字节相等；5AX输入值不同原因未知，不认证输入同步。CNNadded latent flags过渡不称L2，最终CNN L0rev32/storage14、MLP L1rev18/storage10、Transformer L0rev41/storage18。处理中Save footer不认证完成，使用实际reopen链。viewport1280×720来自8887，UA/DPR明确取自先前同IAB8880observer；font/hardware未知。36baseline10项最小字≥7pt、0满足组合示例，实际尺寸/dense人审仍是门。

本阶段不重跑79Studio/9独立性或earlierQpo Python10；研究五席pristine0真人。[取消只读审计](evidence/m4-publication-matrix-work/gesture-cancellation-audit.md)不补活动原生cancel，hidden-only只是增强建议。[旧current-doc解析归档](evidence/before-publication-final-matrix/README.md)保留11docs＋4receipt，旧manifest路径更新后核其files原bytes，不改旧manifest。后续root input/service诊断与恢复在[work说明](evidence/m4-publication-matrix-work/README.md)另列，不属finalaudit或矩阵/性能验收。
