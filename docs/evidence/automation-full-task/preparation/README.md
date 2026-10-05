# 当前 Transformer 完整任务的 automation 准备

这是独立工程冒烟，匿名 code 为 `AUTOMATION_M4_FULL`，kind 为 `automation`。不会计入真实研究者、180 秒成功率或人工出版验收。五个真实研究空席位 `.archcanvas/m4-research-trial-zoom-final` 未被分配或使用。

本轮包位于 `.archcanvas/m4-full-task-automation-final`。冻结的准备器仅接受 3–5 个席位，因此实际 prepare 3 个、first-port 8876；仅 S01 分配给自动化，S02/S03（8877/8878）保留空白。没有为单席请求改动冻结工具或手工裁剪包。准备与分配命令/结果见本目录 JSON。S01 assignment 只绑定初始基线，尚未开始 task timer。

包 manifest SHA256：`20ac2f84e912be44e1cc014999be145c5f39ff683164ad044ffbbe86c7d81448`。基线：

- documentId `canvas-architecture-model.Transformer-01ac6cd61f05-b0bd5bf0`，visual revision 0。
- sourceDigest `01ac6cd61f058e9de5230b0c371527a1fa2b4f73842019e0e5785d5f0deb0916`。
- irDigest `b0bd5bf01fa364bf415f6aba9707f5d74d9b7bb058534c0dac54fc48fd3729e6`。
- 开始只展开模型 root，无 alias/style overrides/annotations/pins，paper180。

## 开场

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --port 8876 \
  --data-dir .archcanvas/m4-full-task-automation-final/slots/S01/workspace/documents \
  --studio-dir studio/dist
```

打开 `http://127.0.0.1:8876/?study=1`，核对原始 Transformer 与 revision 0，保存实际 start 截图。记录器填写 code `AUTOMATION_M4_FULL`、类型“自动化冒烟”，再开始。不得选择 researcher，也不复用真人席位。实际截图与下载的 task JSON放入 S01/incoming，证据目录可另保存公开副本。

## 同一文档的五步与增强范围

按 [原有研究协议](../../../m4-research-protocol.md)执行，步骤只在真实完成后记录。

1. 展开 `repeat:instance:model.Transformer.encoder` 与 `call:instance:model.Transformer.encoder.0`，定位 `call:instance:model.Transformer.encoder.0.self_attention`。保存实际 step1。
2. 修改 Encoder 的 alias/fill，修改一条 legend 文字与颜色，添加并编辑 annotation。为补对象编辑合同，实际改一条已选 edge 的样式和页规格，保留变更前后 Canvas/DOM 与 step2，不把控件存在当操作证明。
3. 移动一个可见节点，固定另一对象（如 `input:model.Transformer:source_tokens`）；对实际完成的操作 undo/redo，保存 undo-before、undo-after、redo-after。核对目标字段与局部几何恢复，不能只检查 revision。
4. Save 后刷新重开，核对完整最终 alias、node/edge style、legend、annotation、pageSpec、layout/pins/frontier 和源码/IR。历史不跨刷新保留，因此 undo/redo应在刷新前完成。保存 reloaded与step4。
5. 从同一已保存最终文档导出当前 SVG 或 PDF，真实打开检查文字、连线、图例/说明、预定尺寸；保存 export-open与step5，再记录最后 checkpoint。若声称两种格式都检查，就分别真实导出并打开；不凭浏览器缩放认证真人真实尺寸审看。

最终导出后不要再编辑，否则需重保存/重导出。下载 ended task JSON。若 UI 卡点、超时或失败，如实记录并保留，不把 automation 改成真人，不改 checkpoint/timestamps 来满足 collector。

## 实际收集

服务导出存储在 `.archcanvas/m4-full-task-automation-final/slots/S01/workspace/exports/<artifactId>`。下面占位 artifactId/文件名必须替换为真实结果；start/final 必需，支持的其他 labels 可按实际提供。可重复 `--export-id`。

```bash
.venv/bin/python scripts/research_trial.py collect \
  --package .archcanvas/m4-full-task-automation-final \
  --slot S01 --participant-code AUTOMATION_M4_FULL \
  --study .archcanvas/m4-full-task-automation-final/slots/S01/incoming/m4-study-AUTOMATION_M4_FULL.json \
  --export-id ACTUAL_32_HEX_ARTIFACT_ID \
  --screenshot start=.archcanvas/m4-full-task-automation-final/slots/S01/incoming/start.jpg \
  --screenshot final=.archcanvas/m4-full-task-automation-final/slots/S01/incoming/final.jpg \
  --screenshot undo-before=.archcanvas/m4-full-task-automation-final/slots/S01/incoming/undo-before.jpg \
  --screenshot undo-after=.archcanvas/m4-full-task-automation-final/slots/S01/incoming/undo-after.jpg \
  --screenshot redo-after=.archcanvas/m4-full-task-automation-final/slots/S01/incoming/redo-after.jpg \
  --screenshot reloaded=.archcanvas/m4-full-task-automation-final/slots/S01/incoming/reloaded.jpg \
  --screenshot export-open=.archcanvas/m4-full-task-automation-final/slots/S01/incoming/export-open.jpg
```

CLI 不强制 input/screenshot 来源是 incoming，故操作者须保留实际来源说明。collector 只核选定字节/绑定与独立 SVG重构，PDF只核本地 receipt，不能证明捕获时间、操作身份、人工成功或 publication审美。collected空模板不写成真人 review。automation 自报即使 completed也继续排除 researcher分母。
