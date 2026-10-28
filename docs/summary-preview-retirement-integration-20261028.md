# Summary 接管后的旧宿主预览职责清理

日期：2026-10-28。本阶段按“Summary 替换重叠内容，Studio 保留面板”的裁决执行 D0。整体迁移仍在进行；此前局部组装复核阶段已单独冻结，不能把其测试计数归于本阶段字节。

## 实际替换范围

| 旧主程序职责 | 当前衔接 | 保留的 Studio 功能 |
| --- | --- | --- |
| `App.tsx` 的 `pointerDown/Move/Up/Cancelled`、DOM node/edge/port/expand 命中 | 删除未挂载的宿主处理器；Summary 原生 pointer/Worker 继续负责 | React 工具栏、左树、对象面板与来源身份映射 |
| `Gesture`、`MovePreview`、`portLayoutPreview`、框选矩形、端口草稿及 rAF 临时状态 | 删除；读取 child 的 dragging、selectedNodes、busy 和 snapshot | 按钮禁用、选区摘要、正式 rebind 提案与审查 |
| `committedScene/scene`、旧拖动 Scene、`presentEditorScene`、旧节点/说明 fallback | 删除预览分支；对象位置、颜色、图例、说明冲突读取 Summary snapshot | 对象/图例/页面表单、视觉覆盖与 CAS |
| “预览位置修复”与应用/取消旧位置提案 | 改为“优化当前布线”，发送 `apply-layout`；不会再预览不可见的 formal geometry | 原 Studio inspector 与 Summary 交互折叠区；路由处理范围仍由 Summary 布线设置决定 |
| “优化自动连接点”调用 `buildScene` 找端口 | 改为当前可见 Summary identity 的 `portLayout(layout:null)`，由 child 物理端口与路由事务处理 | 原连接点折叠区；未映射的原生节点也能从“Summary 交互 → 恢复所选自动连接点”使用 |
| 宿主 preview camera state、sessionStorage、延迟初始化、ResizeObserver、滚轮和平移计算 | 删除；fit、focus 和导航只调用 Summary；缩放由原生画布处理 | 面板折叠/展开、相同 iframe、原生相机与编辑 JSON 保存恢复 |
| 宿主 gesture cancel 只清理已失效的旧状态 | 增加同源 `cancel-gesture`，可在原生手势 busy 时回滚；后续释放不能提交已取消动作 | Escape、切工具、模式/面板动作和现有错误反馈 |

“优化当前布线”保留节点位置，按 Summary 当前 scope、端口与障碍约束处理边；不是旧的移动节点位置修复算法。范围控件的帮助文案已据此修正；对齐和文字移动仍沿用当前/所有前沿范围。失败与 pending 保持原生规则，不能将显式未完成路线描述为全部合法。

端口恢复采用精确 child identity。正式节点先经现有来源映射；已经选中的原生节点使用 snapshot identity，不能用标签、索引或几何猜测。成功提交一项 Summary 历史，undo/redo 与保存继续共用同一 authority；异步端口回复的错误也受加载序列保护。

## 原生取消与相机

新增 `cancelActiveGesture` 复用原版 gesture baseline：恢复已变更 graph、history、future 与 dirty，恢复框选前选区，清除 rAF 和预览层，并先释放 owner 再 release capture。平移取消额外恢复手势开始时的原生相机；此前 Escape/pointercancel 没有恢复 pan camera，这一细节随接管补齐。Escape、pointercancel 和 bridge 使用同一函数。

bridge 仅允许取消指令越过 busy mutation 拒绝；其他修改在手势进行时仍被拒绝。宿主发送取消时走已握手的即时消息，避免被后续 visual 请求超越；仅在 snapshot 标记 dragging 时发送。没有宣称该指令可以中止已经开始的独立 Worker 布线任务。

父窗口失焦不再清理另一套手势。点击 iframe 会让父窗口失焦，不能把这一正常焦点转移当作需要取消原生拖动。原生画布本身继续接收真实 pointercancel 与 Escape。

## 正式边界与尚存依赖

`App` 中 `buildScene` 现在只用于用户明确进入正式源码编辑时建立 source draft；不再用于页面加载、预览 render、相机、聚焦、端口或布线。正式源码会话仍保留自身编辑器相机/工具元数据，用于恢复 `AuthoringStudio`，不会驱动或持久化 Summary 预览相机。正式 AuthoringStudio 的画布、共享 camera/helper 测试、源码事务、ReviewDialog 和 publication 仍保留。

未删除整个 `core`：`scene.ts`、router、端口、源码区域 projection、formal export 等仍有正式工作流依赖，D1 继续按调用方拆分。旧缓存不再被生产预览读写，但不清理用户已有浏览器数据；离线存档仍可显式导入。

## 自省与测试迁移

修改前的 App、PreviewStudio、child app/bridge，以及旧相机/移动回归 harness 放在 `docs/evidence/summary-preview-retirement-20261028/before/`。该副本仅为审计，不在生产或 npm 测试入口执行。

旧测试中 25 项只覆盖已删除的 App 相机/指针/位置提案实现，随职责删除退出活动测试。共享 camera/helper、formal editor、源码会话、生成画布及当前文字指令/排列测试继续执行；没有为维持历史计数保留生产死代码。新增原生取消、pan/框选回滚、端口精确映射/过期错误、Summary 布线委托与 busy bridge 门禁专项，并用真实 Chromium 检查当前唯一画布。

初次专项发现两处旧测试仍抽取已经删除的 `needsFormalScene/committedScene`，现改为检查只有正式源码编辑会调用 Scene，并继续对 480 节点的真实 snapshot 做说明冲突和位置检查。另一次新取消测试的抽取边界错误已修正。浏览器脚本也修正了不存在的切面参数、等待 dragging 时又要求非 busy 的互斥条件，以及 iframe src 相对/绝对地址比较；这些属于测试准备和 oracle 问题，生产逻辑未为此放宽。

## 当前验收

最终计数、来源字节、独立副本与 HTTP 资产核对以本阶段 `docs/evidence/summary-preview-retirement-20261028/validation.json` 为准。前一阶段 892 项全量和 37 项浏览器是旧字节证据；不自动视为本阶段通过结果。

剩余：完整新 generic catalog、CPU runtime/merged 的正式隔离/receipt、测量反馈与 adaptive-frontier、千级规模的预算/传输/取消/压力，以及 D1 依赖继续拆分。不能把 D0 清理描述为整体迁移完成。

## 本阶段最终结果

完整前端 872 项：871 通过、0 失败、1 项沙箱 Chromium 跳过；全部生产修改均先于这次完整运行。主专项与独立副本分别 124 项通过。真实 Chromium：D0 取消/面板/相机 5、组装编辑 12、旧递归与正式边界 23、新原生语义 16，共 56 项通过，无浏览器错误；保存后刷新也有实际断言。

当前构建、独立构建与来源、9 文件字节对照、63 个 HTTP 资源和 59 个集成资产一致；32 个原生 JS 仍与 Summary 逐字节相同。本阶段没有改动后端运行时代码，不把前阶段 33 项后端结果当作新运行。独立副本复用已安装 npm 依赖和系统 Python，源码解析始终从副本 `src` 导入；没有依赖原型运行目录。

旧测试实际退出 25 项（相机会话 3、视口 harness 18、移动/位置修复 4），新增 5 项原生用例，因此从上一阶段 892 项变为 872 项。此前草稿中的 26 项为计数错误，已按文件实数修正。

[验证记录](evidence/summary-preview-retirement-20261028/validation.json) · [实际界面](evidence/summary-preview-retirement-20261028/studio-preview-retirement.png)。
