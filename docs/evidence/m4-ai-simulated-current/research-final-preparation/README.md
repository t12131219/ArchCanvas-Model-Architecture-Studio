# B_XH 当前研究包准备证据

为 AI 代理测试修复后的 `index-B_XHk-wz.js` / `index--unhoRTb.css` 构建新建 `.archcanvas/m4-research-trial-bxh-current`。prepare、初次/最终正式 verify、独立审计均 exit 0；独立审计 **273/273** 通过。M4 仍 partial、M5 not_started、真人 0。

- `process.json`：实际 prepare / verify 命令、运行时间和原始日志散列。
- `readiness-report.json` / `audit_readiness.py`：83 实现绑定、4 基线与 103 个当前严格测试源码/构建绑定精确；5 个隔离席位为空；19 个旧包共 325 个文件未变。审计仅用标准库读取字节、JSON 与独立文件清单，不导入产品 verify/helper。
- `old-cc91-stale.*` / `old-dufx-stale.*`：旧包对当前实现的正式 verify 均 exit 1，拒绝原因是实现已变，原始包字节保持不变。
- `verify-final.*`：独立审计后的正式 verify，冻结基线与实现仍一致。
- `report.json` / `manifest.json`：汇总与本证据/外部绑定字节清单。

包 manifest SHA256：`61ac9fbb61d26d1dd6b68bc0873955a3ec467bd2988b2e927e22f0a299162cdf`。S01–S05 登记端口 43451–43455，未启动服务或检查端口可用性；未分配、采集或执行模型，环境/真人审看模板均待观察/待审看。

实际 Python 入口为正式 `.venv/bin/python`，`sys.prefix` 为正式 `.venv`，底层解释器软链接解析为宿主 `/home/fzg/anaconda3/bin/python3.11`。裸解释器不能直接 import `archcanvas_python` 的失败保存在 `preflight-attempt-1-failure.json`；正式研究脚本实际显式插入正式 `src` / `scripts`，按此入口核验的分析器来自正式源码。未安装依赖或调用旧工程。准备仅静态分析冻结源码并调用正式 Node core。

此包准备不证明 AI 浏览器任务、真人任务、出版尺寸审看、字体/硬件环境、呈现性能或模型数值正确性。AI 代理不能计入真人数量。主任务负责更新当前文档；文档不属于研究包冻结实现清单。
