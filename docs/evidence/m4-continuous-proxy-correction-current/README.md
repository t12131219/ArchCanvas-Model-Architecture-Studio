# 连续 DOM 观测代理修正证据

本目录记录测量工具修正，当前产品仍为 memory continuity 的 CU5 构建；M4 partial、M5 not_started、真人0。见[阶段说明](../../m4-continuous-proxy-correction.md)。

- [正式组合测试](formal-constraint-attempt-1.tap)：71/71（原27＋新增44），exit0、fail/cancel/skip0；不计入 Studio436。
- [独立反例报告](independent-report.json)与[审查说明](independent-review.md)：13有限字节绑定；历史 baseline39 unmet/5wrapperexcluded 是新合同断言，不等于39产品bugs。首轮file-level日志原样保留。
- [只读重放](replay-attempt-1/report.json)：33/33关系、17/17逐输入exact，pan/drag/wheel p95为994.9/1716.1/45.2ms；首次DOM变化不是因果input-to-paint或presented FPS。
- [root 有限读回](root-final-readback.json)：independent13/13、replay8/8、product129/129 字节exact，TAP/报告范围确认，不额外跑测试。
- [原测量代码快照](before-change/manifest.json)：旧validator、原27测试与expected-proxies保留。原26/29报告、no-input失败及历史raw不改绿、不回写。
- [研究清单有限确认](entry-update-work/research-listed-bindings-readback.json)：87/87列明implementation字节exact，两个validators不在清单，不是研究协议重跑或新readiness。
- [文档更新前快照](entry-update-work/before-entry-inputs/manifest.json)：三条旧路径供memory旧248seal明确解析；[文档读回](entry-update-work/document-readback.json)、[新文档seal](entry-update-work/document-seal-final-attempt-1/manifest.json)仅认证本次有限范围。

产品129绑定exact来自重放；本次未新采浏览器、未重跑Studio/publication、未执行模型或增加真人。saved-frontier scope仍[仅设计](../m4-frontier-cache-analysis-next/README.md)，旧collapse候选与失败保持。
