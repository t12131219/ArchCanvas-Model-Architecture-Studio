# Summary 源码模块、参数重解析与精确重建接入

日期：2026-10-28。本阶段继续由 Summary 替换重叠的模型组装功能，保留 Studio 面板与正式源码事务。整体迁移仍在进行。

## 功能与面板衔接

右侧 Summary 模型编辑增加两个折叠区；中央仍是原来的 Summary iframe，左右面板、菜单、对象样式、图例和页面继续使用 Studio 外观。

| Studio 入口 | Summary 行为 | 提交与失败边界 |
| --- | --- | --- |
| 源码模块与参数重解析 → 模块入口、构造参数、Python 源码 | 调用原版 `compile_module`；保存源码全文、构造参数、真实节点、依赖、端口和源码证据 | API 仅返回分析结果；成功加入才产生一次预览历史提交 |
| 解析并加入源码模块 | 原版 `AuthoringModel.add` 插入当前编辑层级，分配新身份 | 保留原源码模块文档，不能当作原模型的 Python 修改 |
| 选中源码模块 | 对象面板投影模块保存的源码与构造参数 | 表单是草稿，输入不立即改图 |
| 重新解析并替换选中构件 | 重新运行静态提取，原版 `replaceModule` 按同名边界接口重映射精确槽位 | 删除已连接输入时原子拒绝；源码输入、原图、连接和历史不变 |
| 对象显示名、颜色等 | 旧模块根的 Studio visual overlay 重映射到新模块根 | 原有图例、页面和其余节点样式保留；不靠位置猜测绑定 |
| 原始构件精确重建 → 开始参考重建 | 原版 `recipe` 分解 baseline；可按模块或源码原子重建 | 清空搭建本身可撤销；保留当前组合库 |
| 恢复构件 | 原版 `add(..., {keepIdentity:true})` 恢复原身份与父级 | 支持逆序加入，不能只在方便的顺序下成功 |
| 恢复现有端点的精确连接 | 原版 `restoreConnection` 恢复跨构件原始依赖及 operand slots | 用户编辑连接已占用输入时拒绝整个本次操作 |
| 重建状态 | 独立比较完整节点与边字段，核对精确重建 | 不只比较数量或相信原始 digest；完整恢复后原版 `sourceIR` 返回原始 IR |
| 撤销、重做、保存、重开 | 继续同一 Summary 图历史与可移植编辑 JSON | 重开当前稿不会隐式重新解析或执行保存的源码；整页重载不恢复完整 undo 栈 |

参数声明和源码重新解析是两个明确动作。仅在“参数声明”改 constructor/arguments 不会改 Python，也不会声称模块已重编译。需要源码事实更新时使用新折叠区的解析/替换操作；正式 Python 写回仍通过明确的源码工作副本和事务审查。

## 后端、来源与资源边界

正式服务新增 `POST /api/preview/authoring/module`，只接受 `{source, entry, constructor?}`，沿用同源、Host/Origin 与 `X-ArchCanvas-Session`。不接受服务器目录、解释器、文件路径或跨端口 fallback。

`archcanvas_preview.authoring_bridge` 使用正式 checkout 的 Python `-I -S -B` 子进程，显式加载正式 `src` 中已迁入的原版 Summary compiler。提交源码只进入 AST，不 import、实例化或执行。结果为原版 `semantic-module/1`，源码位置使用源码摘要支持的稳定 `authoring://module/.../custom_module.py`。

| 资源 | 当前限制 |
| --- | --- |
| 源码 | 非空 UTF-8，120,000 bytes |
| 入口 | 单一 Python identifier，最多 240 字符 |
| 构造参数 | 有限 JSON 对象，最多 16,000 bytes |
| 单次解析 | wall 15 秒，CPU 8 秒，地址空间 512 MiB |
| 子进程输出 | 16,000,000 bytes，临时文件与文件大小资源限制 |
| 文件描述符 | 48 |
| 并发 | 每服务进程一个编译槽；占用时明确拒绝，异常/超时释放 |
| 返回图 | 480 节点 / 3600 依赖；沿用现有原生文档预算 |

