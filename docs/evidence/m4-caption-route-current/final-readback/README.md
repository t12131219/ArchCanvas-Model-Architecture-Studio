# Caption/route 阶段最终只读回读

本目录独立回读 current checks、冻结证据、实际保存与 UI 导出及文档验收输出；不重跑产品测试、输入浏览器手势或执行模型。正式 research verify 只验证冻结实现契约，独立字节/目录检查仍单独执行。

严格 current scope 是 **105** 条 Studio 源码/测试/配置 + **3** 个 dist，共 **108**；另 **11** 条 publication inputs。current 路径和 build snapshot 各自 exact，不能以 snapshot 通过代替 current 通过。实际日志要求 Studio **389/389**、0 fail/skip/cancel，publication **11/11**、无 skip。

历史 current 条目只在其 exact 字节仍保存在已冻结的、相同 SHA/size snapshot 时接受：首 research-final-preparation 的旧 exporter 与出版测试已随修复过期，bytes 在 export-integration-repair/before 原样保留；正式 verifier 的 stale refusal 不是历史包字节损坏。新 research-export-final-preparation 必须在当前原路径 exact，不使用历史回退。旧 22 个包和所有失败日志保持封存。用于证据检验的历史 snapshot 不作为产品 runtime 或 fallback。

另核对最终实际存储 document **20** 与 original document **0**，仅 revision 不同，storage counter **1→3** 单独计；三份 UI export 的 document.json 必须与 final saved document 完全一致。root final browser 报告明确保留 Encoder 下移后 memory 文本/guide 消失、重开相机重新适配，以及连续性能、presented FPS、实体出版和真人仍未通过的限制。

13 current header 与 gate 的历史正文和 Markdown links 由 stage_docs 的独立 verify_entries 输出核验，本脚本回读其通过结果和绑定，不复制其算法。最后的 Skill 校验与文档 seal 同样保留实际 process/log 原字节。

最初 scoped attempt1 在外部 `/tmp/.../exports` 路径上错误调用 relative_to(project)，audit 抛出 ValueError；原脚本和日志保留。允许保留完整绝对外部来源路径后 scoped attempt2 **3486/3486**、3469 binding rows exact，仅当时文档更新尚未完成。最终完整 attempt3 **3882/3882**，**3852** binding rows、**2238** resolved exact inputs；当前正式包 verify exit **0**。独立入口验证最终 **335/335**，**561** Markdown links + **80** gate paths，Skill validator attempt2 exit **0**，scoped diff attempt2 exit **0**。两条文字修正（端点逃逸为 min(originalLead,6)、3 源模型 9 层级前沿）之后的 entry seal **82 artifacts +285 external** 亦逐字节通过。scoped 通过不冒充最终文档验收。

这些关系是字节、契约与文档范围检查，不是额外用户、产品 tests、实测连续输入或质量认证。**M4 仍 partial、真人 0、M5 not_started**；不把本阶段回读通过声明为完整 M4 gate 达成。

[最终报告](report.json)、[精确字节清单](manifest.json) 和 [原始最终 attempt](attempt-3-final/report.json) 保留完整范围；未覆写失败 attempt 或任何其他 sealed 证据。
