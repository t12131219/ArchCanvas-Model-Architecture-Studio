# 下一次可见 IAB 性能诊断的最小流程

这份流程只依据当前测量页面、validator和8889旧raw；未操作浏览器、重跑套件或改产品。目标是确认“这次呈现条件下实际产品的输入/回调是否改变”，并补指定目标拖动链；**不能由现有探针认证持续 presented FPS或完整性能门**。本轮已sealed构建为`index-oI5sT67U.js`，新矩阵仍由root独立采集；性能目录不要混进matrix cases或研究者席位。

## 1. 开场和证据目录

先核8889的实际终端句柄与新浏览器状态。旧生命周期仅记录29028在2026-10-05T00:05:21Z仍running，不证明现在在线；超时本身也不证明终止。若确证原句柄终止/缺失，才在新隔离storage启动，不改8889此前diagnostic bytes、矩阵storage或用户8765。启动命令只能在当前无该服务进程时执行：

```bash
set -o pipefail
PYTHONPATH=src .venv/bin/python scripts/m4_input_harness.py   --port 8889 --data-dir .archcanvas/m4-hierarchy-visible-performance/documents   2>&1 | tee docs/evidence/m4-hierarchy-visible-performance/service-raw.txt
```

新目录由root先创建；若目录已存在且有本轮数据，选另一个全新目录。若8889仍live，保留其实际data-dir和handle到本轮lifecycle，不为了换路径重复启动。

用选定browser 2/IAB的**当前CUA文档**核visibility能力，真实请求set(true)后立即get；看到实际tab后再get，保存各UTC、browserId与实际返回值。沿用root已有binding，不用shell浏览器自动化。后续每个采样窗口之前与结束后立即读取 capability，独立保存；false保持false。两个true只证明两个时点，没有同步连续compositor trace。Cua原生document visible/focus仍照raw记录，两者不要互相替代。viewport/DPR、实际资产脚本与dist hash另存开场观察；font loaded和hardwareConcurrency都不构成字体文件/硬件锁定。

打开`http://127.0.0.1:8889/__m4/`，确认状态“正式构建就绪”、iframe真实Studio与脚本oI5。harness外页控件144px、iframe固定1280×720，外页滚动可能改变frameRect；操作前重新取实际屏幕坐标，不用旧JPEG像素换算CSSpx。

## 2. 页面真实controls与最小产品采样

| 外页control | 实际值/行为 |
|---|---|
| 会话标签 | 可填写`oI5-visible-stress300-<本轮UTC>` |
| 测量模式 | `full`完整输入观测；`raf-only`轻量rAF对照 |
| 开始会话 | 新observer；绑定当前SVG/source/IR、环境并开始监听 |
| 测量操作 | `zoom / drag / pan / undo / redo / toggle / pin` |
| 目标ID / 锚点ID | 逗号或换行分隔；drag/toggle必须非空 |
| 准备此操作 | 只arm，不发产品输入；自动把当前全部pinned IDs加入spec |
| 结束此操作 | 捕获完整after、结束trial；没命中正确trigger则`no-input` |
| 结束会话并显示收据 | drain PO、停止监听、显示readonly原始textarea；pending trial标`stopped-pending` |

先在iframe“示例模型”选择真实option `stress_300`（可见名Dense 300-layer stress）。新storage默认root展开，network收起；若live storage已展开则先普通UI收起并记录开场，不能假装初始rev0。已知canonical IDs仍须用当前DOM核实：

- 展开目标：`call:instance:model.DenseStress300.network`。
- Linear1目标：`call:instance:model.DenseStress300.network.0`。

**最小新增full session是五trial：toggle、pan、指定Linear1 drag、undo、redo。** 前两项旧raw有成功终点；这次以新可见性读数为新条件，后三项补当前build未采的native拖动链，不以MLP替代压力模型。

