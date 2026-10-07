# 路由实施尝试记录

- 首次启动既有 focused 测试时，创建输出目录与启动命令错误地并行执行；shell 先遇到不存在的输出目录，没有运行测试。终端错误为 `../docs/evidence/m4-caption-route-current/router-work/existing-focused-attempt-1.txt: 没有那个文件或目录`，没有伪造该不存在的日志。
- 目录创建后 `existing-focused-attempt-2.txt` 真正运行 66 个既有测试，56 通过、10 失败。失败均为旧发布范围或纸图字节约束：只允许 collapsed-proxy residual 优化、缺 canonical 事实必须保留旧路径、旧纸图 path/derived label 原样。原件保留；父 Agent 在当前测试中显式扩大新通用几何规则的可用范围，并保留源事实/端口/样式/固定位置与独立几何要求，没有改历史 gold。
- `new-focused-attempt-1.txt`：15 条独立测试中 14 通过，1 条错误期望 Transformer L0 必须缩短。手工检查表明历史候选只约束冲突数量，新规则逐对保护具体交点/接触/重叠占据位置，因此正确地保留 L0。测试修正为明确检验保守拒绝，而未放宽几何 oracle。
- `new-focused-attempt-2.txt`：15/15。随后把新 shortcut 的交点与障碍容差从旧路由全局 0.01 独立收紧到 1e-7，并增加 0.005 世界单位移动交点反例、endpoint escape 和更多工作量边界。
- `new-focused-attempt-3.txt`：16/16；本次实施不运行最终构建或浏览器，最终全套由父 Agent 执行。严格 TypeScript 检查独立记录，不等同于最终 Vite 构建。
