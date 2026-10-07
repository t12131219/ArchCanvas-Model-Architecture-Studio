# M4：历史ChS完整浏览器矩阵与体验问题

当前产品已切换为 `index-au3IB_0Q.js` / `index-B6WbMowt.css`，见[祖先侧路由与当前范围](m4-ancestor-corridors.md)。本页下方所有构建、计数、浏览器、研究包及“当前/本轮/最终”均保留其明确历史版本范围；旧BG/ChS矩阵与研究包对au3为stale，不可分配旧研究席位。[切换前1911文件归档](evidence/before-m4-ancestor-corridors/manifest.json)保存原字节；旧raw/manifest/seal不回写。真人0，M4 partial、未进入M5。

当前产品已切换为 `index-BGj2ZBSY.js`，[Repeat共享轮廓修复](m4-repeat-outline.md)改变renderer/端口/路由；本报告与原39例/234工件的complete/pending-human-review事实仅适用于ChS，对BG为stale。旧ChS研究包同样stale，不可分配新参与者。四个新代表案例不构成新36＋3矩阵，AI与真人门分开；真人0、M4 partial。[修复前2916文件归档](evidence/before-m4-repeat-outline/manifest.json)保留旧2915绑定加原seal，旧raw/manifest/seal不回写。

## 封存ChS事实

本轮保持 `index-ChS0wIgb.js`（SHA256 `05019f89f0de0c0c622df7a2cc1a13ed58477c456244c97209a0f37db79139c9`）和 `index-CsXMONBp.css`（SHA256 `7d7a4afc8465d1997a595a4c657edca86b6e95ea8b8bd6bff5ee751cceae9c2b`）不变。正式从头实现的17基础模块、3个透明网络起点及显式位置修复继续使用同一版本；没有导入旧原型或执行模型。

[正式 manifest](evidence/browser-visual-matrix-chs-current/manifest.json) SHA256 `196c673b8f83cabb3911810bee302f2fe0f774c1affc43be3cf6b9fa0a64923b`，219546 bytes；[联系表](evidence/browser-visual-matrix-chs-current/index.html)与[空白人工模板](evidence/browser-visual-matrix-chs-current/review-template.json)随包保留。36基础组合来自九个真实源码前沿，另有三模型各一个编辑后案例，共39例、234工件；两个missing列表为空，`artifactCoverage=complete`。`visualAcceptance=pending-human-review`、`humanAcceptanceCertified=false`。它们分别是工件覆盖和人工审看状态，不能相互替代。

| 模型 | 实际前沿的可见节点数 | 基础组合 | 最终编辑后样本 |
|---|---|---|---|
| Transformer | L0 12、L1 23、L2 41、L3 49 | 16 | L0、彩色180mm、rev42 |
| MLP | L0 4、L1 8 | 8 | L1、彩色180mm、rev17 |
| Residual CNN | L0 8、L1 10、L2 24 | 12 | L0、彩色180mm、rev30、fresh recapture1 |

每个前沿分别采85/180mm与彩色/黑白。MLP/CNN没有的深层不伪造，三份编辑后案例不表示36组合均测试过编辑。全部通过真实界面操作，最终截图使用独立工具调用取得；不是静态SVG转截图。保存envelope、当前公开SVG、实际导出链接UUID与对应文件分别保留，helper只读取该确切UUID，不搜索替代导出。

## 编辑与采集链

[编辑journal核验](evidence/m4-chs-browser-matrix-work/root/edited-journal-verification.json)冻结40份JSON/DOM。MLP文字编辑15→撤销16→重做17；CNN文字24→25→26，清理保留的子展开标记后最终30；Transformer文字40→41→42。每组编辑/重做的完整XML仅revision不同，撤销结果与编辑结果不同；三份最终保存、重开及最终raw的完整SVG逐字相同，document/source/IR身份保持一致。视觉revision与storage revision分别记录。此处不认证私有history或运行数值。

CNN的早期“移到图下方”没有新revision，撤销25/重做26实际回退的是文字，不能作为移动undo证据。CNN与Transformer从深层回到概览后仍保留部分layout缓存；collector明确列出`layout`和`annotations`差异，不声称只改说明。MLP相对其前沿基线只列`annotations`差异。

保留两次排除：Transformer L1彩色85的首次raw误用了上一案例的导出href，真实重新采集`recapture1`；CNN首次edited画面像L0，但父容器内隐藏的子展开标记不符合root-only合同，正式helper拒绝。通过界面逐层折叠、保存重开后重采。详见[排除1](evidence/m4-chs-browser-matrix-work/root/excluded-case-1.json)、[排除2](evidence/m4-chs-browser-matrix-work/root/excluded-case-2.json)。原件和失败日志不修改。首次helper缺少子命令、首次index输出路径不在bound的祖先目录也保留；正式index/collect成功使用新的attempt2路径，未改合同。

## AI 审查发现