1. mode=`full`，开始会话。保持约2秒无产品输入取得同iframe idle回调；这不是固定自动warm-up，记录实际区间。准备toggle目标network，在iframe真实点击“展开 network”，确认前沿4→304/或本次已声明计数变化，结束trial。不要将toggle的down→up约2.7ms窗口当渲染延迟；PO interaction duration另计。
2. 在非trial准备期选择Studio“平移画布”工具，核`aria-pressed=true`/`data-canvas-tool=pan`。外页operation=pan、targetId=Linear1作几何观测，准备；在当前可见viewport普通图区用已文档化CUA atomic drag作一次有限位移，例如约+40/+24 CSSpx。选择实际始点、避button/input；真实down/up同pointer与实际终点由raw核，数字是请求不是真实结果。结束trial。全SVG/frontier/pins/selection和rev应不变，camera应按viewport-relative终点匹配。
3. 在非trial准备期选择“选择对象”工具，核select状态；必要时树选择Linear1并“聚焦这个对象”，记录这次准备的相机变化与目标确实在viewport中。不要在已arm时聚焦或换工具。operation=drag，targetId=Linear1，准备；从当前**Linear1 body内部**起手，避port/展开按钮，用文档化原生drag一次。结束trial后核raw firstEventId真实nodeId确为Linear1、down/up同pointer、moves与终点。错命中保留no-input/失败，另新trial补采，不能删除或换目标ID修raw。
4. targetId仍Linear1，operation=undo，准备，在Studio真实按钮或Ctrl+Z执行一次，结束。redo同理。validator的shapeChanged/operationSucceeded只证明有视觉动作，**不证明撤销精确回同一Scene**；另比较before-drag/after-undo与after-drag/after-redo的完整SVG（只排除实际revision标量），保存实际document/store可补持久化，均与时延分列。
5. 最后trial完成后等待一次已观察稳定状态/可用PO delivery，再结束session；stop会takeRecords，不用固定长等掩盖stall。保存原始textarea完整bytes和字符数。CUA读取若有输出上限，用固定顺序read-only `.value` slices（例如80000字符）拼接同一已停止textarea，记录总长度/每段范围；不改、补字段或重排raw。另保留真实截图和外部visibility读数。若需要第二个session，先保存第一份再开始，新label/新raw文件，不覆盖。

`visibleIds`来自**全部SVG已render的frontier IDs**，并不逐一检查viewport相交。4→304证明304对象被绘入scene，不证明300对象同时可读/在视口内；raw只对指定target/anchors/pins有`intersectsViewport`。fit全图可能只有约1%细条；拖动前聚焦又改变视口。报告同时写“rendered frontier304”与当时目标是否可见，不把它悄悄改成“300对象同时在viewport的顺滑制图验收”。若要认证后者，需额外公开DOM逐body相交事实与真实截图，规格仍不能靠低zoom改写。

## 3. 最少对照及何时停止重复

优先做上述full产品session，因为它直接补当前build路径。若新可见条件下仍约983ms间隔，可做**一个**同IAB/同外viewport的20秒simple control：打开`/__m4/control`，在开场visible capability读数后，点击“开始20秒对照”；记录期真实点击大按钮“可信点击目标”一次，等待自动结束（超过20秒时保留实际timer延迟），结束后立刻capability读数，完整保存readonly raw。start按钮自身不在captured目标输入分母中；三个down/up/click可能只构成一个interaction。

该simple页面是top-level、没有React/SVG/模型/telemetry，且没有longtask订阅；产品在iframe，它们不是随机等价环境。对照也慢支持宿主/环境调度疑点，不能排除完整产品成本；对照快、产品慢提示继续调查产品/iframe，仍不是因果定位。不要反复20秒窗口直到挑出较快结果。如果新的呈现状态、环境或产品版本没有改变，重复旧慢窗口不会推进门槛。

可选而非必做：mode=`raf-only`的新20秒产品idle session，用于比较同Studio iframe下“仅rAF/visibility”与full的回调节奏。此模式不允许arm、**不记录输入/Event Timing/longtasks**，geometry仅session开场一次；在该窗口操作不能获得input latency。先保存fullraw再选择raf-only，不覆盖。它不移除Studio自带telemetry，不能称测量零开销或隔离产品CPU。