当前资源限制依赖 Python `resource`，不可用的平台返回解析失败，没有宣称已经实现跨平台等价沙箱。这里不执行用户程序；这些 AST 进程预算也不等于正式 CPU runtime 的执行隔离认证。

capabilities 的 `preview.nativeAuthoring` 公布实际 endpoint、schema、静态分析方式与 `modelExecuted:false`、`sourceTransactionBinding:false`。

## 并发、自省与持久化

源码解析提交时捕获当前案例、加载序列、workspace UUID、声明摘要和替换目标。App 在 API 返回时先检查是否切换模型；controller 在应用前再次检查 workspace 和文档摘要。解析期间用户切换模型或编辑稿件后，旧回复不能写入新稿。

所有替换、精确连线和 recipe 恢复先在文档副本中执行，经验证和 Worker 构图后才提交。已连接输入被删除、槽位非法或参考输入被用户连接占用时保留原稿。失败表单保留用户源码，便于直接修正。

保存仍由 Summary workspace 声明与当前图组成。恢复时重新计算文档摘要并核对原版 `sourceIR`，不允许独立更换 IR。原始文档保持不可变，组装副本不获得 source adapter、managed-source 或事务许可。即使 recipe 完整重建了原 IR，当前稿仍是文档来源；不能据此发起原始 Python 写回。

## 验证范围

证据单独写入 `docs/evidence/summary-source-authoring-20261028/`；本阶段清单为 `docs/summary-source-authoring-manifest-20261028.json`。旧 authoring 阶段证据保持原样，不能用旧测试计数认证当前新增代码。

- 后端实际 worker 检查源码不执行、稳定证据、构造参数改变真实提取结果、超规模拒绝、并发/超时释放和 session/Origin。
- 控制器检查精确槽位保留、不兼容替换原子拒绝、旧版本回复拒绝，以及模块/原子两种 recipe 逆序加入后完整 IR 相等。
- 真 Chromium 从 Studio 表单验证加入、重解析、样式重映射、拒绝后保稿、undo/redo、保存重开、精确重建和真实延迟 HTTP 回复拒绝。
- 独立正式副本重新构建，并执行新前后端专项，核对运行时字节；不依赖原型服务、源码包或解释器。

自主回归发现旧 AST fixture 将能力描述文件的变化判为过期；已将当前生成输入移到 `studio/tests/fixtures/preview-formal-ast.json`，历史语义阶段 fixture 保持原样。生成器和测试共同核对当前正式解析实现，独立副本也重新生成并验证。

最终实际计数、执行命令、构建、HTTP 资源字节及界面截图以证据目录 `validation.json` 为准。不能把显式 pending 的路线当作完整合法布线。

## 尚余迁移

本阶段未接局部组装结构重认证（原版 `certify_assembly`），也未接完整新版 generic model catalog、正式隔离下的 CPU runtime/merged 补证、测量驱动 adaptive-frontier、千级图预算与取消/压力验证，以及 D0/D1 旧 renderer/interaction 依赖拆分删除。当前成功重解析只表示静态事实更新，不表示 assembled Python、执行、shape/dtype 或训练兼容已验证。

## 本阶段最终验证结果

- 完整前端：889 项，888 通过、0 失败、1 项沙箱 Chromium 跳过；584.634 秒。
- 当前源码/编辑核心 10 项通过；正式后端 29 项通过；独立副本另有前端专项 73 项、多文件来源检查 9 项、后端 29 项通过。不同范围不累加为全量计数。
- 真实 Chromium：源码模块 6、组装编辑 12、文档 14、原生源码 16、旧桥接 23，共 71 项；无浏览器错误，源码模块矩阵未发起事务写入或模型运行。
- 当前构建、独立运行时来源和 17 个运行时/宿主/专项文件的字节对照通过；63 个 HTTP 资源与构建一致，59 个集成静态资产核对通过；32 个原生 JS 仍与 Summary 来源相同。
- 原版 `authoring.py` 与 `authoring-model.js` 保持来源字节，新增逻辑均在明确的正式桥接与 Studio 面板中。

[验证记录](evidence/summary-source-authoring-20261028/validation.json) · [当前界面](evidence/summary-source-authoring-20261028/studio-source-authoring.png) · [来源与适配清单](summary-source-authoring-manifest-20261028.json)。
