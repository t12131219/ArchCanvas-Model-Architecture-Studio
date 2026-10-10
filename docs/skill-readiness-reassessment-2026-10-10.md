**ArchCanvas Skill 当前版本复核 · 2026-10-10**

结论：已具备最小可用 Skill 的工程基础和本地闭环；尚未完全满足原技术计划的完整验收与成熟发布要求。建议使用范围为“本地 Beta 试用：有界源码制图、持续视觉编辑、独立草稿建模和经审核的局部语义变更”。

本复核更新此前审核的现状判断。此前报告与收据保留其原时间点，不再把已经修复的问题当作当前缺陷。审核只新增报告及证据；没有修改产品实现、安装副本或用户模型。

**已经复核通过的修复**

| 项目 | 当前证据 |
|---|---|
| 运行时绑定 | 源码 Skill 有 launcher；本机 `/home/fzg/.codex/skills/archcanvas` 已是完整安装副本，安装 verify 返回 passed，doctor 返回 beta.3、releaseIntegrity=verified、ready-local、74 原子模块/23 预设。 |
| 精确打开模型 | CLI `open` 返回 documentId/sessionId/projectId 和 `?documentId=...` URL；前端优先读取目标 ID，缺失时显示错误。 |
| 同一画布连续改图 | `session read/apply/undo/redo/save/export` 已实现；服务调用 Studio 同一 TypeScript 操作与历史 reducer，并校验存储/视觉版本。 |
| 状态隔离 | `--data-dir` 现为完整 state root，documents/projects/drafts/exports/transactions 位于其内部；真实双服务专项测试通过。 |
| 导出失败恢复 | 导出先暂存产物和回执，普通提交异常恢复旧文件；receipt 目标为目录时旧图保持。该专项测试通过，不据此承诺断电时跨文件原子性。 |

本次重新运行 `tests.test_readiness_fixes`：3/3 通过，包含静态源码 open→read/apply→冲突拒绝→undo/redo→重启恢复→SVG 导出，原模型源字节保持；另包含目录隔离与回执失败保护。开发检出 doctor 和安装版 doctor 都实际调用成功。已安装候选与当前检出的 src、studio/src、scripts 对应文件字节一致。

**仍未满足的要求与发现**

1. **P1：当前检出的默认打包流程仍无法直接产生新候选。** 实际执行 `python scripts/m5_beta_bundle.py pack --output /tmp/archcanvas-readiness-reaudit-candidate-20261010.tar.gz --version 0.1.0-beta.3` 返回 failed：index.html hash mismatch，缺少 `index-B1nPLV0h.js` 和 `index-dmzfR53F.css`。原因是打包先验证的发布清单仍绑定历史 Beta.2 资产。

   临时 staged tree 的 beta.3 候选存在且安装完整性通过，因此不能说“无法分发”；问题是当前工作树到候选的可重复标准发布路径尚未闭合。建议保留冻结历史清单，为新版本提供生成 staged manifest、pack、verify、install 的明确命令或脚本，将候选放入稳定的版本产物目录。当前 beta.3 bundle 仍在 `/tmp`，正式工程 releases 目录保留的包为 beta.1/beta.2。

2. **实际三宿主完整流程仍未验收。** 候选收据的三种宿主安装/verify 是包兼容性证据；Codex、Claude Code、官方 DeepSeek Harness 的实际发现→打开→编辑→保存→导出→语义提案仍标为 not-tested。当前会话能发现 Skill、能调用其 launcher，也不等于完整宿主任务已验收。MCP 是可选实现，不是完成验收的必要条件。

3. **性能、研究者任务和出版审看仍开放。** 原计划要求 300 可见对象 input-to-paint p95≤50ms、呈现≥50fps、中等展开 p95<500ms；3–5 名研究使用者中≥80%在3分钟内完成任务；85/180mm真实尺寸人工审看。当前修复说明与 doctor 均未把这些项宣称为通过。本次不做这种认证。

4. **当前完整回归仍需收敛。** 修复说明记录前端587项、审计相关后端33项以及后续专项通过，也明确记录全量旧集合中存在依赖历史 dist 的 setup 失败与一次 visual-gold 超时。本次只重跑上述3个修复专项，没有把旧审核的587/49/12/9结果当作当前全量回归结论。应区分历史包测试和当前候选测试，并留下当前完整集合的可复查结果。

