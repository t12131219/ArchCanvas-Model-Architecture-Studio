# 模型发现、源码适配与 Studio 最终验证

当前验收入口为 [final-integration/verification.json](final-integration/verification.json)、[final-arrow-support/receipt.json](final-arrow-support/receipt.json) 和[总报告](../../source-adaptation-act-validation.md)。最终规则为 `source-inspection/2`。本目录早期带 `final` 的文件也可能早于最终箭头修复；名称本身不表示绑定当前实现，必须核对收据中的实现 SHA。

最终 Studio 测试 783 项：782 通过、0 失败、1 项因沙箱跳过；该浏览器出版项已有相同实现的单独 3/3 通过证据。TypeScript/Vite 构建、5 项 HTTP 检查和 7 项源码保留检查均通过。当前迁入预览的 19 个集成文件在 public、dist 与 manifest 中一致。

真实 ACTPolicy 界面在保存刷新后保留 8 条紫色源码依赖和 2 条棕色条件关联，全部当前边及源码/布局检查通过、条件路由零诊断。源码依赖、条件关联与张量连接具有不同含义，不能相互替代。截图与独立副本闭环见 [browser verification](final-integration/browser-verification.json)。当前画布真实生成的 [PDF](final-integration/act-training.pdf) 和[导出收据](final-integration/act-training-export-receipt.json)已留存；180 mm 下文字过小，生成成功不代表出版可读性通过。

最终规则的 DETRVAE 已真实完成参数 1→2、源码审阅、新工作副本、保存刷新和再次编辑。后端保存的 20 个 Python 文件仅对应构造字面量变化，见[存储核对](final-integration/generated-copy-storage-verification.json)。原始 act 全部 74 文件集合、内容和修改时间仍不变，见[最终只读审计](final-integration/final-readonly-audit.json)。深层性能、动态运行层级和任意结构修改生成仍不作为完整通过。

以下为早期发现轮次的说明，保留追溯用途：

最终证据为 `discovery-final-verification.json`、`model-discovery-final.json`、`model-discovery-final.md`；目录中的 `intermediate-*` 和未带 final 的最初记录仅供回溯，不能替代最终字节验证。

最终对 act 的 15 个本地模型类分别执行递归预览与正式编辑静态分析，共 30 次打开通过。两侧不执行用户源码；分析前后原目录 74 文件集合、SHA-256 和纳秒修改时间完全一致，正式分析保留全部 20 个 Python 文件。实现的 5 个关键文件在整轮前后哈希一致。

目录扫描已在预算内覆盖全部本地已证明模块类；可能包含关系仍有动态数量、配置分支和外部 torchvision 等未知项，因此 `hierarchyComplete: false`。ACTPolicy 与 DETRVAE 的预览源码检查各有 3 个包含深度预算截断，不能宣称完整运行结构恢复。

`discovery-targeted-test-receipt.json` 绑定 89 项相关 Python 测试：84 通过、5 项因沙箱 loopback 不可用跳过。方法替换、无效参数绑定、已覆盖赋值退休、共享别名、条件候选均有通用正反例。旧 rebind 测试的两项假设已纠正：被未知 __call__ 覆盖的 forward 不再取得入口，被替换 __init__ 的原模块调用只能 opaque；sentinel 检查证明替代函数也未执行。

全仓库测试曾因长时间无结果而中断，不计为通过；本目录显式保留 `full-python-suite-interrupted.json`。最终服务、UI、注册适配和源码保留生成的证据由本次集成的其他验收收据提供。
