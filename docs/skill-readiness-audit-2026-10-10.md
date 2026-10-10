**ArchCanvas Skill 开发完成度审核 · 2026-10-10**

结论：当前项目具备可用的本地 Studio 和有界模型编辑基础，但尚未满足原技术计划中的完整 Skill/Beta 验收要求。适合标为“本地试用版：受限静态源码制图、视觉编辑、草稿建模和经审核的局部语义变更”，不宜标为“三宿主已验证、安装即可一句话打开任意模型的成熟 Skill”。

审核对象是正式工程 `/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio` 的当前工作树，包括未提交修改；Git HEAD 为 `2a8cee94`。另行检查了本机会话加载的 `/home/fzg/.codex/skills/archcanvas`、冻结的 Beta.2 发布包，以及用户先前提供的两个模型。未读取或运行失败的 Temp 原型；未安装到用户实际宿主目录、未修改用户模型、未提交语义事务。

**审核基准与参考版本**

- [原技术计划书](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_双向模型可视化与编辑框架_技术计划书.md:1186)：M0–M5 出口、最小产品闭环、首次制图、性能、真人任务和三宿主验收。
- [当前 Skill 契约](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/skills/archcanvas/SKILL.md:29)：运行时发现、同一画布、未知区域、视觉与语义修改的边界。
- Tavotto 使用本地参考源码的 [Skill](/home/fzg/PycharmProjects/ArchCanvas/Source_Code_Project/Tavotto/codex-plugin/skills/tavotto-figure/SKILL.md:15) 和 [插件说明](/home/fzg/PycharmProjects/ArchCanvas/Source_Code_Project/Tavotto/codex-plugin/README.md:1)。未对 Tavotto 做实际运行认证，也未假定本地快照等于其远端最新版。
- Archify 使用用户指定 GitHub 仓库，固定到 [7f483b61e8f68d0d5c3219d2c943c5381c8db0b1 的 Skill](https://github.com/tt-a1i/archify/blob/7f483b61e8f68d0d5c3219d2c943c5381c8db0b1/archify/SKILL.md)，提交时间 2026-10-09；README 标识 stable 3.0.1。本机另装的旧版 Archify 没有被当作该远端版本。

参考项目的指令作为审核证据，未当作用户对执行、安装或源码写回的授权。

**发现与优先级**

1. **P1：本机加载的 Skill 缺少确定的运行时绑定，复制说明文件不足以交付画布。** `/home/fzg/.codex/skills/archcanvas` 没有 `scripts/archcanvas_runtime.py`、`archcanvas-install.json` 或内嵌 runtime。其 [第 10 行](/home/fzg/.codex/skills/archcanvas/SKILL.md:10) 的 `../../docs/m5-beta-release.md` 实际指向不存在的 `/home/fzg/.codex/docs/m5-beta-release.md`。运行时参考还混杂多轮历史状态与指向开发目录的链接。结果是 Agent 能发现 Skill 名称，却不能仅凭该副本确定可执行入口和对应版本。

   项目并非没有安装实现：[安装器](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/scripts/m5_host_install.py:254) 会写入安装合同、生成相对路径 launcher，并重写资源链接。本次在临时目录独立校验、解包、安装 Beta.2、再次 verify，并调用安装后 launcher 的 capabilities，均成功。问题在于当前加载方式仍是 instruction-only，且用户入口没有明确区分“只复制 Skill”与“安装完整发布包”。应统一推荐安装路径，安装后用 doctor/capabilities 明确返回版本、运行时位置、Studio 状态和下一步。

2. **P1：缺少确定打开目标文档并继续改图的程序入口。** 当前 CLI 提供 `capabilities/analyze/patch/serve/runtime`，没有统一的 open/session/visual-apply 入口。启动 Studio 后，[App 初始化](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/App.tsx:376) 依赖 localStorage 恢复活动文档，否则打开上次或默认例子，没有发现按 URL/documentId 精确选择目标的路径。HTTP 能保存完整文档，但不是与前端同源的逐条视觉操作接口。

   因而“启动服务并打开 URL”不能证明打开了用户指定模型。Agent 仍需编排分析、导入和浏览器交互；现有 UI 操作可以完成局部流程，但缺少像 Tavotto `open_figure(project_path, stem) → session_id` 一样稳定的交接合同。建议先提供 CLI 或 HTTP 的 `open(source, entry) → documentId/sessionId/url`，以及复用前端类型操作和历史的 `apply/read/save/export`。MCP 是可选适配层，缺少 MCP 本身不是不合格依据。

3. **P1：当前开发版、冻结发布包和验收记录不能互相替代。** 当前模块库是 74 个原子模块、23 个透明起点；实际 Beta.2 包仍是 17/3。[Beta.2 说明](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/m5-beta2.md:7) 也明确记载 17/3。当前重新构建得到 `index-C_IPbSCh.js` / `index-CZR1k8bj.css`，与 [M5 完成收据](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/m5-completion-v1/receipt.json:19) 绑定的 `index-B1nPLV0h.js` / `index-dmzfR53F.css` 不同。Beta.2 SHA256 本次核对成功，但只能证明那个冻结包。

   应将 74/23 明确标为当前工作树能力，重新冻结版本并对新包做安装与宿主验收。不要用旧包的通过记录证明当前未提交实现已经可发布；Skill 的能力描述也应按实际 runtime 协商，避免把 74/23 用于旧包。

4. **P2：兄弟 `--data-dir` 目录不能隔离完整工作区。** [服务构造器](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/src/archcanvas_cli/server.py:202) 把该参数用作文档目录，却把其父目录用作 projects、exports、drafts、transactions 的根。设置 `/tmp/X/alpha-documents` 与 `/tmp/X/beta-documents` 会隔离 documents，但共享其他状态。本次用真实存储构造和读写复现：A 保存草稿，B 能读到同一草稿；只替换了 HTTP socket 初始化，未把此项冒称为双服务 HTTP 端到端验证。

   建议参数改为完整 state-root，或显式区分 state-root 与 documents-dir 并拒绝碰撞。修复前，应使用 `<独立项目>/.archcanvas/documents`，为每个实例保留不同父目录；遵守一个状态根只运行一个服务进程的限制。

5. **P2：导出失败不能保留上一版完整成果。** [导出脚本](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/scripts/export_canvas.mjs:52) 先覆盖 SVG/PDF/PNG，再写 receipt。将 receipt 路径设为已有目录后，命令退出 2，但旧 SVG 已被新 SVG 替换。这会让失败结果混入上一版正式交付。

   建议在同目录暂存和校验产物、回执，再提交；失败时保留上一组可用文件。为产物和回执提供一致的提交/恢复合同，而不是只对单个文件做写入。

6. **发布门仍未完成，测试数无法补足。** [完成收据](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/m5-completion-v1/receipt.json:4) 明确是 `complete-local-beta`，`publicRelease=false`、真人参与数为 0、publicationReviewCertified 为 false；三个实际宿主客户端 E2E 均为 `not-tested`。既有浏览器证据有价值，但不能证明当前版本已满足全部性能目标或真实使用任务。

   原计划要求的 300 可见对象 p95 ≤50ms / ≥50fps、中等展开 p95 <500ms、3–5 名研究使用者任务、85/180mm 真实尺寸人工审看，以及 Codex/Claude Code/官方 DeepSeek Harness 实际发现→打开→改图→保存→导出→语义提案，仍需分别关门。允许在这些门未完成时继续开发，不等于取消这些发布要求。

**用户现在可以怎样使用**

| 使用方式 | 当前支持与条件 |
|---|---|
| 给模型源码生成视图 | 指定源码根和 `module:Class`，静态分析后导入 Studio；不需要为静态图执行模型，也不应强制要求输入 shape。未知结构显示为 opaque。 |
| 手动改论文图 | 在同一 CanvasDocument 中改显示名、颜色、图元、边样式、图例、注释、位置、页规格，展开/收起、撤销、保存和重开。属于视觉操作，不需要源码审核。 |
| 用文字改图 | 当前 UI 有对所选节点的有界指令，例如“设为蓝色”“命名为…”“向右移动 24”“展开/收起/固定”，与手势共用操作历史。不是任意自然语言都可执行，也不是已提供宿主对话到画布的完整工具 API。 |
| 从零搭建模型 | 当前工作树可使用 74 原子模块和 23 透明预设；保存独立 authored draft，验证声明的张量和连接，查看生成源码，打开新 managed model。该验证不等于执行成功；旧 Beta.2 是 17/3。 |
| 编辑当前源码视图 | 使用“编辑当前模型”，导入可恢复的 source-derived draft 并保持受支持的布局/样式/历史。这不自动授权把任意草稿结构覆盖回原源码。 |
| 修改模型语义 | 仅对注册合同支持的 literal/config 概率参数、默认 ReLU/GELU 替换和局部 RebindInput 走准备→验证→具体 diff 审核→批准→提交。需要执行的门必须显式配置隔离 runtime。批准不把 unsupported 变成 supported。 |
| 写原件还是副本 | HTTP 编辑围绕上传后注册的 managed copy；CLI patch 可针对明确绑定的源根，但仍受具体审批、摘要新鲜度与恢复合同约束。应在操作前说明实际修改目标。 |
| 导出 | 由当前 document/scene 导出 SVG/PDF/PNG；PDF/PNG 取决于可信解释器、CairoSVG/native Cairo 和字体。当前机器通过导出检查，不代表所有平台同样可用。 |

不在当前支持承诺内：任意动态 Python 的完整恢复、任意 PyTorch 模型全面往返编辑、任意训练/checkpoint/优化器迁移、无需运行时的完整交互画布、公开多用户云服务。Skill 的加载不会额外授予模型执行、安装或源码提交权限。

当前开发检出可按已有文档这样启动（现有前端已构建，本次未覆盖原 dist）：

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve \
  --host 127.0.0.1 --port 8765 \
  --data-dir /path/to/independent-project/.archcanvas/documents
```

打开 `http://127.0.0.1:8765` 后，通过 Studio 导入真实模型。此命令仅启动画布服务，不会自动指定目标模型。缺失依赖或构建时按 README 配置。完整分发应使用 [校验并安装发布包的路径](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/m5-beta2.md:13)，而不是只复制 SKILL.md；本次审核没有替用户执行实际安装。

可以向 Agent 说：“使用 archcanvas，静态分析这个目录的 `module:Class`，打开对应模型的可编辑画布，保留未知区域，不执行模型。”对现有画布则说：“把当前 Encoder 改成蓝色，保存并导出 180mm SVG/PDF。”前者需要可定位的正式 runtime 和具体模型导入；后者需要 Agent 能访问同一活动文档。当前指令包不能单独保证这两条宿主流程完成。

**用户提供的两个模型揭示的真实导入边界**

本次只调用静态 AST 分析，没有导入或执行模型：

| 源码入口 | 实际分析结果 | 影响 |
|---|---|---|
| `pytorch_transformer_original` / `transformer:Transformer` | 10 节点、14 边；3 个 opaque 区域，包括 `self.encode`、`self.decode` 和 OpaqueModule | 无法据此声称已恢复完整 Encoder/Decoder/Attention 可编辑内部结构。 |
| `PatchTST/PatchTST_supervised` / `models.PatchTST:Model` | 4 节点、3 边；1 个 ConditionalRegion opaque 区域，configs/条件初始化未充分解析 | 当前入口只能给出有限视图，不能声称完整 PatchTST 内部图已由源码自动恢复。 |

这是当前分析器的已声明覆盖边界，不应把保留 opaque 本身当作造假；74 个编辑原子模块也不能证明能自动导入所有对应源码形态。要让这两个模型成为主要示范，需要补充配置/方法调用/条件分支的 source lowering，并为真实项目建立独立关系预期。不要用教材模板或手工 SVG 替代来源证据。

**对 Tavotto 与 Archify 的可借鉴部分**

| 维度 | Tavotto（本地源码参考） | Archify（固定 GitHub 版本） | ArchCanvas 当前 |
|---|---|---|---|
| 确定入口 | health → open_figure → session_id | candidate → 单次 finalize → HTML + receipt | capabilities/analyze/serve 已有；目标文档打开和宿主会话交接仍分散 |
| Skill 与软件关系 | Skill、MCP server、内嵌 canvas 分层；健康检查区分安装/工具/引擎故障 | Skill 附 CLI/schema/renderers/assets；生成独立 HTML | 源码 Skill 为纯说明，项目安装器可绑定完整 runtime；本机当前副本未绑定 |
| 同一对象持续修改 | overrides、预检和导出围绕同一 session；支持 UI 缺失时工具降级 | JSON 与产物来源一致，可重复 finalize/修复 | 前端操作/历史合同较强，外部 Agent 的稳定接入仍不足 |
| 交付验证 | 明确 health、preflight/export 和失败恢复 | finalize 合并 validate/deliver/strict check/real-browser browser-check；视觉审看另报 | 测试与历史证据充分，但当前版本缺统一交付回执和完整真实宿主链路 |
| 用户看见什么 | 直接打开具体 figure 并改图 | 可独立浏览的 HTML 文件 | 通常启动本地 Studio 后还需导入目标模型 |

优先学习其明确入口、版本和资源定位、同一对象的连续操作、可解释故障与可核验交付，不必照搬其图形类型或强制采用 MCP。Archify 的 finalize 通过也不代表已做人工视觉审看；Tavotto 的文档设计也不等于本次替它验证了全部能力。

**本次验证与证据范围**

- TypeScript `tsc --noEmit`：通过。
- 当前源码 Vite production build：通过；输出到独立临时目录，未替换原 dist。JS/CSS 名称与当前检出的构建相同。出现大 chunk 提示，未据此推断交互性能。
- Studio 完整测试：587/587，通过，0 failed/skipped/cancelled。
- 后端 catalog/custom modules/source-authoring bridge/config/activation/rebind 选择性检查：49/49，通过。不是全量后端或所有模型的运行认证。
- publication 与 Detail CLI：12/12，通过，覆盖实际 SVG/PDF/PNG、85/180mm 尺寸、CJK 与来源合同。
- 本地 loopback authoring/custom-modules HTTP：9/9，通过，无跳过。
- Beta.2 独立校验/解包、临时 Codex 目录安装、verify、launcher capabilities：通过。不是实际 Codex 客户端加载或三宿主 E2E。
- 数据目录共享与导出回执失败：均复现，见 [复现结果](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/skill-readiness-audit-20261010/reproductions.json)。

本次没有重新认证实际浏览器视觉、input-to-paint/呈现 FPS、研究者任务或纸张尺寸审看。历史收据按原版本保留，未升级为当前版本认证。本次只新增审核文档与证据，不修改产品实现。日志、来源摘要和检查绑定见 [审核证据目录](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/skill-readiness-audit-20261010/summary.json)。

**建议的完成顺序**

先修正运行时绑定、安装与版本说明；再提供精确 open 和可复用的 visual-operation/session 入口，同时修复状态目录与导出失败恢复。随后冻结包含 74/23 的候选包，从干净工作区跑真实宿主任务；最后补性能、真人任务和出版审看。真实模型支持按源码形态逐项宣布。完成这些门之后，再将“本地试用”提升为已验证的成熟 Skill 发布。
