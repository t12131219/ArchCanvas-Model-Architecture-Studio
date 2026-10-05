# M4 当前构建原生输入与活动取消：只读采集方案

本方案只审阅正式工程与既有独立测量工具。未启动服务、控制浏览器、安装依赖、修改产品、回写旧证据或取得新性能试次；UI actions = 0，真人 = 0。审阅输入和构建的确切哈希见 `requirement-evidence-map.json`。如后续产品或构建改变，重新绑定相关输入，不把本方案或旧收据提升为新版本验收。

本轮优先完成当前构建的完整视觉矩阵。随后可以用普通 UI 取得原生展开/收起收据，并复用已有独立输入观测台补充拖动、平移、撤销、重做、缩放与固定的工程诊断。当前宿主只能完成 atomic drag，不能在 pointer 仍按下时插入按键或失焦；也没有已确认的 compositor/presentation trace。因此进行中的手势取消、持续 input-to-presented-paint 和 presented FPS 保留缺口。子 Agent 或可信自动化输入都不能增加真人分母。

## 需求与证据范围

| 需求 | 现有可用机制 | 最小补采与仍未证明的事项 |
| --- | --- | --- |
| 计划书 §9.7 / 第649行：真实 input-to-paint、长任务与帧率；DOM/几何完成不能替代顺滑度 | `nativePerformance.ts` 捕获可信展开/收起；`perf.ts` 提供 Event Timing、long task；独立 observer v2 记录可信输入、离散 Event Timing、rAF、long task、自身成本 | 在当前构建普通 UI 采集，保留 eligible/matched/missing 数与原始 buffers。离散匹配子集不是整页 INP；pointermove/wheel 的 DOM proxy 和 rAF cadence 都不能证明持续呈现。 |
| §9.5 / 第632行：展开屏幕锚点、无关 pin、再次展开恢复局部布局 | native 记录 body 起点的 canvas/window-client 坐标与 frontier；独立 observer 记录公开 SVG、camera、viewport、frame bounds | 使用确实无关、可见的 pin，展开→收起→重展开，比较完整局部坐标/routes。native 的 body 起点不是完整 SVG 或局部布局恢复证明；iframe client 稳定不等于宿主屏幕稳定。 |
| §9.6 / 第640行：pointer-up 一次命令；§9.7 / 第647行：长任务可取消，旧 generation/digest 不得覆盖新文档 | App 的 ownership、RAF、document identity、load sequence/request guards；AuthoringStudio 有独立草稿与取消路径 | 普通完整 drag + undo/redo 可补已提交命令证据。活动取消及取消先于异步回复必须具备 held-down 事件次序/中途公开 preview；当前 CUA 不支持，代码存在不等于原生执行通过。 |
| §18.1 / 第1225、1227行：固定 browser/hardware/fonts/DPR/page/scale，并采截图与交互 | receipt 的 UA、DPR、viewport、字体加载状态、DOM build URLs；harness 的磁盘 build/probe 哈希 | 同一会话记录实际页面规格与对象规模、top/frame bounds/focus、开始/结束环境。font status 不能锁定 resolved fallback bytes，UA 不能锁定硬件，磁盘哈希不能自行证明网络 response bytes。缺失项写 unknown。 |
| §17.2 / 第1194行：M4 真实浏览器性能和研究任务门 | 工程收据、真实矩阵、人审包分开保存 | 原生工程诊断只能推进覆盖；真人、出版审看、持续呈现或固定环境仍缺失时 M4 partial，不能进入 M5。 |
| §18.5 / 第1274、1281–1285行：Beta 数值目标 | p95、anchor、pin、long task 和 rAF 等可计算字段 | 50ms / 50fps / 8px / 500ms / ≥80% 是计划明确写出的 Beta 目标，不是现有数据，也不能新增解释成每项独立 M4 数值退出门。记录实际值与目标，缺失保持 null。 |

## 可立即执行的最小真实 UI 协议

