# M4：新手检查、声明形状与参数引导

2026-10-06，正式构建为 `index-CWqdzert.js` / `index-DEZFMW6R.css`。本轮增加“检查模型”、准确节点定位、节点与属性面板中的声明形状、缩放外的12px端口提示，以及全部34个注册参数字段的中文说明。模型没有执行；声明形状不能作为运行时观测。继续从头实现，未采用失败原型代码，也未改后端、API、schema、路由或源码生成合同。

检查结果绑定草稿语义键：包含草稿身份、节点/边顺序、身份、类型、参数和绑定；位置、显示名、标题与revision不改变适用性。参数或连接变更清除旧声明；移动/改显示名保留声明。成功及失败回包均检查请求快照和当前语义，返回草稿也必须匹配。解析器核静态响应的结构/预算/拓扑/张量/诊断及digest格式，但不重新计算digest或独立推导形状。乱序响应保护有源码与helper证据，本轮没有真实延迟/乱序浏览器样本。

最终专项48/48、Studio284/284、strict TypeScript/Vite退出0；专项包含于全套，不相加。新增9项独立helper测试已包含在该计数内；34/34字段与12个有参数模块的正式后端AST核对是说明覆盖记录，不是额外测试数。[最终独立源码/检查读回](evidence/m4-authoring-guidance-work/acceptance-attempt-1/source-and-checks-report-attempt-4.json)分别核109/109/112绑定；[参数说明核对](evidence/m4-authoring-guidance-work/parameter-help-review-attempt-1.md)保留作者核合同范围。已通过检查后没有继续改产品源码或重跑产品套件；Python全套与完整独立发行未在本轮重新认证。

[最终浏览器22组/88原始文件](evidence/m4-authoring-guidance-work/browser-attempt-3/manifest.json)属于CW构建恢复后的Input→Linear→GELU→Output四节点三边草稿。修正in_features15→16，输出8→12，检查并定位缺失Linear输入，重连后静态检查；Linear四方向各移动16world units，每次下一方向前撤销。节点身份、其他位置、绑定与声明保持。显示名从特征编码改为编码层，声明保留。缺边时两类诊断可见，但unused Input定位按钮没有点击样本。最终[保存envelope](evidence/m4-authoring-guidance-work/saved-draft-attempt-1.json)为草稿revision44、存储revision2；[独立DOM/保存读回](evidence/m4-authoring-guidance-work/acceptance-attempt-1/browser-and-save-report-attempt-1.json)核原始88、资源3及保存原件/副本逐字一致，重开可见身份/位置/边一致，未宣称重开UI暴露全部参数。

[独立AI像素审查](evidence/m4-authoring-guidance-work/pixel-review-attempt-1/report.json)亲看全部22张JPEG；[root像素记录](evidence/m4-authoring-guidance-work/root-pixel-review-attempt-1.json)亲看其中11张，不能与22相加。四向小幅移动未见交叉或穿无关节点；横移仍为直线，上下移动出现短正交折线。58%与100%提示框都为12px、pointer-events:none，公共DOM与对应实际像素分别读取，提示文字清晰。保留58%节点/端口常驻小字，100%提示框遮住Linear/GELU底部约16px及GELU类型文字开头，70%定位与100%放大有局部裁切。删边帧右卡已要求检查、声明已清空，但页脚仍有此前取消提示；本轮只消除过时“检查通过”，未称所有上下文提示都自动更新。不会把22图称为22个无问题的视觉通过。

两项实际浏览器发现已修复：开始新连接会清掉旧定位错误，pending连接Escape后提示取消；参数变更后的页脚不再保留旧“静态检查通过”。[原生操作回顾](evidence/m4-authoring-guidance-work/native-actions-retrospective-attempt-1.json)是回顾记录，非同步OS事件流或性能遥测。直线SVG组locator点击曾超时，随后按公开path位置原生点击并通过可见按钮删除；采集闭包曾把48个BdH中间文件追加到原24个DS目录，空attempt2 ledger也保留。[BdH48份恢复副本](evidence/m4-authoring-guidance-work/browser-bdh-recovered-attempt-1/manifest.json)明确旧目录并非整体冻结；CW使用单独最终目录。从空白搭建只属于DS中间证据，未称CW重新从零搭建。本轮没有生成源码、打开新managed或导出；克隆目录中的旧项目/导出不是本轮结果。attempt1中间JS未留存，不能称该旧构建完整可解析；后续两次中间源码/资源各有明确归档。

模块库仍为17基础模块＋3透明起点，本轮没有扩增。[AI新手模块库审查](evidence/m4-authoring-guidance-work/novice-library-review-attempt-1.md)建议下一项先让基础模块/网络起点入口明确，避免三个preset占满首屏、Input/Output/Linear需滚动寻找；新增模块必须先有独立静态/生成合同。M4仍partial、M5未开始、真人0。AI合同、字段、新手、DOM/保存和像素审查不替代真人任务或物理出版评审。长分支/CNN/Transformer、全模块/preset、任意布局美观、held取消/展开锚点、当前Studio A/B/三次矩阵与真实呈现性能仍开放。

原预览session58729末读exit143、原因未知；临时36653服务已主动停止，随后同一克隆存储在原地址[127.0.0.1:42933](http://127.0.0.1:42933/)重新启动。恢复草稿并fit后的[预览交接](evidence/m4-authoring-guidance-work/preview-handoff-attempt-2/manifest.json)单列，不追加到22组验收原始目录；可用性仅属最后观察时点，不保证持续在线。此前[草稿合流路由](m4-draft-merge-routing.md)BSA与端口交互ye保留原版本范围；旧原字节通过[实现前归档](evidence/m4-authoring-guidance-work/before-implementation-attempt-1/manifest.json)和[当前文档更新前归档](evidence/m4-authoring-guidance-work/before-current-doc-update-attempt-1/manifest.json)解析。[schema15当前状态](evidence/m4-human-review-handoff-status-followup.json)仅绑定本轮实证。

独立末读发现首份交接manifest自记录为零字节（先打开文件再枚举目录造成），原件与首次封印保留为失败ledger。修正attempt2仅复制三份原始交接文件且排除自记录；没有重新操作浏览器或新增验收帧。首次封印只说明字节被冻结，不能证明其内部清单正确。