5. **P2：Skill 说明仍有版本措辞矛盾。** 当前入口已经说明完整安装和内嵌 runtime，但源码 Skill 第32行仍称“This distribution contains instructions, not a bundled runtime or a completed editor.”这也被复制到完整安装版。建议改成按 distribution 判断，避免 Agent 把已安装运行时误判为不存在。

6. **复杂真实模型的静态恢复边界仍存在。** 本轮修复没有新增原 Transformer 的 encode/decode、工厂/深拷贝，以及 PatchTST 的 configs、条件构造/前向等 lowering 合同。不能因编辑库有74个算子就承诺自动恢复任意模型内部关系。opaque 必须保留，不能用教材模板补成“源码事实”。

**用户被允许的使用方式**

| 用户请求 | 可以执行的范围 | 审核/权限条件 |
|---|---|---|
| “把这个模型打开成架构图” | 静态读取指定源码入口，通过 open 创建/重开对应受管理画布。 | 静态图无需执行模型，不应强制要求输入shape；来源不足显示opaque。 |
| “把Encoder改蓝、改显示名、移动图例” | 同一画布的别名、样式、布局、图例、注释、展开/收起和端口视觉位置。 | 可逆视觉操作无需源码审批；不得更改canonical连接。 |
| “继续改图并保存、撤销、导出” | 使用同一session的类型操作、历史和保存，导出当前文档SVG/PDF/PNG。 | 外部改图前先保存UI未保存内容；使用最新版本号，冲突不覆盖。PDF/PNG需实际可用的转换依赖。 |
| “从零搭一个模型” | 使用运行时实际74/23目录建立独立草稿，静态验证，展示并生成新受管理源码。 | 声明形状验证不等于模型已执行；不自动覆盖导入模型的原件。 |
| “把dropout改为0.2/换激活/重接输入” | 仅注册合同支持的literal/config概率、默认ReLU/GELU替换和局部RebindInput。 | 必须准备、验证、展示具体diff、取得对应批准后提交；需要执行的验证门须显式配置隔离runtime。 |
| “执行模型看看实际shape” | 独立、显式的运行工作流。 | 用户授权、支持的输入/模式和隔离环境均满足时才能执行；加载Skill本身不是执行授权。 |

HTTP语义写回操作的是managed copy；CLI patch可绑定明确的源根并经审核提交。操作前必须说明实际目标。任意动态Python全恢复、任意结构全面往返、训练/checkpoint/优化器迁移、公开多用户云服务都不在当前承诺范围。

用户可以直接请求：“使用archcanvas，静态打开这个目录的module:Class并显示对应画布”“把当前Encoder改成蓝色，保留布局，保存后导出180mm SVG/PDF”。Agent应处理类型操作和版本号，无需让普通用户手写JSON。画布内本地文字指令仍是有界命令解析；宿主Agent可把请求转换成受支持的类型操作，二者不应混称为任意自然语言都能执行。

**当前可复查的入口**

源码检出启动方式（两个终端；先服务，后open）：

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
PYTHONPATH=src .venv/bin/python -m archcanvas_cli doctor
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve --port 8765 --data-dir /absolute/project/.archcanvas
```

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
PYTHONPATH=src .venv/bin/python -m archcanvas_cli open --root /absolute/model-root --entry model:Network --server http://127.0.0.1:8765
```

打开open返回的精确URL。服务需保持运行。`--data-dir`现在传完整状态根；若要重开旧版曾显式传入documents目录的状态，应按修复说明选择原父根，没有自动迁移。每个状态根只运行一个服务进程。

本机完整安装副本可先执行：

```bash
python3 -I -B /home/fzg/.codex/skills/archcanvas/scripts/archcanvas_runtime.py doctor
```

来源链接：[Skill契约](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/skills/archcanvas/SKILL.md:10)、[open/session CLI](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/src/archcanvas_cli/__main__.py:19)、[精确文档加载](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/studio/src/App.tsx:384)、[状态根](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/src/archcanvas_cli/server.py:224)、[导出恢复](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/scripts/atomic_export.mjs:4)、[修复说明](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/skill-readiness-fixes-2026-10-10.md)、[原验收目标](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_双向模型可视化与编辑框架_技术计划书.md:1276)。

本次证据见 [复核summary](/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio/docs/evidence/skill-readiness-reassessment-20261010/summary.json)。本次没有重跑全部前后端测试、三宿主完整任务、浏览器性能或真人/纸张评审；历史与当前证据分别记录。