以下是待执行流程，不是运行记录。根 Agent 拥有浏览器；采集前确认建议端口空闲，使用新持久化目录，避开用户 8765、矩阵服务与五个人审席位。无需重新编写 observer 或修改正式 Studio。

```bash
PYTHONPATH=src .venv/bin/python scripts/m4_input_harness.py \
  --port 8982 \
  --data-dir .archcanvas/m4-bcf-native-performance/documents
```

1. 通过受支持的 CUA tab 在 `http://127.0.0.1:8982/?benchmark=1` 打开正式 Studio。选择一个有已证明非根容器的模型，记录实际示例、source/IR digest、document ID/revision、loaded JS/CSS URLs、当前物理页宽/配色、camera、viewport/DPR、可见对象规模。当前审阅 build 名称/hash只说明磁盘字节；采样时必须重新核对实际 DOM scripts。
2. 用普通 UI 固定一个无关叶节点；记录其 ID、body 可见且与 viewport 相交、与待展开容器既非祖先亦非后代。native 过滤 target 和后代，未过滤祖先；不要用祖先 pin 代替无关 pin。记录目标 body 的窗口坐标、容器局部布局与 routes。性能浮层可能遮挡画布，记录可见区域，不把该环境等同普通矩阵页面。
3. 点击 **开始原生输入采样**。预先声明 pilot 为两次展开/收起循环，加一次重展开，共五次独立动作；每次只使用树上的展开控件或画布的展开控件之一，明确路径与 target stable ID。等待可观察到该动作的 frontier/revision 变化，并留出两次 rAF 的 geometry boundary，避免上一试次未结束就发下一个动作。慢调度时不能用固定一秒等待声称稳定。
4. 点击 **结束原生输入采样**。从公开 readonly **原生性能 JSON** 读出完整 raw；避免工具截断。保留全部 missing/null/error/buffer 情况、起止截图与操作 journal。pilot 不能代表足够样本的总体 p95；需要扩样时另行预声明次数、固定场景与环境，native 目前最多100个 trial。
5. 对独立保存的 raw 运行下列 checker，保留 stdout/stderr/exit code。再核对所有计划动作确实 targetChanged、revision +1、digest不变、有 anchor 与可见无关 pin；不把 validator 返回 `validated-engineering-receipt` 改成性能验收通过。

```bash
node scripts/validate_native_performance.mjs \
  docs/evidence/m4-bcf-browser-matrix-work/native-performance/raw.json
```

6. 用 raw 里的 `interactionId`、时间与 stable target 核对离散子集，单列 interaction 去重后的最大 duration 与 eligible/missing 数。native 原有 summary 是按 valid trial 计算的匹配子集 p95，保留原字段并说明其范围；不要改 raw、补零或把它称为总体 INP。首末 rAF 的 `(N−1)/(last−first)` 只称回调 cadence；该分母包括准备/等待，不能称持续展开呈现 FPS。
7. 如 UI 自身错误、服务退出、目标命中失败或未完成 geometry sampling，原始失败照存。重试使用新 session/文件名；不能覆盖失败 raw 或把错误 trial 加入成功覆盖。

不要用 **运行20组性能采样** 补原生输入。这一按钮在真正浏览器里运行，但 `perfBenchmark.ts` 通过 `.click()` 发出 synthetic 控件事件，且 frame window 与整个40动作循环并非同一区间；只能报告 handler/two-rAF proxy 工程采样。

## 复用独立输入观测台补充四向操作

在同一隔离服务打开 `http://127.0.0.1:8982/__m4/`。外页只控制观察器，正式 Studio 是未改构建的同源1280×720 iframe；当前宿主窗口未必容得下完整 iframe，必须记录实际 frame rect、top/iframe focus 与外页滚动。

