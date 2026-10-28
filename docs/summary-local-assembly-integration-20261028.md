# Summary 组装局部结构复核接入

日期：2026-10-28。继续由 Summary 提供模型组装和语义规则，Studio 保留主菜单、左右面板与正式源码事务。本阶段完成局部结构规则的接入，整体迁移仍在进行。

## 面板与功能

右侧 Summary 编辑面板增加“组装局部结构复核”折叠区。“复核当前组装结构”将当前声明 IR 提交正式同源 API，使用 Summary 原版 `certify_assembly` 重新识别操作数结构。

| 操作 | 当前行为 |
| --- | --- |
| 当前稿复核 | 先清除旧契约，使用原版 recognizer 生成局部契约；节点、依赖、槽位、源码文本与 authoring 声明不变 |
| 语义 F0/F1 | 由同一 Summary 原生 pipeline 使用局部契约，未建立第二套图元或路由 |
| 新增、删除、重接、参数/结构等声明编辑 | 丢弃旧复核结果，派生新的未验证 IR；可再次复核 |
| 单纯视觉编辑、切面 | 当前声明未变时保留结果 |
| 撤销/重做 | 复核本身只提交一项现有预览历史；恢复该版本声明与对应结果 |
| 浏览器保存、编辑 JSON | 保存声明、局部结果与当前视图；重新核对摘要和完整事实后恢复 |
| 原始参考、精确 recipe 复原 | 原始 IR 不标记为 edited 时不重复认证，仍保留其原有事实；结构修改后可复核 |

按钮与错误仍在原 Studio inspector 中。参数声明的帮助文案也更新为引导用户使用已经迁入的“源码模块与参数重解析”，避免旧文案错误引导到另一套编辑入口。

## 正式 API 与进程

新增 `POST /api/preview/authoring/certify`，只接受 `{ir}`，要求当前 session、Host/Origin 与同源。`preview.nativeAuthoring.localAssembly` 公布 endpoint、schema 与限定范围。它不接受服务器路径、不读模型目录，也不启动原型服务。

正式 `assembly_bridge.py` 使用当前正式解释器的 `-I -S -B` 进程，加载正式 `src` 中的原版 Summary 规则。输入只作为 JSON 声明，模块保存的 Python 也只是字符串；不会 import、执行或写回 Python。它与源码模块解析共享每服务进程一个静态分析槽，超时或异常后释放。

预算保持 480 节点、3600 依赖、16 MB、128 层父级；wall 15 秒、CPU 8 秒、地址空间 512 MiB、48 文件描述符。输出经临时文件与文件大小限制，并由父进程再次检查。当前使用 Python `resource`，没有宣称跨平台的等价执行沙箱。

返回 `archcanvas-summary-local-assembly/1`，以 `irText` 保留 Python canonical JSON 原文，并附 SHA256 和明确的 analysis 范围。契约必须声明：只覆盖当前组装声明的局部操作数结构，不证明原始 Python 未改、shape 兼容或 assembled-program execution。

## 保持声明与派生结果的边界

`generic.authoring` 继续是唯一可写组装声明。当前声明摘要不因复核动作变化；局部结果放在 workspace 元数据的 `localAnalysis`，不是第二份可写模型。恢复时先用原版 `sourceIR` 从声明生成基础 IR，然后验证：

1. workspace 的声明 SHA256 与结果起始声明一致。
2. `irText` 的字节摘要正确，结构预算有效。
3. 去除 `ir_digest`、契约列表/依据和唯一 `local_contracts_recomputed` 标志后，完整 IR 与声明派生事实相等。
4. 每项契约保持原版局部 scope 和三项不承诺内容；analysis 不能宣称模型执行或源码事务权限。
5. 正常 Summary 生成器重新检查图元，当前图与声明/派生结果继续严格匹配。

这样没有将 `D.matches` 放宽为只检查计数或忽略任意语义变化。对节点/依赖的篡改即使重算结果 SHA256 也不能通过；失败不替换已提交图。

保存的结果属于可移植文档声明，并非服务端签名或新一轮源码认证。导入时不会自动调用服务器重新复核，界面明确显示“已保存局部结构结果”“文档来源，模型未执行”。它不授予 source adapter、Canvas CAS 或 prepare/review/approve/commit 权限。

复核请求还固定案例加载序列、workspace UUID 和声明摘要；真实延迟回复不能认证同一 workspace 的后续版本。声明编辑后保守清理结果，包括标题等声明字段变动；不宣称最小化失效范围。

## 自主验证

当前专项包含：原版实际 recognizer 识别 residual 契约；完整节点/边/声明守恒；旧契约清理；模型/模块源码不执行；无效图、循环、端点、有限 JSON、规模、并发和超时；真实 session/Origin；本地结果的篡改、scope 扩大、旧版本拒绝；原生切面、保存恢复、编辑后清理与旧历史恢复。

真 Chromium 从折叠面板点击并核对 HTTP 结果、撤销/重做、保存重开、F0/F1、跨上下文 JSON、重算 SHA 后的事实篡改拒绝，以及截留真实 HTTP 回复后修改声明的拒绝。测试最初按 JSON 字段序列字符串比较节点；Python canonical 排序只改变字段顺序，已改为比较完整对象值，原失败记录保留。生产代码没有为此放宽比较。

本阶段证据为 `docs/evidence/summary-local-assembly-20261028/validation.json`，来源与当前适配指纹为 `docs/summary-local-assembly-manifest-20261028.json`。上一源码模块阶段的 889 项计数只覆盖上一阶段字节，不能用于认证本阶段新增的恢复规则。

## 尚余迁移

完整新版 generic catalog、正式隔离下的 CPU runtime/merged、测量驱动 adaptive-frontier、千级预算/传输/取消/压力，以及 D0/D1 旧 renderer/interaction 依赖拆分删除仍未完成。局部结构复核不代替这些门禁。

## 本阶段最终结果

完整前端 892 项：891 通过、0 失败、1 项沙箱 Chromium 跳过。该运行启动后增加了解析后 IR 的 `bounded(ir)` 深度/对象预算 guard；完整计数不能归于最后这一行。guard 后最终专项 85 项、独立副本 85 项和真实 Chromium 局部复核 5 项再次通过，包括重算摘要后仍拒绝 140 层 proof 的负例。

正式后端和独立副本分别 33 项通过。真实 Chromium 组装编辑 12、文档 14、源码模块 6，加本阶段局部复核 5，共 37 项通过，无浏览器错误。当前构建、独立运行时来源、11 文件字节对照、63 个 HTTP 资源和 59 个集成资产核对通过，32 个原生 JS 仍与 Summary 来源逐字节相同。历史阶段计数不累加。

[验证记录](evidence/summary-local-assembly-20261028/validation.json) · [实际界面](evidence/summary-local-assembly-20261028/studio-local-assembly.png)。
