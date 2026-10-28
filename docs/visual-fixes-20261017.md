# 视图箭头、展开和导出修复复核（2026-10-17）

本轮修复原审计列出的两项 P1 和两项布线 P2，并改善深层图的阅读导航。改动落在公共投影、端口、路由、控制线、相机和出版适配阶段，不按案例名称、固定 ID 或固定坐标打补丁。**这不等于《通用优化测试规范》全量视觉验收通过**：历史案例仍有 16 个结构失败，未逐一目视复核全部 229 个案例。

原始基线：[首轮审计](visual-audit-20261017.md)、[40 张原始截图](evidence/visual-audit-20261017/gallery.html)。原审计证据保持不变；本轮证据保存在 [独立目录](evidence/visual-fixes-20261017/)。

## 环境和范围

- 正式开发目录：`ArchCanvas_Model_Architecture_Studio`，基于 HEAD `e293d8eb91f56d7800c7135a66049022a2de0d45` 的已有工作区继续修改；未重置其他未提交工作。
- 使用本地源码树 archcanvas Skill 的正式 launcher，隔离服务 `127.0.0.1:8898`，状态目录 `/tmp/archcanvas-visual-fixes-20261017`。未使用失败的 Temp runtime。
- 真实 UI 视口为 1280 × 720。更小视口只有相机函数的几何检查，未宣称真实响应式验收。
- `act` 原目录只做静态读取；没有运行模型、修改原模型或新增专用适配器。生成的陌生测试源码保存在证据目录和隔离工作区。
- SVG 通过 Studio 右上方统一导出入口实际生成；文件和收据从服务的实际导出目录归档。浏览器下载辅助工具超时，未将它记作“已成功下载”；文件生成、服务产物和独立渲染已确认。

## 缺陷闭环

### P1：陌生条件分支展开被通道、边界检查拒绝

状态：本次复现图及结构变换回归已修复。

结构：双 MLP 并列，条件内部再调用投影或 Identity，返回值存在多个语法可能依赖；包含折叠、局部和全部展开状态。

通用根因有两层：不同语法依赖使用同一逻辑消费字段时，物理端口被当成一个槽；折叠模板成为展开容器时，直接落在容器边界的连接没有对应接口记录。全部展开通过并不能证明混合展开正确，本轮补测因此发现并修复了第二层问题。

修复：独立 wire 分配独立展示端口；可见层级改变时，为新展开的端点容器登记实际物理接口。canonical producer/consumer、wire、语义 IR 和源码内容均保持原样，几何和语义校验继续严格执行。

复现和结果：打开 `inputs/transformed_mlp.py` 的 Wrapper，展开待解析区域，再逐层展开或“展开全部”，随后折叠/恢复。初始 8 节点/7 边、全部 46 节点/35 边均通过；不再报独立 lane 重叠和未登记边界。

回归：`previewVisualRegression.test.ts` 同时覆盖原图、改名并重排独立调用、增加第三条嵌套分支的 Triple，检查混合展开、独立端口、全部展开和折叠恢复，以及源包不变。Triple 是拓扑变化，不只是换标签；真实界面另保存 [第三分支细节](evidence/visual-fixes-20261017/11-third-branch-detail.png)，51 个源码图元可全部展开。

证据：[局部展开](evidence/visual-fixes-20261017/01-mixed-frontier.png)、[全部展开](evidence/visual-fixes-20261017/02-full-frontier.png)、[分支细节](evidence/visual-fixes-20261017/03-branch-detail.png)。

### P1：Transformer / VAE SVG 文件生成失败

状态：真实 UI 生成和实际文件复核已通过。

根因：预览专用身份 `preview-only:caseId` 被作为 SHA256 摘要发送；修正身份后，实际生成又暴露出原型场景的嵌套 `<defs>` 不符合出版词汇。

修复：预览身份放在 caseId，真实摘要仍须满足严格 SHA256 校验；将嵌套 definitions 包装展开，同时保留 marker 的继承绘制属性。未放宽后端 XML、安全或摘要校验。

验证：在模型菜单中的折叠案例库打开标准 Transformer（`01093cc06a87b35a`）和 VAE（`0342f4170c15ba8e`），点击右上导出 → SVG → 生成文件。均出现文件链接和收据，实际文件通过出版校验，并独立渲染检查箭头、文字、Memory 与 Gaussian sample。

产物：[Transformer SVG](evidence/visual-fixes-20261017/transformer-figure.svg)、[收据](evidence/visual-fixes-20261017/transformer-figure.svg.receipt.json)、[VAE SVG](evidence/visual-fixes-20261017/vae-figure.svg)、[收据](evidence/visual-fixes-20261017/vae-figure.svg.receipt.json)。界面证据：[Transformer](evidence/visual-fixes-20261017/04-transformer-export.png)、[VAE](evidence/visual-fixes-20261017/05-vae-export.png)。

限制：文件成功生成不表示 180 mm 整图中所有小字达到论文阅读字号；VAE 的尺寸预检仍如实提示最小字号不足，应采用建议页宽或详情范围。收据的 `sourceBindingVerified:false` 也保留，未伪造源码认证。

### P2：ACT 条件虚线出现 2 单位折返

状态：原始 ACTPolicy 场景实测已修复。

根因：条件语法控制线的候选路由只验合法性，允许几乎贴合的反向平行段。

修复：控制线候选拒绝相隔不足 10 单位的反向折返，按路径代价选择合法候选，失败时尝试有限的端口/通道备选；保持与张量依赖的视觉和语义区分。