## 4. 原始schema与精确验证命令

产品raw为`schemaVersion:2 / protocol:archcanvas-input-observation/2`，顶层有measurement、environment/timeOrigin/scripts/fonts、startedAt/stoppedAt、bindingAtStart、trials、events、frames、eventTiming、longTasks、visibility、overhead、buffers/errors、context、harness。trial含spec/armedAt/before/after/first-lastEventId/finishedAt；input有eventAt与capturedAt、trusted、target token/id/kind、pointer/buttons、viewport与coalesced；frame的`at`是rAF动画时间，`observedAt`是DOM读完时间。full前后有完整SVG/frontier/pins/selection，frame几何只对指定objects，不能认证hidden文档/history。

在正式工程目录离线验证**本次新raw路径**，stdout/stderr分开保存、记exit code；不重跑Studio/Python大suite：

```bash
node scripts/validate_input_observation.mjs   docs/evidence/m4-hierarchy-visible-performance/product-raw.json   > docs/evidence/m4-hierarchy-visible-performance/product-validation.json   2> docs/evidence/m4-hierarchy-visible-performance/product-validation-stderr.txt

node scripts/validate_scheduling_control.mjs   docs/evidence/m4-hierarchy-visible-performance/control-raw.json   --root /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio   > docs/evidence/m4-hierarchy-visible-performance/control-validation.json   2> docs/evidence/m4-hierarchy-visible-performance/control-validation-stderr.txt
```

simple validator自动绑定raw/自身字节并核context current files；产品validator仅输出consistency字段，root应另从冻结raw/validator/probe/build同bytes hash后parse，审计后重读稳定，不改validator输出加字段。若用`--visibility`，现有simple parser**仅接受**`archcanvas-cua-visibility-observation/1`及capturedAt/browserId/attemptedSet/before/reportedAfter/controlReceipts等真实字段；root当前`visibility-attempt.json`和旧`archcanvas-cua-host-presentation-observation/1`不兼容，不能直接传，也不能通过改旧bytes修成兼容。额外连续时点读数另存原文件；即使有效v1输入为true，validator的hostPresentation仍unconfirmed。

## 5. 独立摘要应该写什么

按每session分别报告eligible/matched/interaction分母、双向唯一type/target/±8ms/正interaction匹配、每interaction取最大duration的nearest-rank p95；EventTiming阈值16ms、duration约8ms量化。缺失可能below-threshold/detached/unobserved/ambiguous，全部null，**不能补0或据此宣称<50ms**。五trial只是一条有界诊断，不是代表性p95或整个页面INP；若条件恢复且值得正式采样，才设计固定环境/次数/warm-up的完整benchmark，保留所有失败。

连续gesture独立摘要限制为真实first trusted down到同pointer up的`eventAt`闭区间：实际duration、同pointer moves/coalesced数、input event→capture延迟、该区间rAF数/间隔p95/每秒桶、DOM几何变化次数；`observedAt`窗另列，session/trial准备等待不要混入gesture分母。raw里的post-up lostcapture不算active cancellation。比较public SVG/frontier/camera/targets与source/IR/rev；pin为空不认证pin保护。

现有validator字段`frameCadence.fps`/`idleCadence.fps`实际是**rAF回调cadence**；输出保留原名、报告准确释义，不能改称≥50fps、presented frames、掉帧或连续input-to-paint。`continuousProxies`只是某input之后首个DOM几何变化，不识别因果input或paint。longtask未观测不证明没有全部系统stall；observerSelfCost类别重叠且排除browser delivery/产品telemetry/renderer/system，只是局部成本。当前工具没有compositor/presented-frame测量能力，没有方法通过这次采样关闭该门。研究者、人类审美、固定解析字体/硬件同样不由这次代理诊断认证。

活动取消独立：仅当现行CUA文档确有held-down→move→Escape/blur→release时采另一个trial并配sentinel/history/store rollback核查。atomic drag后Esc已在up之后，不能满足活动取消；operationSucceeded=false/cancelled=true也不等于回滚成功。


## 只读来源绑定

