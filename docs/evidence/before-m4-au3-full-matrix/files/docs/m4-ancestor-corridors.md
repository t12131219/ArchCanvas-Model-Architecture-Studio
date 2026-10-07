# M4：精确 memory 家族与祖先侧路由

当前正式构建（2026-10-06）为 `index-au3IB_0Q.js`，SHA256 `dca15460bc9ed8def5ff80c9da5dfcf16bb49f7a230986e0ffeef1a6b0e7548b`；CSS 为 `index-B6WbMowt.css`，SHA256 `172a09a8c147e53c3bef426cf76b59b8cc4893e891eb6e920aa7b25a0bb024e0`。本轮继续从头实现，没有采用失败原型代码、执行模型或安装依赖。M4 仍 partial，未进入 M5；AI 浏览器试用不计真人研究。

## 路由变化

不同 display source、canonical source node/port、tensor、role、实际 stroke/width/dashed、source side 或端点坐标的连接不会组成家族。whole/detail 投影逐项反查 canonical edge，确认全部源绑定与样式一致，并核 public ScenePort 的 canonicalBindings/edge coverage；未解析或混合的 proxy 保持独立。每条原始 edge、消费者、端口与 canonical membership 都保留，不合并模型事实。

新增阶段只处理精确 memory 家族的六点 V-H-V-H-V 路线，从源分支的最外层独有展开祖先推导相关侧边，依次尝试原有的 6/14 单位间距。它保留端点和目标 gate，统一 source gate/共享干线。没有硬编码 Transformer ID 或页坐标。名义卡片/Repeat 背板、端点 own-body 与祖先标题均是障碍；无法通过法线、无反向折返、body/header、全景指标及家族总长度/弯折检查时原子拒绝。

预算没有提高：最多1024节点、512路线、4096 route points、32768 pair checks、150000 segment checks、60000 obstacle checks、384候选、8次 refinement、2 passes。每次 generic refinement 的候选上限仍为80，这是历史的 per-refinement 语义，不是所有 passes 合计每条路线80。只为一个符合条件的双成员家族在上述总额内留出4候选/2次 refinement；其 generic 成员本次上限78，普通 generic 阶段保留最多380候选/6次 refinement，然后家族使用余量。没有符合条件的双成员时沿用原总额。

generic 阶段继续使用此前不同 tensor 评分与 tensor overlap exemption。新增 family 阶段额外保护每个受影响 same-tensor pair 的 strict crossing pairs/points，不允许用消除另一分叉的交叉抵消新增交叉；合法共享干线的同 tensor 重合不因此拒绝。不同 tensor 的受保护计数保持 aggregate 单调，仍可能交换具体交叉对，不是逐 pair 或全局最优保证。固定 work caps 不等于性能认证。

## 当前独立结果

最终 [Studio179/179 收据](evidence/m4-ancestor-corridor-work/root/full-studio-attempt-2/receipt.json)与 [strict TypeScript/production build 收据](evidence/m4-ancestor-corridor-work/root/build-attempt-3/receipt.json)均 exit0，前后输入精确一致；专项9＋Repeat17的26/26属于另一次运行，不与179相加。新增 [独立 oracle](evidence/m4-ancestor-corridor-work/acceptance/README.md)解析实际 Scene/SVG、路径交点与每 pair 区间并集，不用产品 router/scorer 得出预期。

| 前沿 | 不同 tensor strict pairs/points | overlap pairs | 改变的路线 |
| --- | --- | --- | --- |
| Transformer L1 | 20/21 → 19/20 | 7 → 5 | 44、55 |
| Transformer L2 | 22/25 → 22/25 | 19 → 17 | 44、55 |
| Transformer L3 | 20/23 → 20/23 | 19 → 17 | 44、55 |

[12视图独立报告](evidence/m4-ancestor-corridor-work/acceptance/current-attempt-1/report.json)覆盖九个前沿与三个相关详情。L3 overlap length为4314.21→4068.81，disjoint strict pairs/points为17/20→16/19，disjoint overlap pairs保持13。44/45与44/46两处 memory/mask 重合消失，44/55共同走由祖先推导的x468干线；两条路径总长减少480.8单位，弯折不增加，没有新增 same-tensor pair crossing。具体不同 tensor 交叉对交换为：新增43/44、44/47、44/51，移除44/50、44/57、44/69；不是每对交叉都下降。same-tensor overlap pairs仍17，合法共享干线的重合长度5545.36→7788.36；这项增长保留为视觉权衡，不能把不同tensor重合减少称为全部重合消失。

剩余六前沿与三个详情的 Scene/SVG 与归档 BG 字节精确一致。全部12视图的 Canvas/source/IR、canonical branches、对象/端口/front/pins/style、hidden accounting 和 export scope 保持；无新增 nominal body/backplate/header 内穿，长度/弯折保护通过。当前 Repeat 测试只把 Transformer L1/L2/L3 的旧“不变 SVG”断言改为独立 BG invariant 比较，其余原检查与 sealed-ChS 负控范围保留。独立 oracle另拒绝词法/几何污染、缺 branch、改 source/style/circle、own-body 侵入、单memory新增同tensor交叉等反例。

## 失败与版本范围

