# M4 拖动预览计算路径

拖动每一帧原先把临时 move 交给 `applyVisualBatch`，完整校验文档、复制含源码全文的文档、物化 scene，再另建 scene 与 SVG。新路径在 pointerdown 一次校验、复制和冻结 gesture snapshot，并确定有效移动根节点；每帧只复制 layout 索引并修改这些根节点的局部坐标，随后仍调用同一 `buildScene` 和 `renderSvg`。

正式提交仍调用 `reduceHistory → applyVisualBatch`，执行两次完整文档校验、更新所有保存的 frontier 布局、复制历史快照，并保留一次拖动对应一次 undo 的合同。临时预览不生成可存储的 CanvasDocument，不更新 source、IR、frontier、document revision 或历史。预览 scene 的 revision 与即将提交的 move 相同，用于同一 renderer 的完整等价比较。

`studio/src/core/movePreview.ts` 保留当前 move 的规则：重复选择去重、选中祖先覆盖选中后代、任意 pinned 后代保护祖先子树、可见稀疏布局先物化、隐藏节点必须已有布局。冻结副本隔离调用者后续修改，也阻止返回 scene 的共享 page/semantic 引用破坏下次预览。每帧使用相同 scene 投影器，所以容器增长、手动尺寸、边路由、投影端口、说明和图例无需另写近似几何逻辑。

`studio/src/App.tsx` 将预览绑定到开始拖动时的实际 document 对象。其他视觉操作、undo/redo、源码刷新或切换文档替换 current 后，scene memo 不呈现旧预览；RAF 和 pointerup 都要求 `historyRef.current.document === active.document`，否则旧 gesture 不再提交。相同网格坐标的重复 pointermove 不再触发额外 React state 更新。取消 pointer 只丢弃临时预览。

六项专项测试覆盖完整 scene 和 interactive SVG 等价、负坐标/手动布局/容器 resize、重复帧、祖先与后代多选、pin 保护、可见稀疏与隐藏布局、来源与历史不变、commit 的 frontier 更新和 undo/redo、stale commit rejection、冻结快照、伪造 session、非法对象和非有限坐标。当前一次完整 Studio 检查通过 46/46，无 skip；`tsc --noEmit` 通过。日志保留在 `docs/evidence/m4-drag-studio-tests.txt` 与 `m4-drag-typescript-check.txt`，数量代表该次源码快照，不替代后来新增测试的总结果。

## 独立 CPU 证据

`scripts/benchmark_move_preview.mjs` 将正式 core 复制到独立 `/tmp` 目录，使用真实静态解析的 `DenseStress300` 输入，验证 fixture 当前源码字节与 receipt 的 SHA256 相同。旧 frame 调用链与新 frame 调用链使用**同一份当前** core、scene 与 SVG serializer；不把新 metadata 下的字节等价冒充与历史 SVG 的比较。每轮完整 scene 与 interactive SVG 比较在计时之外完成，另检查正式 commit、undo/redo、未修改输入和 architecture。

运行环境为 Node v24.19.0、Linux x64、Intel i5-13400F；使用 `process.hrtime.bigint`，10 次 warmup、60 次 sample，交替旧/新调用顺序。完整原始 sample、copied core/App/script SHA256、source/IR digest 和 scene/SVG SHA 保存在 `docs/evidence/m4-drag-core-performance.json`。

| CPU 阶段 | p50 | p95 |
| --- | ---: | ---: |
| 原路径每帧 document→scene | 11.70 ms | 14.32 ms |
| 新路径每帧 prepared preview→scene | 3.86 ms | 5.75 ms |
| 新增一次 gesture preparation | 7.08 ms | 9.55 ms |
| 原路径 SVG serializer | 4.22 ms | 5.90 ms |
| 新路径 SVG serializer | 4.11 ms | 5.54 ms |
| 正式 guarded history commit | 9.72 ms | 13.78 ms |

计时之外的独立 instrumentation 确认原每帧有 2 次 validateDocument/validateArchitecture、1 次 structuredClone、2 次 buildScene；新 preparation 仅在开始执行 1 次校验、1 次 clone、1 次 scene，每帧仅 1 次 scene。正式 commit 加 App scene 仍有 2 次校验、2 次 clone、2 次 scene。SVG serializer 未做优化。

这些是 CPU 分阶段数据，不能代替浏览器的 native 输入、DOM 渲染、FPS、INP 或 Event Timing。开始拖动新增了一次 snapshot preparation；整个 scene 布局和完整 SVG serialization 仍每帧执行。浏览器应优先实测 300 层展开后的单层拖动、network 子树拖动、祖先+后代多选、pin 子层后拖祖先、拖过容器边界后的 resize，以及松开后一次 undo/redo 和拖动期间版本变化取消。

复现命令：

```bash
node scripts/benchmark_move_preview.mjs --architecture <正式静态分析的300层architecture.json> --samples 60 --warmup 10
```