本流程检查时间：2026-10-05T00:44:05.690629+00:00。下列原bytes已缓存hash，文档写入前再次核磁盘未变化；未调用浏览器。

| 来源 | bytes | SHA256 |
|---|---:|---|
| [scripts/m4_input_harness.py](../../../scripts/m4_input_harness.py) | 3709 | `79d1a3bcd38684e1d886c3237c261c17a713ec688ff5f0d1c0f2ce1eea3f7fa4` |
| [scripts/m4_input_support/harness.html](../../../scripts/m4_input_support/harness.html) | 2531 | `ed0884ac60f7fe7d60f32d2f784b83f9e68861741c941affd25c07dfe7d86593` |
| [scripts/m4_input_support/harness.mjs](../../../scripts/m4_input_support/harness.mjs) | 2475 | `f0307f5daa3ec76f8969f2f7852e687e16c125d0a2c14c73dd9504234bb4e2d5` |
| [scripts/m4_input_support/control.html](../../../scripts/m4_input_support/control.html) | 1210 | `dd214bb2b2cc75fa37c8a04db65af59e8f6bb19458c2a802cca600d5ce99b44f` |
| [scripts/m4_input_support/control.mjs](../../../scripts/m4_input_support/control.mjs) | 3989 | `752b565fda3c5bcf90a003cb1445c2a5117a3f6cc5e8051eec306379ef3132d4` |
| [scripts/m4_input_observer.mjs](../../../scripts/m4_input_observer.mjs) | 17697 | `b7b8b11da1d267caf5fe18050545bd70a798ea395a492a470349a81041a981b0` |
| [scripts/validate_input_observation.mjs](../../../scripts/validate_input_observation.mjs) | 25888 | `21426de5e08ab0fd7bbf20008ff4f050ba63983209cf1bb00c9aef5565d6d414` |
| [scripts/validate_scheduling_control.mjs](../../../scripts/validate_scheduling_control.mjs) | 19229 | `8761d136aaa9b3172b708670c7bf7cda9716dd4c2dfe01785c0bcf4c80d22557` |
| [studio/src/App.tsx](../../../studio/src/App.tsx) | 67125 | `da7a9d95c95f32afe9f7606392dbde22abc9661cd1378e4f31fed56f1b83e7b5` |
| [src/archcanvas_cli/server.py](../../../src/archcanvas_cli/server.py) | 34405 | `44d0753a3053f507aba8c141ab419095ea47369f3bc5b5b12b555340e6339040` |
| [studio/dist/index.html](../../../studio/dist/index.html) | 477 | `a720b7b9bd4a41814d1962382985491b6e32bab71ed59fb9ee88ec50152c31da` |
| [studio/dist/assets/index-oI5sT67U.js](../../../studio/dist/assets/index-oI5sT67U.js) | 376042 | `2c769087f0765ba47892e9f26f12a19e4336ec12573dce5859ac636e310f446c` |
| [studio/dist/assets/index-DK5lov-h.css](../../../studio/dist/assets/index-DK5lov-h.css) | 27591 | `d6d5f8f4d8824f28b313ffffe685678225486e5cf25966f0528d3846eb6a8a7f` |
| [docs/evidence/m4-hierarchy-optimization/native-stress300-raw.json](../../../docs/evidence/m4-hierarchy-optimization/native-stress300-raw.json) | 3335243 | `8ad2e110e445d36b091025f98eac8215453dec05c3db78f3a0f21c386399bc5d` |
| [docs/evidence/m4-hierarchy-optimization/native-stress300-validation.json](../../../docs/evidence/m4-hierarchy-optimization/native-stress300-validation.json) | 8617 | `f08cdce0da304bdced8d1d9ea366e52e30e74b0c091b7b4557387a5d652fefff` |
| [docs/evidence/m4-hierarchy-optimization/service-lifecycle.json](../../../docs/evidence/m4-hierarchy-optimization/service-lifecycle.json) | 1094 | `9f07f8fb8cf7abaff0e9454eec1aa1bfe4203f2a6f40fe253d2ec232a4b87490` |
