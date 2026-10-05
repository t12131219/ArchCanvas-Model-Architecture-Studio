# M4 边界修正构建：性能、活动取消与真人门下一步审计

当前 `index-Cr_xKW9U.js` / `ce7f7f733…` Python 冻结版本的完整性能、活动手势取消、人工出版审看和研究者任务仍未认证。此次只读正式计划、产品探针、旧证据和当前席位；仅新增本报告及 [JSON](performance-next-audit.json)，没有操作浏览器、启动服务、执行模型、重跑测试、改源码/build 或旧 seal。完整 36＋3 浏览器矩阵由 root 独立推进；本审计不替它填采集数量。

JSON 绑定 49 份实际读取输入，并内嵌四份可能随后更新的当前说明原字节，以便本报告按审计时点复核。另逐字节检查新研究包的 61 个实施文件和五席基线。旧 `oI5` native 诊断保留历史范围，不能成为新构建性能证据。

## 真实门槛与当前能力

计划 §17.2 的 M4 硬出口含真实浏览器性能和研究使用者任务。§18.1 要求固定浏览器、硬件、字体、DPR、页规格、图规模，实际源码 Studio 的输入/截图，六维人工视觉评审及 3–5 人任务时间/卡点。§18.5 的 300 可见对象 p95≤50ms、交互≥50fps、中等展开 p95<500ms、锚点≤8px/pins零位移、3分钟内≥80% 完成是初始 **Beta 数值目标**；不新增一个计划未写的 M4 数值门，也不以降低目标或纯CPU/DOM数字宣布体验完成。

root 已保存 [本轮实际环境观察](current-environment.json)：IAB 2 / tab35，在 `2026-10-05T02:51:16.948Z` visibility 为 **true**，当时 viewport **1102×835**、DPR1、UA未知。此前 root 提到的1280×720是另一时点；本报告不能概称整个会话固定1280×720。后续若用现行已文档化 viewport override 固定矩阵尺寸，须单独保存实际读数、起止与结束reset，不能反写这份原观察。旧false读数也不能替换本次true。一次true并不证明整个交互窗口持续呈现。

| 现有路径 | 可证实范围 | 仍缺什么 |
|---|---|---|
| Studio「开始原生输入采样」 | 可信 tree click/画布expand pointerdown；唯一匹配 Event Timing；两rAF后锚点/无关pins | 仅toggle；缺连续drag/wheel input-to-paint、compositor呈现帧、固定环境 |
| Studio「运行20组性能采样」 | 一组warm-up、20组展开/收起；handler和两rAF代理；rAF回调节奏 | 内部合成DOM点击、排除初始输入队列；不是原生输入或真实paint/FPS |
| `/__m4/` full harness | zoom/drag/pan/undo/redo/toggle/pin的普通真实输入、SVG/几何、Event Timing、longtask、visibility及rAF | continuousProxies不认定因果input或paint；fps是回调cadence；没有回滚/history成功判断 |
| 当前CUA工具合同 | click、atomic drag(from,to)、pressKey、只读DOM | 无分开的held down/up、无持续presented/compositor trace |

磁盘插件的 generic CDP 文档不等于本会话已发现/可调用的 CUA 能力。本轮实际工具合同尚无呈现帧接口，不能用文档存在把能力填为实现。root 的当前合同事实见上方环境收据；本agent没有独立重放浏览器。

测量实现另有一个未认证边界：Studio toggle panel 的 `joinNativeTrials` 与其validator使用顺序候选唯一/used匹配，没有full harness的双向唯一候选图。两条trial若同type/target/±8ms均可解释同一entry，先者可能取得该entry；validator复算相同规则不能排除这类跨trial歧义。这是源码可见的匹配合同缺口，不是本轮已发生的浏览器故障。下一次优先使用full observer的双向唯一匹配，不把toggle panel升级成完整原生性能认证；后续改工具需独立反例和新版本范围。

`document.fonts.status=loaded`、请求字体栈、CSS computed font-family、UA或hardwareConcurrency均不锁定浏览器实际字体文件和硬件。当前五席包的环境模板仍全空，`environment.json`不存在。产品图字体栈是 `Noto Sans CJK SC, Inter, Noto Sans, Arial, sans-serif`；UI另有不同fallback。publication preflight核主机glyph覆盖，不认证浏览器fallback字节、shaping、同family或embedding。不能凭已有导出receipt填“固定fonts/hardware通过”。

## 最短可执行工程流程

1. 先完成此次冻结构建的39例独立矩阵。性能storage、矩阵storage和真人席位分开；用户8765不动。保存当前工具合同、实际资产/source hash与环境读数。当前具备meaningful UI采集能力，不能因人尚未到场停止这项工作。
2. 如要补新构建的原生输入诊断，在确认端口空闲、无同目录live服务后，用**新的隔离目录**和候选8907启动harness；8906留给矩阵、8901–8905留给人。保留真实句柄与生命周期，不能因为超时猜服务终止或重复启动。
3. 在full模式下取约2秒实际idle，再做五条trial：stress300 network toggle、pan、**指定Linear1 body** drag、undo、redo。准备期选择工具/聚焦目标，arm后才做单一产品输入。带一个无关可见pin和实际anchor；失败命中、no-input和缺条目原样保留，另加新trial，不改target修raw。camera/pin/viewport变化单列。
4. 停止后保存readonly raw原字节、截图、visibility起止读数和实际store，用独立validator验证。全SVG undo/redo链仅排除两个实际revision标量；save/reopen另外比较全SVG和最终Canvas/store。一个五请求诊断不提供代表性p95/FPS认证。
5. 若新呈现条件下仍低频，最多加一个新20秒simple control；必要时再加一个同产品raf-only对照。保留全部窗口，不能重复挑最快结果。simple top-level与产品iframe不是随机等价环境，对照不能定位唯一原因或免除完整产品测量。

