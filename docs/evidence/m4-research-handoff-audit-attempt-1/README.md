# M4 研究者交接只读审计（attempt 1）

本目录是对 M4 研究者任务开场材料的独立、只读补充。审计读取技术计划 §18、正式研究协议、两份当前交接 status JSON、两个被文档列为五席候选的试用包，并比较其冻结实现摘要与当前正式工程。它没有调用 `assign`、`collect` 或 `serve`，没有启动浏览器，没有发送邀请或消息，也没有改写任何旧 manifest、seal 或 handoff status。

## 结论

- `m4-research-trial-boundary-final` 与 `m4-research-trial-zoom-final` 各有 S01–S05 五个席位。每个席位的 manifest assignment 仍为 `unassigned`、`participantCode=null`，baseline envelope 的字节摘要一致，`assignment.json`、`collected` 以及 incoming/exports/projects/transactions 均为空。审计观察到 5/5 席位 pristine；这代表空白准备状态，不代表研究者。
- 两个包的冻结实现/build 已落后当前正式树。针对它们运行 `scripts/research_trial.py verify` 返回 `Formal implementation changed after preparation; prepare a fresh package.`。当前 `studio/dist` 是 `index-thbum3BQ.js` / `index-QPVAzYp6.css`，旧包冻结的是更早的资产。因此当前没有可安全分配的研究包。
- `m4-human-review-handoff-status.json`（schema 12）和 `m4-human-review-handoff-status-followup.json`（schema 16）均记录 `preparedForCurrentBuild=false`、`verifiedForCurrentBuild=false`、`assigned=0`、`collected=0`、`researchers=0`、`humanAcceptanceCertified=false`，且 `aiCountedAsHuman=false`。
- `StudyPanel` schema v1 是本地 self-report；`m4_input_observer` schema v2 只记录 DOM、Event Timing、长任务和 rAF/几何代理。源文件明确指出它们不能证明真人身份、presented paint 或连续 input-to-paint。技术计划 §18 的 3–5 研究使用者、任务时间、版式/尺寸人工审看、input-to-paint/长任务/帧率门均仍缺真实证据。

## 可复核入口

- [report.json](report.json) 保存本次检查的绝对路径、哈希、五席状态、当前构建、交接状态、任务/observer schema 事实和限制。
- [audit.py](audit.py) 是可重复的只读审计脚本；它只读项目和候选包，不修改其内容。
- [boundary-verify.log](boundary-verify.log) 保留旧包 `verify` 的失败输出；本次结论也有报告中逐文件 frozen binding mismatch。
- [新手/视图探索卡](novice-and-view-task-card.md) 与 [空白侧车 schema](exploration-template.json) 具体列出从零建模、模块库、节点/相机四方向、箭头美观、低缩放提示、删除/history/保存重开与生成/出版的独立探索。它们尚未执行，不改变原五步 180 秒分母或真人计数。

## 下一安全动作

先冻结最终正式 build 和浏览器研究版本，在新目录执行 `research_trial.py prepare --slots 5`，随后 `verify` 与本审计；只有真实参与者到场时才为未使用席位执行 `assign`。真人任务、导出打开、截图和独立 reviewer 记录完成前，保持 `humanAcceptanceCertified=false`、M4 partial 和真人计数 0。

本报告不提升任何旧证据范围，也不改变 M4/M5 状态。
