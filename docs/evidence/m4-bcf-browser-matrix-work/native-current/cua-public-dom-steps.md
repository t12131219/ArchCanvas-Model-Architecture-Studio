# 当前8982独立native采样：公开UI与DOM步骤

本步骤来自已读取的正式harness/observer/App源码，不是已执行浏览器操作，也不是新增当前性能试次。浏览器归根Agent；使用其已加载文档中确认支持的CUA普通click/drag/presskeys/scroll及只读DOM。以下selectors/读取对象只是公开DOM定位依据，不擅自声明任何新的CUA API。不得调用产品window globals、React私有state、observer函数、fetch或合成event。

## 页面与公开控制

| 页面/区域 | 公开目标 | 普通动作与需要读取的结果 |
| --- | --- | --- |
| `http://127.0.0.1:8982/__m4/` 外页 | `#label` / aria-label 会话标签 | 输入预声明标签，如 `bcf-mlp-native-pilot-1`，发生在会话开始前。 |
| 外页 | `#mode` / 测量模式 | 选择可见option **完整输入观测**（value `full`）；本表不假定CUA支持selectOption，按已documented方式操作。 |
| 外页 | `#start` / 开始会话；`#status` | 点击开始；status显示记录中，arm启用。start触发observer，外页按钮不计产品输入。 |
| 外页 | `#operation` / 测量操作 | 选择可见option：缩放、拖动节点、平移画布、撤销、重做、展开/收起、固定/解锁。 |
| 外页 | `#targets` / 目标 ID；`#anchors` / 锚点 ID | 通过普通输入填实际公开stable IDs；drag/toggle必须target，逗号或换行分隔。pins自动从iframe公开DOM采入，不可手写假pin。 |
| 外页 | `#arm` / 准备此操作；`#finish` / 结束此操作 | arm→产品内一次明确动作→读取稳定结果→finish。不要把被arm之外或错目标的输入补计成功。 |
| 外页 | `#stop` / 结束会话并显示收据；`#receipt` / 原始输入测量收据 | 点击stop，读取readonly textarea实际 `value`。不要调用observer.stop、改textarea或读取module私有变量。 |
| `iframe#studio` / title 未修改的正式 ArchCanvas Studio | 子文档 | iframe同源，读取其公开DOM。先确认loaded scripts为 `index-BcFxpKDY.js`、CSS `index-NmgHfiF5.css`，记录真实top/frame位置和焦点。 |
| 子页 | `select[aria-label="示例模型"]` | 会话前打开MLP、Dense 300-layer stress等真实option；加载完成后再start。source-backed300场景必须实际展开才达到规模。 |
| 子页canvas toolbar | `button[aria-label="选择对象"]` / `button[aria-label="平移画布"]` | drag前选择对象且aria-pressed=true；pan前手工具且aria-pressed=true，`.canvas-viewport`的data-canvas-tool一致。 |
| 子页tree | `[data-tree-node-id]`、`.tree-toggle`、aria-expanded | 从实际DOM选容器stableID；树上toggle通常以click触发。独立observer以pointerdown识别toggle，普通click包含该输入。 |
| 子页SVG | `[data-expand-id]`、`[data-canonical-id]`、`[data-node-id]` | canvas toggle/节点body可从实际DOM确定target。drag避免端口、expand按钮、文字编辑和祖先容器body误命中。 |
| 子页toolbar | title 撤销 Ctrl+Z / 重做 Ctrl+Shift+Z / 固定 / 解锁 | 使用公开按钮或已documented快捷键；输入框焦点必须先移开。observer读取aria-label或title，不能仅看图标猜动作。 |
| 子页zoom | aria-label 放大 / 缩小 / 适合画布 | 普通按钮可采离散input；scroll wheel只给连续DOM proxy，不会产生可配对native wheel Event Timing。 |

## 采样前后最小公开DOM快照

只读保存以下DOM字段，不用产品private state：