1. 在 iframe 的普通 UI 打开目标模型，并记录期望节点/anchor/pin 的公开 stable ID；选择 **完整输入观测** 后点击 **开始会话**。同一会话不更换 build/模型；不同模型或压力场景使用独立会话。
2. 外页选择 **拖动节点**，填 target IDs 和 anchor IDs，点击 **准备此操作**；通过 CUA atomic drag 在 iframe 内完成一次左/右/上/下中的明确方向。每次结束后点击 **结束此操作**，分别保存四个 trials，不把四方向合成一次 drag。移动量大于误触阈值且避开展开/端口/文字输入控件；从公开 DOM 校准实际命中节点，不能只凭点击坐标假设。
3. 在正式 UI 切换 **平移画布** 手工具，再为四向 pan 分别准备/结束 trial。observer v2 可以从公开 `data-canvas-tool` 与 `aria-pressed` 确认 pan 模式，并核对同pointer up与 viewport-relative camera终点。不要在选择工具下拖空白后称已测 pan。
4. 对已提交的 drag 分别观察 **撤销** 与 **重做**，比较完整公开 scene/SVG/frontier/routes/geometry。不能只用 revision变化宣称恢复；camera pan 不属于模型布局历史命令。另采 toggle、pin、zoom button；wheel若需要普通 CUA scroll，报告实际 wheel 与 camera改变，但 native Event Timing 不覆盖 wheel。
5. 每次变更后保存全图与局部路由截图，审查端点是否脱离、节点/文字是否覆盖、意外穿越、额外折点与无必要相交；AI观察只能列工程发现，不能填真人美学栏。目标拖动即使成功也不等于视图美观。
6. 点击 **结束会话并显示收据**，从公开 readonly **原始输入测量收据** 保留完整 JSON并运行独立 validator。该工具已做双向唯一匹配与 interaction 最大 duration去重，优先使用它解释输入匹配，不重复实现一套新系统。

```bash
node scripts/validate_input_observation.mjs \
  docs/evidence/m4-bcf-browser-matrix-work/native-input/full-raw.json
```

`operationSucceeded` 的范围是可信事件序列与已提交公开 DOM事实；`completeBuffers`、longtask0、iframe visible/focused 都不证明 smooth/presented/human。`continuousProxies` 只表示某输入之后首次观察到几何改变，不能辨别造成该帧的因果输入。压力场景应记录实际scene对象数；计划的300对象目标不能用可见DOM之外的 canonical节点数充当。若要分离观测器自身开销，可用现有 **轻量 rAF 对照** 和 `/__m4/control`，但非随机、环境不同的历史对照不能归因当前宿主或产品。

## 活动取消所需证据与当前能力缺口

根 Agent 确认当前 CUA Tab 的 documented 接口只有 `drag(from,to)`、click、presskeys、scroll；无可交错 mouse-down/move/up。Playwright接口也没有相应 held-down primitive，且没有已确认 presentation recorder。此报告来自本轮根 Agent 对已加载 CUA文档的核对，本子任务没有自行打开浏览器或读取其文档。禁止为补样本使用 `dispatchEvent`、eval修改产品状态或私有React状态。

后续只有在真人或另一已获授权且确实支持 held-down 的宿主可用时，才执行以下协议：

1. 记录 baseline source/IR、revision、完整公开SVG/frontier/body/routes、camera及已有历史的可观察操作链。在画布开始node move或pan，保留可信同pointer down→move及仍按住的中途公开preview。不能以正常drag已完成后再按Esc代替。
2. 在同pointer up之前，以Esc或真正window blur取消。observer v2能够记录Esc、window blur、pointercancel、lostcapture；它会将这些drag/pan拒绝为正常成功，但没有独立 `cancel` operation或rollback通过声明。需要旁侧人工/原生journal绑定事件次序和中途/取消后DOM。
3. 等待实际观测帧，确认preview/port draft不再出现，node move没有新文档命令，pan回到起手camera。Esc可清selection、pointerdown可选中节点，现存合同没有要求所有selection回滚，不以selection差异单独判产品违约。
4. 释放原pointer，检查late up不追加命令；再完成一条新drag并undo/redo，确认新操作为一次命令，取消没有插入历史项。保存前后完整Canvas/公开SVG，只凭DOM不能认证隐藏history bytes相等。
5. 对端口异步候选等场景，还需证明取消早于未完成回复，晚到reply不重开提案；对源码/文档切换，证明旧generation/digest回复不覆盖新文档。仅看到代码guard或迅速切换页面不是race样本。

