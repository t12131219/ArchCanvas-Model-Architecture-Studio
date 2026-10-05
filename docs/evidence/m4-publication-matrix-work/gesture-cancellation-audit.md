# M4 手势取消：只读代码与证据审计

本审计绑定最终 `index-DPwoyNJW.js`（SHA-256 `c7189a047fbd29cba25779a9098d5b2c1265e21c827620834379d0e611af3bc4`）。没有修改产品源码、构建、测量工具或既有证据；没有控制浏览器、启动服务或重跑测试。结果来自现有代码、实际保存的测试日志和历史原始收据，不能认证原生取消、真人、出版或性能。机器可读范围与输入哈希见 [gesture-cancellation-audit.json](gesture-cancellation-audit.json)。

## 结论与需求边界

现有 Studio 有 `Escape`、`window blur`、同一 pointer 的 `pointercancel` 和 `lostpointercapture` 取消路径；节点 preview 与相机导航的纯函数性质有测试证据，但 UI 的 capture/RAF/React 生命周期取消没有直接执行测试，也没有已采集的活动手势原生取消样本。

正式计划书 §9.1/§9.6（第591/641行）要求 RAF 临时预览、pointer-up 形成一个命令；§9.5（第631行）要求文本 Enter 提交、Esc 取消、输入/IME 期间不触发画布快捷键。[Skill visual-workflow.md](../../../skills/archcanvas/references/visual-workflow.md)第35/37行对应完成拖动单历史命令和文本 Esc 合同。检查计划书、AGENTS 和 Skill 后，没有找到“页面 hidden 必须取消活动手势”的明文要求。因此 **hidden-only 路径是增强建议和此次指定审计的未覆盖项，不是已证明的产品违约或实际浏览器缺陷**。

## 产品取消路径

以下行号均指当前源码 [App.tsx](../../../studio/src/App.tsx)。

| 路径/对象 | 代码行为与行号 | 当前证据边界 |
| --- | --- | --- |
| 共同取消 | 110–120：先清 `gesture`/`portGesture` ownership 并增加 request generation，再取消 RAF、清 preview/box/port draft/isPanning，最后按 capture 状态释放。先清 owner 可避免 release 引起的 lostcapture 重入。取消函数不调用 `apply` 或 `reduceHistory`。 | 静态代码证据；没有活动取消的原生事件顺序证明。 |
| 相机 pan | 283–284 起手保存原 camera；339 更新临时 camera；117 在取消时恢复原 camera/ref。349–374 的正常 pointer-up 同步计算最终坐标、清 owner 后释放 capture。 | 8项 camera helper 测试证明坐标/终点/快照，不能证明 UI rollback 或原生 capture。 |
| 节点 move | 309–315 起手可改变 selection，但仅创建 frozen preview session；341 对当前 document 引用校验；取消清 preview。375 只在匹配 document 且 pointer-up 超过阈值后 `apply` 一次。 | 6项 preview测试证明 history/frontier/architecture 不变和一次 commit/undo/redo；无取消 handler测试。 |
| 框选 | 319–321 可先清 selection，保存 Shift 初始 IDs；346显示 marquee；376–381仅正常 pointer-up 完成框选；取消清 box。 | 没有对应 UI/原生取消测试；selection不一定回到起手前。 |
| 输入端口提案 | 290–301创建 port draft与异步 candidate读取；取消清 owner/draft并增加 request generation。300与358/362的 promise守卫防取消后旧回复创建提案；pointer-up本身只创建提案，不提交源码。 | 代码守卫存在；没有“取消先于异步回复”的原生 race样本或纯生命周期测试。 |
| Escape | 238–254：编辑目标或任一 modal存在时全局处理器先return；244否则取消并清 selection/inline。 | 不是“保持 selection原样”的合同。输入焦点下不能假定全局取消执行。 |
| window blur | 122–126：清 Space标志并共同取消。App listener非capture，内部input blur不等于window blur。 | 无活动手势原生 blur样本。 |
| pointercancel/lostcapture | 384–386只对活动owner同一pointer取消；578挂接两个React handler。正常pointer-up在释放前清owner，因此随后的lostcapture不会取消已完成操作。 | 无活动capture丢失样本；历史4pan的正常release后lostcapture不是取消证据。 |
| hidden-only | App没有visibilitychange监听。[perf.ts](../../../studio/src/perf.ts)95–98/135只记录可见性，不调用共同取消。 | 若宿主hidden同时发送blur，既有blur路径可能取消；不能从hidden本身推断已取消。未执行hidden-only反例。 |
| 工具/modal/其它操作 | 121/247–248切工具，127打开modal，130视觉apply、142–143undo/redo、146fit、179载模型、519import、527/536focus、557zoom均先共同取消。262活动gesture时忽略wheel。 | 代码证据；modal期间实际按键guard历史证据不等于“打开modal时取消活动drag”。 |

