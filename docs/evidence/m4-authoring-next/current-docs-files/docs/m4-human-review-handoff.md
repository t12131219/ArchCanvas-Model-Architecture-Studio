# M4 当前交接：从零搭建与 AI 使用测试

当前构建 `index-CIVB6v-J.js`（SHA256 `d5b0c8369aaa8ae793473d934774663fd06b5650ea1103ef3f65d5dfcd8f0d9f`）。[本轮搭建报告](m4-authoring.md)记录三个 AI 测试角色、17 种模块、独立后端/交互审查及实际新手代表浏览器任务；AI 不能计入真人席位。Studio 113/113、获准环境 Python 300/300、strict/build 通过，M4 仍 partial、未进入 M5。

| 待完成门 | 当前状态 | 材料与下一步 |
|---|---|---|
| 新版完整浏览器矩阵 | 未针对当前构建准备；0/36基础、0/3编辑 | 旧[routing-visible spec](../.archcanvas/browser-visual-matrix-routing-visible/spec.json)只绑定 C7 的 9 frontier。当前 25 份代表 DOM 与截图不能计为完整矩阵。 |
| 人工出版审看 | 未认证 | 当前复采后审看字号、字体、连线、图例、黑白和实际尺寸。路由避开body/header不代表线间交叉/弯折美观。 |
| 原生性能、活动取消 | 未认证 | 新构建没有持续presented性能或活动取消成功证据；候选CPU与旧Cr原生诊断分开。固定浏览器/硬件/字体后实际采集。 |
| 3–5真实研究使用者任务 | 当前未prepare，0分配/收集/真人 | 旧 C7 的[五席准备](evidence/m4-ai-usability-next/preparation-visible/README.md)仍 pristine，但 63 实施绑定/4 基线不适用于当前构建；须重新准备。 |
| 从零模型搭建与模块库 | 有界实现 | 17种模块/独立草稿/参数/端口/新模型静态闭环，见[m4-authoring](m4-authoring.md)；Attention/LSTM/组合预设尚未实现，AI不计真人。 |

研究任务继续遵循[研究协议](m4-research-protocol.md)。真实使用者开场才 assign，AI 模拟一律 automation；主持人记录环境和全部失败、超时、放弃。旧 C7 五席 S01–S05 的端口是 8921–8925，manifest SHA256 `95231009eae473c1d863a8eace4d7ee62e979839dddc12c5e9138636c971c490` 仅为历史绑定，不保证端口空闲或在线服务。

当前代表任务的 [独立审查](evidence/m4-authoring-next/browser-audit/README.md)核对 25 份 DOM、11 个服务工件与 38 个污染反例。四向移动与平移通过，只有左移有单独撤销/重做记录；论文图仍有两处中心错位导致的 4 个折点，无交叉或叶节点穿框。未认证完整矩阵、出版人审或性能门。隔离预览 [8916](http://127.0.0.1:8916/) 与搭建页保留供审看，用户 8765 服务和标签未触碰。

旧 Cr/boundary-final、Dgt/routing-next 的 stale 检查及旧 Cr39 矩阵继续保留历史范围；旧 C7 的 8912 服务停止及 38/39 标签关闭也只属于前轮。新构建切换前 904 项字节见[归档](evidence/before-m4-authoring-next/manifest.json)，旧 seal/raw 不回写。机器当前范围见[状态JSON](evidence/m4-human-review-handoff-status.json)。
