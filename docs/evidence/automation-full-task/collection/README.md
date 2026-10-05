# 自动化完整任务的原始收集层

这里公开 S01 / `AUTOMATION_M4_FULL` 的真实 collect 原件。5/5 checkpoint 为自动化自报完成；最后 elapsed=1,230,519 ms，UTC 起止差及 collector duration=1,230,520 ms，差 1 ms。它不是 180 秒真人成功样本，真人分母为 0、researchGate=not_run。

- [收集清单](collected/manifest.json)与[根 collect receipt](../collect-receipt.json)逐字节一致。
- [task](collected/task.json)、[保存文档](collected/final.canvas.json)、[保存 envelope](collected/final-storage.json)、[collector audit](../collector-audit.json)提供身份、checkpoint、源码/IR、最终 revision 与工件绑定。
- `incoming/` 27 文件、`collected/` 21 文件、`workspace-exports/` 6 文件、`baseline/` 4 文件，加 package-manifest / assignment / final-workspace-storage 共 61 个原字节副本；未修改 JSON、截图或 receipt 内的原路径。
- [SVG](collected/exports/77de76b8a527438c83c0348e8b22ad4a/figure.svg)与[PDF](collected/exports/764e8fd549874a8a8f6fc702038ec0e0/figure.pdf)输入均为同一最终保存文档，visual revision18 / storage revision2。19 个 collector 工件的 SHA256 与字节数全部匹配。
- [独立 Scene 重核](scene-recheck.json)从最终文档重建两次 Scene，并由冻结 formal publisher 规范化 SVG；实际 SVG 85,287 bytes 完全一致。PDF仅验证输入、receipt、header和输出摘要，没有独立重新转换或内容认证。

独立按原字段定义重算 sourceDigest=`01ac6cd61f058e9de5230b0c371527a1fa2b4f73842019e0e5785d5f0deb0916`、IR=`b0bd5bf01fa364bf415f6aba9707f5d74d9b7bb058534c0dac54fc48fd3729e6`；两份 .py 与 frozen source、formal fixture、architecture.source.content 字节一致，完整 architecture 与 baseline 一致。保存前后 reload 的 envelope 也逐字节一致。55 实现与4 baseline冻结文件未改；S02/S03仍保持 pristine baseline。

checkpoint2 在 rev9；后续 color-style 的 rev14 和 undo-before 的 rev15 才记录 FFN 展开/edge18样式。不能把后续追加的样式归到 checkpoint2 的完成时刻。最后三个 checkpoint 为 rev18；原始记录保留这条时序。

此层通过的是收集绑定，不能覆盖[独立字段审计](../independent-field-audit.json)对局部布局与屏幕连续性的失败项或未知项。截图摘要不证明捕获时间/真实性；reviewer仍null，7个收集截图的contentReview仍pending。没有为真人或视觉审阅填入通过结论。

已查看保存的[SVG打开截图](incoming/export-open.jpg)：图形可见，85 mm minTextPt≈2.828、nodeLabelPt≈3.676，文字很小；注释跨 Add/残差区域。保存的[PDF打开截图](incoming/PDF-open-blank.jpg)是空白暗色画面，不能证明PDF内容可读。85 mm测量不构成出版质量认证，宿主字体/整形和连续输入绘制仍无独立认证。

本审计没有重复 collect，没有改冻结 manifest、current-verification、产品代码或其他审计文件。`verify --package`只验证冻结 baseline/implementation；它的 prepared-no-participants 是不可变准备快照，不能解释为当前没有这条 automation assignment。该 CLI 也不审计 collected 内容，后者由本收集层单独核查。
