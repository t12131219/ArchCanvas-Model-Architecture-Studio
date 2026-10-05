# M4 独立输入观测与调度诊断

当前平移/说明构建为 `index-DWpF-img.js` / `index-DK5lov-h.css`，新增显式手工具并修复pointerup最终相机更新。观测协议v2读取公开 `aria-pressed` 手工具状态，核对实际同pointer输入终点，不发出输入。两份本轮原始session共四次可信左键pan，终点精确匹配；完整性能验收仍未通过。Studio68/68、strict TypeScript/build通过；当前[测量工具详细反例日志](evidence/m4-pan-annotation-work/observer-tests-expanded.txt)32/32无skip，使用`--test-isolation=none`记录真实项数；它与Studio68项分别验证，不累加成产品测试总数。

旧缩放build的MLP/304对象/滚轮诊断、24项测试和原始收据保留历史范围；本轮产品改变使旧39矩阵与zoom-final五席包stale，不能称无需重采。[切换归档](evidence/before-pan-annotation-build/manifest.json)保留旧实施/build/完整矩阵/spec/core/研究包。新spec和8881–8885五席包已prepare/verify；当前[完整矩阵](evidence/browser-visual-matrix-pan-annotation-full/manifest.json)实际36/36基础＋三模型各一编辑后、39case/234工件，coverage=complete/人工pending/false，真实研究者仍0。以下先列当前v2，再保留历史诊断。

完整矩阵采集不新增性能试次。其20份公开说明编辑journal、三对save/reopen SVG一致与final rev54/22/39属于持久化/工件链；camera变化/history reset、reopen后又切preset/width并save/export均保留。helper旧URL导致37项导出副本错配，按完整Canvas/formatSVG唯一匹配实际服务工件修正，截图/时刻/DOM/Canvas不变，不称浏览器复采或再次读取链接。UA/DPR来自同浏览器先前8880 observer，硬件/解析字体未锁定；[独立字段核对](evidence/browser-visual-pixel-observation-pan-annotation-full/field-audit.json)已重建39份Canvas/DOM/publication SVG；[AI像素观察](evidence/browser-visual-pixel-observation-pan-annotation-full/pixel-review.md)记录密集小字和CNN“skip p / ath.”英文断行问题，不认证连续paint、性能、出版或真人。

## 当前v2平移证据

| 原始收据与独立输出 | 实际覆盖 | 终点/公开连续性 | 离散匹配子集 |
| --- | --- | --- | --- |
| [pan-native-v2 raw](evidence/m4-pan-annotation-work/pan-native-v2-raw.json)、[validation](evidence/m4-pan-annotation-work/pan-native-v2-validation.json) | 手工具普通左键pan两次，每次8条可信pointermove，同pointer down/up | +80/+48、+32/+20 CSSpx；最终camera精确匹配，scale、public SVG/frontier/pins/公开selection不变，rev delta0 | 6 eligible /3 matched /1 interaction；p95 2008ms，缺失仍null |
| [pan-priority-v2 raw](evidence/m4-pan-annotation-work/pan-priority-v2-raw.json)、[validation](evidence/m4-pan-annotation-work/pan-priority-v2-validation.json) | 从展开控件与输入端口起手，各8条可信pointermove | +24/+16、+20/+12 CSSpx；终点匹配，未展开或生成绑定修改，public SVG/frontier/pins不变 | 6 eligible /2 matched /1 interaction；p95 2024ms，缺失仍null |

独立validator重算input down/up的viewport-relative坐标与camera增量，读取公开hand状态并保留协议1历史兼容；拒绝错误模式、伪/错pointer、错终点和不可证明连续性等反例。连续pointermove仍只有首次DOM变化proxy，不证明因果输入或paint。首末捕获帧区间的 rAF callback cadence约1.88/1.86次/秒，分母为lastFrame−firstFrame，包含准备/等待；按真正start/stop会话区间计算则约1.8715/1.8673次/秒。两者都不是持续pan的呈现FPS。buffer完整与没有active long task也不认证系统顺畅。当前观测器SHA256为 `b7b8b11da1d267caf5fe18050545bd70a798ea395a492a470349a81041a981b0`，独立validator为 `21426de5e08ab0fd7bbf20008ff4f050ba63983209cf1bb00c9aef5565d6d414`。

[Transformer独立UI核对](evidence/m4-pan-annotation-work/ui-field-audit.md)另记录+64/+40 camera，十份viewport一致，SVG/rev18/frontier/pin与按钮状态不变；公开selection数组与status文案不一致，不能据此认证隐藏selection/history。选择工具端口仍proposal，模态guard有[实际按键记录](evidence/m4-pan-annotation-work/modal-keyboard-guard.json)；进行中gesture cancel目前只有pure测试/代码证据，没有原生取消样本。既有说明正文重叠消除、新说明、undo/redo和rev23保存重开另按字段与真实导出核对；reopen camera变化、history重置。

## 历史缩放build的工具与来源

