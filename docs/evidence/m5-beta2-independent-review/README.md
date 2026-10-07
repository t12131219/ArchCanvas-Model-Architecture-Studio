# M5 Beta.2 独立复核

最终候选审查在 [candidate-final-v1/report.json](candidate-final-v1/report.json)，SHA256 `890817a1cd2abca2f83d778a463999641b2c5d182c54e167915489b082f34b8c`。本审查不改共享源码、manifest、dist 或压缩包；运行证据位于新目录与本次自建 `/tmp/archcanvas-beta2-independent-review-9xxlcujr`。

| 实际输入 | SHA256 |
|---|---|
| 冻结 beta.1 | `2c44459c195540fd3ac99a0fa7f52583090d85eae47b26fea4a64d1da85ff9ff` |
| 最终本地 beta.2 候选 | `763fff38af08c735ead53d95a0684904307ee6546f7e7538d9835c3187a72bf3` |

29 条黑盒命令退出 0。Beta.2 包含 258 个交付文件与一份 BUNDLE-MANIFEST，全部交付字节在审查时匹配正式工作树；八个 lifecycle 工具/测试在库存中且实际存在。独立解包的三个源码入口得到 MLP 8、Residual CNN 24、Transformer 49 节点；模块来源均在解包副本。没有 fixture/model 导入或执行。

版本目录使用候选**包内**工具，真实执行 beta.1 → beta.2 → beta.1 安装、激活与回滚。beta.1 的 218 文件及 beta.2 的 259 文件（各含 BUNDLE-MANIFEST）始终保留摘要；外部用户文件不变。

三个项目级宿主目录各完成 beta.1 安装 → 归档 beta.1 → 安装 beta.2 → 归档 beta.2 → 恢复 beta.1。每种宿主的旧版 227 文件、新版 268 文件包括生成 launcher、安装合同与本地资源说明；归档及恢复逐文件核对原字节，外部 state 不变。新归档继续保留，旧归档标记已恢复。该结果是项目路径/可恢复安装生命周期，三宿主客户端 E2E 均仍为 `not-tested`。

新可靠性工具的 [冻结 beta.1 后端实跑](baseline-reliability-permitted-v2/receipt.json)通过 9 项拒绝/持久化检查，两次自有 loopback 服务退出码均为 `-15` 且停止。原默认 sandbox 的 socket `EPERM` 启动失败在 [baseline-reliability-v1/receipt.json](baseline-reliability-v1/receipt.json)原样保留，0 检查不计通过。实跑不批准语义变更；伪 approval 提交被拒绝且持久化字节不变。最终候选已将 scope 的 `graceful-restart` 改为 `owned-termination-restart`，与 SIGTERM 行为一致。

[独立反例套件](source-counterexamples-v1/report.json)为 7/7，主动检查预期错误状态被 HTTP 200 冒充、错误诊断、被称为拒绝但实际写盘、缺失新版工具的自洽 archive/installed directory、beta.1 兼容与仅终止自身 child。其一项 archive 测试逐一移除八个 lifecycle 必需文件。此套件保存 wording 修正前的工具字节，审查报告明确其有限输入范围；最终候选由上面的包内黑盒链单独验证。

本结果不认证真实宿主客户、浏览器手势/录像、模型数值或运行、依赖安装、公开发行、真人任务、出版美学或跨平台恢复。有限反例不是任意伪造不可成功的证明；当前产品明确仍为本地未签名预览。
