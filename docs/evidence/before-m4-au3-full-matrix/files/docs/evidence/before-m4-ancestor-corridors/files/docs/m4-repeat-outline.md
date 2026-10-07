# M4：折叠 Repeat 的共享外轮廓

当前产品（2026-10-06）为 `index-BGj2ZBSY.js`，SHA256 `8755924c0ca77285927550f88bf0a49e43c73856c1888294b356e34fc0bcea53`；CSS为 `index-CsXMONBp.css`，SHA256 `7d7a4afc8465d1997a595a4c657edca86b6e95ea8b8bd6bff5ee751cceae9c2b`。本轮修复折叠 Repeat 的输出线穿过自身两层背板的问题。正式工程继续从头实现，未采用失败原型代码、执行模型或安装依赖；17基础模块、3透明网络起点和显式位置修复继续保留各自范围。

## 产品变化与边界

`nodeVisualOutline.ts` 是共享纯几何入口。前卡片与 +3.5/+7 背板组成 nominal rectangle union；SVG绘制、端口显示、路由端点/障碍、场景范围和详情导出使用同一轮廓。输出端口沿原外法向投影到实际矩形并集边界：CNN `(177,416)→(177,423)`，Transformer横向memory `(274,444.1)→(281,444.1)`。靠近左/上角的投影根据射线所遇卡片采用 +0/+3.5/+7；不会把端口移到整体包围框的空角。圆角仍使用保守矩形障碍，未实现任意多边形路由。

显示side各自拥有端口对象及准确的canonical edge覆盖，避免同一canonical memory输出的bottom/right消费者在后续路由中互相改动public circle。节点前卡片、Canvas layout、local anchors、pins、canonical端口绑定、源码与IR不变；incoming top、非Repeat与展开态保留原位置。三张矩形共享同一owner，重叠/标题侵入诊断按owner去重；实际背板冲突不会作为装饰忽略。无法绕开的手工重叠仍保留锚点并报告受阻。

原不同tensor交叉/重叠评分和候选预算未扩展。L3仍有19对不同tensor重叠和20对严格交叉；密集图小字、说明/图面空白、真实尺寸阅读、字体与硬件固定、presented性能、进行中取消、研究者与出版人工门保持开放。M4 partial，未进入M5；AI复核不等于真人验收。

## 当前回归与独立证据

| 检查 | 当前结果 | 范围与原记录 |
|---|---|---|
| 全套Studio | 170/170，exit0 | [full-studio-attempt-2收据](evidence/m4-repeat-outline-work/root/full-studio-attempt-2/receipt.json)；专项17/17与历史adapter14/14均在各自运行中报告，不与170相加 |
| strict TypeScript / production build | 两者exit0 | [strict收据](evidence/m4-repeat-outline-work/root/strict-ts-attempt-1/receipt.json)、[build收据](evidence/m4-repeat-outline-work/root/build-attempt-1/receipt.json)；实际构建与源哈希绑定 |
| Skill Markdown校验 | exit0 | [本轮收据](evidence/m4-repeat-outline-work/root/skill-validation-attempt-1/receipt.json)；host Python只校验指令文档，未用作产品runtime，未安装依赖 |
| 正式独立发行 | 9项，exit0 | [范围审查](evidence/m4-repeat-outline-work/acceptance/standalone-attempt-1/standalone-scope-review.md)、[实际报告](evidence/m4-repeat-outline-work/acceptance/standalone-attempt-1/retry-1/actual-independence-report.json)；`-I -S`及复制正式源/已安装依赖，非clean install |
| 独立轮廓oracle | 17/17 | [报告](evidence/m4-repeat-outline-work/oracle/summary.json)、[范围说明](evidence/m4-repeat-outline-work/oracle/README.md)；解析实际SVG矩形/circle/path，不使用产品outline或交点函数作预期 |
| 源码前沿/详情 | 九个前沿＋三个含折叠Repeat的详情 | 封存ChS的6次叠片穿透/6个埋入端口均变为0；端点、悬空、own-body及裁切均0；六个无折叠Repeat前沿SVG字节相等；Canvas/source/IR/canonical/front/pins保持 |
| 历史路由合约 | adapter14/14，73记录无原始指标回退 | [原始指标](evidence/m4-repeat-outline-work/oracle/historical-routing-metrics.json)；限定外轮廓投影的内存适配，不回写历史baseline；原15反例及新8反例保留 |

首轮全套保留3个历史front-port不变断言失败；最终adapter仅允许独立SVG横截面证明的外法向投影及side ID，并继续核原始不同tensor/disjoint指标、路由方向、body/header和既有受阻事实。首轮oracle16/17的fixture pin位置冲突、child-spawn EPERM、standalone wrapper根路径失败和中间adapter失败均保留，未通过修产品或删除旧证据隐藏。具体范围以[oracle说明](evidence/m4-repeat-outline-work/oracle/README.md)与[发行说明](evidence/m4-repeat-outline-work/acceptance/standalone-attempt-1/standalone-scope-review.md)为准。

历史 `mlp-level0-paper-180-move-up` 已有front-body重叠；当前仍明确受阻。adapter仅对同一历史原始front-body侵入加当前matching diagnostic保留例外，新backplate-only侵入即使伪造blocked diagnostic仍拒绝。九个未改基线前沿与三相关详情没有该例外。

