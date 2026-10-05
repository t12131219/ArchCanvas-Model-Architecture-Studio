# 当前研究试用开场材料

本材料绑定当前 `index-Cr_xKW9U.js` 和 `.archcanvas/m4-research-trial-boundary-final`。它是主持人开场清单，不是参与者、完成记录或人工验收。此次只读核对报告为 [readiness-report.json](readiness-report.json)，正式包 `verify` 与当前 21 项研究专项、12 项独立工件链反例日志见 [process.json](process.json)。五席保持未分配；旧包、测试临时席位和 AI 操作不能计入样本。3–5 个子代理可以另做标明 automation 的模拟可用性检查，其数量和相互独立不使它们成为真实研究者，也不能填真人完成率或人工出版结论。

## 开场前

1. 主持人邀请 3–5 位实际模型制图使用者，保留匿名代码、开场席位和研究范围；不要把自动化操作标为 researcher。本轮尚未邀请或联系任何人。
2. 在固定的一套浏览器/硬件/字体/viewport/DPR 上完成本轮。将包中的 `environment-template.json` 复制为 `environment.json`，逐项记录真实观察和字体解析证据。未知项保留 unknown，不从 `preparationRuntime` 或 CSS 字体名称推断固定字体。
3. 从正式目录执行以下只读核对。包 verify 只核 frozen bytes；补充审计进一步核五席基线 envelope、空 incoming/exports/projects/transactions、未分配/未收集和空审看模板。补充审计只适用于第一次实际分配前，任何席位开始后保留该事实并停止用“全部 pristine”作为本轮现状。

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
.venv/bin/python scripts/research_trial.py verify --package .archcanvas/m4-research-trial-boundary-final
.venv/bin/python docs/evidence/m4-research-readiness-work/audit_readiness.py \
  --project . --package .archcanvas/m4-research-trial-boundary-final
```

4. 当前 slot mapping 为 S01→8901、S02→8902、S03→8903、S04→8904、S05→8905。查实际端口占用，已有进程时停止开场，勿覆盖别人服务。只给实际已到场的参与者分配新的席位；无需、也不可预先填虚构代号。
5. 若源码/build/基线变更，停止使用本包，保留原字节及已开始记录，另建新目录；不编辑 manifest 摘要以继续。

## 参与者到场才执行

S01 为一份具体示范；主持人把 `R01` 换为真实开场的唯一匿名代码，后续改为 manifest 中的新席位和端口。

```bash
.venv/bin/python scripts/research_trial.py assign \
  --package .archcanvas/m4-research-trial-boundary-final \
  --slot S01 --participant-code R01 --kind researcher
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --port 8901 \
  --data-dir .archcanvas/m4-research-trial-boundary-final/slots/S01/workspace/documents \
  --studio-dir studio/dist
```

独立浏览器 session 打开 `http://127.0.0.1:8901/?study=1`。主持人先核 revision=0、Transformer 总览、无显示 alias/style overrides/pin，保存实际开场截图再计时。服务命令保持前台，结束后用该进程的正常终止方式停止；本材料未启动任何席位服务。下一人使用新的席位/端口/session。点击“开始下一份记录”不会重置服务文档，不可复用旧席位。

## 给参与者的任务卡

请在 3 分钟内，从当前未编辑的 Transformer 总览完成以下任务。可以记录卡点；超时或放弃也提交记录，保留在分母。不要改模型源码。

1. 展开 Encoder 和第一层，找到 self attention。
2. 修改 Encoder 的显示别名和填充；修改一条图例和说明文字。
3. 移动一个对象，固定另一个对象；撤销并重做一次。
4. 保存并刷新，核对别名、样式、图例和固定位置。
5. 从最终保存文档导出 SVG/PDF，打开文件，检查文字、连接与最终尺寸。

每一步在研究面板自报完成；结束或放弃后下载 task JSON 到本席位 incoming。主持人保存 start、final、五个 checkpoint、undo-before、undo-after、redo-after、reloaded、export-open 的实际截图。源码/IR/sourceBinding 不应变化。保存/导出后如果继续编辑，要重新保存并导出后再记录末步。完整命令及导出 artifactId 的取得方式在正式 [m4-research-protocol.md](../../m4-research-protocol.md)；不要把占位 artifactId 或旧席位文件当实际证据。

## 独立复核卡

实际复核者复制本席位 `collected/review-template.json` 为 `review.json`，记录独立 reviewer 匿名代码、逐步证据路径和观察事实。脚本通过、五次自报、合法摘要或截图文件签名都不能替代以下事实：

| 任务 | 人工要确认的事实 |
|---|---|
| 1 | 真实 UI 中已找到 self attention；展开身份属于本基线，未凭名称补图。 |
| 2 | 实际 alias/fill/legend/annotation 结果可见并与最终 Canvas 一致。 |
| 3 | 目标移动、另一对象 pin，以及 undo/redo 的真实前后恢复有证据。 |
| 4 | 保存刷新后的视觉字段和 pin 保留；不能用当前文档猜测发生过刷新。 |
| 5 | 打开本席位实际 SVG/PDF，以所选 85/180 mm 尺寸阅读文字/线条/图例，核连接与无裁剪。 |

缺少的观察填 missing/unverified；不是成功，也不能只挑成功者。研究摘要只汇总 self report，仍等待独立工件复核。任务完成率和浏览器 input-to-paint/FPS 是不同指标。M4 人审还包括当前39例黄金矩阵的版式、层级、留白、色彩/黑白、字体、连线及真实尺寸阅读；这份研究任务卡不自动完成矩阵出版门。

## 本次工程核对与仍需外部事实

- 当前机械准备可用：61 implementation bindings、4 baseline files、五个独立 envelope/端口、空 blank reviews；当前专项与独立反例均通过。没有分配参与者，没有启动服务或操作用户8765。
- 仍需真实人：3–5位实际使用者的完整任务、时间/卡点/放弃记录、独立复核者对实际工件逐项结论，以及39例出版审看。
- 仍需目标环境的真实测量：固定已解析字体/硬件、持续 presented paint、代表 input-to-paint 和 held-down active cancel。当前调度诊断、CPU核心时间和此空包都不能补足它们。

因此 `researchGate=not_run`、`humanSuccessCertified=false`；本材料不改变 M4 partial 或已有 seal。
