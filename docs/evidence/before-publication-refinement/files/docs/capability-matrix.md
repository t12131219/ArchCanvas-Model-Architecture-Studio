# 首批真实能力矩阵

状态以2026-10-05正式目录代码及各自版本绑定的命令/工件为准。`通过` 表示有独立实现和可复核检查；`未认证` 表示不能作为支持承诺。

| 能力面 | 当前状态 | 真实边界与证据 |
|---|---|---|
| 运行入口与来源 | 通过 | `archcanvas_cli` / `archcanvas_python` 从正式目录 `src` 解析；`check_independence.py --build` 的 `/tmp` 报告检查 module origin、capability receipt 和发行源字节 |
| 静态源码分析 | Alpha 通过 | stdlib AST 子集；显式本地模块、字面量构造、模块层级、producer/consumer、具名 MHA 端口、固定tuple/list/dict输出路径、获证张量依赖旁路、bounded repeat/shared identity |
| Transformer gold | 通过 | 独立人工 oracle；多输入、self/cross attention、mask、7 个残差、2 个独立 Encoder layer、无源码 Softmax |
| MLP / Residual CNN / Vision holdout gold | 通过（有界） | MLP/CNN完整手写源码oracle独立11/11（含9项腐坏反例），家族holdout6项加output/bypass22项独立28/28；未知 Conv1d 保留 opaque。没有把 fixture 快照当作任意模型泛化保证，详见 [M4 验收](m4-completion.md) |
| 未知与动态结构 | 有界 | 动态控制、反射、未知 constructor、继承 forward、预算截断保留 opaque/diagnostic；不伪造 proven 关系 |
| Runtime execution / concrete shape | Linux CPU 本地通过 | 静态分析仍不执行模型；独立显式 `runtime` / `verify_structural` 使用冻结具名 shape/dtype/fill/seed/modes 和源码默认构造。真实 MHA Lq≠Lk、Q/K/V/mask 绑定、forward/backward、同种子结构/输出/梯度/state replay 已验收，均限于声明样本 |
| 执行隔离与环境绑定 | Linux x86-64 本地通过 | Mandatory Bubblewrap namespaces＋kernel seccomp，源 generation 只读，私有 scratch；Python exe/标准库/ELF closure 为私有只读字节副本，不暴露整 Conda/宿主目录；全部 venv 字节、依赖锁、解释器/adapter 摘要与执行后 freshness。真实越界文件/源码写、宿主 listener、子进程、CPU/timeout/cancel 和大内存分配反例通过；缺能力禁用 profile，无普通 subprocess fallback。内存为 per-process RLIMIT_AS，未配置 cgroup 聚合 RSS/tmpfs 总配额 |
| 模型状态观察 | 样本本地通过 | state_dict keys/shape/dtype、parameter/buffer、对象/存储共享组、train/eval 状态变化有独立手写测试；不加载或迁移 checkpoint，optimizer/scheduler/progress/random training state 分别列为未提供/未迁移 |
| CanvasDocument | 通过 | source/IR digest、canonical identity、display alias、节点/边样式、图例、注释、页规格、layout、pin、expanded frontier |
| 对象来源与共享/输出事实 | 有界通过 | inspector展示同instance不同call、repeat independent/shared instances、完整outputPath、opaque和source location；SVG metadata分开保存whole-source-architecture事实与实际rendered对象/bindings。sourceFacts独立5/5及Temporal/Skip/GNN真实存储重开→publication SVG链通过；source/IR与Canvas schema不变，Scene/SVG字节变，旧renderer收据不冒充当前 |
| Visual history | 通过 | 手势和当前局部确定性视觉指令共用 VisualOperation、undo/redo 和 document revision；没有通用 LLM 语言解析 |
| 层级展开 | Alpha有界，侵入布局修复已回归 | 同一scene projection、proxy ports、局部布局和pinned保护有core tests；真实浏览器Encoder展开保持原位。并排展开先以已有空位吸收增长，再推动剩余实际侵入，8项新反例与最新54项core回归通过；Transformer新序列空白1130→38px、scene高3474→2382px。已有保存布局/cache不自动迁移；当前39项浏览器工件已完整封存，出版人工审看和任意模型空间连续性仍未认证，见[修复记录](m4-expansion-intrusion.md) |
| 拖动预览路径 | 实现与CPU反例通过，体验未认证 | 开场校验/冻结gesture snapshot，每帧共用Scene/SVG；松开经guarded history，版本切换使旧gesture失效。300层独立CPU frame→scene p95 14.32→5.75 ms，完整Scene/SVG/commit/undo/redo一致；不替代native输入/DOM/FPS，见[专项](m4-drag-preview.md) |
| 画布缩放与实际手势 | 当前代表UI通过，完整门未认证 | 历史zoom按钮/节点移动+32/+20及undo/redo、收起重展开有[原几何记录](evidence/m4-actual-gesture-zoom-current.json)；当前hand/select工具和pointerup终点修复通过Studio68、strict TypeScript/build（`index-DWpF-img.js`）。[代表UI核对](evidence/m4-pan-annotation-work/ui-field-audit.md)确认Transformer+64/+40同viewport/publicSVG，四次v2 hand pan终点匹配，selection/history只核公开状态。native进行中cancel未采，持续DOM proxy不认证paint；reopen camera变/history reset |
| 保存与冲突 | 通过 | loopback server JSON CAS；storage revision 与 document revision 分离；immutable architecture/source binding；root 允许 loopback 环境 HTTP tests 通过，浏览器 alias 保存与刷新重开已实测 |
| SVG | 通过 | 当前 scene 的单一 SVG renderer，转义用户文本，publication 默认不含 editor controls；85/180 mm 字节和几何检查通过。本机中英混排实际 PNG 审看无缺字；黑白与全套黄金图待验收 |
| PNG / PDF | M2 本地通过 | 正式 `.venv` CairoSVG 2.8.2 仅从当前 SVG 派生；85/180 mm PDF MediaBox、PNG 像素与 300 DPI/pHYs 通过；receipt 绑定 scene hash、实际依赖来源和 Cairo glyph coverage。共享 Scene font 首选 Noto Sans CJK SC，字体仍依赖宿主；跨机器排字/嵌入未认证 |
| 参数审核与提交 | M2/M3 本地通过 | 显式 float literal Dropout.p/MHA.dropout，或唯一 module-top-level float 且全部读者为已注册概率参数；单 token 保格式改动，完整影响列表、独立 Expected/Observed、具体 review/HMAC approval、全 corpus/staged freshness、single-file journal/recovery。HTTP 只改受管理副本，CLI 写显式绑定 root |
| 局部连接事务 | M3 本地通过 | 保留同-base pure unary 条件式静态 API，G6 为 not_run；新 `structural-verified` 支持 entry-root 直线 unary/MHA 的 positional/keyword Name、具名 q/key/value/mask、明确 input specs、冻结独立整图 oracle、实际 producer/shape/dtype/梯度/状态核对，运行必需门失败不进入 ReviewReady。CLI/HTTP/Python prepare→review→approve→commit 共用守卫；异步 HTTP 可取消，不改原导入目录 |
| 激活替换 | M3 本地通过 | 无参 ReLU↔GELU constructor、完整影响作用域与独立结构 oracle；Studio/CLI 必须显式 CPU profile，保留实际 forward/backward/replay/state receipt；in-place/functional/带参/未知影响拒绝 |
| 动态连接 / 派生配置 / 多文件事务 | 未实现 | in-place、unknown call/state、控制流、nested/shared authored scope、alias/reassignment、未证明端口/type/shape 路径拒绝；派生/歧义配置和整数源概率 literal 拒绝；不承诺多文件原子提交、全程序执行或数学等价 |
| MCP adapter | 未实现 | Skill 文档描述合同，不存在可调用 MCP 工具 |
| Codex / Claude Code / DeepSeek Harness | 未认证 | Skill 指令包与引用已整理；三宿主 discovery/open/edit/save/export E2E 尚未实测 |
| Publication quality / performance | M4 partial，当前工件完整、人工与性能门未认证 | 当前Studio68/68、strict TypeScript/build与纯正式副本发行核对通过，JS `index-DWpF-img.js`；历史Python219、collector8、研究链12/sourceFacts5及观测工具32项各自分列。[当前完整矩阵](evidence/browser-visual-matrix-pan-annotation-full/manifest.json)36/36基础＋三模型各一编辑后，39case/234工件、coverage=complete、人工pending/false；[独立字段核对](evidence/browser-visual-pixel-observation-pan-annotation-full/field-audit.json)重建39份Canvas/DOM/publication SVG；[AI像素观察](evidence/browser-visual-pixel-observation-pan-annotation-full/pixel-review.md)不认证美观/解析字体/印样，CNN“skip p / ath.”英文断行仍需修正。三对edited save/reopen SVG一致但camera变/history reset，final rev54/22/39为后来再次配色/页宽/save/export；旧copy错误按完整Canvas唯一匹配实际服务导出修正，不称浏览器复采。Transformer L3/85mm minText2.53093pt/nodeLabel3.29021pt，旧rev23约2.896pt另scope。四pan终点匹配、离散p95 2008/2024ms，持续输入只有DOM proxy。固定硬件/解析字体、持续呈现、出版人工评分与3–5真人仍未认证；当前8881–8885五席0分配/采集/真人，旧zoom-final及其它包stale。见[M4出口](m4-completion.md)、[性能](m4-performance.md)、[协议](browser-visual-matrix-protocol.md) |

静态分析通过只说明支持子集的源码事实可恢复；样本运行通过只说明声明的 CPU 输入、模式和样本观测。两者均不把 opaque 区域变成可编辑源码。执行安装与命令见 [README](../README.md)，逐项阶段状态见 [完整 M3 出口](m3-completion.md)、[source oracle](source-oracle.md) 和 [acceptance ledger](acceptance.md)。
