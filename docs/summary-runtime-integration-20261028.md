# Summary 新 CPU 观察接入正式隔离

日期：2026-10-28。最终验收状态及当前字节以 [validation.json](evidence/summary-runtime-20261028/validation.json) 为准；开发失败记录与最终结果分别保留。

## 替换与保留

迁入原版 Summary 的 ATen 操作、输入/输出张量 producer、模块调用 identity、完整源码调用栈、分支结果、fresh same-seed replay、可选 torch.export 诊断和原版 merge/source-runtime 关联语义。原版 `runtime_worker.py` 保持逐字节一致，来源与集成文件见 [manifest](summary-runtime-manifest-20261028.json)。原正式 structural-verified module hooks 保留事务用途，不能用它的通过收据替代 Summary 观察。

执行基础设施使用正式 `archcanvas_runtime` 的锁定 CPU venv、解释器/标准库/ELF 私有快照、只读冻结源码、Bubblewrap namespaces、强制 seccomp、资源限制、取消和环境前后字节核对。只复用旧 probe 的纯规格校验，不调用原型 subprocess 启动器；隔离不可用时按钮禁用、服务返回不可用，没有普通 subprocess 回退。

## Studio 面板和状态流

| 用户入口 | 实际行为与所有权 | 失败或返回 |
| --- | --- | --- |
| 右侧对象 → 新 CPU 观察 | Studio 原有 inspector 折叠形式；显示真实 capabilities、明确 JSON 规格及已有收据。展开面板、导入源码和切换已有轨迹均不执行模型。 | 无环境/无文本时禁用执行，仍可查看原有记录。 |
| CPU 样例规格 | 使用原版 semantic-inputs/1：constructor、cases、具名 tensor/scalar、seed、eval/train、finite_domain、可选 export。默认 inputs 为空，用户必须显式填写。 | 拒绝非法 JSON、非有限值、未知字段、超限 tensor/seed；不推断输入。 |
| 运行 CPU 观察 | App 冻结 case 与 loadSequence；发送完整 Python 文件、entry、规格及可选来源摘要。正式服务建立独立异步 job。 | A→B→A 或异步源码读取失去模型归属时拒绝旧结果。 |
| 观察收据 | 记录 profile、完整 source generation/text、输入、解释器/依赖/worker/controller 摘要、真实隔离 probe、ATen/producer/模块/分支/replay 和明确限制。 | 失败/截断/replay 不一致/来源不匹配只保留诊断，document 为 null。完整收据仅在用户展开内层折叠区后渲染。 |
| 打开本次观察结果 | 成功结果仍需显式打开。通过同一个 Summary native reader、Worker、图元/路由校验进入独立原生文档；原模型保留。 | 无可验证结果时拒绝，不直接覆盖源文档或创建源码事务。 |
| 源码 / CPU / 合并及 F0/F1 | 同一原生 IR、账本、真实调用 region、历史和相机；Studio 面板发桥命令。 | 未证明的静态 opaque 及 coverage 边界保留，不能补成全输入证明。 |
| 取消 CPU 观察 | 专用 job cancel；创建 job 之前点击也会在身份返回后立即取消。卸载面板取消在途运行并忽略迟到结果。 | 不改当前 graph、undo、redo，不展示可打开的新文档。 |
| 保存、刷新与 JSON | 完整收据、source_files、规格随原生文档保存；恢复和文件导入不重执行。再次运行仍需明确点击。 | 搬运文档的源码声明不会获得正式 source-adapter/managed-source 写回权限。 |
| 编辑 / 视图 | 结果可进入 Summary 声明组装副本，完整 baseline 保留；返回视图仍是同一原生副本。 | 正式 Python 写回继续显式进入原有 authoring/transaction/CAS。 |

## 服务与执行边界

