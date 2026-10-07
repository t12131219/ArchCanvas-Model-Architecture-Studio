# au3 矩阵独立审计

本目录仅追加审计辅助代码与新回执。没有操作浏览器、执行模型、安装依赖、运行产品测试或构建；产品、正式文档、旧证据、旧 seal 未改。正式浏览器采集由 root 执行，证据绑定 helper 由 corridor_design 负责。

静态准备审计独立核 preparation 的 83 个输入及 before/after、三次 exit 0 的原日志、spec 的 24 个 implementation / 72 个 Canvas-SVG / 3 个 build 绑定。独立从三份 architecture 的源字节与语义内容重算 source/IR digest；从真实 parent/children 导出 Transformer 4、MLP 2、CNN 3，共 9 个 authored frontiers。每个前沿覆盖彩色/黑白与 85/180 mm，合计 36 个变体。检查 Canvas canonical digest、页规格、完整展开成员、Scene 可见成员与 SVG 绑定。静态候选不计浏览器截图或人审。

病例审计只读取已发布的 `bound/*/binding-receipt.json`。逐例核原 inputs、helper-source 快照、source/build 不变、copiedFiles、实际观察 UUID 对应的原导出 Canvas/SVG/receipt、public SVG 字节及 metadata、保存快照、JPEG/PNG 完整解码、截图后缀纠正原字节、UA/DPR 历史出处。`screen-receipt.json` 的后续独立 hash stamping 仅允许改变两个 hash 字段；未 stamping 不计正式 collect 完成。

首例 `transformer-level0-paper-180` 没有在 live store 更新前捕获 stored envelope。它仅是实际导出 Canvas 与公开 DOM 的绑定，storageRevision 为 null；不得推导保存快照、保存重开或存储认证。其他病例的 snapshot 若缺 originalCopiedAt，其 copiedAt 明确只是 sidecar 写入时间，不能冒充原复制时间。

UA/DPR 明确来源于历史同 IAB observer 的具体文件/hash/JSON pointer；本轮 viewport 来自各例公开 DOM。`currentNavigatorObserved=false`，browserVersion/hardware 为 null，fontEvidence 为空。字体、硬件、当前版本与物理像素校准不由这些字段认证。

仅获 root 明示授权的 `heightMm` 有限正数序列化差可用绝对容差 1e-10。所有其他 metadata 字段严格一致；原 `public.svg` 字节与 `browser-scene.svg` 精确；捕获 SVG 与实际 publication SVG metadata 仍严格一致。应用容差的病例明确记录差值与 exact=false，不能称全部 public metadata 字节精确。先前 strict binding 失败保留在原 failed-binding-attempts。

`preparation-attempt-1/2` 是 reviewer 辅助实现失败：首次把 expandedIds 的顺序误当合同要求，二次为定位同一断言；实际合同采用 sorted 成员相等。失败文件保留，`preparation-attempt-3` 修正后通过。后续 bound-readback 使用新目录追加，每份报告有完整 inputs before/after，不覆盖较早回执。较早回执没有自带 auditor source 快照；当前 helper 从下一份开始保存精确 `auditor-source.py`。

工程一致性与 image decoder 通过不证明 screenshot 内容、原生采集来源、美学、人类参与、真实尺寸可读性或性能。正式 collect 的 renderer/normalizer 比较及后续像素/人审分别验收，未完成病例保持缺失。

## 新增交互与保存重开审计

`gestures/residual-cnn-attempt-1`、`gestures/mlp-attempt-1` 与 `gestures/transformer-attempt-1` 分别核真实输入指令记录与四方向 public SVG 的最终几何、undo/redo。每次移动、撤销、重做各增一个 revision；完整 SVG 只排除 revision 表示后恢复精确，无关 body 不变。输入起点在所选节点真实 screen body 内，screen delta 按观察 CSS zoom 和 4-unit grid 换算为实际 world delta。atomicNativeDrag 来自 root 的记录，独立 observer 未记录事件来源，activeHeldCancelTested=false，不认证时序、帧率或原生事件来源。Transformer 左移 edge69 的 route elbow 大跳由另行像素审查记录，几何/history 合同不认证路由视觉稳定性或美观。

这些 gesture 报告只绑定截图文件的字节，没有解码、像素比对或 current-pixel 结论。像素审查另行发现 MLP `02-right-move.jpg` 显示 revision 22/X138，而同名 public JSON 为 revision 23/x142；原因未定，原图不能认证当前终点像素。该差异不被 SVG 的 undo/redo 几何审计遮盖，原材料保持不变，后续补采只能追加新 attempt。

`gestures/residual-cnn-persistence-attempt-1`、`gestures/mlp-persistence-attempt-1` 与 `gestures/transformer-persistence-attempt-1` 分别核保存 envelope 与 last-redo/save/reopened 完整 SVG 逐字节一致、metadata 精确、architecture/source/IR、展开/可见成员，以及所有可见节点的局部坐标沿 ancestor 求和等于实际 SVG 坐标。重开相机 fit 变化明确允许且记录，不属于存储文档；重开 UI 的撤销/重做均 disabled，仅证明公开控件状态，未独立读取内部 history state。CNN 首次 reload 后立即读 SVG null 属加载中失败并保留，不计成功；MLP save DOM 截取时仍 busy，成功保存/重开结论来自 envelope 与后续 `已保存 / 已重开保存的画布`。

矩阵最终增量审计复用已过的 25-case 报告，不重新解码旧截图或重做 static/core。授权的 screen-receipt 两字段 hash stamping 会改变旧 receipt 字节；新报告须以精确保留的 unstamped 快照核旧绑定，只比较排除两 hash 字段后的完整成员并验新 hash，逐例披露 authorizedScreenReceiptHashTransitions，不能将这些变化称为旧 receipt 原字节不变。

## 最终矩阵结果

`final-bound-collected-attempt-1/report.json` 通过，2515 个本次读取输入 before/after 精确不变。复用 25 个已验病例，仅对新增 14 例做核心/图片解码；旧报告 1147 个绑定中，1122 个按原哈希或精确 auditor-source 归档回读，另 25 个旧 screen receipt 的授权两 hash 转换逐例披露。完整新矩阵为 36 个 baseline 与 CNN/MLP/Transformer 各一个 edited，共 39 例；234 个 capture 文件与 bound 字节精确相同，36 份 core-preview 副本精确。

正式收集协议独立核 39 次 stamp、1 次 index、1 次 collect，41 份命令回执均 exit 0、stderr 为空，原日志哈希精确。39 份 unstamped 原件保留精确；39 份 stamped receipt 仅两个 hash 字段改变，新 hash 正确，其余 bound 与 source/build 不变。336 个 collector 显式输入副本、Python/Node runtime identity 哈希及 352 个 collector 输出 inventory 回读精确；审计未重跑 collector。6 例 `heightMm` 序列化容差仍逐例披露。

`artifactCoverage=complete` 只表示工件完整和一致性。正式 manifest 的 `visualAcceptance=pending-human-review`、`humanAcceptanceCertified=false` 保持原义，独立审计不把这些工件转成全部截图的 current pixel、美学、物理文字尺寸、性能或人类验收证书。

`final-readback-attempt-1` 为 reviewer 辅助程序失败：回执序列化错误地要求外部 Node runtime 的绝对路径必须位于 repo 内。失败源码与观察错误记录保留，错误记录不是原始 stdout/stderr；修正仅让外部 runtime 路径继续使用绝对路径，按既有 audit 报告惯例，在新 attempt 做 hash-only closure。这不是产品或已通过矩阵审计失败。