当前没有 route/annotation/legend 原生拖动：`Gesture`类型仅 move/pan/box（App23），port单列。edge/legend/annotation在316–318仅选择并return。注释“移到图下方”通过550–554的显式annotation操作；607提供文本/移动/删除按钮。EdgeStyle只有stroke/width/dashed（[types.ts](../../../studio/src/core/types.ts)62/84–94）；没有手动拐点/走廊gesture。不能把这些未实现交互的取消标成通过。

文本取消另有合同：App585原位alias输入用`inlineCancelled`避免Esc卸载/blur提交；624–628的TextField用cancelled标志恢复已提交值、blur不提交，Enter转为blur提交；IME时return。这些是文本代码路径，没有对应React事件次序测试。annotation/legend的TextField使用同一路径，但不等于annotation/legend拖动取消。

## 已有 meaningful 纯测试究竟证明什么

- [camera-gesture.test.ts](../../../studio/tests/camera-gesture.test.ts)8–70：8项，覆盖无move/RAF的terminal endpoint、超出最后preview的终点、CSS像素与zoom无关、返回初始坐标无漂移、viewport原点变化、错误pointer、snapshot/input不可变和非法输入。helper没有cancel函数；“返回起点”不是“Esc恢复camera”。
- [move-preview.test.ts](../../../studio/tests/move-preview.test.ts)29–35/38–126：6项，以独立手写结构/routing事实核对完整Scene/SVG、parent/child只移动一次、pin、稀疏/hidden layout、history/frontier/source未改、一次commit与undo/redo、冻结snapshot和非法session。80–99明确多帧preview不改history bytes。丢弃preview因此有可靠基础，但没有执行App cancelGesture。
- [annotation-placement.test.ts](../../../studio/tests/annotation-placement.test.ts)90–115/118–144：复杂展开不移动旧note；显式移到图下方是一个历史操作、保留architecture/layout、支持undo/redo及持久化SVG。不是annotation拖动/取消测试。
- [core.test.ts](../../../studio/tests/core.test.ts)55–73：拒绝语义字段注入/过期revision及整批history恢复，提供共享命令基础；不是原生取消证明。
- [最终Studio日志](../m4-publication-refinement-work/studio-tests-final.txt)保存79/79通过、0fail/skip。上述测试属于其中；本审计没有重跑或新增计数。日志中的`cancelled 0`是Node测试运行器计数，不能解释为手势取消覆盖。
- 外部独立工具 [m4_input_observation.test.mjs](../../../tests/m4_input_observation.test.mjs)140–143、311–343用手写输入反例拒绝cancel/missing/wrong pointer为成功drag/pan；普通pointer-up之后的lostcapture不追溯取消。它测试的是validator拒绝错误成功声明，**没有断言产品rollback正确**。 [m4_input_observer_trigger.test.mjs](../../../tests/m4_input_observer_trigger.test.mjs)94–109测试observer Space状态在window blur清除、忽略内部blur/输入框Space。[32/32旧工具日志](../m4-pan-annotation-work/observer-tests-expanded.txt)是独立工具来源，不能加入Studio79总数或冒充新浏览器样本。

## 原生观测工具的能力与缺口

[m4_input_observer.mjs](../../../scripts/m4_input_observer.mjs)只读DOM，不导入Studio、发input或读React私有状态。第3行记录down/move/up/cancel/lostcapture/click/key/wheel/window blur，69–82有trusted、pointer identity、时间、viewport与coalesced samples；138–148过滤内部blur并处理Space；171/213记录visibility/focus。102–131记录paper CSS camera、目标body几何、source/IR/revision、SVG/frontier/pins/selection markup；full前后与RAF之间证据不同。

其operation枚举（第2/92–99/216–223行）只支持drag/pan/zoom/undo/redo/toggle/pin；没有box、port draft、route、annotation drag或text-edit trial。最多100trial、各buffer有dropped；不能把缺失/截断当0延迟。 [NativePerformanceSession](../../../studio/src/nativePerformance.ts)10–13/111–127只抓tree click与expand控件pointerdown的expand/collapse，也不能补齐一般取消。

