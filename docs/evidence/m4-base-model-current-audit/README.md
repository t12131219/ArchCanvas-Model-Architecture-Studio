# M4 当前基础模型独立静态审计

[report.json](report.json) 记录当前正式 MLP 与 Residual CNN 的独立 11/11 静态 oracle 运行，无失败、错误或 skip。其中两项核对完整模型，九项主动破坏端口、producer/tensor、containment、shared instance 与 repeat metadata 后要求明确拒绝。既有产品、测试和历史报告没有修改。

| 模型 | 节点 / 边 | 声明端口 | tensor producer | call / instance | opaque |
| --- | ---: | ---: | ---: | ---: | ---: |
| MLP | 8 / 8 | 13 | 5 | 6 / 6 | 0 |
| ResidualCNN | 24 / 24 | 43 | 19 | 19 / 17 | 0 |

本次复制正式 `src` 的 Python 源文件、两份手写 oracle/checker 和三个 fixture 源文件到新的 `/tmp/archcanvas-base-model-current-t5psll12/release`，从该独立工作目录使用正式 `.venv/bin/python -I -S -B`。`sys.path` 只额外加入 copied `src` 与 copied `tests`；正式 package 与测试的实际来源均位于副本，没有 failed Temp/prototype 或 site-packages 路径。fixture 仅作为 AST 输入读取，未导入或执行。审计还以标准库 audit hook 拒绝 fixture/framework import 和 fixture source execution；本次没有这类尝试。

完整临时运行内容已逐字保留在 [run](run/)：正式输入原字节、`input-manifest.json`、`runner.py`、确切命令、stdout/stderr、两模型的 Architecture 与归一 proof，以及原始隔离/来源报告。保留的报告仍记录实际 `/tmp` 路径，未重写 provenance；`run/<relative path>` 可解析这些临时运行内容。报告核对全部 copied 输入和正式输入在运行前后不变，所选旧 base-model/holdout 报告也保持原字节。

复核时从正式工程根执行，使用新输出目录：

```bash
python docs/evidence/m4-base-model-current-audit/audit.py \
  --output /tmp/archcanvas-base-model-current-audit-next
```

此审计只证明两份声明源码的静态节点、端口、关系、参数、source range、containment、repeat、instance/call 和 producer↔tensor 合同。它不认证每个 parameter origin、具体 shape/dtype、数值或 forward/backward 等价、任意模型、浏览器性能、实际 paint、出版可读性或真人验收，不能单独宣布 M4 完成。
