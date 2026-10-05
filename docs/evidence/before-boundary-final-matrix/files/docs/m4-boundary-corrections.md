# M4 边界修正与体验收敛

本轮修正正式工程的未知边界和画布交互，并以新构建单独记录。旧的 oI5 层级矩阵、旧研究席位和旧原生诊断已经在 [边界修正前归档](evidence/before-m4-boundary-corrections/manifest.json) 中保留原字节；它们不能证明当前新构建的浏览器覆盖或验收。

当前构建是 `index-Cr_xKW9U.js`（SHA256 `1f4f51f9818e523916dacea184a7005fa7459bd3f2c4c8bfe6bfc83006e5be29`），CSS 为 `index-DK5lov-h.css`（SHA256 `d6d5f8f4d8824f28b313ffffe685678225486e5cf25966f0528d3846eb6a8a7f`）。边界修正的文件、构建、测试日志与限制由 [work README](evidence/m4-boundary-corrections-work/README.md) 和 [verification.json](evidence/m4-boundary-corrections-work/verification.json) 绑定；不回写旧 seal、manifest、raw 或研究包。

## 修正内容

- 未知的 `__init__` 控制流、未知构造和直接重赋值会使受影响属性失去先前的已知contract。未知mutation会就地使原Spec opaque，传播到alias与Sequential/ModuleList捕获项并保留shared identity；直接重绑定保留旧对象，使用稳定constructor occurrence区分旧、新instance。多目标赋值只求值一次RHS，保留真正共享关系；未知helper/RHS传入已有对象也不能留下旧contract。确定的常量分支仍可恢复。
- `ModuleList` 的直接调用没有被当作 `Sequential` 展开。没有 shape 证据的 `chunk`/`split` 不生成固定数量的输出槽位；不确定循环和被遮蔽的 `range` 保留 opaque。已知无 `break` 的循环执行 `else` 分支，不能静默忽略它。
- 摄像机改用 world coordinates。负坐标 bounds、fit/focus、指针中心缩放、平移和框选共享同一投影，避免纸张局部坐标造成屏幕漂移。
- 连线检查器读取实际 scene 中的 canonical edge appearance，包括推导样式；它不会只显示 `CanvasDocument` 的 override。重复、共享和 opaque 身份仍来自 source-backed facts。

## 已验证范围与未完成门

最终静态Python回归为62/62（含18个新增边界反例）和额外21/21，无skip，命令使用记录的Anaconda Python；[精确命令/环境/日志](evidence/m4-boundary-corrections-work/python-final-command-receipts.json)逐项绑定，不能与较早38/补充12项相加。独立正式副本另用`.venv`完成 [base-model 11项](evidence/m4-boundary-corrections-work/final-base-models-report.json)、[holdout 28项与Studio3项](evidence/m4-boundary-corrections-work/independent-holdout-final/m4-holdout-report.json)、[发行9项](evidence/m4-boundary-corrections-work/final-independence-report.json)。Studio88/88、TypeScript与生产build通过。具体范围见 [verification](evidence/m4-boundary-corrections-work/verification.json)，本轮最终字节另由 [final verification](evidence/m4-boundary-final-verification.json) 封存。

本轮 [实际浏览器journal](evidence/m4-boundary-corrections-work/browser-journal.json) 和 [11项验证](evidence/m4-boundary-corrections-work/browser-validation.json) 记录新UI构建的一个Transformer总览：原生root拖动client −80px，经zoom与4px网格提交canvas −148px，viewBox x从0变为−128；root实际CSS位移−79.692291px，期望−79.692308px，未移动legend的CSS位移为0。Undo/redo的完整SVG仅排除两个revision标量后精确恢复，保存重开的完整SVG原字节相同。mask edge:7检查器显示 `#a194a8`、width1.5、虚线已选中；一次取消勾选立即成为实线，undo恢复完整SVG，最后保存visual5/storage2，root layout x−98、pins为空、edge overrides恢复为空。

8900后台是保留的d884中间frontend，UI JS始终为Cr_xKW9U。最终ce7 frontend的 [14项IR/完整SVG回放](evidence/m4-boundary-corrections-work/final-source-and-canvas-replay.json) 核实际存储与fresh Transformer architecture全字段相同，完整XML树/metadata/revision精确；raw SVG字节因DOM序列化不同，未忽略任何字段。该一致性支持此固定Transformer的UI坐标/样式事实，不认证后加unknown/captured-Spec反例的原生浏览器范围。

最终源码的 [fresh静态视觉准备](evidence/m4-boundary-corrections-work/visual-static-preparation.json) 完成36候选/9frontier、geometry/spatial core检查和 [新spec](../.archcanvas/browser-visual-matrix-boundary-final/spec.json) prepare/verify，浏览器collect仍0。候选实际最小字号2.531–8.575pt，10/36≥7pt；这不是期刊合格线或真人出版结论。[新五席包](evidence/m4-boundary-corrections-work/research-current-preparation.json) `.archcanvas/m4-research-trial-boundary-final` 已prepare/verify，61实施绑定/4baseline、8901–8905，0分配/收集/真人。

这只是一个坐标/样式正确性核对，没有重新采集完整视觉矩阵，也没有新增presented-performance、活动手势取消、pins、真人出版审看或研究者任务认证。旧39例矩阵保持历史状态；旧五席包的 [实际verify失败](evidence/m4-boundary-corrections-work/old-research-stale.log) 明确报告正式实现已改变，不能沿用旧哈希或分配新人。8900临时服务和tab已关闭，不承诺在线；用户8765未触碰。M4继续partial，当前矩阵、真实性能条件、人工审看和研究者任务仍需分别取得可复核证据。
