# Caption/route 最终构建的冻结研究包准备

实际新包为 `.archcanvas/m4-research-trial-caption-route-current`，manifest SHA-256：`dd0cb0e2dc53615a38c2045e0af5b33f36278eb9aa900847946e8597acbadea2`。正式 `.venv/bin/python` 执行 prepare、初次 verify、末次 verify 均 exit 0；analyzer 来自正式 `src/archcanvas_python`，底层解释器为现有 Anaconda Python，不加载失败原型。准备只做静态分析、Canvas 初始化和独立席位文件，不执行模型。

包绑定 **84** 个运行实现文件、**4** 个 baseline 文件，当前包 **17** 个文件保持原字节。五个席位 S01–S05 仅登记端口 **43561–43565**；assignment 和 collect 为 0，各 workspace 文档只有未编辑 baseline，review 仍空白。没有开服务、检查端口可用性或填写浏览器、硬件、字体环境。

准备前逐字节核对 [最终 checks attempt 3](../checks-final-attempt-3/receipt.json)：Studio 实际 **389/389**、0 fail/skip/cancel；严格 TypeScript/Vite exit 0；publication **9/9**，无 skip。产品源、测试、配置 **105** 条加 **3** 个 dist 共 **108** 条 exact bindings；另 **11** 条 publication inputs 独立绑定。JS `index-Divs1MJA.js`，CSS `index--unhoRTb.css`。前两个失败检查保持原证据，不计入本次通过结果。

[audit_readiness.py](audit_readiness.py) 仅导入 Python 标准库，没有调用产品 verify/helper。它独立核对 implementation inventory、baseline/canonical identity、全部 pristine seats、环境空值、实际测试日志与所有 source/build/publication 字节，以及旧包完整目录和字节，得到 **295/295**。这些是独立准备度关系，不是额外 Studio tests，也不是使用者任务。旧 **21** 包的 **359** 个文件和目录 inventory 与准备前完全相同，见 [old-invariant.json](old-invariant.json)。

[report.json](report.json)、[readiness-report.json](readiness-report.json)、[manifest.json](manifest.json) 提供完整可复核绑定。此包仅认证当前构建的未分配准备状态，**真人参与者仍为 0，M4 partial、M5 not_started**。后续任何产品或 dist 变化都使此冻结包过期，应另建新包，不能覆写此路径。出版像素、字体解析、真实研究者任务和实际呈现性能不由准备度校验认证。