收据 profile 为 `summary-aten-observed/1`，通过 `/api/capabilities` 的 `runtimeProfiles.summaryObserved` 公布真实可用性。新增 `POST /api/preview/runtime-jobs`、`GET /api/preview/runtime-jobs/{id}`、`POST /api/preview/runtime-jobs/{id}/cancel`，要求正式 session 和同源 Host/Origin。启动只接受 files、entry、inputSpec、sourceSha256，不接服务器目录或用户解释器。取消只接受空对象、只命中本 job；正式 project runtime route 不能读取或取消 Summary job。

全部 runtime profile 共用单个运行槽；服务只保留最近四个 Summary job，关闭服务会取消在途 job。HTTP 返回的“complete”表示 job 已结束，模型是否通过由 result.receipt.status/runtimeVerified 决定。API 轮询有界，180 秒到期发送定向取消。

规格沿用原版 1–64 个明确 case、唯一 eval/train、至多八维且每维 1–4096、每 case 合计一百万 tensor 元素；此接入另限 16 个具名输入、seed 为 [0, 2**32)。完整 Python corpus 仍为 80 文件/2 MB。正式 wall/CPU/内存/文件/禁止新进程等限制保留；原版 observer 需要 96 个文件描述符，因此本 profile 单独使用 96。返回原生文档仍限 4000 节点、5000 边、64 MB，完整 reader 和引用校验保留。

原版 observer 作为真实 Python 模块加载到验证过的只读 `/summary-worker.py`。最初采用 runpy 时，torch.export 无法重新定位观察器模块；自省修复为 importlib spec 注册后，独立实际测试确认 export captured，而非只接受“unsupported”即声称通过。

模型与观察工具同处隔离进程，收据不是对恶意模型的独立执行认证；不宣称任意输入覆盖、旧/新数值等价、checkpoint 或训练进度迁移。finite_domain 的 exhaustive 仅适用于用户列明的有限具体输入集合。

## 独立判据与自主测试

手写 `fixtures/summary_runtime/model.py` 刻意使用 getattr 动态构造 Linear，静态调用保持 opaque。正/负两分支各调用共享 projection 两次；独立预期为 `t, mm, t, mm, add.Tensor` 和 `t, mm, t, mm, sub.Tensor`。测试核对 input:x/最终 producer、不同 call identity、forward 第 11/12 行精确 source stack、四处调用 regions、完整 source generation 与 trace digest，且 coverage.complete 仍为 false。

- 真实正式隔离 CPU 核心测试覆盖上述判据、可选 export、来源篡改、失败/截断/缺 replay 不能合并、缺环境/已取消不执行或 fallback。
- 实际 HTTP 覆盖 session/Origin、参数白名单、异步读取、定向取消、profile 串行和跨 profile 拒绝；原正式 runtime 回归另行执行。
- 前端测试执行实际 App/API/表单 callback，检查源码读取/观察迟到回复、创建 job 前取消、unmount、native reader 和 unavailable 状态。
- 真实 Chromium 从产品表单导入 Python，显式运行实际 CPU，打开结果、切换源码/CPU/合并及 F0/F1、保存刷新、真实 JSON 文件输入、取消并检查完整 graph/history、进入与返回双模式。记录任何 source-write 请求和浏览器错误。
- 独立副本执行当前源码、controller、observer、fixture、前端专项与构建；CPU 测试明确复用正式锁定 .venv-runtime。它证明源码/Worker 独立，不声称独立安装 CPU/npm 依赖。

浏览器早期失败分别暴露测试基线未 flush 自动布局缓存、错误桥命令名、未等待异步打开完成、semantic-view 未使用 patch 合同；均保留原失败证据。最终比较完整 graph，未删除缓存、源码、几何或状态字段来放宽断言。

本阶段最终计数、构建、资源/来源等价及证据文件见 validation.json；不将历史阶段计数相加作为当前全量。

最终验证通过：前端全量 992/993（唯一沙箱跳过另行通过）、独立前端 187、主/独立 CPU 各 7、HTTP/正式 runtime 10、语义/组装/HTTP 33，最终浏览器 45 个检查；构建、来源与资源等价通过。范围与限制以 validation.json 为准。