[开发测量服务](../scripts/m4_input_harness.py)继承正式 loopback 服务，仅增加固定 `/__m4/` 只读路由。正式 Studio 以同源 1280×720 iframe 加载，API、资产与持久化沿用正式实现；存储是 `.archcanvas/m4-input-observation/documents`，没有使用原型目录、用户服务 8765 或真人试用席位。测量页面自身在 scripts 目录，正式产品页面没有新增测量控件。

[独立观测器](../scripts/m4_input_observer.mjs)读取公开 DOM、可信输入、Event Timing、long task、rAF 与自身 callback 区段成本，不读取产品 window 全局或发出输入。外页按钮仅开始/准备/结束观察；产品操作由 CUA 普通点击、拖动与滚轮完成。当时的 SHA256 为 `fb409d86902457647f7506028623343492a7e6f4d39de346ed9a3906cb84c9af`；当前v2字节另见上节。首次 pilot 使用的是历史探针，[存档字节](evidence/input-observation/observer-pilot-source.mjs)已按原始上下文摘要核对，不能将其改称当前探针。

[输入校验器](../scripts/validate_input_observation.mjs)不导入观测器或产品代码，独立计算事实与指标。原生条目按名称、实际 target token、±8 ms、正 interactionId 建立双向候选图，只有两侧均唯一时才匹配；同 interaction 的离散事件以最大 duration 计一次。缺失、歧义与截断不会变成零延迟。13 个独立反例覆盖竞争条目、错目标、伪输入、错误变换、缺少 pointerup、取消、无动作撤销、离屏 pin 与 buffer 丢失。

历史缩放探针收据声明的 3 个 production 和 6 个 probe 文件的哈希/大小都与实际磁盘字节相符；JS 文件名也在 iframe DOM scripts 中观察到。实际网络 response body 未另行捕获，因此不将磁盘绑定升级成响应字节证明。其正式 JS 为 `index-oH4Ot2L9.js`，SHA256 `2e77f8616f8408afc985740e77b6a69c7728816f7ec4231f0ee7fe9224752e9f`；当时冻结verify通过。本轮build改变后这些是历史绑定，当前矩阵须使用新spec单独采集。

## 简单页面对照

[独立简单页面](../scripts/m4_input_support/control.html)没有 React、SVG、模型或产品遥测。两份 20 秒窗口分别记录 40 / 384 个 rAF 时间戳，目标按钮的一次匹配交互 duration 为 1000 / 2016 ms。第二窗前 14 秒慢、后 6 秒回调加快；不能仅用全窗 p95 16.8 ms 将其称为持续 60 FPS。

[对照独立报告](evidence/input-observation/scheduling-control-comparison.md)保留秒桶、长间隔、匹配与探针成本。浏览器 capability 在 `set(true)` 前后都返回 false；文档 visible/focused 不证明宿主呈现。两窗 viewport 也不同，非随机窗口不能建立可见性或视口变化的因果关系。这些事实说明低频调度在简单页面中也存在，尚不能确定 Studio、系统或宿主的原因。原有失败性能记录仍保留。

后续另封存[宿主可见性为 true 的第三窗](evidence/m4-visible-host-control/README.md)，没有回写上述两窗或原 bundle。20,000.4 ms 内仍为 40 次 rAF，每个完整秒桶 2 次；一次匹配交互 1016 ms，pointerdown 缺失保持 null。宿主 capability 的前后两次读数为 true，但后读数比窗口结束晚 54.5637 秒，不能证明连续呈现。独立 validator 未摄入该 capability 文件，原 `hostPresentation=unconfirmed` 仍保留。这个对照不确立可见性或低频调度的因果关系。

## 历史缩放build的实际操作结果

| 原始收据与独立输出 | 实际覆盖 | 离散原生子集 | 首末 rAF 时间戳区间回调差分率，非呈现帧率 |
| --- | --- | --- | --- |
| [MLP raw](evidence/input-observation/MLP-final-observer-raw.json)、[validation](evidence/input-observation/MLP-final-observer-validation.json)、[独立审计](evidence/input-observation/MLP-final-observer-audit.json) | 展开、拖动、撤销、重做、缩放按钮、固定，共 6 试次 | 17 eligible / 16 matched；6 interactions；p95 2016 ms | 约 1.83 次/秒；trial 含外页操作与等待，不能称持续拖动 FPS |
| [stress300 raw](evidence/input-observation/stress300-final-observer-raw.json)、[validation](evidence/input-observation/stress300-final-observer-validation.json)、[独立审计](evidence/input-observation/stress300-final-observer-audit.json) | 展开后实际 304 scene objects，拖动、撤销、重做，共 4 试次 | 11 eligible / 10 matched；4 interactions；p95 2016 ms | 约 1.94 次/秒 |
| [stress300 wheel raw](evidence/input-observation/stress300-wheel-raw.json)、[validation](evidence/input-observation/stress300-wheel-validation.json)、[独立审计](evidence/input-observation/stress300-wheel-audit.json) | 1 条可信 wheel，相机 scale 改变 | 0 eligible，原生延迟为 null | 约 1.98 次/秒 |

