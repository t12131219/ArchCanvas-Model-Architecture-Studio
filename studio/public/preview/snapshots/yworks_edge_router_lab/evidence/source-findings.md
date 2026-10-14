# yWorks Edge Router 源码证据（本地仓库）

调查对象是本地 GitHub 源码 `Source_Code_Project/yfiles-for-html-demos-master`（`package.json` 版本 31.0.3），而不是把在线页面的当前运行时当作已验证事实。以下引用均带仓库内 JS/GraphML 行号；结论分为源码观察与可复刻建议。源码许可证头也要求有效 yFiles for HTML 许可，原型只复刻交互概念与数据流，不复制 yFiles 实现。

## 关键观察

### 1. 默认边的箭头由样式负责，边路由算法不负责

- `demos/demo-app/demo-styles.js:130-144` 的 `createDemoEdgeStyle` 创建 `PolylineEdgeStyle`：线宽 1.5px、`smoothingLength: 8`，默认 `targetArrow` 为同色 `small triangle`，可用 `showTargetArrow: false` 改成 `none`。
- `resources/edge-router.graphml:459-472` 的第一条边 `e0` 直接保存 `sourceport="p0" targetport="p0"`；样式含 `orthogonalEditing="true"`，目标箭头 `TRIANGLE`（长度/宽度缩放 0.75、`cropLength=1`），源箭头 `NONE`。仓库脚本统计该样本有 16 节点、61 边、122 个端口；每条边各有 TRIANGLE 与 NONE 一个。因此原始 `edge-router` 样本**确实有目标箭头**，不能根据页面截图把它判断成无箭头。
- `LayoutStylesDemo.js:792-817` 的“生成/重置边方向”只改 `style.targetArrow`，并通过 `IArrow.NONE` 表示无方向；`adoptFromOldStyle`（819-827）保留源/目标箭头和 `smoothingLength`。`updateThicknessButtonsState`（337-357）只在 Hierarchical 布局启用方向按钮，切到 Edge Router 时重置为默认方向。

### 2. 连接点（ports）是边端点数据，样本使用命名端口

- GraphML 的边端点使用 `sourceport`/`targetport`（例如 `edge-router.graphml:459-460`）；节点内部有 `p0…` 命名端口（例如 `:81-92`）。端口没有 `d16` 位置覆盖，说明样本依赖 GraphML/yFiles 端口参数的默认模型，而非在此文件中写入固定坐标。
- Edge Router 配置的 `portSidesItem` 默认 `any`（`PolylineEdgeRouterConfig.js:511-520`）。选择 `left-right` 或 `top-bottom` 时，`createConfiguredLayoutData` 写入 `EdgePortCandidates`，允许的候选边分别为左右或上下（`:624-636`）。这会影响路由器选择端口侧，不会改变箭头定义。
- 可复刻交互建议：节点模型至少保存 `{id, rect, ports:[{id, ratio/side}], edges:[{sourcePort,targetPort}]}`；拖拽连线时先选端口，再由路由器生成折线路径，箭头只在渲染层读取 edge 的 target/source direction。

### 3. 新建连接与手动 bend 的输入模式

- `LayoutStylesDemo.js:914-928` 建立 `GraphEditorInputMode`，默认 `GraphSnapContext.enabled=false`、`GridSnapTypes.NONE`；`OrthogonalEdgeEditingContext.enabled=false`（`:920-927`），工具栏复选框在 `:1065-1074` 开关吸附与正交编辑。
- `:930-936` 明确把 `createBendInputMode.priority` 设为比 `moveSelectedItemsInputMode` 低 1：拖选中的边（不是已有 bend）优先创建新 bend，而不是整体移动全部 bends；这也是手动重新布线的关键交互。
- GraphML 加载后，`LayoutStylesDemo.js:704-711` 只读样本并更新样式默认值；样本自身没有 `<Bend>`/`EdgeGeometry` 数据（脚本统计 bend=0），所以首屏路径由后续 `applyLayout` 计算，而非从 GraphML 中恢复手工拐点。
- Edge Router 配置可选“保留 bends 为中间点”：`PolylineEdgeRouterConfig.js:601-607` 把当前 `edge.bends` 转成 `intermediateRoutingPoints`；因此“手动 bend”在启用该选项时成为路由约束，否则路由计算可重写它。

### 4. 重新布线不是节点拖动的隐式副作用（Edge Router showcase）

