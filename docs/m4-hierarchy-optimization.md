# M4 层级树渲染优化

当前（2026-10-05）`index-Cr_xKW9U.js`（SHA256 `1f4f51f9818e523916dacea184a7005fa7459bd3f2c4c8bfe6bfc83006e5be29`）与最终ce7 frontend 的[新版浏览器矩阵](m4-boundary-final-matrix.md)已完成真实UI采集：36 baseline＋三模型各一 edited-after，共39例/234工件、9 frontier；完整Scene/export重建与独立核对通过，artifactCoverage=complete，humanAcceptanceCertified=false。39张实际截图已有AI逐张观察，三组提交后的undo/redo/保存重开链另有完整SVG核对；这些不认证物理出版或真人。Studio88/88、Python62/62及额外21/21属于此前边界修正轮，本矩阵轮未重跑、未改产品源码/build。当前五席研究包61实施绑定、0真人；presented性能、活动取消、固定字体/硬件、人审与3–5真实任务仍未认证，M4保持partial、未进入M5。旧oI5矩阵/诊断/研究包仍属历史；[矩阵前归档](evidence/before-boundary-final-matrix/manifest.json)保留更新前文档和完整3644绑定解析，旧seal不改。

优化轮历史完整浏览器矩阵曾在同一`index-oI5sT67U.js`构建完成36＋3/39/234封存，人工仍pending/false；[收尾说明](m4-hierarchy-final-matrix.md)与[本轮原生诊断](evidence/m4-hierarchy-visible-performance/README.md)单列新结果。五请求14/13/5匹配子集p95=4008ms、capability false，持续presented/取消/字体硬件门未认证；五席59bindings/0真人，M4仍partial。下方优化轮React/UI/native与候选记录保留其冻结范围，较早2016ms不与本轮合并。

优化轮构建 `index-oI5sT67U.js`（SHA256 `2c769087f0765ba47892e9f26f12a19e4336ec12573dce5859ac636e310f446c`）已抽离层级树、建立节点索引并稳定选择/展开回调。修改前的 App、完整构建和当前文档已按原字节[归档](evidence/before-hierarchy-optimization/manifest.json)，旧1532绑定全部复核一致。DPwoy 的39例矩阵、8888原生诊断与publication-final五席研究包只对应历史版本；新证据单列，不改旧哈希。

层级树使用默认 React memo；architecture 引用决定有序 roots/byId 索引，expanded、selected、pinned 使用 Set。App 的两个稳定回调仍走同一选择状态与 typed visual operation。保留 child 顺序、空字符串别名、repeat、pin、treeitem/data 属性与 ARIA。commit/undo/source refresh 仍会刷新树，不使用仅比较 ID/digest 的自定义 comparator。

304节点源码压力文档的一次旧树渲染需要303次线性子节点查找，累计46,358次ID比较。独立生产 React [探针原始记录](evidence/m4-hierarchy-optimization/react-probe-browser-raw.json)在同一 IAB、1280×720/DPR1执行初始＋17次可信点击，共18个commit。五次稳定父更新分别模拟 camera/preview/box/portDraft/camera，旧树每轮读取49,401次 id/label/children，新树为0；初始旧49,401/新3,043。九种必要更新和三次树回调正常刷新，18轮浏览器记录的完整DOM exact比较均通过。[独立审计](evidence/m4-hierarchy-optimization/react-probe-independent-audit.md)从同一冻结bytes重算所有访问/facts/引用情境，53输入稳定。探针使用代理节点，未执行完整Studio画布路径，不测耗时、FPS或paint；raw保留DOM hash/等价结果与facts，未保存18对完整HTML字符串，无法独立rehash这些DOM。

独立[回归测试](../studio/tests/hierarchy-tree.test.ts)覆盖乱序多根、alias转义/空值、repeat/pin/select/ARIA、latent展开、同ID新架构和实际源码304节点；新旧SSR HTML精确相同。全套[Studio85/85](evidence/m4-hierarchy-optimization/studio-tests.txt)无skip、strict TypeScript/[build](evidence/m4-hierarchy-optimization/build.txt)与[纯正式副本9项核对](evidence/m4-hierarchy-optimization/independence-report.json)通过。SSR不证明跨更新memo，React探针不证明完整产品性能。

实际8889 Studio 的[12个DOM观察](evidence/m4-hierarchy-optimization/ui-journal-final.json)支持MLP展开、指定Linear1选择、Projection α别名、固定、undo/redo、收起/重展开、保存重开与CNN切换。独立[UI审计](evidence/m4-hierarchy-optimization/ui-independent-audit.md)核25个稳定输入、11个MLP SVG与formal core replay精确、完整保存document/store一致；保存重开SVG原字节相同，visual7/storage1。早期递归pin查询误把祖先当pinned，raw原样保留；V2直接行与store只有Linear1 pinned。重开清selection/history、改变camera，不声称这些状态持久。

优化轮构建独立[原生收据](evidence/m4-hierarchy-optimization/native-stress300-raw.json)和[validator](evidence/m4-hierarchy-optimization/native-stress300-validation.json)支持stress300展开与pan两请求。pan终点+40/+24 CSSpx、revision和完整公开SVG/frontier/pins/selection不变。离散eligible6/matched3/interaction1，匹配子集p95仍2016ms；连续pointermove仍只有DOM/rAF观测代理，性能门未通过。没有新拖节点、原生活动取消或固定硬件/解析字体认证。失败选择器/只读iframe查询及原始读块范围见[工具记录](evidence/m4-hierarchy-optimization/tool-observations.json)。

[原生独立审计](evidence/m4-hierarchy-optimization/native-independent-audit.md)核23个稳定输入、fresh validator全字段、实际fixture/source/IR与5个全SVG sourceFacts。唯一匹配interaction来自toggle；pan三个缺失原生离散样本继续null。pan实际down→up窗口8003.8ms、16事件窗口rAF／17观测窗口rAF、8次几何变化，toggle点击窗口2.7ms／0回调；iframe y−8↔144的外页滚动保留，不用这些数换算presented FPS。首跑审计错误期待Sequential kind的失败已转录保留，实际IR为Module/container/repeat independent；只修正审计假设，未改raw。

重新生成的[36份candidate SVG](evidence/m4-hierarchy-optimization/renderer-candidate-parity.json)与原DPwoy候选逐字节一致，只证明本轮候选renderer不变。新[矩阵spec](../.archcanvas/browser-visual-matrix-hierarchy-final/spec.json)绑定新build、9frontier/36baseline；优化轮冻结时尚未collect，原verification记录0/36基线、0/3edited；同构建随后已在[本轮新矩阵](evidence/browser-visual-matrix-hierarchy-final/manifest.json)独立采齐，不继承旧39截图。

优化轮五席试用包 `.archcanvas/m4-research-trial-hierarchy-final` 已[prepare](evidence/m4-hierarchy-optimization/research-prepare.txt)/[verify](evidence/m4-hierarchy-optimization/research-verify.txt)，manifest SHA256 `364eb60843ebaa89ed3b9e1270d1166f4ed62f06c4772a1158cf05cedfc5117c`，59实施绑定，S01–S05端口8891–8895，0分配/收集/真人。旧publication-final包实际[verify失败](evidence/m4-hierarchy-optimization/research-old-stale.txt)。本轮fresh verify仍保持五pristine/0真人；完整当前矩阵工件已齐，人工出版审看、持续呈现性能、活动取消和3–5真人任务继续待完成，M4仍partial、未进入M5。原verification保持历史字节，本轮另见[最终验证](evidence/m4-hierarchy-final-verification.json)。
