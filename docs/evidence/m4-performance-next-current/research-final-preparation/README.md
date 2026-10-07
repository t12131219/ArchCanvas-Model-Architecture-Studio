# BTw7 当前研究包准备证据

为 `index-BTw7OHsD.js` / `index--unhoRTb.css` 新建 `.archcanvas/m4-research-trial-btw-current`。prepare、初次/最终正式 verify 与独立审计均 exit 0；独立审计 **280/280** 通过。准备不是研究验收：M4 partial、M5 not_started、真人 0。

- `preflight.json`：读取的正式 AGENTS/Skill/runtime 说明、实际运行时来源、106 个严格源码/构建绑定及旧包完整清单；说明快照在 `instructions-read/`。Runtime 说明的 B_XH 首段按读取时点保留，实际 BTw7 身份由当前构建收据确认。
- `process.json` / 原始 stdout、stderr：实际 prepare / verify 命令、运行时间与散列。
- `audit_readiness.py` / `readiness-report.json`：仅标准库独立字节/JSON/目录核对；84 实现绑定、4 基线、106 严格源码/构建绑定精确；5 空白隔离席位；20 个旧包、342 个文件不变。不导入产品 helper 或模型。
- `old-bxh-stale.*`：B_XH 旧包正式 verify exit 1，因实现变化拒绝；旧包原始字节保持。
- `verify-final.*`：独立审计后正式 verify exit 0，冻结实现/基线仍一致。
- `report.json` / `manifest.json`：汇总与本目录及外部输入字节绑定。

包 manifest SHA256 为 `8a8be05f0ebbfde11e4fa208bee1b7e12a5a49f7e7cc74529e5215d4416b3a96`。S01–S05 只登记端口 43551–43555；未检查可用性、启动席位服务、分配或采集。环境与真人审看模板保持待填。

实际 `.venv/bin/python` 的 prefix 为正式 `.venv`，底层 symlink 解析为宿主 `/home/fzg/anaconda3/bin/python3.11`。正式研究脚本显式加入正式 `src` / `scripts`；来源核对按此入口解析为正式分析器，未安装依赖或调用 Temp。准备仅静态分析冻结 fixture，并调用正式 Node core。Studio 358/358、publication 9/9、均零 skip 和 strict/build exit 0 来自已完成收据/日志的读取，没有重复运行产品测试。

280 个核对断言不是额外产品测试、真人任务、出版尺寸人审、呈现性能或数值正确性。AI 仍不计真人；入口文档和 gate 由主任务更新，本任务未编辑产品或入口。