原 false 路径：`(386,1154) → (386,1166) → (324,1166) → (324,1168) → (735.5,1168) → (735.5,1192)`，长度 511.5，4 弯折，最小反向间距 2。

修复后：`(386,1154) → (386,1166) → (735.5,1166) → (735.5,1192)`，长度 387.5，2 弯折，无反向折返。true / false 两条控制线均可见。

回归：`previewSourceControls.test.ts` 注入窄折返返回值并测试平移后的相同结构，确保 fallback 也满足规则。证据：[ACT 条件细节](evidence/visual-fixes-20261017/06-act-branch.png)、[实际 DOM 路径](evidence/visual-fixes-20261017/act-controls.json)。

### P2：展开后仍需点击“优化连线”才消除多余弯折

状态：复现链及方向/约束回归已修复，未承诺任意复杂路径全局最优。

根因：默认 frontier 的合法路径清理范围不足，两个对齐、可移动端口的算子会保留侧面 U 形绕行。

修复：在默认路由的有界清理阶段比较合法直连候选；只改变物理端口和路径，不移动节点。共享干线、容器接口、固定端口、手动折点和其他边的质量约束继续受保护。缓存键包含作用范围及端口侧；展示版本更新到 19，以免复用旧布线路径缓存。

种子 `20261017` 的 SeededFanout，嵌套残差单元 Linear → GELU：原长度 152、2 弯折；现在默认展开即长度 54、0 弯折，随后 Apply 也为 54、0。真实 UI 未先点击 Apply。

回归：`previewRecursiveLaneRepair.test.ts` 覆盖横向/纵向、固定接口和手动折点保护；现有跨层、残差、循环、共享值、移动、撤销和恢复测试一起运行。

证据：[默认直连](evidence/visual-fixes-20261017/09-default-straight-route.png)、[结构及指标](evidence/visual-fixes-20261017/repro-results.json)。

### P2：深层图总览缩放过小，难以阅读

状态：阅读导航已改善；未把全图缩小视为“每个文字均可读”。

深图受有限屏幕高度限制，完整总览仍需缩小。修复提供可折叠缩略导航、点击定位、方向键移动、Home 返回总览和“阅读细节”；从左层级树选择模块时以可读尺度聚焦，超大容器聚焦标题及首段内容，避免再次把整棵深树缩小。

验证：U-Net 全部展开后总览 7%，选择深层 `Conv 3x3: 256 -> 512` 后 100%；SeededFanout 中实测键盘移动、Home、阅读细节和折叠导航。移动相机前后的节点 transform、边路径均一致，没有产生新的布局/源码修改。

证据：[U-Net 总览](evidence/visual-fixes-20261017/07-unet-overview.png)、[100% 细节](evidence/visual-fixes-20261017/08-unet-readable-focus.png)、[导航折叠](evidence/visual-fixes-20261017/10-collapsed-navigation.png)、[导航前后几何](evidence/visual-fixes-20261017/navigation-check.json)。

## 验证与复现

1. 构建：`cd studio && npm run build`。
2. 前端回归：`cd studio && npm test`，最终 **837 项通过、0 失败、1 项明确跳过**（总计 838，327.4 秒）；新增/更新的重点测试为 `previewVisualRegression`、`previewRecursiveLaneRepair`、`previewSourceControls`、`previewViewNavigation`、`previewHierarchy`、`previewPublication`。
3. 后端：项目 `.venv` 中通过 unittest 分别运行 `test_preview_backend.py`（13 项）、`test_publication_export.py`（12 项），共 25 项通过；后端 HTTP 检查使用允许 loopback 的运行环境。
4. 批量现有案例：`node docs/evidence/visual-fixes-20261017/reproduce.mjs`，检查每个案例初始/全部展开。结构检查当前 114/114、历史 99/115；失败集合与原审计完全一致，详见 [差异](evidence/visual-fixes-20261017/catalog-delta.json)。进程正常退出只代表结果已写出，不代表所有案例成功。
5. 浏览器实测：Wrapper 混合/全展开与条件细节、Triple 额外分支、ACT 条件控制线、种子分叉默认直连、U-Net 深层导航、Transformer / VAE 实际 SVG 生成。截图通过真实 UI 获取；实际导出文件另外独立渲染。

前端 DOM 出版单测在当前命令沙箱无法启动 Chromium，会明确 skip；真实浏览器已通过上述 Studio 导出流程验证，没有把 skip 计成通过。构建存在大 bundle 警告；本轮未做打包拆分，也未宣称性能全量验收。

## 仍未解决与验收边界

历史失败共 16 个：bilinear attention、capsule routing、compact bilinear pooling、ggnn step、graph attention、graphsage mean、graphwavelet sparse、weighted bilinear pooling、旧 autoformer、旧 timemixer，4 个旧 Transformer 快照及 2 个旧残差 SVG。分别仍有独立 lane/边界冲突、junction 越出 owner 或历史 containment 变更。完整 ID 与错误在 `repro-results.json`，没有隐藏或自动改成成功。

当前案例结构通过不证明全部视觉通过；未复核所有窗口尺寸、任意新增/重接图、所有历史混合展开或所有出版尺寸。紧凑度、交叉数和计算预算存在取舍，固定接口和手动布局优先保留。此次没有把不支持的源码动态分支解释成已验证张量连接，也没有改变模型实现。
