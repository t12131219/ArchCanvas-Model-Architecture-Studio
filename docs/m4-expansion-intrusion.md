# M4 展开空白收敛修复

真实浏览器矩阵暴露了 Transformer 二、三级完整 frontier 的下游长空白。二级保存画布的 `output_projection` 局部 Y 为 3086，模型 Output 为 3186；两条并列 encoder/decoder 分支已经在全局 Y=2048/1756 结束，projection 仍在 Y=3178，留下 1130 px 空白。Fit 按整张图缩放，空白进一步压小可读内容。

只用 `createDocument(saved.architecture)`，按该画布的五次展开顺序重演，就能与真实保存的 `layout`、全部 `layoutByFrontier` 和 `expandedIds` 完全一致。该画布没有 pin、alias 或样式编辑。因此这次空白来自自动展开位移，不是用户手动摆放。原算法对 downstream 邻居一律加上容器的完整高度增长，即使邻居已经因另一条更高分支而留出足够空间。

原始 36 个基础图和 3 个编辑后图的真实截图矩阵先完成验证并封存于 `docs/evidence/browser-visual-matrix-before-intrusion-fix/manifest.json`。此后才应用修复，原来的浏览器事实仍可单独审查。

修复只改变 `studio/src/core/document.ts` 的新 frontier 展开修复逻辑。每个受影响 containment 层先确定横向或纵向的一组 sibling，取它们离增长边界最近的一项，计算增长实际侵入现有空间的距离。已有空白吸收增长，只有剩余侵入量才推动整组 sibling；组内相对间距保持不变。标准 gap 最多保留 42/38 px，原有更窄的间距不被扩大，宽阔的手动留白不触发额外移动。横向优先规则、从内向外修复顺序、操作锚点、pin 与祖先保护保持原合同。

修复前后的相同真实 Transformer 二级展开序列：

| 布局事实 | 修复前 | 修复候选 |
| --- | ---: | ---: |
| projection 局部 Y | 3086 | 1994 |
| projection 全局 Y | 3178 | 2086 |
| 最高并列分支底部 | 2048 | 2048 |
| projection 前空白 | 1130 | 38 |
| scene 总高度 | 3474 | 2382 |

这些数字来自独立复制 core 的 scene 计算，随后实际源码按候选 SHA256 精确应用。它们不是修复后浏览器截图或人工视觉验收。scene 的标准投影、route、port、SVG 和导出实现没有由这次修复替换。

新增 `studio/tests/expansion-intrusion.test.ts` 的八项 meaningful 回归覆盖：独立手写两个并排容器的较矮分支展开不再移动已留空位的 output；横向已有空位和相邻间距；远处手動 output、用户移动与 frontier 恢复；pinned output 和 pinned 后代；重复 collapse/reexpand 与 undo/redo；真实 Transformer 二、三级 anchor、完整 sibling 无交叠和手动 FFN 位置；真实 CNN 两块展开后 pool/flatten/classifier 空间与缓存恢复。独立发行副本跑旧 46 项加新 8 项，共 54/54 通过、无 skip，并通过 strict TypeScript 检查。应用到实际项目后轻量重跑专项 8/8 通过；构建由主流程统一执行。

准备期证据位于 `docs/evidence/m4-expansion-intrusion-prepared/`，其中含原始重演报告、candidate-only patch、完整测试、独立全套 stdout 和 SHA context。实际应用 receipt 为 `docs/evidence/m4-expansion-intrusion-application.json`：原 document SHA256 为 `5748fc60dd8644e4d33a02d6a53c9d98cc30c2c50d7fa412a6992cf736ba4148`，应用后为 `a7f21768c718aa891701c73a150fd30aa4f05599b371ba22d41384130191694f`，与经过独立测试的候选完全一致。

已有保存画布和 frontier cache 保留原位置；此次修复不会自动压缩、迁移或重排用户文档。新矩阵应从 fresh document 重演展开。固定对象造成的冲突继续保留锚点并显示原有 overlap warning。修复后 production build、真实浏览器矩阵和人工视觉门必须各自取得证据。


应用后的core全套54/54、无skip，strict TypeScript和production build通过。后续只增加缩放控件pointerdown隔离，最终 `index-oH4Ot2L9.js` 的[完整实际浏览器矩阵](evidence/browser-visual-matrix-zoom-full/manifest.json)另封存36基础+3编辑后样本；旧修复前39及前导4样本各自保留。最终required Transformer L2的封存DOM为viewBox892×2382、Encoder底部2048、projection Y2086，实际空白38 px；L3 viewBox952×3166。少decoderFF的832宽额外frontier只作补充观察，未计入规定L2矩阵。保存布局/cache不自动迁移的边界继续有效。全部文件覆盖和AI像素观察不等于人工出版验收；native性能、解析字体与真实研究者门仍待取得。
