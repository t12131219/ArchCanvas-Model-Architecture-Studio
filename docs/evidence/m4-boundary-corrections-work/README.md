# M4 boundary corrections work

当前（2026-10-05）`index-Cr_xKW9U.js`（SHA256 `1f4f51f9818e523916dacea184a7005fa7459bd3f2c4c8bfe6bfc83006e5be29`）与最终ce7 frontend 的[新版浏览器矩阵](../../m4-boundary-final-matrix.md)已完成真实UI采集：36 baseline＋三模型各一 edited-after，共39例/234工件、9 frontier；完整Scene/export重建与独立核对通过，artifactCoverage=complete，humanAcceptanceCertified=false。39张实际截图已有AI逐张观察，三组提交后的undo/redo/保存重开链另有完整SVG核对；这些不认证物理出版或真人。Studio88/88、Python62/62及额外21/21属于此前边界修正轮，本矩阵轮未重跑、未改产品源码/build。当前五席研究包61实施绑定、0真人；presented性能、活动取消、固定字体/硬件、人审与3–5真实任务仍未认证，M4保持partial、未进入M5。旧oI5矩阵/诊断/研究包仍属历史；[矩阵前归档](../before-boundary-final-matrix/manifest.json)保留更新前文档和完整3644绑定解析，旧seal不改。

本目录绑定边界修正后的当前实现快照。它只记录新构建的源码/测试/build 字节和本轮限制，不重封旧矩阵，也不将旧浏览器收据升级到新版本。

## Current snapshot

- JS: `studio/dist/assets/index-Cr_xKW9U.js`, 377100 bytes, SHA256 `1f4f51f9818e523916dacea184a7005fa7459bd3f2c4c8bfe6bfc83006e5be29`
- CSS: `studio/dist/assets/index-DK5lov-h.css`, 27591 bytes, SHA256 `d6d5f8f4d8824f28b313ffffe685678225486e5cf25966f0528d3846eb6a8a7f`
- HTML: `studio/dist/index.html`, SHA256 `bb2bb6fa312cfbc7448fa5dbb182c5ee9876b3a95bc4b638cdf2c1161331c6ce`（完整值见 verification.json）

最终 frontend 为 `src/archcanvas_python/frontend.py`，64135 bytes，SHA256 `ce7f7f733da28cb31ecff80ca029a53094e88f8451bffc3874f8167f80a07d00`；新增 `tests/test_m4_unknown_boundaries.py` 的18个反例，15047 bytes，SHA256 `7234d21e22350639404ff6ce11d4852a74b1ecfcf592375053e4ff0ea476578c`。

`build.log` 是 `tsc --noEmit && vite build` 的成功输出；`studio-tests.log` 是 Node Studio 套件的88/88输出。最终Python套件为62/62（含新增18项），额外静态rebind/outputpaths套件为21/21，均无skip；[精确命令收据](python-final-command-receipts.json)绑定实际 `/home/fzg/anaconda3/bin/python` 命令、环境、退出0和 [62项日志](python-final-62.stderr.txt)/[21项日志](python-final-static-21.stderr.txt)。较早 `python-tests.log` 的38/38和 `python-boundary-regression.log` 的12项（11通过、1skip）仅保留中间过程，不能与最终套件相加。

独立正式副本另用 `.venv` 完成 [base-model 11/11](final-base-models-report.json)、[holdout 28/28与Studio 3项](independent-holdout-final/m4-holdout-report.json)、[发行独立性9项](final-independence-report.json)。各自的命令与provenance单独绑定，不能概括为所有检查均使用同一解释器。最终文件、产物和检查汇总在 [verification.json](verification.json)，本轮最终字节另由 [final verification](../m4-boundary-final-verification.json) 封存。

## Boundary contracts covered

