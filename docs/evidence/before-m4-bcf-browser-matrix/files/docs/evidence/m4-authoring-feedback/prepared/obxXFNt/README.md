# 当前构建的准备包

本目录保存正式工程 **index-obxXFNt_.js / index-NmgHfiF5.css** 的视觉矩阵与五席研究任务包准备证据。两个 `prepare` 和两个 `verify` 均 exit 0；没有控制浏览器、收集截图、分配真人或启动席位服务。现有状态文档和已封存独立验收 manifest 未改。

| 文件/合同 | 版本与 SHA256 |
| --- | --- |
| JS | `index-obxXFNt_.js` · `f973e423b493a440815297a2ff268f20848269153335a11799852052e42a17ec` |
| CSS | `index-NmgHfiF5.css` · `0026e211728f2ae0aec210a2b2da0df06a46f068f0e26cbef5752ed3137dff2b` |
| HTML | `304b6772abdcdd64ed869a845875001863463a17bd0dfb6903d2939d74e5d855` |
| 矩阵 spec | `schemaVersion=1`，`archcanvas-browser-visual-matrix/1`；SHA `813cb2cdbed59688ba110e104163a5819c9574685beb4ff1049ad2d155fe6aa4` |
| 研究 manifest | `schemaVersion=1`，`archcanvas-m4-trial-package/1`；SHA `7088bdbfea61025dfdd3c6715c35fa35cb862a417f3e39f445606e393c1acd99` |
| 正式准备运行时 | Python 3.11.5，正式 `.venv/bin/python`；Node v24.19.0；analyzer origin 位于正式工程 `src/archcanvas_python/frontend.py`。这不是浏览器环境记录。 |

## 新视觉矩阵

路径：`.archcanvas/browser-visual-matrix-authoring-feedback-obx/`。包含 spec、空采集模板、待采集任务及空 screen receipt 模板。9 个实际源码前沿：Transformer L0–L3、MLP L0–L1、Residual CNN L0–L2；各组合 paper/monochrome × 85/180 mm，共36基础配置。另要求三类模型各一份独立编辑后工件。

当前 core 的 13 个源码文件 SHA、既有 72 个静态 candidate 文件绑定、已完成 core report SHA 均与上一轮匹配，因此沿用这些静态 source-bound 候选作新矩阵的输入。新 spec 重新冻结实际3个 build 文件、22个矩阵相关实施文件和72个静态候选；**没有继承任何历史浏览器截图、编辑操作或人工结论**。矩阵实施字段的22项不是全产品源码列表；实际 bundle 字节以及全产品准备绑定另由70项研究 manifest共同记录。

已经实际执行的命令如下；准备目录已经存在，后续只运行 verify，不重复 prepare 覆盖。

```bash
.venv/bin/python scripts/browser_visual_matrix.py prepare \
  --core-dir docs/evidence/visual-golds-routing-refinement \
  --output .archcanvas/browser-visual-matrix-authoring-feedback-obx
.venv/bin/python scripts/browser_visual_matrix.py verify \
  --matrix .archcanvas/browser-visual-matrix-authoring-feedback-obx
```

`verify` 返回 `frozenFilesUnchanged=true`、`visualAcceptance=not-evaluated`。没有执行 collector：实际基础截图 **0/36**，编辑后模型 **0/3**，人工审看0。spec 的 `visualAcceptance=pending-human-and-browser-review`。

## 新五席研究包

路径：`.archcanvas/m4-research-trial-authoring-feedback-obx/`。包有70项实施文件绑定、4个 baseline 文件、S01–S05 五个独立 pristine workspace；端口元数据8951–8955。每席 `participantCode=null`、`assignment=unassigned`、Canvas视觉 revision=0、存储 envelope revision=1，与共同 baseline逐字段相同。所有 review任务待定，incoming/exports/projects/transactions空，无 assignment 或 collected。`researcherCount=0`、`researchGate=not_run`，`state=prepared-no-participants`。

```bash
.venv/bin/python scripts/research_trial.py prepare \
  --output .archcanvas/m4-research-trial-authoring-feedback-obx \
  --slots 5 --first-port 8951
.venv/bin/python scripts/research_trial.py verify \
  --package .archcanvas/m4-research-trial-authoring-feedback-obx
```

`verify` 返回 `baselineAndImplementationUnchanged=true`，范围为 `frozen-baseline-and-implementation-only`，研究门 `not_evaluated`。新增 helper 已包含在70项实施绑定；旧包的69项绑定不被提升为当前。

此包维持原 M4 从未编辑 Transformer图开始的五步研究任务：展开找 attention、改别名/样式/图例/说明、移动与固定并撤销重做、保存刷新、导出并看实际尺寸。它不等于从空白搭建模型的新手测试，也没有为代理填写真人席位。只有真实参与者实际开场时才执行 assign；AI探索使用其他 automation证据目录。

席位服务尚未启动。一次只读 loopback socket可用性检查被沙箱拒绝在创建socket之前，记录为 `PermissionError [Errno1] Operation not permitted`，因此端口可用性未验证。准备器只分配端口元数据，不证明对应服务在线。未来需要服务时，先验证包并根据实际可用性处理；S01启动命令的已确认接口是：

```bash
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --port 8951 \
  --data-dir .archcanvas/m4-research-trial-authoring-feedback-obx/slots/S01/workspace/documents \
  --studio-dir studio/dist
```

## 原始证据与开放项

`help-*.txt` 与 `help-receipts.json` 保留正式脚本的实际帮助和命令接口。`matrix-prepare.txt`、`research-prepare.txt` 是脚本原始 stdout；`*-receipt.json` 保存执行时间、命令、exit和日志摘要。`preparation-verification.json` 另核70项实施、4个baseline、5个pristine席位、历史 spec/manifest未改以及已封存反馈证据15项文件未改。`manifest.json` 冻结本目录和新准备包的文件字节，并保存封存前后实施哈希。

开放项仍包括当前构建的36基础＋3模型编辑后真实浏览器工件、操作时实际 viewport/DPR/硬件/字体证据、六维真人出版审看、密集图实际尺寸阅读、持续 input→presented性能、原生活动手势取消，以及3–5真实研究者任务及独立复核。静态候选、prepared workspace和verify成功不完成这些门；M4状态未由本操作提升。
