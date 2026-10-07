# M4 草稿合并路由跟进

本轮为模型搭建草稿增加有限路由细化：共享路由器生成初始路径后，小规模草稿尝试有界网格绕行，检查模块体穿透、不同来源的折点接触和叠线。五边 Input A/B→Add→Concat→Output 实际浏览器复核已消除原 (614,220) 交叉，边身份和生成源码保持一致。

证据：

- [独立合同与边界](evidence/m4-draft-merge-routing-work/independent-contract-attempt-1/README.md)
- [本轮跟进机器状态](evidence/m4-human-review-handoff-status-followup.json)
- [浏览器原始记录](evidence/m4-draft-merge-routing-work/browser-attempt-2/manifest.json)
- [最终专项收据](evidence/m4-draft-merge-routing-work/checks/target-attempt-2/receipt.json)
- [全套与构建收据](evidence/m4-draft-merge-routing-work/checks/suite-attempt-1/receipt.json)

[逐图审查](evidence/m4-draft-merge-routing-work/visual-review-attempt-1/final-review-receipt.json)亲看14张 JPEG：清晰总览、重开和四向移动中五节点五边完整，未见穿体或不同来源交叉；横向平移有端点裁切，局部缩放两帧像素/DOM 不一致，生成后的旧 final-fit 图仍含弹窗。清晰补帧独立保留，失败图不改。A→Concat.b 多弯长绕行仍是审美问题。

[真实性能能力审计](evidence/m4-performance-next-audit-attempt-1/README.md)确认当前 browser2/tab60 无 trace/CDP；1秒rAF节律不等同呈现 FPS，性能门仍未认证。

范围仍是有限小图：不推广为任意布局无交叉或最少折弯，不认证性能、物理出版或真人研究任务。M4 partial，M5 未开始，真人 0。