- top document、iframe与canvas viewport的真实client rectangles；outer/frame滚动位置若可从公开DOM读到；top/iframe `document.hasFocus()`与visibilityState按已documented只读DOM能力读取。host窗口size未知就标unknown，不能把1280×720 iframe宣称为宿主size。
- iframe script/src、link[rel=stylesheet]/href，原始SVG `outerHTML`、metadata原文、data-document-id/data-revision、viewBox、物理width/height。
- `.publication-scene`的data-expanded-ids/data-pinned-ids；工具data-canvas-tool及button aria-pressed。
- 实际目标 `[data-canonical-id]` group的stableID和**direct child rect[stroke-width]** body几何/矩阵或bounds；排除repeat shadow、glyph和展开按钮rect。节点body的中心可以用read-onlyrect+getScreenCTM转换，但实际CUA点击必须在可见bounds内。
- 实际route `g[data-edge-id]` 的首个path/d、data-tensor-id；source/target/canonical IDs来自公开metadata，不能通过节点label臆测。
- 计划用的无关pin需真实membership、可见body与viewport相交、既非target祖先亦非后代。无pin样本如实标无覆盖。

有界快照可先记录目标和路线，完整SVG另读并完整保存。真实DOMvalue与AX文字若不一致，分别保存并标unknown原因，不用AX填充raw缺失。

## 建议最小pilot与可继续扩样的顺序

1. **MLP新会话**：start之前选择MLP、fit、公开确认非根容器与一个实际visible leaf ID。执行toggle一次、正确叶节点drag一次、undo、redo、zoom按钮一次、pin一次；每次独立arm/finish。简单pilot先验证observer/目标命中，不代表总体p95或足够sample size。
2. **四向补充**：在同场景另开标记清楚的session，四个drag方向、四个pan方向分别独立trial。针对一个可见leaf完成drag/undo/redo回到baseline后再下一方向，避免累积布局导致目标离屏；pan用真实手工具，恢复工具/位置发生在arm之外并journal记录。atomicdrag虽包含原生down/move/up，不能插入进行中Esc/blur。
3. **300对象独立会话**：会话前选择Dense300；arm toggle→普通展开→finish，确认实际SVG scene nodes/edges数量并报告objects定义。再选当前可见非input/output leaf，至少drag+undo+redo、四向pan和zoom。未命中requested target必须保留no-input；不要替换成实际移动的父容器。
4. 每session结束先用只读textarea读取完整raw，再进行save/reopen等额外任务。两会话不混淆source/digest/build，先保留pilot缺失再补采，不覆盖失败。

observer的 `finish` 由外页点击，trial会包含操作前后等待和焦点切换；rAF全trial或session分母不是持续drag的呈现区间。后审计可另从可信same-pointer down→up重算active window cadence，仍不称presentedFPS。切到外页自然造成iframefocus变化，不等于真实windowblur取消活动手势；pointer-up后的lostcapture不是取消样本。

## 完整读取readonly raw

先通过公开DOM只读取 `#receipt.value.length`与头尾片段确认协议和完整性；再按宿主允许的只读DOM读取方式得到完整value或固定长度分块。每块必须携带offset和length，连续offset精确拼接，不截断、不补JSON、不重新序列化为“原始值”。避免一次工具output被截断；raw可能数MB。

成功读取后在新的会话目录保存 `raw.json` 与capture journal，独立校验：

```bash
node scripts/validate_input_observation.mjs \
  docs/evidence/m4-bcf-browser-matrix-work/native-current/mlp-pilot-1/raw.json
```

保存真实stdout/stderr/exit；另核对context.productionAssets/probeSources与实际preparedhash、DOM脚本URL及原始trusted event序列。eligible/matched/missing/interaction分母明确；缺失保持null。任何native匹配p95都只覆盖离散matched subset，不是总体INP。buffers丢失、observererrors、长期rAF间隔、longtask原样保存，不能删失败试次制造通过。

该v2收据已经具备双向唯一ET匹配、interaction去重、公开pan终点核对及selfcost记录，优先完整采它。`/?benchmark=1`原生expand-only面板可以另外取得top-level5toggle pilot；两环境/协议分开，不能把iframe结果提升top-level，禁止synthetic“运行20组”代替native。

## 留给独立审计的工件

新raw、实际capture日志、before/after DOM+SVG与截图、服务log增量snapshot、publicloadedassets/context hash、source/store envelope（如实际save）、所有validator输出。独立审计本次将只读取这些文件，不重新控制浏览器或补假输入。presentation、held-down取消、fixedresolvedfonts/hardware、真人门当前均不因此关闭。