独立代理逐张审看39份最终原始JPEG与对应公开DOM/保存文档，另审看预拍图；预拍时的导出弹窗不计有效最终截图。最终图的模型、页面、前沿和revision粗字段一致，不推导逐字glyph、marker、全部私有状态或物理尺寸合格。深图14–18% fit无法可靠逐字阅读。

[独立可读结论](evidence/m4-chs-browser-matrix-work/pixel-review/final-review/selected-39-readable-conclusions.md)汇总78张有效案例原图：39最终图、37带模态框的预拍图、2普通预拍图；排除CNN的两张原图另计，总80张唯一原图。817路线/1634端点的名义数值核验没有前景卡片重叠/穿透，仍有28次背景叠片穿透、997点接触、547共线重叠、365严格交叉；这些是跨场景的线段发生次数，不是唯一网络对。25张最终图观察到工作区点网格，公开JSON没有网格状态，不能认证全状态相等或推测原因。

[末次文件核验](evidence/m4-chs-browser-matrix-work/collection/attempt-2/final-local-byte-audit.json)逐一核234个raw→bound→collected映射，1060唯一输入在末次核验期间未变；三处variant声明修正只改变variantId，原始观察全部保留。文件核验不替代像素审查，两份结论的范围分别记录。

独立geometry审查区分卡片前景、repeat背景叠片、端口中心和路线中心线。Transformer L3名义几何有34对严格相交（不同tensor23、相同tensor11）、56对共线接触/重叠（不同tensor22、相同tensor34）。[优先清单](evidence/m4-chs-browser-matrix-work/pixel-review/attempt-5/geometry/routing-priority-review.json)列出19对不同tensor正长度重叠和20对严格交叉作为改进候选；必要fan-out可以保留，不能把所有交叉直接判错或承诺全局零交叉。已检查的路线端点与名义端口中心相符、无自交；这些数值不认证stroke、箭头外形或字体轮廓。

Transformer概览的memory线、MLP概览的network输出线、CNN概览的blocks输出线穿过两层repeat背景叠片，前景卡片正文未穿过。路由器只避前景矩形，视觉叠片仍是实际改进项。CNN新edited图的主体与pool相邻间距约38scene单位，远处说明使页面高781.71mm并产生大段空白；旧失败例的1614间距不套用新图。

36基础组合仅10个最小字号达到7pt；最小为约2.53pt。三份edited最小字号：MLP8.58pt、CNN8.58pt、Transformer6.45pt；Transformer建议宽196mm，但增加宽度还要检查页高和目标版面。7pt预检是提示，不是期刊通用合格标准。当前39例未达到整体出版审看门。

## 研究与性能

新五席包[manifest](../.archcanvas/m4-research-trial-chs-current/manifest.json) SHA256 `ea10901224a5e2e8ebc8ad4136f68b8bd5b4e1db51f8bda38e92a66665b6efbf`，72实施绑定、4baseline、五个pristine席位，登记8991–8995。0分配、0收集、0真人；端口可用性未测、席位服务未启动。旧包保持历史，不用于当前开场。[任务合同审查](evidence/m4-chs-browser-matrix-work/research/attempt-1/task-contract-review.md)说明原五步仍是同源Transformer制图；17+3搭建和位置修复探索另表计时，不塞入原180秒任务分母。AI可以模拟新手与独立审查，不能填写researcher身份或计入真人分母。

[性能合同审计](evidence/m4-chs-browser-matrix-work/performance-audit/attempt-1/README.md)保留正式300对象p95≤50ms、≥50fps目标。本轮无产品性能试次，当前环境支持页只取同一IAB的UA/DPR及公开能力来源，正式iframe每例viewport1280×720由当前DOM读取。Chrome154 UA不是浏览器二进制/version锁定，loaded字体不是实际glyph字体证明。支持页0产品trial，停止服务实际工具exit1；8985服务日志仍会增长，不作不可变封印。

下一步先处理不同tensor的路由重叠与repeat叠片边界、概览说明位置及密集图阅读；再实现性能observer全部缓冲清单和预声明离散trial的完整性核验。真实离散Event Timing可以独立测，rAF不替代presented FPS；当前受支持浏览器API没有原生trace或held-pointer分步输入，相关门保持开放。M4仍partial，未进入M5。

## 封存与回归范围

本轮未改产品源码/build，既有Studio152/152、strict/build0和独立发行9项通过保持其正式版本范围，没有无理由重跑。静态矩阵准备另核36前沿/布局/Canvas replay及8独立工件反例；这些不是浏览器、人审或性能结果。[work记录](evidence/m4-chs-browser-matrix-work/README.md)保存本轮准备、raw、绑定、collection、失败与独立审查。

更新文档/status之前，[归档](evidence/before-m4-chs-browser-matrix/manifest.json)完整复制此前799封印绑定加原seal共800文件，并前后逐字核验。旧2894归档链继续保留。新的封印只绑定本轮明确范围，不将旧文档或失败raw重写为成功。本轮用户8765页面未操作。
