# M4：黑白线型与真实角色图例

本轮为黑白视图增加实际角色线型和由可见边生成的图例，已完成有界文档、SVG、保存和导出核验。封存对象是 `index-CG7A-7XR.js`（SHA256 `6398eb5e7c6e39af497e7e2675cb71173c096dd3a935f49382791df98809fc31`）与 `index-B6WbMowt.css` 的角色改动版本；后续折叠布局修复及其新构建属于另一轮证据。M4 仍 partial，M5 未开始，真人参与者为 0。正式工程继续独立实现，未导入失败原型 runtime、执行用户模型或安装依赖。

默认黑白线型直接进入 Scene、SVG、分支合并证明和 router 的实际样式身份。显式 `dashed:true` 使用 `[5,4]`，`false` 使用实线，未指定时沿用角色默认；保存的颜色覆写不会被黑白投影删除。彩色 paper 保持原有同模式表示，单纯角色改动不增加黑白派生字段。

| 角色 | 默认黑白 dash pattern | 可见表现 |
| --- | --- | --- |
| data | `[]` | 实线 |
| residual | `[9,4]` | 长虚线 |
| memory | `[9,3,1,3]` | 点划线 |
| mask | `[3,3]` | 短虚线 |

图例按实际可见角色及线宽、颜色、线型变体生成，保留完整 canonical membership；隐藏角色不伪造样例，用户手工图例、注释和身份不被覆盖。线样例使用与所属边相同的 marker、stroke 与 pattern，宽线样例长度随线宽增加。detail 出版图重新计算真实边界及图例、引用位置。实现过程中保留了 sparse pattern 校验、宽线 marker 边界和出版导出器属性词表修复的原始反例与前后字节；实现作者的源码审查不是独立验收。

[专项收据](evidence/m4-monochrome-role-work/checks/target-attempt-3/receipt.json)为 **31/31**，[Studio 全套](evidence/m4-monochrome-role-work/checks/suite-attempt-1/receipt.json)为 **234/234**，均无 skip、退出 0，专项包含在全套中，计数不相加。[strict TypeScript/Vite build](evidence/m4-monochrome-role-work/checks/build-attempt-1/receipt.json)退出 0；[Python 出版检查](evidence/m4-monochrome-role-work/checks/publication-attempt-1/receipt.json)为 **9/9**。Python 成功日志在 stderr。两次先前专项失败分别来自 reviewer 将可行 corridor 当作唯一产品坐标、以及错误要求每条 branch 都缩短；失败、原断言和按既定 family 总长合同修正的理由均保留，没有把产品观测改为 gold。检查时 README 的旧字节只通过已验证的独立副本解析，不能称后续 README 曾参加这些检查。

角色版本的源码、Studio tests 和 dist 另在[折叠修复开始前快照](evidence/m4-collapse-continuity-work/before-implementation-attempt-1/manifest.json)保留。封存按角色检查/core 收据的历史 hash 逐项核对副本，不把随后变化的工作区源码或新构建冒充这 234 项测试的输入。动态 document store 后续可推进；本轮保存 envelope、原始 UUID export 和检查时绑定仍按各自时点保留。

[9 case 浏览器 manifest](evidence/m4-monochrome-role-work/browser-nine-case-final-manifest-attempt-1.json)绑定 **122 个实际文件**：CNN L0–L2 × 黑白 × 85/180 mm 六例、经历深层展开/折叠的 CNN L0 paper180 一例、Transformer L0/L3 黑白180 两例。库存有 22 张原始 JPEG；AI 实看其中 **21 张**，即 **20 组完整 before/after 截图**及一张保留的导出失败图。CNN mono85 的 revision5 `expanded-fit` 探索图缺 after，不能计入 revision4 case。TF 最初导出失败、裁切 footer 与随后成功导出及完整 footer 均保留。

[独立操作回放](evidence/m4-monochrome-role-work/acceptance/journal-replay-attempt-1/receipt.json)使 9 个完整 CanvasDocument 检查点与冻结的正式旧版 document/history 契约精确一致，包括 CNN undo 缓存及 TF 保存重开。操作列表来自 root 采集者的原生 UI 动作声明，检查点另有实际观察、保存与导出；它不是自动同步的手势事件流。旧版正式契约仅作冻结预期执行器，与失败原型无关。[当前 core](evidence/m4-monochrome-role-work/core-current-attempt-1/receipt.json)只生成产品观测，不生成 reviewer 的预期。

