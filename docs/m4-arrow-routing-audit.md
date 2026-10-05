# M4：箭头几何补审与有限避障修复

本轮继续 M4，发现并修复了默认路线穿过无关对象和展开容器标题区域的问题。实现来自正式工程自身的几何契约，没有采用旧版代码。当前证据支持以下范围内的几何正确性；它不宣布 M4 完成，也不建立真人任务、实际帧率或论文出版验收。

## 修复为何必要

独立 Python 审查器先通过 7 个刻意构造的反例测试，再读取旧冻构建 `index-Cr_xKW9U.js` 保存的 39 份实际浏览器 SVG。检查不调用产品 Scene、路由器或其求交代码。结果是 0 端点/marker 缺陷、0 无关对象重叠，但有 300 条路线穿入无关对象内部的记录。记录包括宽度和色板变体的重复，不代表 300 个独立缺陷。不同 tensor 的线段严格交叉观察为 465 条。

Transformer 深展开中的 mask 路线 `edge:7`、`edge:11`、`edge:25`、`edge:29` 穿入 decoder/body，`edge:21` residual 路线穿入 encoder feedforward 容器。深展开 MLP/CNN 在这份审查范围内没有无关对象穿入，但全图适配截图分别约为 46%/17%/14% 缩放，不能据此认证最终尺寸的小字或出版可读性。此前 `novice/import-dialog.png` 和 `novice/mlp-example.png` 的像素与对应状态不一致，已被排除。

原始观察保留在 [matrix-geometry.json](evidence/m4-ai-usability-next/arrows/matrix-geometry.json)，修复前正式源码与构建保留在 [before-routing-obstacle-fix/manifest.json](evidence/before-routing-obstacle-fix/manifest.json)。旧的矩阵、封印与原始截图未被新结果覆盖。

## 实现边界

`studio/src/core/orthogonalRouter.ts` 提供整个画布和详情导出共用的正交路由。没有碰撞的原始路径保持逐字节一致；只有穿过对象 body、源/目标 body 或展开祖先 header 的路线才尝试绕行。端口位置固定，合法的祖先内容区域可通行，标题区域作为障碍。简单折线和单走廊候选先按曼哈顿长度与转折代价选择，必要时使用限制为 40,000 网格单元的 Hanan-grid 搜索。所有路线点纳入 Scene bounds，防止外绕路线被裁掉。

路由不会移动节点，也不会改变 canonical tensor、语义端口、SourceFacts 或手工布局/history。源/目标重新穿入自己的 body 也接受检查。无关对象 broad phase 将长展开容器与 leaf 分开索引，避免 DenseStress300 的纵向大 frame 使每次相邻路线检查扫描所有 leaf。

找到路线并不代表线间交叉或共用走廊已经最优。人工重叠、端口被遮挡、标题覆盖或搜索预算不足时，保留人工坐标及原路线，输出 `layout-overlap`、`layout-header-overlap` 或 `layout-route-blocked`。诊断附真实 objectIds/edgeId，ID 即使以 `#header` 结尾也不经过 suffix 解码。界面按可见别名显示中文布局提示，并说明移动对象或增加间距；源码分析提示与布局提示分开。

## 当前冻结证据

最终 Studio 全套测试 **102/102**，严格 TypeScript 与构建 exit 0。几何回归包括 9 个层级 frontier、32 个详情 selection、四方向 preview/guarded commit Scene/SVG 精确相等、undo/redo、语义不变性，以及人工重叠和真实 canonical-ID 诊断。冻结源码、dist、配置、相关测试和 frontend 的完整清单位于 [arrows/frozen-final/manifest.json](evidence/m4-ai-usability-next/arrows/frozen-final/manifest.json)。清单 SHA-256 为 `e327f55cc2b0c4bcfa3717d5907a75c32bc8a84d50378bac72a3a99e4c05072c`。

| 当前文件 | SHA-256 |
| --- | --- |
| `studio/dist/assets/index-DgtJrWU9.js` | `84baa013033ea696c3dcec4d5abaaf5b5417730c36cc0518a326f28d1f56329a` |
| `studio/dist/assets/index-DK5lov-h.css` | `d6d5f8f4d8824f28b313ffffe685678225486e5cf25966f0528d3846eb6a8a7f` |
| `src/archcanvas_python/frontend.py` | `ce7f7f733da28cb31ecff80ca029a53094e88f8451bffc3874f8167f80a07d00` |
| `studio/src/core/orthogonalRouter.ts` | `bc06c53ed75793f9e7dd9315d21040bbe36c7acd97eab54ef6feb74ba5247c15` |
| `studio/src/core/scene.ts` | `c8832855ba54c6ec696b64f77588487ab5f2d016c5e38d0f06d77c62c285862d` |
| `studio/src/core/exportScene.ts` | `e1f8bb7c145b619821f2598d811df263792edbd9e96a79257d12b0df1f9cbc58` |

