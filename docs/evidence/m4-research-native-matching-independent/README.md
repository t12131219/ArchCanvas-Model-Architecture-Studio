# 新 native-matching 研究包独立只读核对

审查者 `/root/research_handoff_audit` 读取当前正式源码/build、`.archcanvas/m4-research-trial-native-matching-current` 的 manifest、baseline 与完整五席状态，执行正式 `research_trial.py verify` 和已有只读 readiness audit。没有 assign/collect/serve，没有浏览器操作、参与者消息、模型执行或依赖安装，包内容未改。

正式 `verify` 退出 0，只认证 frozen baseline/implementation；补充审计 **136/136 checks 通过**，当前 **81/81 implementation bindings**、4 baseline bindings、五席 pristine。manifest SHA256 为 `321c1c2c83126f57b2cb96f1debafd07849c946afce60a95e5db73b6778dd13c`，当前 build 为 `index-D60-bDcz.js` / `index-QPVAzYp6.css`。

| 席位 | manifest登记端口 | 独立 dataDir |
|---|---:|---|
| S01 | 43151 | `.archcanvas/m4-research-trial-native-matching-current/slots/S01/workspace/documents` |
| S02 | 43152 | `.archcanvas/m4-research-trial-native-matching-current/slots/S02/workspace/documents` |
| S03 | 43153 | `.archcanvas/m4-research-trial-native-matching-current/slots/S03/workspace/documents` |
| S04 | 43154 | `.archcanvas/m4-research-trial-native-matching-current/slots/S04/workspace/documents` |
| S05 | 43155 | `.archcanvas/m4-research-trial-native-matching-current/slots/S05/workspace/documents` |

各席位 `participantCode=null`、`assignment=unassigned`，相同 baseline envelope 为 85,818 bytes、SHA256 `22400cc1b9ec5cb6d38f88b14ff7536029a2a1dfadd4f44a65f50f50def6916a`；`assignment.json`/`collected` 不存在，incoming/exports/projects/transactions为空，blank review 与 environment templates 未填写。端口只是登记值，本次未检查占用或证明服务在线。

读 [report.json](report.json) 的输入绑定、实际绝对 dataDirs 与 before/after 包清单；[readiness-report.json](readiness-report.json) 保存136条机械检查，[verify-process.json](verify-process.json) 绑定实际命令/时间/exit和stdout/stderr。

研究者 **0、assigned 0、collected 0、humanSuccessCertified=false**。固定浏览器/硬件/解析字体、真人五步任务、实际出版尺寸人审与 presented performance 未由准备包证明；M4仍partial、M5未开始。