[独立浏览器读回](evidence/m4-monochrome-role-work/acceptance/browser-readback-attempt-2/report.json)为 **9/9 有界通过**，519 项输入复读一致，无 `heightMm` JSON 例外。公开交互 SVG 与当前 core 交互 SVG 的完整 XML 在同模式精确；实际出版 SVG 与当前 core 出版 SVG 的完整 XML 只允许已按 viewBox 公式核对的根 width/height 毫米字符串精度差异，不忽略 metadata、正文、路径或对象。交互和出版两种模式不要求彼此整 XML 一样。实际 UI href、UUID exporter 原件、收据 digest、保存 envelope 和导出 Canvas 均核对；TF L0 的真实 PDF 只认证字节与输入文档/Scene 来源，不认证 PDF 像素或字体。

八例保护原始匹配 frontier 的节点、端口、路径、标签、事实和 pair-local 几何；CNN 折叠历史 paper 例只保护同一动作链的冻结预期，**不等于原始 L0 布局**。从展开到折叠后，pool/flatten/classifier/output 比原始紧凑 frontier 下移 **1576 scene units**，root 高度同增 1576。当前实际 blocks 底边 423 到 pool 顶边 2030 留下 **1607 units** 空洞；这与 1576 的前后位置增量是不同度量。180 mm 出版图高达 764.168 mm。旧版契约独立重现了该已有 cache/frontier 空间连续性缺陷，同历史一致不构成视觉通过。

[独立 AI 像素收据](evidence/m4-monochrome-role-work/pixel-review-attempt-1/nine-case-review-receipt.json)还实看了 **27 张转换 PNG**，来自九份真实出版 SVG 的整图、frontier 和 footer。它们按 world-unit 放大转换，既不是 Studio 原生 PNG 导出，也不是 85/180 mm 实物印刷验收。默认 1.5 线宽的图例和局部 CNN residual、TF memory stub 可辨；深层 CNN/Transformer 仍需局部导航，整页 fit 不能认证端到端可追踪。Transformer 实际 mask7 与 residual13 在 y397 重叠 16.2 units，与 residual51 重叠 32.4 units，并与 data43 在 `(348.3,397)` 严格相交；不同 tensor 的 mask 还重叠 65–227 units。角色图例改善不表示这些路线已消除重叠或足够美观。原生 **线宽 3/12** 的覆写像素仍 pending，round-cap 填补短 gap 只是待验证的源码担忧。

另有[三份实际最小控制页分析](evidence/m4-performance-controls-work/analysis-attempt-3/receipt.json)：raf-idle、full-click、full-idle 各一份，固定 2 秒预热＋20 秒采集＋2 秒 drain，会计核验 3/3。rAF callback cadence 分别为 1.951719、2.050915、2.050926 次/秒；click 的三份匹配 EventTiming 属同一 interaction，duration 为 1024 ms，原生 down→up 约 0.7 ms。这三份 control 的 context 绑定旧 `Dzp9we5t` 资产集，页面本身未加载产品资产，不能归给新的角色 renderer，也不能相减成产品性能。隐藏方式创建、DOM visible/focus 与外部实际呈现不同；[动作日志补充审查](evidence/m4-performance-controls-work/analysis-attempt-3/supplement-receipt.json)不定位原因。持续 presented FPS、完整 INP、命名后台策略及三次匹配条件矩阵均未认证；12/12 损坏收据反例是完整性检查，不是新浏览器试次。

本轮不新增四向移动、非空 pin 保护、held-pointer 活动取消或从零搭建的完整可用性认证，也不继承旧矩阵为当前 renderer 的新验收。17 个基础模块与 3 个透明网络起点的已有目录能力仍属各自历史范围；首期仍需继续验证视觉移动、连线排布、预制模块搭建、物理出版/字体环境和真人任务。人 0、M4 partial、M5 not started 保持不变。冻结入口为 [独立封存 manifest](evidence/m4-monochrome-role-verification-sealed.json)，不会改写任何旧 seal。
