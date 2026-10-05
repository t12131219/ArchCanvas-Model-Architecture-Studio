# 平移与注释改善前的独立几何诊断

[geometry-analysis.json](geometry-analysis.json)只读分析旧 full-task 的实际 DOM、最终 Canvas、正式 layout/Scene 源码和[技术计划](../../../../ArchCanvas_双向模型可视化与编辑框架_技术计划书.md)。没有修改原 oracle/report、产品或 current-verification，也没有为新实现运行浏览器、构建、测试或 prepare。

移动目标 `feedforward.expand` 的画布坐标从 (170,996) 到 (202,1016)，正好 +32/+20。其余20个节点的 body 坐标、尺寸和外观逐字段不变。四个祖先的 x/y/height 不变，width 各增32：

| 祖先 | width 前→后 | 分类 |
|---|---:|---|
| FFN | 254→286 | 子节点右界增加32，保留30单位右内边距 |
| EncoderLayer1 | 314→346 | 随 FFN 右界增加，保留内边距 |
| Encoder | 374→406 | 随第一层右界增加，保留内边距 |
| Transformer | 670→702 | 行宽聚合下界增加；实际保存子节点最大右界仍690，外层增宽不是最小包围所必需 |

这些祖先属于目标的布局依赖。前三项是保留现有内边距的相关 resize；最外层是可解释的算法扩宽，仍有减少多余范围的优化空间。不能把四项都当无关锚点漂移，也不能把它们都称作严格必要或审美通过。源码证据在 [scene.ts](../../../studio/src/core/scene.ts) 第57行：行宽下界、递归 size、保存局部坐标与 port 比例定位。

连线6/7/16的端口位于相关祖先：第一层 width 增32，使两个输入端口分别从214.7→225.3、319.3→340.7；FFN的单输入端口从267→283。路径因此重接相同的 canonical source/target/port/tensor。连线17/18直接接移动目标，变化也合理。它们没有改变计算来源，mask corridor599保持不变；这不是路由美观或无交叉认证。

原[严格字段报告](../automation-full-task/independent-field-audit.json)仍 failed（1025 pass /70 fail /11 unknown）。它要求所有非目标 body/path 保持完全相同，比“目标相关祖先 resize、必要邻域与端口重接”的计划合同更强。这次依赖分析不回改那些谓词或结果；下一次若采用允许相关依赖变化的 oracle，须在输入前另行声明并保留旧失败证据。

画布历史的可观察字段恢复正确：排除 revision、metadata.revision、camera、viewport 与 node.screen 后，before=undo、after=redo=reopen。真正保留的屏幕证据缺口是 viewport：before/after 为 x230、783×526，undo/redo 为 x200、672×641；camera CSS相同，但25个 node.screen 的 x统一减30。因此不能认证固定视口屏幕连续性，也不能从这些快照指认 camera-reset 产品错误。protected pin画布 body始终(80,154,150,42)，但屏幕 y=-563、离屏；可见 pin 零位移仍未证明。没有每个历史状态的完整隐藏文档或连续输入绘制测量。

计划§9.5/§13.4/§18.5要求保护相机、局部邻域、无关 pin 与展开锚点，不是禁止所有相关框尺寸变化。本轮显式平移应单独记录 trusted 同 pointer 的实际输入、精确相机增量及文档/选择/历史不变；注释应先保存真实添加前 Scene，检查文字正文、叶节点、连线与图例的冲突，再做历史、保存重开和导出链。

## 新版本切换

现有工具没有 `--current-only` 参数；这是报告范围区分。旧39矩阵、五真人席与当前报告必须先按原字节存档，新版本使用新路径和新哈希，旧结论不改。仅保存旧 manifest 不够：研究包的55个 implementationFiles主要指向工作目录，需额外保留实际旧源码和 dist 字节；矩阵还需保留 spec、其 `coreDirectory`、构建及像素观察。事务 approval-key 不进入公开证据。

当前旧矩阵 spec 是 `docs/evidence/browser-visual-matrix-spec-zoom-current/spec.json`，coreDirectory是 `docs/evidence/visual-golds-intrusion-current`；39收集目录本身没有 spec。后续代码/build变化会使旧 verify 失败，这是历史范围提示，不能更换旧哈希继续。App.tsx不在矩阵的20个 core实现清单中，必须先真实 build，再新 prepare，并记录浏览器实际加载资产。

最小后续步骤和未执行命令已列在诊断 JSON：归档 → build → 新 core36候选 → 新矩阵 prepare/verify → 新 caseId 的实际采集/collect；另 prepare/verify 新五席人类包。先做本轮少量平移/注释回归可以，但协议仍需36基础＋至少每模型1编辑样本才是完整矩阵，不能用少量新图继承旧39 coverage。人类包保持 unassigned/0/not_run；自动化复跑用另一个3席包，实际 assignment 后才开始操作。

本诊断只记录上述判断与操作步骤，没有执行归档或版本切换。源码与工件摘要绑定读取时的旧输入；root正在独立实现新功能，后续新证据需要新记录。