## 浏览器与研究包的当前范围

[最终有界独审](evidence/m4-repeat-outline-work/acceptance/browser-attempt-1/SUMMARY.md)覆盖MLP L0、CNN L0、Transformer L0及Encoder展开主画布/详情导出的四个代表案例。4主画布交互SVG与实际Canvas replay原字节/XML精确；4静态导出仅按根物理高度8有效位与XML序列化变换后字节精确，不能写未变原字节相等。source/IR独立重算、旧baseline完整Architecture与每个export UUID的文档/图/receipt精确。四张最终主画布、四向截图、一个详情弹窗primer及一个CNN草稿final均实际original打开；没有完整详情页的最终像素截图。

Transformer四方向实际位移分别(+28,0)、(-28,0)、(0,-28)、(0,+28)，其他节点卡片不变。四次undo仅归一根data-revision与metadata.revision后完整SVG恢复；down redo/save/reopen的完整SVG字符串精确，重开使用0.9缩放。保存捕获footer仍显示“正在处理”，成功依据来自后续“已重开保存的画布”；不把pending截图作为完成证据。

[独立名义几何](evidence/m4-repeat-outline-work/acceptance/browser-attempt-1/geometry-child/report-final.md)对21工件记录229次路径、458次端点观察，包含static/interactive、preview/export及恢复重复，不是unique对象数。458端点均解析，端点/外法向与Repeat/背板/header内穿为0；向上移动edge7仍有3次真实卡片段内穿、2个Embedding对象对（source97+3、target194单位），UI明确blocked，不能写四方向无冲突。first pass的10个未解析是5个hidden attention canonical targets×preview/export，原报告保留；[补充150项绑定核查](evidence/m4-repeat-outline-work/acceptance/browser-attempt-1/geometry-child/detail-projection-bindings.md)用最近可见typed collapsed parent、unique端点与实际ScenePort canonicalBindings/edge IDs核对，并拒绝错误role/位置/缺binding/缺edge反例。这只核名义矩形和route centerline，不认证圆角stroke、glyph/marker、raster crossing或物理出版。

[CNN点击冒烟](evidence/m4-repeat-outline-work/acceptance/browser-attempt-1/authoring/review.json)实际8节点/7连接，一步undo到0/0，redo与inserted完整SVG相等，save/reopen有成功DOM。重开原SVG不相等，唯一差异为首Input取消selected class；仅该差异归一后XML一致，几何/IDs/paths/text保留。[追加校正](evidence/m4-repeat-outline-work/acceptance/browser-attempt-1/authoring/reopen-selection-correction.json)覆盖旧authoring README误述，原件未删除。catalog17模块＋3起点只是DOM存在；没有saved draft payload、模块拖入、17模块逐项E2E、另外两起点交互、生成源码/模型执行/论文导出证据。这不是新36＋3浏览器矩阵，不继承ChS人工评分或持续presented性能。[当前机器状态](evidence/m4-human-review-handoff-status.json)单列以上范围。

新的 `.archcanvas/m4-research-trial-repeat-outline-current` 已[prepare/verify exit0](evidence/m4-repeat-outline-work/research/attempt-1/preparation-verification.json)；manifest SHA256 `b2b918a8700884cff5d96db3a08165b7030514b6493c5b27b532d04f1260f726`，16591 bytes，冻结73实施文件/4baseline、五个未分配席位，端口9001–9005仅登记未查可用、未启动研究服务。根操作78输入前后精确；[独立研究包审查](evidence/m4-repeat-outline-work/acceptance/research-attempt-1/review.json)另核73实施/4baseline/17包文件、104输入稳定与fresh正式origin probe，未重新prepare/verify或启服务。旧2916归档与806当前raw/collected字节复核精确，806在浏览器独审中重新核过，2916在此前归档审计中核过。0assigned/collected/真人，researchGate=not_run。按已固定的[研究协议](m4-research-protocol.md)从实际manifest读取端口，未开场不能assign。原五步任务与搭建/位置修复探索分别计时和评判；AI不能改成researcher或签人工成功。

ChS39例/234工件保持其原版本 `artifactCoverage=complete`、`pending-human-review`、`humanAcceptanceCertified=false`，对本BG构建为stale；旧ChS研究包同样stale。ChS seal的2915绑定加原seal共2916文件已[完整逐字归档](evidence/before-m4-repeat-outline/manifest.json)，manifest SHA256 `a0ae1bd0d2b21589a4986acc992c13c3f6cde0659a0c94c770f37fd5be299e70`。旧raw、manifest、seal和研究包不回写；当前文档是允许更新的说明，不反过来改变旧认证范围。

## 下一步可复核候选

[不同tensor候选报告](evidence/m4-repeat-outline-work/routing-next/attempt-1/recommendation.md)仅为只读几何试验。memory同源/同tensor/同role/style家族的替代中缝可消除两处mask重叠：假设路径全景overlap19→17、strict20不变，并公开新旧交叉交换及长共享干线的视觉风险。residual左侧方案strict20→19，但会增加不同role/style同tensor分叉交叉，属于条件候选，不能自动豁免。简单mask平移会把重叠变成更多交叉，负结果完整保留。没有实施这些路径，不计当前修复或M4通过。

最终源/测试/build/浏览器/研究/文档的当前验证seal由主任务在末读一致后另建；本报告不自行创建seal或补签真人结论。
