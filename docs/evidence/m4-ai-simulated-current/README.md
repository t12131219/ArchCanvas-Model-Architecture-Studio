# 三角色 AI 模拟与最终构建证据

本目录对应用户授权的三角色 AI 模拟、发现问题后的修复、版本分开的补采与准备审计。产品阶段说明见 [m4-ai-simulated-current.md](../../m4-ai-simulated-current.md)，当前门见 [m4-current-gate-audit.json](../m4-current-gate-audit.json)。真人 0；M4 partial，M5 not_started。

| 目录 | 版本与范围 |
| --- | --- |
| [novice](novice/README.md)、[gestures](gestures/README.md)、[catalog-visual](catalog-visual/README.md) | DuFX：3 AI 角色实际 UI 操作。小白空白搭建、四向/history/reopen、17 参数界面与预制网络；原发现/失败不改。 |
| [browser-fixes](browser-fixes/receipt.json)、[catalog-followup](catalog-followup/README.md)、[zoom-followup](zoom-followup/README.md) | CC91：修复后针对性 UI 操作、缩放几何和有限像素审看；滞后图保留。 |
| [fix-independent](fix-independent/FINAL-README.md) | 26+9 有界属性断言；独立静态生成，不执行模型，不相加到 Studio 测试。 |
| [novice-followup](novice-followup/README.md) | 浏览器不可用，未完成补采；不计成功。 |
| [checks-final-attempt-3](checks-final-attempt-3/receipt.json) | 最终 B_XH：347/347、0 skipped，strict TypeScript/Vite exit0；100 源码/测试/配置＋3 构建绑定。此前失败/中间检查保留。 |
| [final-browser](final-browser/receipt.json) | 最终 B_XH：7 状态/30 文件；CNN 2×4 84%、池化 2×2 / Linear 32 修正及保存重开、重开直线源图。 |
| [catalog-independent](final-readback/catalog-independent/README.md) | 最终 103 绑定、7 原图有限匹配、42 条草稿状态路线及保存文件、空白研究包的独立末读。 |
| [research-final-preparation](research-final-preparation/README.md) | B_XH：273/273 空白包准备审计；5 席位、0 分配/收集/真人，19 旧包 325 文件不变。较早 DuFX/CC91 准备各按自己的冻结版本阅读。 |
| [before-entry-update](before-entry-update/manifest.json)、[before-fixes](before-fixes/manifest.json)、[before-final-label](before-final-label/manifest.json) | 入口 15 文件、修复前产品 102 文件、末次池化名称前 4 文件的原字节快照。 |

修复前 DuFX 的两对小场景原生性能诊断在 [m4-dufx-performance-visibility](../m4-dufx-performance-visibility/receipt.json)，条件审计在 [m4-current-performance-condition-review](../m4-current-performance-condition-review/README.md)。p95 40 ms / rAF 约 60 Hz 不认证最终 B_XH、300 对象、实际呈现帧率、全输入或宿主显示 A/B。

这里的条目计数是各自报告/文件/几何范围，不相加为产品测试、真实使用者或最终全模型认证。冻结的 raw、失败、manifest、收据和旧研究包不回写；最新入口文档用明确版本说明读取它们。
