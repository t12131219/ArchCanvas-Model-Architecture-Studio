# 编辑模式排版与视图连续性复核 · 2026-10-29

本轮处理截图中的按钮挤连、编辑侧栏功能层级、视图进入编辑时展开状态丢失，以及首次进入编辑的长时间等待。基于正式项目实施，继续保持 Summary 原生语义图权威和独立源码事务边界。

## 用户视角与界面调整

- 原先“添加输入／添加输出”等操作使用了模式切换控件的连体背景，紧贴搜索框，容易被误认为互斥选项。现在使用各自带边框的按钮和 8 px 间距，并将接口操作从模块库中移到“模型接口”区。
- 原侧栏同时展示名称、层级、构件库、选中节点、连接、源码解析和重建功能。改为“添加／选中／高级”三组：常用添加入口首先出现；复制、删除、组合和精确槽位连接归入“选中”；名称、源码重解析、参考重建和局部复核归入“高级”。
- 编辑层级只列当前层、上级及直接子模块，使用模块名称；不再在下拉框中一次铺开数百个长源码身份。可逐级进入，或返回模型顶层。
- 顶栏采用“模型／编辑／视图／排列”：模型负责打开与创建；编辑放置构件入口、撤销重做及正式源码工作流；视图归纳展开、定位、源码证据和运行观察；排列保留布线、对齐和分布。
- 原始源码构件列表、精确连接表单在真正展开后才挂载；高级表单只在进入对应分组时挂载。这样避免初次进入编辑就创建 3371 个隐藏源码按钮与数千条隐藏依赖选项。

浏览器实际检查了三组切换、构件搜索、顶栏编辑菜单及 Esc 关闭。当前 970 × 835 视口中，编辑侧栏没有横向溢出；添加组实际只有 23 个按钮、2 个层级选项，模块列表为 16 个预设；关闭的精确槽位连接表单没有挂载其依赖选项。

## 状态丢失和卡顿的根因

原流程从 IR 创建新的 authoring 文档时，`fromIR` 只复制源码事实，`open` 默认为空。文档工作区随后强制切换到源码原子展示，只在结束后重新应用部分 `moduleCuts`。因此普通展开、角色路径展开、部分模块内的打开状态和相机没有完整继承。

同时，该过程先构建并布线默认原子图，再应用保留的展开深度，导致在需要的中间语义图出现之前，先处理一次规模远大于当前画面的图。此外，宿主预读完整快照、桥接多次发送最终完整状态、隐藏编辑表单大量挂载，也增加了等待。

## 实现与语义边界

1. 首次创建编辑副本时，将完整 `generic.state` 保存为副本中的 `canvasView`；文档摘要包含这份视图状态，便携恢复时可还原。
2. 独立生成组装文档的 IR，并进行完整内容比较，确认初始化没有改变事实。只有内部准备的、语义及视图未改变的副本可以复制当前原生图的几何。
3. 该候选图仍通过 Worker 的完整图校验和 `accepts` 检查；模式切换不再重建布局或重新布线。源适配绑定移除，副本明确标记 `sourceVerified:false`、`modelExecuted:false`。
4. 外部导入 JSON 仍执行文档恢复、摘要和原生图生成／校验；外部消息不能使用内部准备参数跳过这些流程。
5. 继承相机、可见选区和展示覆盖。真正修改组装结构后删除 `canvasView`，继续使用原有清理逻辑去除过期契约及合成展开记录。
6. 宿主省去选择编辑器前的完整源码快照往返；authoring 桥接只发送一次最终响应，处理中保留轻量交互状态。

主要文件：

- [副本初始化与视图保存](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/public/preview/yworks_edge_router_lab/studio-authoring.js)
- [文档恢复](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/public/preview/yworks_edge_router_lab/studio-documents.js)
- [内部候选图校验与安装](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/public/preview/yworks_edge_router_lab/app.js)
- [模式切换及菜单](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/App.tsx)
- [编辑侧栏](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/SummaryAuthoringPanel.tsx)

## 实测与测试边界

使用原始 Transformer（3371 个原始节点、3663 条依赖），从已展开的 82 节点视图首次建立全新编辑副本。DOM 比较确认：82 个可见节点的身份和位置、所有展开控制的位置及名称、相机 viewBox 均完全一致。刷新后再次进入该编辑副本也保持展开状态。

最终浏览器记录的原生引擎处理时间为 **3422.9 ms**，布局构建时间为 **0 ms**。计时包含副本准备、Worker 校验及安装；不包含宿主收到完整状态后的 React 处理。仍需几秒，不能表述为瞬时切换。没有可信的修复前同机基准，因此不报告加速倍数。

- 构建通过；预览边界审计通过；`git diff --check` 通过；集成 manifest 的 bytes/SHA256 一致。
- 相关测试 32 项通过；混合切面的编辑状态保留测试针对新要求更新断言并单独复跑通过，合计 **33 项、0 失败、0 跳过**。
- 测试覆盖：完整状态及几何保留、便携恢复、原始图不被修改、源权限分离、结构修改失效处理、外部导入仍走生成流程、单次桥接响应、延迟表单挂载、源码模块及重建契约。
- 同时运行过混合切面全量检查，其余场景通过；本记录的 33 项为最终相关检查，不表示全仓所有测试通过。
- 浏览器最终读取的错误日志为空。未发布或提交代码；页面保留在编辑模式供检查。

证据：

- [最终编辑侧栏](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/edit-mode-20261029/editing-after.jpg)
- [选中组](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/edit-mode-20261029/selection-after.jpg)
- [高级组](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/edit-mode-20261029/advanced-after.jpg)
- [编辑菜单](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/edit-mode-20261029/edit-menu-after.jpg)
- [展开与计时记录](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/edit-mode-20261029/browser-checks.json)
- [相关测试日志](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/edit-mode-20261029/tests.log)