family-first 中途投影虽然局部看似改善，却因抢占 generic 预算使全场 overlap19→20、disjoint overlap13→16；[首捕获](evidence/m4-ancestor-corridor-work/root/capture-attempt-1/report.json)与独立拒绝结果完整保留。把新 guard直接加入 generic 后的 [attempt2](evidence/m4-ancestor-corridor-work/implementation/attempt-2/receipt.json)仍回退到22 overlap；[attempt3](evidence/m4-ancestor-corridor-work/implementation/attempt-3/receipt.json)恢复完整 BG 场景但预算耗尽、家族未触发。最终 [attempt4](evidence/m4-ancestor-corridor-work/implementation/attempt-4/all-frontier-metrics.json)在原 caps 内重分配少量额度，12视图通过后才采用。早期截断工具结果以[诚实观察记录](evidence/m4-ancestor-corridor-work/implementation/attempt-1/intermediate-observations.json)单列，不补造完整 stdout 或源绑定。

改动前 BG 1896绑定＋seal共1897文件，另14末读文件，共1911文件已[完整归档](evidence/before-m4-ancestor-corridors/manifest.json)，manifest SHA256 `c1969548ea2b2b1e9158c3f424b5e29f6910fe124879ce7f658b54d5e996df28`。旧 raw、失败、manifest、seal 与研究包不回写。ChS39/234矩阵与 BG 四代表均对 au3 为 stale，不继承为新完整矩阵。

## 浏览器与搭建试用

同一轮的 [BG AI试用](evidence/m4-ancestor-corridor-work/browser-ai-only/report.json)绑定旧 `index-BGj2ZBSY.js`，不是 au3 当前验证：17模块逐个点击添加、3起点分别点击、Input与CNN起点原生拖入、四节点空白连线/排版、MLP上下左右各16单位及残差MLP静态生成均有各自公开DOM/SVG/截图。47工件逐哈希复核；17模块的参数/生成逐项未验、其余起点未逐个拖入。旧端口group中心点击失败、准确圆点点击/拖动成功，以及一次DOM Y54却截图Y70的失配原件保留，失配图不计像素通过。同步补采的MLP四向图单列。没有在该试用保存/重开、创建工作副本、执行模型或导出出版页。

新CSS把端口text恢复为可点击命中区域。主任务在当前au3的[真实浏览器AI复验](evidence/m4-ancestor-corridor-work/browser-final-attempt-1/report.json)分别用role click和原生文字中心click建立Input→Linear，观察连接撤销/重做。然后逐项连接Input→Linear→ReLU→Output，按连接排版，保存并重开4模块/3连接草稿；arranged/reopened SVG原字节一致。静态审看生成的新Python后，实际创建独立工作副本、打开并保存论文图。[独立搭建回读](evidence/m4-ancestor-corridor-work/acceptance/authored-browser-readback-attempt-1/final-readback.json)核Draft、655字节新源码/AST/IR和公开生成图：计算叶图为4节点3边，全canonical IR另含root为5节点4边、root关系在公开图计hidden。shape/dtype仍为声明与静态规则，不是模型运行结果；未执行模型或训练，未修改已有模型源文件。该链不认证imported Canvas alias编辑/刷新重开。

当前单个source-bound Transformer L3的交互SVG、实际SVG/PDF UUID与保存文档/源码/IR由[独立只读回读](evidence/m4-ancestor-corridor-work/acceptance/browser-source-readback-attempt-1/final-readback.json)核对，路径/cards/circles/styles/metadata/canonical coverage与当前Scene一致，strict20/23、overlap17。实际SVG为150384字节，PDF36333字节，单页180×605.611052mm。14%fit全景和只显示顶部的导出截图不认证出版细字/字形/像素；211字节`l3-export-preview.svg`实际是modal关闭图标，保留并排除。没有新完整39矩阵或当前完整四向复采。

首次快速批量连端口的`from-zero-complete.*`实际4节点1边，不计完成，原因未定；后来逐动作核状态才达4/3。outerHTML/getAttribute与fs/promises采集误用、封存时误要求sandbox看到宿主PID的失败也保留，不冒称产品失败。60份raw绑定含13session冻结副本逐哈希核对。服务在8987的managed session36749末读为running，sandbox看不到host PID，不能承诺宿主终止后仍在线；用户8765未操作。子Agent [fresh retest阻塞记录](evidence/m4-ancestor-corridor-work/browser-ai-only/fresh-port-hit-attempt-1/report.json)仍只证明其浏览器不可用，与主任务实际成功独立保留。

当前 [独立发行收据](evidence/m4-ancestor-corridor-work/acceptance/standalone-attempt-1/run-1/process.json) exit0、9/9，通过实际完整正式目录与既装依赖复制后的隔离静态analyze和Studio build。[scope review](evidence/m4-ancestor-corridor-work/acceptance/standalone-attempt-1/standalone-scope-review.json)核209源码与654依赖文件前后精确，5dependency symlink目标精确、完整复制清单28523条及实际analyze输出读回一致。不是clean install、模型执行、完整产品测试、浏览器像素或真人验收。

## 开放门

17基础模块＋MLP/CNN/残差MLP三个透明起点继续存在；Attention/LSTM/Sigmoid/Tanh/Conv1d/AvgPool2d/BatchNorm1d、任意Python节点和自动训练仍不在搭建合同。三个起点是可编辑普通草稿图，不新增模块种类。最终 au3研究包本轮未 prepare/verify；旧 repeat-outline/ChS包 stale，不可分配新人，assigned/collected/真人均0。原五步与搭建/位置修复探索仍分别计时，不改变180秒分母。

L3仍有17不同tensor overlap与20 strict crossing，长共享干线的像素审美、深图字形与85/180mm实看、字体/硬件固定、300对象输入到呈现p95≤50ms/≥50fps、活动手势取消及3–5位真实研究者任务均未认证。AI不能成为真人或签署出版验收；这些门保持开放，并继续推进可独立验证的产品改进。
