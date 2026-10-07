# Bc 最终构建：新准备包与只读跟进

当前准备包绑定 `index-BcFxpKDY.js`（SHA `98eae2934004ecaec4036f7b0746fb8304b3412c467b2417b68988dd4e4afe3a`）与 `index-NmgHfiF5.css`（SHA `0026e211728f2ae0aec210a2b2da0df06a46f068f0e26cbef5752ed3137dff2b`）。HTML SHA `221e58f1a35d1dbb21e2cdab0581be5f23bfcc7453886a8552dd8379efeeffc1`；当前 `AuthoringStudio.tsx` SHA `762ee90921f93be10cd744a4b4f3894162b61c78de4f6d5d3f158cfb02683edc`。

| 当前材料 | 冻结摘要与实际范围 |
| --- | --- |
| `.archcanvas/browser-visual-matrix-authoring-feedback-bcf/spec.json` | SHA `e1bbeee66de228eb2ad0ee4b901e0d41de2a9e87071c15da38118591a1bd224a`；schema1，`archcanvas-browser-visual-matrix/1`，9前沿/36基础候选、22实施绑定、72静态core文件、3build文件；本准备工作实际截图0/36、编辑后模型0/3。 |
| `.archcanvas/m4-research-trial-authoring-feedback-bcf/manifest.json` | SHA `3db788746efba54e53429f8a3b33920d8b86f7fc748957d7ac3d414200dec245`；schema1，`archcanvas-m4-trial-package/1`，70实施绑定、4baseline、5 pristine未分配席位，真人0。 |
| `source-only-followup-2.json` | 只读检查UI已有错误时仍可显示无效输入放弃信息，绑定当前UI副本与差异；没有新增测试或浏览器操作。 |

## 精确准备命令

以下四条命令已经执行，均exit0。目录已存在，后续只运行verify，不覆盖prepare。

```bash
.venv/bin/python scripts/browser_visual_matrix.py prepare \
  --core-dir docs/evidence/visual-golds-routing-refinement \
  --output .archcanvas/browser-visual-matrix-authoring-feedback-bcf
.venv/bin/python scripts/browser_visual_matrix.py verify \
  --matrix .archcanvas/browser-visual-matrix-authoring-feedback-bcf
.venv/bin/python scripts/research_trial.py prepare \
  --output .archcanvas/m4-research-trial-authoring-feedback-bcf \
  --slots 5 --first-port 8961
.venv/bin/python scripts/research_trial.py verify \
  --package .archcanvas/m4-research-trial-authoring-feedback-bcf
```

工作目录为正式工程。帮助合同沿用上一轮实际检查的同字节脚本；没有安装依赖、运行用户模型或调用旧原型。静态core13源码SHA、72个候选绑定及原core报告未变，所以保留已有source-bound静态图作输入；**不继承旧浏览器截图或研究结果**。36组合是Transformer L0–L3、MLP L0–L1、Residual CNN L0–L2各自彩色/黑白×85/180mm，另三模型各一独立编辑后要求。

矩阵verify只返回 `frozenFilesUnchanged=true` 与 `visualAcceptance=not-evaluated`；研究verify范围是 `frozen-baseline-and-implementation-only`，`researchGate=not_evaluated`。实际准备状态是 `prepared-no-participants`、`researchGate=not_run`。S01–S05端口元数据8961–8965，每席Canvas视觉revision0、storage revision1；无assignment、collected、incoming、exports、projects或transactions，reviewer为null，任务全部pending。没有启动服务或检查端口可用性；实际浏览器/hardware/fonts/viewport环境模板仍待观察。

## 与旧obx范围的关系

旧obx39个封存文件、旧独立审查15个封存文件逐字节未改。旧失败记录与Escape18观察由主代理保留；本代理没有把旧失败改成通过或据主代理消息宣称自己看过真实UI。

本次产品差异仅为UI新增 `discardInvalidInput`：在普通notice中显示放弃信息；如果已有error，信息也追加一次到error，以免footer的 `error || notice` 选择遮住提示。参数原始值/模型事实不因此更改，backend feedback仍保留。所有DraftField放弃回调使用同一函数，Escape、卸载和真正值替换继续显式提示。其余7项前一轮独立公共依赖SHA未变；10/10公共helper/API测试没有重复运行。只读跟进明确与主代理真实Bc浏览器复测分开。

原始 `*-prepare.txt` / `*-verify.txt` 与结构化receipt保留命令、时间、exit和SHA；`preparation-verification.json` 核70实施、4baseline与5pristine席位。`manifest.json` 冻结新准备文件、收据和源码副本，保存封存前后源码/build哈希。

完整36基础＋3编辑后当前构建矩阵、真实参与者五步任务与人审、六维出版审看、密集图物理尺寸阅读、持续presented性能及原生活动手势取消仍开放。本准备包不代表这些门已执行，主代理的代表UI回归也不会自动计作完整矩阵或真人使用者记录。