`frontend.py` 清除不确定初始化和控制流重赋值留下的旧contract。未知mutation就地使原Spec opaque，传播到alias、Sequential和ModuleList捕获项，保留真正的shared identity；直接重绑定保留尚被捕获的旧对象，用稳定constructor occurrence区分旧、新instance。多目标赋值只求值一次RHS；未知helper/RHS收到已有对象也不能留下旧contract。`ModuleList`直接调用保留opaque，无shape的 `chunk`/`split` 不生成固定输出槽位；不确定循环、`break`/`continue`与shadowed `range`保留opaque，已知无break的range循环执行else分支。

`cameraProjection.ts` 与 `App.tsx` 的world-coordinate投影覆盖负bounds、fit/focus、缩放、平移和框选；`edgeAppearance.ts` 让Inspector与实际rendered canonical edge style一致。Studio tests还覆盖gesture identity、终点采样、undo/redo、共享/repeat/opaque facts和现有导出合同。residual依赖判定属于此前已有修复。

## Bounded browser check

[browser-journal.json](browser-journal.json)保存真实CUA操作与只读DOM观察，[browser-validation.json](browser-validation.json)11项检查通过。一个Transformer L0 root拖动client−80px→canvas−148px，viewBox x0→−128；rootCSS−79.692291px对期望−79.692308px，legendCSS0。完整SVG的undo/redo仅排除两个revision标量后精确恢复；保存/重开SVG含revision原字节相同。mask edge:7默认UI为`#a194a8`/width1.5/checkedtrue；一次uncheck立即实线，undo整SVG恢复，最后保存visual5/storage2，root layout x−98、pins为空、edge overrides为空。[实际存储副本](actual-document-store.json)和[最终截图](browser-final.jpg)与journal/validation由本轮收据绑定。

浏览器8900使用保留的d884中间backend，UI JS始终是Cr_xKW9U；实际standalone副本的 [backend字节](browser-backend-initial.py.txt) 与 [收据](browser-backend-initial-receipt.json) 保存该范围。最终ce7 frontend的 [IR/完整SVG回放](final-source-and-canvas-replay.json) 为14/14：fresh Transformer architecture全字段等于实际store，完整XML树、metadata、revision精确，无忽略字段。raw SVG字节因DOM序列化不同而不相等；XML解析仅处理entity、自闭合写法和属性顺序。该回放支持此固定Transformer坐标/样式行为，不能认证后加unknown/captured-Spec反例的最终backend原生浏览器范围。

8900隔离服务session46721已明确Ctrl-C退出0，临时tab34关闭，不承诺在线。用户8765未触碰；service观察是生命周期事实，不认证浏览器性能。旧五席包的[实际verify](old-research-stale.log)返回“Formal implementation changed”，命令exit1，保留旧包与旧哈希。

## Current preparations

[fresh静态视觉准备](visual-static-preparation.json) 完成36候选/9frontier、117文件与geometry/spatial core检查；候选最小字号2.531–8.575pt，10/36≥7pt，不是期刊合格线。[新browser spec](../../../.archcanvas/browser-visual-matrix-boundary-final/spec.json) prepare/verify通过，绑定72 core、21 implementation与3 build文件，此前prepare时浏览器collect为0，静态候选不是浏览器截图；同一最终构建随后另完成[新39例实际矩阵](../../m4-boundary-final-matrix.md)。

[fresh研究包准备](research-current-preparation.json) 的 `.archcanvas/m4-research-trial-boundary-final` prepare/verify均退出0，manifest绑定61实施文件/4baseline，5个pristine席位使用8901–8905；0分配、0收集、0真人，未启动席位服务。verify只核冻结baseline与implementation，研究任务门仍not_evaluated。

## Evidence boundary

旧版本的39-case矩阵、五席研究包、旧native/performance receipts和旧seal由 [before-m4-boundary-corrections](../before-m4-boundary-corrections/manifest.json) 保存165个文件原字节；旧seal的3188绑定仍可解析到原字节，不改旧哈希。此前回归核对见 [previous-bindings-final-recheck.json](previous-bindings-final-recheck.json)。本目录的一例坐标/样式核对不构成完整浏览器矩阵、持续presented性能、活动取消、pins、真人出版评分或3–5研究者任务认证；这些门保持未认证。`verification.json`是机器字节、测试和有界浏览器核对收据，M4仍partial。
