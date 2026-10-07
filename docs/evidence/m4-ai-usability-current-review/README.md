# M4 近期 AI 体验审查覆盖汇总

这是 `/root/research_handoff_audit` 的只读证据汇总。审查者没有操作浏览器、重跑旧验收、执行模型或改产品；本次只读取已冻结的动作、DOM/公开状态、像素复核、保存/生成工件和源合同报告。AI 角色不是 3–5 位真人，当前真人计数仍为 0，M4 partial、M5 未开始。

汇总时正式 `studio/dist` 已变为 `index-D60-bDcz.js` / `index-QPVAzYp6.css`。最近完整可读画布样本仍属于 `index-thbum3BQ.js`：22 帧、66 个 DOM/public/JPEG 文件全部按原 manifest 字节匹配，其中两帧像素错位保留失败、另外一帧检查 fetch 失败。新 native Event Timing 匹配修复产生的新 build 没有在本汇总中继承旧 build 的像素或体验认证。

## 各 AI 角色实际职责

| 角色 | 实际工作 | 可用证据与限制 |
|---|---|---|
| root（CUA 操作者） | 原生浏览器点击/拖动/键盘、截图与公开状态采集，保存草稿与生成工件。 | 可读画布 manifest 的 22 帧；旧 ye/BSA 的四链/合流/预制起点链。不是五个独立真人操作；事后动作声明也不是同步 OS 遥测。 |
| `/root/guidance_acceptance` | 独立 helper/源合同、收据/log/build 读回；曾识别中文/宽 Latin 越框、端口字号与命中框不一致、提示覆盖邻节点并推动修复。 | [source report](../m4-readable-canvas-work/independent-source/report.json)；只读最终源码范围，不是浏览器、出版或全 runtime 依赖认证。 |
| `/root/palette_acceptance`（相关报告写作 AI readback） | BV 15 张 JPEG 直接检查与字节/DOM对照，发现动作 JPEG 落后一步；随后可读画布 22 帧独立末读。 | [BV failed readback](../m4-module-library-final-readback-attempt-1/report.json) 和 [可读画布 readback](../m4-readable-canvas-final-readback-attempt-1/report.json)；不操作浏览器，不能用 DOM 覆盖冲突像素。 |
| `/root/guidance_novice_catalog` | 源码库存、参数帮助和首屏可发现性启发式审查，亲看两张 CW 图。 | [novice review](../m4-authoring-guidance-work/novice-library-review-attempt-1.md)；17种/34参数是库存，非逐模块 native 全流程。 |
| 历史独立路由/像素/工件角色 | ye 端点/hit/history、公有几何；BSA 合流避交叉像素；保存草稿、生成 Python AST、new managed/实际SVG核对。 | [native audit](../m4-authoring-interaction-work/acceptance/native-audit-attempt-1/report.json)、[BSA pixels](../m4-draft-merge-routing-work/visual-review-attempt-1/final-review-receipt.json)、[actual artifact audit](../m4-authoring-interaction-work/authoring-artifact-audit-attempt-1/attempt-2/receipt.json)。职责不等于不同研究参与者，旧build范围各自保留。 |
| 本汇总审查者 | 只读核66字节、四向公开坐标/route、保存重开公开字段，关联各角色与新缺口。 | [report.json](report.json)；不追加像素、美观、真人或性能结论。 |

## 用户要求的当前证据边界

| 用户要求 | 已有实际覆盖 | 仍未覆盖或不能继承 |
|---|---|---|
| 节点左右上下移动 | thbum MLP 的同一 ReLU 从 `(290,188)` 分别到 `(274,188)`、`(306,188)`、`(290,172)`、`(290,204)`；四个其它节点坐标、5节点/4边保持。上下移产生两条短正交 jog，保存/重开公开节点与边逐字段相同。 | 这4帧是独立base-relative结果，不是当前新build的 moved/undo/redo/restored 全像素链，也不认证复杂分支/全部模块。 |
| 相机左右上下移动 | ye public geometry 曾核四向40px；BSA四向JPEG存在，垂直全图可见，水平两端有裁切。 | thbum这22帧没有相机四方向样本；新D60没有本汇总核过的新链，不能说完整四向视觉验收。 |
| 箭头美观 | ye纵向四链3条直线；原合流 `(614,220)` 交叉保留。BSA有限五节点五边修复该交叉；thbum小MLP/双输入Add局部端点与route样本可读。 | A→Concat.b外绕长、多弯及CNN跨两排回线仍开放；Transformer复杂图、任意布局最少交叉/弯折、85/180mm人审未认证。提示只避节点，不避线/marker。 |
| 完全视图从零搭建 | ye从空白 Input→Linear16→8→GELU→Output，通过文字点击/圆点拖动/Enter-Space连接、重复拒绝、history、保存重开、静态生成、新managed和SVG。 | thbum没有重做空白到生成/managed/导出的链；CW是恢复编辑，DS中间才从零。新D60仍待实际任务，不从源码存在推定完成。 |
| 17基础模块/3预制起点 | 当前catalog AST为17；当前preset源码为MLP5/4、CNN8/7、残差MLP6/6，透明草稿。ye MLP/残差点击、CNN拖入均保存，MLP/CNN静态生成；BV基础/起点切换与搜索有DOM。 | 非17×click/drag/generate矩阵。residual旧轮未生成；BV多数动作JPEG错位，不能认证可见切换/搜索/添加。thbum只观察一个MLP/Adaptive入口，不认证三preset拖入。 |
| save/reopen/generate | thbum MLP保存/重开5节点4边 public完全匹配；ye四链保存/源码/newmanaged/实际SVG独审6/6；BSA合流保存/生成源码AST核对。 | BSA合流未打开新managed，thbum未generate；无模型执行/训练认证。新D60的准备包不等于研究任务。 |

## 只补采两个明确场景

1. **最终build空白四链与模块库入口**：独立automation workspace，从空白通过左库拖入 Input/Linear/激活/Output、可见参数与三种连接模式建图；核模块/起点切换、跨类搜索、未支持说明；保存重开后静态生成并打开newmanaged。每次动作等同一render稳定后采DOM/public/JPEG，保留状态错位。该场景补当前build从零链与BV截图失配，不一次扩称17模块全部认证。
2. **残差MLP原生拖入与完整四向视图链**：在另独立空白草稿拖入残差起点，补此前只有点击且未生成的缺口；对Add节点四方向各16world，逐次undo/redo/restored，另相机四方向各40CSSpx与返程，在fit与局部100%看skip长线/双输入端口/tooltip。保存重开并静态生成，若条件允许打开managed；精确记录冗余弯折/交叉/叠线或端点裁切。只认证这个分支，CNN/Transformer全局美观仍开放。

无需重跑已有旧审查。本次没有执行这两个场景，也没有分配席位或启动研究服务。真人五步180秒任务、出版尺寸人工审看与呈现性能继续单独取得证据。