[frozen-final/cpu-scenes.json](evidence/m4-ai-usability-next/arrows/frozen-final/cpu-scenes.json) 记录 39 份历史 CanvasDocument 输入由冻源码拷贝重新生成的 CPU SVG，输入和归档源码均检查哈希。它们是新 CPU rerender，不能继承旧 39 份浏览器覆盖。每份 Scene 的一个静态 AST info 提示保留；这些输入没有布局 warning。[frozen-final/independent-geometry.json](evidence/m4-ai-usability-next/arrows/frozen-final/independent-geometry.json) 记录 0 端点/marker 缺陷、0 无关 body 穿入和 0 无关 body 重叠。不同 tensor 交叉观察仍有 293 条；该数值不是线间美观的验收指标。

另一个独立代理维护的 [routing-independent/audit.json](evidence/m4-ai-usability-next/routing-independent/audit.json) 复制并绑定最终 core 的 `1fa6c7a0c4f7eb48` 快照，使用与产品不同的 parser、求交和矩形 oracle。39 个 whole scene 与 32 个 detail scene 的无关 body、源/目标 body、展开 header、脱离端口与越界检查均为 0。作为历史对照，其更严格的旧源码检查分别记录 304、4、233、0、0 条；这个范围与上文 inset 2 的 300 条不同，不应混计。

独立审查还通过 120 个固定 seed 整数障碍场、8 个明确路由反例、overlap 索引与独立二次扫描一致性、canonical 关系覆盖/SourceFacts 与旧源码一致性，以及 source-backed DenseStress300 的 12 次四方向移动。其完整 Scene/SVG、preview/commit、history 与 undo/redo 均检查相等。大幅纵向移动造成的人工重叠保留且用准确 objectIds/edgeId 报告。

## 实际手工位置观察

主代理保留的旧构建四方向实际拖动各有 before/moved/undo/redo 四份 JSON/SVG/PNG。[shared-ui-move-geometry.json](evidence/m4-ai-usability-next/arrows/shared-ui-move-geometry.json) 只读审查 16 份记录：每次实际位移为 ±32 SVG 单位，undo/redo 恢复精确 body 坐标，camera transform 不变，0 端点缺陷与无关 body 穿入。

向上移动把 Linear 从 `(110,316)` 移到 `(110,284)`，与 network 的可见标题区重叠 `194 × 12 = 2328` 平方 SVG 单位；redo 保留相同冲突。实际截图也能看见标题区被压住。此坐标属于用户手工编辑，修复不会静默 clamp。最终 core 针对此案例保留坐标并输出 header-overlap 与 route-blocked 提示；新的构建还需要以实际浏览器检查可见提示和手势，旧记录不能代替该验收。

## 性能与限制

CPU benchmark 三份保留在 `arrows/candidate/move-preview*.json`。最初与检查并发的 sampling 受争用，prepared Scene p95 为 18.50 ms；隔离运行为 16.23 ms；broad-phase 优化后的、**structured diagnostics 最终修改之前**的副本为 11.50 ms。后者 prepare p95 15.47 ms、SVG 5.79 ms、guarded 每帧 Scene 25.74 ms、commit/history 18.42 ms。旧路由 prepared Scene 的历史 p95 5.32 ms，避障增加成本不能隐去。这些只是 CPU 诊断，不能声称最终构建已达到 presented FPS、INP 或 browser latency 目标。

网格上限会漏过已知存在的复杂路线：独立 300-box maze 反例触及 40,000 cells，保留原来的两次碰撞并报告冲突。因此路由是有预算的修复，不能宣称完备避障。路线写出使用 0.01 SVG 单位精度，产品求交容差为 0.01；负数小数端点反例记录了严格 0.001 单位的 rounding 接触，0.02 inset 检查排除这项数值接触。候选走廊不处理 edge-edge crossing 与平行 lane 分离。

这份报告不改变 M4/M5 状态。实际新构建浏览器交互/性能、最终物理尺寸可读性和真人任务结果由相应独立证据处理；本报告不以 CPU 结果或 AI screenshot 观察替代这些验收。