启动和离线验证命令仅供下一次真实操作；本审计没有执行它们，`NEW-SESSION`需由操作者替换为不存在的新目录：

```bash
PYTHONPATH=src .venv/bin/python scripts/m4_input_harness.py --port 8907 --data-dir .archcanvas/m4-boundary-performance-NEW-SESSION/documents
node scripts/validate_input_observation.mjs docs/evidence/m4-boundary-performance-NEW-SESSION/product-raw.json
```

统计每session自己的eligible/matched/interaction分母，双向唯一type/target/±8ms/正interaction匹配；每interaction取最大duration，再算nearest-rank p95。16ms报告阈值、约8ms量化及null全部保留，不补0，不称整体page INP。连续gesture分母仅为同pointer真实down→up的`eventAt`窗口；rAF/秒桶、几何变化、event→capture和长任务单列。`visibleIds=304`只证明rendered frontier，不证明300对象同时在viewport中可读；若要支持“300可见对象”主张，另核所有body与viewport相交及实际呈现。

完成真实性能门仍需要**已支持的呈现帧/连续input-to-paint测量，或实际操作者从真实浏览器取得可复核trace**，同固定环境、场景和输入绑定。现有read-only harness不是这个能力；收到trace前保持未认证。无需继续反复采同一慢窗口来增加证据数量。

## 活动取消的可执行边界

App有非编辑/modal状态Escape、window blur、同pointer的pointercancel/lostpointercapture取消路径：先清ownership，再取消pending rAF、清preview/box/portDraft；pan回初始camera，port代次守卫拒绝迟到proposal。当前纯函数测试不执行App capture/rAF/React完整生命周期。validator的`cancelled:true`仅分类中断、拒绝成功drag/pan，**不证明rollback/history正确**。普通up之后的lostcapture不算取消。

当前atomic drag无法插入Escape-before-up；先drag后Esc只发生在完成之后。不能用synthetic event、隐藏接口或修改探针伪造活动取消。最少需要真实操作者或新发现的已文档化native held-input能力：先提交一个sentinel视觉编辑并save，记录base；down→move直到实际preview→Escape/blur早于同pointer up→release。取消后两次DOM/截图核pan camera或baseScene恢复，source/IR/frontier/pins保持，保存核实际Canvas/store；Undo只撤销sentinel一次、Redo恢复它，再save/reopen、新普通drag和迟到窗口核没有额外commit。selection被Esc清空不应误当失败。

Escape是否落在editingTarget/modal guard须从实际target/focus判断，不能从任意Escape分类推断App执行取消。未知的hidden-only取消没有现存明文合同，属于增强建议；若出现hidden+blur只按实际组合命名。port晚回复另需独立proof，node取消不能替代它。

目前还能工程化补App适配层pending-frame/late-response反例及独立rollback判断，之后仍需真实native取消样本。本报告没有以这些建议要求改当前已冻结build；任何下一轮实现变更都要保留本轮原bytes并把matrix/研究包按版本分开。

## 最少真人交接材料

新包 `.archcanvas/m4-research-trial-boundary-final` 已冻结61实施文件和五席基线。此次磁盘核五席pristine、0 assignment/collected/incoming/export、reviewer均未填、**0研究者**。不能代替人assign、发邀请或把agent/automation计入人数。下一次开场前先verify包；没有改源码/build时无需再prepare覆盖。

所需协调输入仅为真实3–5名制图使用者的人数/时间、主持者与实际独立复核者；可使用匿名代号，无需提交个人资料。环境材料是实际浏览器/version、硬件/显示器、viewport/DPR、浏览器与导出字体解析文件/哈希证据。应由操作者选定一套环境并记录变化，不能从准备runtime猜硬件。

每位从新席位开始，真实开场时assign code→slot；保留start/final、结束的study JSON和任务time/blockers/checkpoints、undo-before/after、redo-after、reloaded、最终Canvas/store、实际当前SVG/PDF与receipt、export-open。成功需五步全部实际完成且≤180秒；超时、放弃计入分母，automation排除。3人需3/3，4人需4/4，5人需4/5才能≥80%。collector和summary只证一致性/自报；真实复核者逐工件填review，未看到填unverified/missing。

出版门另须真正reviewer记录该当前build的39例工件身份、六维意见（版式、层级、留白、彩色/黑白、字体、连线）、85/180mm实际尺寸查看方法和dense detail可读性。未必要求额外人数，可由有资格的实际复核者承担，但不能由AI像素报告或manifest代签审美结论。没有普遍期刊字号准则可由现有10份≥7pt自动认证。

以上人审、真实任务及当前工具之外的呈现/held-input证据是外部依赖。独立工程矩阵、环境观察和适配层proof仍能推进；**M4保持partial，不标完成，不进入M5**。