当前 App 在取消时先清gesture/port ownership与request generation，再取消RAF、清preview，pan恢复原camera，最后释放capture；pointer-up清owner之后出现lostcapture是正常结束，不是活动取消。源码同pointer guards/late generation checks与纯helper测试提供基础，但不能宣称已原生执行UI取消。AuthoringStudio也有取消与pan恢复路径，native展开采样与当前独立 `.publication-scene` observer都不覆盖草稿画布性能/取消，不能继承论文图证据。

## 测量系统的小范围问题与处置顺序

| 问题 | 实际影响 | 当前最小处置 |
| --- | --- | --- |
| native matching按trial顺序消耗event entry，未建立跨trial双向候选图（`nativePerformance.ts:23`；native validator重算相同算法） | 竞争同条目时首trial可获分配；checker复制算法一致不是消除歧义证明 | 采集动作间隔、保存全raw；用独立候选核查。需要产品修正时仅改匹配合同并加竞争反例，不为获取通过而调阈值。 |
| native summary按trial计duration，未按interactionId取最大去重（`:53`） | 值应称matched-trial subset；不能称总体INP或独立interaction p95 | 保留原summary，附单列去重值及样本/缺失率；优先使用已有v2独立validator的interaction summary。 |
| native validator未验证完整environment、longtask/buffer/build，first/last时间有限性/顺序与interval sum未完整交叉检查；允许空trial与zero intervals | 一致性返回值不保证采样覆盖、时钟完整、长期帧缓存未丢、长任务窗口或固定环境 | 对raw做旁侧检查并写coverage/missing；未来必要时加有针对性的独立反例与metadata/timebase检查，当前不重写测量系统。 |
| native只比较target body起点与pin起点；pin unrelated过滤不排祖先，没viewport可见交叉检查 | anchor起点位移不证明完整层级/routes恢复；offscreen pin不能当可见保护 | 明确挑选无关可见叶pin，另存完整 scene/SVG 与body/viewport交叉；不扩大native字段结论。 |
| 所有fps字段来自rAF callbacks；无presented frames/active-only连续帧证据 | FPS目标仍未认证；缓存/等待可使全窗cadence与实际拖动不同 | 标注rAF cadence及分母；保留active down→up桶/间隔，但presented gap保留。需要真实性能诊断时使用宿主真实presentation trace，不调目标。 |
| font-load/UA/visible状态信息不足以锁定resolved fonts/hardware/宿主持续呈现；observer selfcost不能隔离system/product CPU | 无法完成固定环境或根因判断 | 缺失写unknown；另收supported host metadata/trace，旧简单页面失败/低cadence原样保留，不推断原因。 |

先完成矩阵和当前native工程收据。只有新raw暴露具体renderer瓶颈或测量合同缺陷影响结论时，再开展对应的小范围诊断/产品修改；本方案没有要求修改阈值、安装工具或把现有缺口默认为通过。

## 建议新增工件

按会话独立保存：`raw.json`、validator原stdout/exit、capture-journal、before/after DOM与实际截图、source/build/probe绑定、operation coverage/missing表、与raw分离的interaction/active-cadence二次统计。最后写明确certification：`engineeringObservationOnly=true`、`humanCertified=false`、`presentedPaintCertified=false`、`activityCancellationCertified=false`，固定环境未锁定时仍pending。

这是一份采集准备与范围审计，未新增任何当前build浏览器矩阵、性能、真人或出版通过数。
