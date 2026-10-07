# ChS fresh research package preparation

新包 `.archcanvas/m4-research-trial-chs-current` 已通过正式 prepare 与 verify：72 项当前实施绑定、4 项 Transformer 基线、5 个独立未分配席位，登记8991–8995端口。manifest SHA256 为 `ea10901224a5e2e8ebc8ad4136f68b8bd5b4e1db51f8bda38e92a66665b6efbf`，当前 JS 为 ChS 的 `05019f89…`。实际准备解释器是正式工程 `.venv/bin/python`，analyzer 来源为正式 `src/archcanvas_python/frontend.py`。

[preparation-verification.json](preparation-verification.json)保存命令、日志、包文件绑定与限制；77项相关输入前后相同，旧799项seal在prepare前后全部原字节一致。每席Canvas visual revision0/storage1，无别名、样式覆盖和pin；reviewer/participant为null，incoming/exports为空，无assignment、collected、projects或transactions。真人、分配、收集与human success均为0/false，没有启动服务、检查端口可用性或执行模型。

[task-contract-review.md](task-contract-review.md)说明旧协议顶层版本/包路径过期与现有五步的实际适用范围。现有同源Transformer制图五步仍保留；17+3搭建草稿及显式位置修复探索须单独记录。StudyPanel只观察publication scene，collector要求同一document/source/IR，不能把生成的新模型冒充原五步的一次视觉编辑。旧180秒/80%是目标，未成为本轮实测。

[exploration-template.json](exploration-template.json)是空白补充提案，无参与者、计时、结果或证据，不扩展原五步成功分母。prepare脚本、StudyPanel、collector、旧任务协议/包和旧浏览器原件均未修改；`check_research_trial.py`仅做源码合同检查，未重跑12项automation suite。研究者任务与人工出版门保持未执行，M4仍partial。