[validate_input_observation.mjs](../../../scripts/validate_input_observation.mjs)185–190把首次down至对应up之前的同pointer cancel/lostcapture、window blur、Escape标为cancelled，222–224阻止算作成功drag/pan。**cancelled:true只是中断分类；当前没有cancellationSucceeded/rollback判定。** 196–200明确public SVG/frontier/pins/selection不认证hidden Canvas/history。full geometry中的preview revision可能是base+1（[movePreview.ts](../../../studio/src/core/movePreview.ts)64）；不应凭preview SVG revision认定历史已提交。

具体待改进项（本轮仅建议）：

1. 若将hidden-only纳入正式取消合同，App需在`document.visibilityState === 'hidden'`时清Space并cancel；同时增加针对pending RAF/随后pointer-up/随后promise回复的适配层反例。现有文档没有这项明文，修改前应先准确登记范围。原生隐藏试次需确认事件是否同时包含blur；否则不能归因为hidden。
2. observer有visibility trace，但validator第90行只验证格式，189不把hidden列为取消。当前不能用它认证hidden取消；下一版应单独分类中断原因并核camera/baseSVG回滚，而不是仅让`operationSucceeded=false`。
3. App240在editingTarget时先return，而canvas pointerDown323的preventDefault可能保留此前input焦点。若在输入框尚聚焦时开始canvas手势，Esc可能只走文本取消或被忽略；这是**待原生复现的焦点风险**，不是本审计已执行缺陷。validator189目前无editing/modal条件就把任意Escape标cancel，与App合同可能不同；应保留target和modal证据、避免虚报产品已取消。
4. 原生UI的undo栈、document bytes仍需额外可观察验证；比较SVG不能认证内部相等。取消node/box的selection可以按上述合同变化，不能以“前后selection不等”单独判为文档损坏。

## 最小下一步原生实验（本审计未执行）

优先做两次独立试次：正常窗口/无input焦点下的 **活动pan + Esc** 与 **活动node drag + Esc**。使用另一个独立data-dir的正式DPwoy输入测量服务，不碰当前矩阵/user文档或8881–8885研究席位；按服务帮助核对实际路径、context资产哈希和真实生命周期。现有measurement harness仅准备/结束观察，不模拟输入。

1. 在小前沿MLP通过普通控件准备一个确定的sentinel视觉编辑，保存；记录实际CanvasDocument/source文件哈希、revision、source/IR、完整SVG/frontier/pins、camera、undo/redo按钮状态和截图。node试次按目标canonical ID通过公有DOM定位；pan先选显式手工具。
2. 通过宿主已支持的可信原生输入保持down，移动超过阈值，等待至少观察到一个临时camera或node几何变化，**尚未pointer-up时**按Esc；随后release同pointer，再移动。使用CUA真实输入能力；若宿主只有自动完成down→up的drag调用，不能以串接普通click或`dispatchEvent`伪造活动取消，保留“能力未满足”。
3. 确认raw中对应down/move、Esc早于up，记录实际cancel/lostcapture顺序；采取消后至少两次独立DOM状态/截图。pan应回原camera；node应回baseScene（不计选框等编辑装饰）。两者实际document revision、saved bytes、frontier/pins、canonical bindings/source/IR应保持，source bytes未写；不得将Esc清selection列失败。
4. 用普通Save核对真正DocumentStore bytes；普通Undo应撤销sentinel一次，Redo应恢复sentinel一次，再save/reopen比较。这个有界行为验证可以排除多插入的取消命令，仍不认证全部hidden历史内容或跨刷新历史持久化。后续另做一次正常drag，确认捕获/RAF残留没有阻止新操作。
5. 对window blur、lostcapture、pointercancel分别追加试次：只使用宿主确实支持的自然输入/焦点路径。返回后release/move，检查是否迟到提交；严格根据raw实际事件命名。正常up之后lostcapture不能算活动取消；混合blur+lostcapture只能证实该组合。hidden-only试次必须看到visibility hidden且活动区间无blur/cancel/lostcapture，能力不足时保持未采集。

port提案异步取消、box selection和文本Esc需要新observer operation或另附只读DOM事件journal（与当前build绑定）；不能复用“成功pan”的validator条件。纯测试下一轮应针对UI取消状态机/adapter的可观察不变量，而不是复制实现行数。任何原生输入试次均是代理操作诊断；不认证真人、continuous input-to-presented paint/FPS、字体解析或M4完成。
