# D1：旧预览移动与位置修复退出生产源码

日期：2026-10-28。按 Summary 为主的移植裁决，继续在 D0 已切换实际画布之后，删除生产树中的重复预览实现。Studio 的菜单、层级树、折叠面板和正式源码/CAS/事务能力保留。

## 已退出的内容

| 原位置 | 当前处理 | 实际替代 |
| --- | --- | --- |
| `studio/src/core/movePreview.ts`，72 行 / 3,932 字节 | 从生产源码移除；必要的正式 core 比较辅助迁至 `studio/tests/retired-preview/movePreview.ts` | Summary 原生 gesture baseline、实时/兼容拖动、Worker 校验、撤销与取消恢复 |
| `studio/src/core/layoutRecovery.ts`，226 行 / 15,388 字节 | 从生产源码移除；旧算法反例仅由测试专用副本继续覆盖 | Studio 布局面板 → `repairSummaryLayout` → child `apply-layout`；物理端口恢复也由 child 处理 |
| `scripts/benchmark_move_preview.mjs`，10,144 字节 | 移除旧 benchmark 入口；完整原脚本冻结在本阶段 before 目录 | 当前原生浏览器手势/布线验证；不把旧 formal Scene CPU 数据转换为 Summary 性能结论 |

当前源码无正式调用方、无 `core/index.ts` 导出。删除前这两个模块只形成 `layoutRecovery → movePreview` 的内部关系，另有九份 live 测试直接使用；历史 evidence 中自带的冻结版本没有修改。

删除前原文件、来源字节和旧 benchmark 保存在 [删除前记录](evidence/summary-d1-retirement-20261028/removed-inputs.json)。测试副本仅调整 import 路径并加上历史用途说明；去除 import/comment 后的完整 AST 与删除前相等，见 [实现主体对照](evidence/summary-d1-retirement-20261028/helper-equivalence.json)。九份测试更新 import/type import/AST 读取路径，并明确这些用例不证明当前 Summary 的拖动性能。

## 正式功能的保留边界

`scene.ts`、`orthogonalRouter.ts`、`portRouting.ts`、`sourceRelationRoutes.ts`、`memoryContinuity.ts`、`exportScene.ts`、`svg.ts` 和 `document.ts` 仍承担正式用途，不能因文件名与原预览重叠而整组删除：

- `AuthoringStudio` 的正式模块端口、草稿连接与源码关系仍使用 formal geometry；默认 Summary 组装编辑继续走原生模型，不借这些旧 helper 拖动画布。
- `sourceEditingClient → sourceEditingWorker → sourceEditingProjection` 仍构造正式源码编辑视图；Worker 通过 `new Worker(new URL(...))` 引入，不能只查 import 字符串而漏掉它。
- `ExportDialog` 使用正式 `buildExportScene/renderSvg` 与 publication preflight；`ReviewDialog` 使用 `buildScene/renderSvg` 展示具体事务。`generatedCanvas`、`generatedWorkspace`、`sourcePresentation` 也仍需正式投影。
- `App.tsx` 唯一的 `buildScene(frozen)` 调用属于 `api.importSourceDraft`；原生预览 render、拖动、端口、布局和相机继续由 Summary 提供。

因此本阶段完成的是 D1 两个无生产用途模块的退出，保留的正式投影/路由/出版链路有实际调用依据。当前预览没有回退到测试副本或旧 benchmark。

## 依赖门禁

新增 `npm run audit:preview`。它使用 TypeScript AST 读取所有 source import/export、inline type import、literal dynamic import 和 literal URL/Worker 入口，保守地包含 type 依赖。它同时拒绝未解析的动态 import、旧生产路径、生产树中的旧 helper 声明及生产代码指向 retired test support 的路径；不会把未知动态依赖当作已验证。

本阶段删除前后使用同一审计器，结果为 97 → 95 个 source 模块，实际入口及 Worker 可达模块均为 88 个。正式源码 Worker、编辑器、Scene、router、memory、publication 仍可达。删除前是故意保留旧路径的负例，不标成通过；删除后才通过，见 [删除前](evidence/summary-d1-retirement-20261028/before-authority-audit.json) 与 [当前](evidence/summary-d1-retirement-20261028/authority-audit.json)。另有合成反例验证 export cycle、Worker URL、改名文件藏旧声明和无法静态解析的 import。

生产构建与上一阶段验证过的 112 项入口/资源逐字节一致，证明这次删除没有改变已打包的运行时；该结论仅覆盖列出的资源。当前 HTTP 字节、实际手势及正式源码编辑往返仍单独复核，不用依赖图替代功能验证。

## 验证范围和状态

目标测试覆盖移动/位置修复的历史辅助、当前正式 Scene 端口与路由、固定/隐藏节点、隐式根约束和相机事务；完整前端继续覆盖 source authoring、正式导出和当前 Summary。独立副本实际删除同样三条路径，再构建并运行正式编辑、export、inspector 与退休边界回归。

Chromium 复核 Summary 拖动/取消、中键平移、折叠端口面板、布局修复、F0/F1、latent source 导航、物理端口、保存/JSON/SVG、正式源码编辑后返回画布等。没有新 CPU 执行和后端修改。

历史 [M4 拖动文档](m4-drag-preview.md) 已加退出说明，旧数据仍作为历史保存，不再提供可误认为当前实现的 benchmark 入口。当前文件和删除项清单见 [本阶段 manifest](summary-d1-retirement-manifest-20261028.json)，最终结果见 [验证目录](evidence/summary-d1-retirement-20261028/)。

大图完整开放、新 CPU 正式隔离执行/receipt，以及最终按两份主文档的逐项完成审计仍待继续；本阶段不能作为整体迁移完成的结论。


D1 本阶段最终验证：完整前端 967 项（966 通过、0 失败、1 沙箱 Chromium 跳过）；核心专项 70 项、最终审计专项 3 项、独立副本最终专项 118 项通过。真实 Chromium 手势 5、原生 16，共 21 项通过。主/独立构建与依赖审计通过，112 HTTP 资源及上一阶段运行资源逐字节一致；32 原版模块、45 目录资产原样。独立副本核对 172 项输入、69 个 Python 文件、8 个模块来源及 5 个静态 fixture。首次独立测试因缺少约定解释器启动失败，一次修复目录有误；两份失败日志保留，正确根目录最小环境下最终通过。详见[本阶段验证](evidence/summary-d1-retirement-20261028/validation.json)。大图、新 CPU 与最终逐项审计仍未完成。
