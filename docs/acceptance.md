# Alpha 验收记录与限制

验收依据是技术计划 §16、§18 和 §21，以及正式目录的 `AGENTS.md`。本记录只适用于新工程。

## 必须分开记录的证据

| 层面 | 证据 | 不能据此推出 |
|---|---|---|
| 源码静态事实 | 手工源码关系 oracle、端口/绑定反例、分析 diagnostics | 运行 shape、训练行为、任意 Python 支持 |
| 视觉文档 | 视觉操作不改变 source/IR digest、历史与保存重开 | 语义修改或批准写回 |
| 渲染与导出 | 当前文档的单一 scene/SVG renderer、真实尺寸审看 | PNG/PDF 已实现、出版质量已通过 |
| 独立发行 | `/tmp` 副本中的模块来源、CLI 分析与 Studio build | 三宿主安装与完整 E2E 认证 |
| 浏览器交互 | 用户任务、截图、空间连续性与性能测量 | DOM 更新等于顺滑、测试数等于支持范围 |

## 第一批手工用户任务

1. 导入一个实际 fixture，并核对源/目标输入、cross-attention memory 与残差两输入。
2. 展开层级；记录操作对象屏幕锚点、无关 pinned 节点位置，以及再次展开后局部排版。
3. 改显示别名、节点与边样式、独立图例和注释；撤销/重做。
4. 保存后重开，核对全部视觉字段和版本。两个页面同时编辑时，旧存储版本的保存应拒绝覆盖。
5. 导出当前 SVG，检查文字、连线、图例、黑白和真实尺寸；确认源文件字节与导入前一致。

自然语言客户端尚未接入时，不把手势编辑通过登记为语言编辑通过。未实现的语义事务保持未支持；不能把“提案”或“静态检查通过”描述为可批准写回。

## 证据登记

本轮运行结果在完成验证后写入本表。命令说明不等于命令已通过。

| 验证项 | 当前状态 | 证据/限制 |
|---|---|---|
| 正式目录独立性 | 通过 | 2026-10-04：`python scripts/check_independence.py --build`；最终 root 报告 `docs/evidence/independence-report.json（原运行目录 /tmp/archcanvas-independent-8755mub4）`。隔离包来源、三 fixture 静态分析、源字节不变、复制本地依赖后的独立 Studio build 均通过 |
| Python 静态语义检查 | 通过 | Transformer self/cross attention 端口角色、残差、多输出、共享实例、opaque、source 不执行与身份稳定等静态关系测试通过；HTTP 结果另行登记 |
| Studio 构建 | 通过 | `cd studio && npm test`：9/9；`npm run build`：TypeScript 与 Vite 构建通过 |
| Python runtime tests | 通过 | 允许 loopback 的本地环境完整 21/21（2.071 s），包含 4 个 HTTP 测试和本地 torch shadowing、alias 遮蔽、MHA need_weights=False 反例。受限 sandbox 会跳过 4 个 socket 测试；完整通过证据来自允许 socket 的运行 |
| 浏览器用户任务 | Alpha 冒烟通过 | 2026-10-04：root 在真实页面选中 Encoder，改名为 Encoder Stack、改色、undo/redo、保存并刷新重开，alias 完整保留。图例文字改为“模型输入”、增加“实验说明”条目、修改说明文字为“源码支持的 Post-LN Transformer”，保存并刷新后完整恢复；展开 Encoder → EncoderLayer 1 → self attention，显示真实 Attention 契约节点。最终总览 696 × 806，主流两列。导出按钮触发后内置浏览器未提供下载事件，因此浏览器下载未认证；同一 renderer 的本地导出已验证，完整性能与出版尺寸审看仍待补齐 |
| 85/180 mm 和黑白审看 | 待运行 | 需导出产物与人工视觉审看 |
| 三宿主端到端 | 未认证 | 指令包校验不替代宿主实测 |
| 源码写回事务 | 未实现 | 后续需具体 diff、独立验证、批准/stale/journal |

## 本地实际工件

- `evidence/studio-alpha.jpg`：真实浏览器截图。
- `evidence/transformer-overview.svg` 与 `.receipt.json`：已改 Encoder 别名/颜色和图例的当前总览，180 mm，revision 2。
- `evidence/transformer-edited.svg` 与 `.receipt.json`：包含层级展开、手动图例和说明文字的保存文档，revision 7。XML 有效，编辑控制不进入出版场景。
- `scripts/export_canvas.mjs`：Node 24+ 直接复用正式 TypeScript Scene/SVG renderer，从保存文档导出，不重新生成模型事实。

浏览器撤销历史当前属于会话，刷新恢复当前视觉结果及版本。构建隔离通过不等于 wheel 已捆绑 Studio 与 fixtures；当前发行方式以完整正式目录为准。