表中差分率为 `(N−1)×1000/(末帧−首帧时间戳)`。整 session 的 `N×1000/(stop−start)` 分别为约 1.827 / 1.934 / 1.954 次/秒；两种分母明确分开，均不认证呈现帧率。

MLP 与 stress300 的 Linear 1 从 canvas `(110,316)` 拖到 `(150,340)`，即 `+40/+24`，按编辑网格吸附。独立审计比较完整所选对象事实、camera、frontier 与 pins，确认 undo 恢复拖动前状态、redo 恢复拖动后状态，不能只凭 revision 增量称操作恢复。源/IR digest 未改变，buffer 完整、错误为空。

每次拖动有可信 down/up 和 8 条 pointermove，并各有 8 个 DOM 变化 proxy。proxy 表示某输入后首次观察到所选几何变化，不识别因果输入，也不证明 paint；原生 drag pointerdown 缺少匹配，保持 null。wheel 同样只给 DOM proxy，Event Timing 不覆盖 wheel 或 pointermove。压力场景展开/撤销/重做各记录一个 ≥50 ms long task；其他试次没记录到此类条目不能证明没有系统停顿。

压力拖动实际 down→up 为 8062.2 ms，该有界区间内 16 次 rAF、8 次目标几何变化，间隔交替约 16.7/983.4 ms，最大 983.4 ms。8 条 move 的事件到 capture 已约 897–953 ms，DOM proxy 约 950–1015 ms；滚轮 proxy 1004.8 ms，其中事件到 capture 为 998.4 ms。保留这个代理自动化输入序列的原始时序，不将 8 秒称为正常人工拖动耗时或用其计算用户体验成功率；这些数据仍不能定位 CUA、宿主、系统或产品调度的原因。

展开锚点在 iframe client 坐标的位移为 0；原有固定 input 的 canvas 坐标保持不动。MLP 缩放 trial 的 pin 起点在 viewport 外，不能称可见 pin 全程保护；其余试次仅证实 body 与 viewport 相交。MLP 独立 audit 的 `protectedPin.before/after` 字段表示 viewport 相交情况；trial5 的 false→true 是可见范围变化，raw 中该对象的 pin membership 始终存在。外页在准备控件时自动滚动，frame 顶部从 82 变为 144 px；因此 iframe client 连续性不能升级为宿主屏幕位置不变。iframe 焦点在外页操作与产品输入间切换，top 始终 hasFocus，不是全程 iframe focused。

[MLP 普通 Save/重开后的 DOM](evidence/input-observation/MLP-save-reopen-DOM.json)及[截图](evidence/input-observation/MLP-save-reopen.jpg)显示 revision 6、拖动位置与两个固定 ID 仍在；[存储核对](evidence/input-observation/MLP-save-reopen-audit.json)确认选定几何、源绑定、frontier/pins 与实际 DocumentStore bytes 及最终试次相符。这是持久化观察，不证明历史栈跨刷新恢复，也不纳入输入性能试次。

首轮 pilot 的请求拖动没有命中预设子节点，实际移动了父容器。其[原始记录](evidence/input-observation/MLP-pilot-raw.json)和[独立校验](evidence/input-observation/MLP-pilot-validation.json)中，请求 drag 试次保留为 no-input，不能计算到 requested drag 的覆盖中；同份收据的 zoom/toggle 是已观察到的独立试次。

## 可复核运行与剩余门

```bash
PYTHONPATH=src .venv/bin/python scripts/m4_input_harness.py --port 8773
node --test --test-isolation=none \
  tests/m4_input_observation.test.mjs tests/test_scheduling_control.mjs
node scripts/validate_input_observation.mjs \
  docs/evidence/input-observation/MLP-final-observer-raw.json
```

历史独立测量工具24项测试通过，记录在[测试日志](evidence/input-observation/independent-tool-tests.txt)。这是新工具的有界验证，不加入历史 Python 219/Studio 54 的总数。当时没有为这些历史观测运行生产rebuild或模型forward；当前v2对应上节的新build。

历史版本没有原生pan覆盖；当前显式手工具已取得上述四次可信左键pan终点证据。固定原生浏览器/硬件/实际解析字体、持续连续输入到呈现、计划性能目标、当前矩阵工件已完整，真人出版审看、3–5位实际研究者任务仍未通过。真实研究者仍0；[当前接手说明](m4-human-review-handoff.md)指向新五席包，M4保持partial。

另有[完整 Transformer 自动化任务](evidence/automation-full-task/README.md)补充同文档对象编辑、保存重开与实际导出工件链。该任务未附加输入 observer，不属于本页原生或连续输入采样；5/5 是 automation 自报，不能加入真人分母。字段/历史验证、祖先容器增长、视口变化、85 mm 可读性与 PDF 浏览器空白均单列，不将任务完成记录升级为性能或出版通过。