- Showcase 输入模式只注册 `node-created`、删除、复制、粘贴、标签、`edge-created` 等事件来标记 Modified Graph（`LayoutStylesDemo.js:869-887`），没有注册节点拖动完成后调用 `applyLayout` 的监听器。因此从源码看，拖动节点不会自动触发该 showcase 的全局 Edge Router。
- 重新布线由用户显式点击 Apply 或按 Ctrl/⌘+Enter（`:1076-1078`、`:1127-1137`）；`applyLayout`（`:312-331`）才调用当前配置的 layout。
- 路由配置默认 `scopeItem='route-all-edges'`、`routingPolicy=PATH`（`PolylineEdgeRouterConfig.js:491-505`）。配置数据将 scope 映射为所有边、选中边或选中节点的 incident edges（`:613-622`）；可选 `PATH_AS_NEEDED`/`SEGMENTS_AS_NEEDED` 等路由策略来自 `:192-201`。
- 用于对照的独立 `demos/layout/interactiveedgerouting/InteractiveEdgeRoutingDemo.js` 是另一种明确“自动重布线”实现：`createInputMode` 在节点/边拖动完成、创建、删除等事件上调用 `reRouteEdges`（`:92-109`）；`reRouteEdges` 使用 `PATH_AS_NEEDED` 或 `SEGMENTS_AS_NEEDED`（`:116-149`）。这证明 yFiles 能做拖动后重布线，但不能把该独立 demo 的行为误归因于 showcase 页面。

### 5. Orthogonal / Octilinear / Curved 的切换

- `PolylineEdgeRouterConfig.js:278-289` 暴露三种 `routingStyleItem`：Orthogonal、Octilinear、Curved；创建 layout 时设置到 `router.defaultEdgeDescriptor`（`:537-560`），每条边的 `EdgeRouterEdgeDescriptor` 也带同一项（`:582-599`）。
- 曲线连接端还可选 source/target 的 `CurveConnectionStyle`（Straight/Organic，`:311-333`）。`LayoutSamples.js:605-609` 的 `edge-router-with-curves` 预设只把 routing style 设为 `CURVED`，描述明确为 smooth curves。配置说明（`PolylineEdgeRouterConfig.js:731`）指出 Edge Router 不移动节点，只计算边路径；Orthogonal 为水平/垂直段，Octilinear 加斜段，Curved 用平滑曲线替代。
- 这与 `PolylineEdgeStyle.smoothingLength=8` 不同：前者是路由几何风格，后者是绘制折线拐角的样式平滑长度。复刻时应将 `routingStyle` 与 `smoothingLength` 分成两个开关。

## 给 prototype 的最小可复刻交互

1. 初始化 3–6 个矩形节点，每个节点提供中心/四侧端口；默认每条边画 1.5px 折线、target 三角箭头、source 无箭头。
2. 从端口拖到端口创建连接；高亮候选端口，并在拖动预览中按当前 routing style（正交/八向/曲线）计算路径。
3. 选中边后拖边身插入 bend，拖 bend 移动路径；正交开关开启时约束为水平/垂直，关闭时允许自由折线。
4. Apply 按钮显式调用路由器；提供 All / Selected / Incident 三种 scope，以及 Preserve bends（中间路由点）选项。
5. 用一个单独的 Auto reroute 开关实现 `drag-finished → route(scope)`，并在 UI 文案中标明它是额外交互能力，不要暗示 showcase 默认自动重布线。
6. 用 direction toggle 切换 target arrow `triangle/none`；换样式时保留 edge 的 sourceArrow、targetArrow、stroke 与 smoothingLength。

## 证据边界与未验证项

- 本文件是**本地源码/GraphML 静态证据**。我没有把在线 yWorks 页面当前打包产物、浏览器 DOM 或鼠标操作结果冒充源码证据；在线版本可能与仓库 31.0.3 不同，箭头颜色、默认参数和 UI 排版应以 REA/浏览器运行时观测复核。
- 源码能证明事件注册、layout 配置与样本数据，不能单独证明某个浏览器手势在特定设备上的命中测试、动画帧或最终像素。原型应把这些作为可观察结果记录（截图/录屏或 DOM/事件日志）。
- `edge-router.graphml` 的 `p0…` 端口没有显式位置数据；端口最终几何位置由 GraphML 解析器与 yFiles 端口模型决定，静态文件不足以还原每个端口的屏幕坐标。

