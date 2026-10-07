# DuFX 当前研究包准备证据

为当前 DuFX 构建新建 `.archcanvas/m4-research-trial-dufx-current`，保留全部旧包。准备、正式 verify 与独立审计均 exit 0；独立审计 269/269 通过。这里仅记录冻结包准备状态，M4 仍为 partial，M5 为 not_started。

- `process.json`：实际 prepare / verify 命令、环境、日志散列。
- `readiness-report.json`：83 个实现绑定、4 个基线绑定、102 个当前源码/构建绑定精确；5 个隔离席位均为空；17 个旧包共 291 个文件未变。
- `audit_readiness.py`：仅用标准库读取字节、JSON 与独立文件清单，不导入产品 verify/helper。
- `verify-final.process.json` / `verify-final.stdout.json`：独立审计后正式 verify，冻结基线与实现仍一致。
- `report.json`：汇总、运行时来源及边界；`manifest.json`：本证据目录和外部绑定的字节清单。

包 manifest SHA256：`cb8970c94d9cd7f7c739e27035c3c63c8d6a78b05c5ea0949563337a6e4915cb`。S01–S05 登记端口 43251–43255，未启动服务，也未检查端口是否可用。没有分配、采集或真人记录；环境/浏览器/字体与真人审看模板保持待观察/待审看。

实际 Python 入口为正式 `.venv/bin/python`，`sys.prefix` 为正式 `.venv`，分析器来自正式 `src/archcanvas_python`。底层解释器软链接解析为宿主 `/home/fzg/anaconda3/bin/python3.11`；这不是旧工程运行时，也不是重新安装的独立解释器。准备仅静态分析冻结源码并调用正式 Node core，未导入或执行模型、未安装依赖。

这些证据不证明真人任务、Agent 浏览器任务、出版尺寸审看、字体解析、硬件性能或模型数值正确性；AI 代理不能计入真人数量。
