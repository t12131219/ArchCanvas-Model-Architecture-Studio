# BTw7 入口更新与最终回读

已更新 13 个当前说明、2 个旧阶段历史提示，以及当前 gate。研究协议的 verify 指向 fresh BTw7 包；一处旧 B_XH 当前指针改为明确失效／BTw7 上下文。其他历史正文精确保持，旧 AI 阶段 evidence 索引未改。更新前 121 个原始快照准确。

`final-report.json` / `verify_current_entries.py` 读取最终入口、真实收据与冻结历史，**862/862 文档／字节关系**通过、无实质发现；568 条本地 Markdown 链接与 60 条 gate 证据路径存在。该脚本仅用标准库，没有调用产品 helper、模型或新产品测试。`final-inputs/` 冻结此次最终读到的字节，`final-entry-diffs.json` 保存全部入口差异。

三个计数分开读取：Studio **358/358**、publication **9/9** 是已完成产品检查；**280/280** 是五席位研究包准备；本目录 **862/862** 是文档／字节关系，不相加，不计用户。源码／构建 106 个绑定精确。新 native 3/3 的 p95 160 ms 是匹配子集；不同视口不推导 224→160 性能改善。标签名义避障仍不解决关联距离，actual export 尺寸预检不认证真人出版。

最终 scoped `git diff --check` 与 Skill `quick_validate.py` 均 exit 0。正式 `.venv` 缺 PyYAML 的第一次 Skill 校验失败原样保留；未安装依赖，改用已核明 `/home/fzg/anaconda3/bin/python3` / PyYAML 6.0 运行纯文档校验。研究包仍使用正式 `.venv`，不把宿主文档校验解释为产品运行时。

本目录保留初始编辑记录、更新 native 字段、真实收据读回、所有失败／日志及最终结果；不修改旧收据／manifest／研究包。最终 manifest 绑定已完成阶段与收据，故意不绑定主 Agent 未来的 final 报告以免循环。当前说明没有触发新 build。

M4 partial、M5 not_started、真人 0。上一轮三位 AI 模拟者按历史范围阅读；本轮审计者不新增模拟用户或真人。
