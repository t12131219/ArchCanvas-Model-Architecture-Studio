# 2026-10-10 审计修复

本次针对 [原审计](skill-readiness-audit-2026-10-10.md) 修复运行时发现、精确模型交接、状态隔离和导出恢复。原审计与 Beta.2 历史回执保留；后续验证绑定本次实际文件，不能代替真人、性能、出版审看或三宿主客户端验收。

| 审计项 | 本次变化 |
| --- | --- |
| P1 运行时绑定 | 源码 Skill 提供明确 launcher；安装版使用内嵌 release/安装合同。doctor 返回实际版本、运行时/解释器路径、构建资产摘要、当前模块与起点数量。复制单个 SKILL.md 仍不等于安装软件。 |
| P1 精确打开/连续改图 | CLI open 静态分析指定入口，并向本机服务注册受管理源码副本；返回 documentId/sessionId/projectId/revision/精确 URL。URL 中的 documentId 优先于浏览器缓存，目标缺失时显示错误。session 入口使用前端同一 TS 操作、撤销 reducer 与持久历史。 |
| P1 当前版与旧包混用 | doctor 明确区分开发检出和冻结本地候选包，并显示实际资产及目录数量。Beta.2 的 17/3、旧构建与旧宿主收据保留其历史范围。新候选的临时安装/verify 是本地工程检查。 |
| P2 状态目录共享 | data-dir 现在是完整 state root；documents/projects/drafts/exports/transactions 全部在各自根内。兄弟目录的真实双服务测试验证无法互读。 |
| P2 导出覆盖旧成果 | 转换并校验后，暂存完整产物与回执，串行提交；普通提交异常恢复旧文件。回执目标为目录/软链接时拒绝替换。恢复本身失败时保留暂存备份并报告位置。 |
| 发布门 | 三宿主真实客户端任务、3–5 名研究者、纸张人工审看和当前版性能指标仍待实际验收。没有把工程测试改写成这些门通过。 |

开发检出使用：

```bash
cd /home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio
PYTHONPATH=src .venv/bin/python -m archcanvas_cli doctor
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve --port 8765 --data-dir /absolute/project/.archcanvas
# 另一个终端；源码只进行静态分析。
PYTHONPATH=src .venv/bin/python -m archcanvas_cli open --root /absolute/model-root --entry model:Network --server http://127.0.0.1:8765
```

打开返回的 URL，即可访问指定文档。已安装 Skill 通过 `python3 -I -B <skill>/scripts/archcanvas_runtime.py` 调用同样的命令；先 doctor，再根据实际 capabilities 使用功能。

```bash
# 使用 open 返回的 ID。
PYTHONPATH=src .venv/bin/python -m archcanvas_cli session read --document-id ID --server http://127.0.0.1:8765
```

read 返回 `revision`（存储版本）与 `document.revision`（视觉版本）。例如 `ops.json` 为 `[ {"type":"alias","id":"实际节点ID","label":"Encoder"} ]`，使用 read 中的精确 ID；apply 为一个撤销步骤：

```bash
PYTHONPATH=src .venv/bin/python -m archcanvas_cli session apply --document-id ID --expected-revision N --visual-revision V --operations ops.json
PYTHONPATH=src .venv/bin/python -m archcanvas_cli session undo --document-id ID --expected-revision N --visual-revision V
PYTHONPATH=src .venv/bin/python -m archcanvas_cli session export --document-id ID --expected-revision N --visual-revision V --format svg --width-mm 180
```

每次使用最新 read 返回的版本。save 接受 CanvasDocument 或已保存的 history envelope，必须提供当前存储版本。所有 session 视觉变更只修改持久画布，不写原模型源码。语义修改仍需具体 diff 的审核、批准、隔离验证与提交合同。

可见 Studio 在无本地未保存改动时同步同一文档的外部操作与历史；本地未保存改动保持原状，遇到外部更新提示冲突。外部操作前先保存 UI 编辑。历史最多 100 个快照，文档及历史共同受 4 MB 持久化预算约束。

默认状态仍在正式 runtime 的 `.archcanvas`。旧命令若显式传 `.../.archcanvas/documents`，重开旧状态时应显式改用其父根 `.../.archcanvas`；没有自动迁移。每根运行一个进程。导出异常恢复不承诺断电时跨文件系统事务；异常锁/备份保留时应核对文件后恢复。

真实源码覆盖仍有限。原 Transformer 的 `encode/decode` 方法、模块工厂/深拷贝，PatchTST 的外部 configs、分支构造、条件前向等需要独立的 lowering 合同与关系预期；本次没有用教材模板填充这些 opaque 区域，也没有执行用户模型来绕过静态分析边界。

## 本轮验证结果

- 前端完整回归：587/587 通过，0 failed/skipped/cancelled；`npm run build` 通过，只有既有大 chunk 提示。
- 审计相关后端回归：33/33 通过；其中包含两个真实兄弟 state root 服务的隔离、open → read/apply/conflict/rollback/restart/export、以及导出回执失败时保留旧 artifact。
- `doctor` 对正式开发检出返回 `ready-local`，实际目录为 74 个原子模块、23 个透明起点；当前 Studio 资产和 Node/Python 路径均被列出。
- 已在 `/tmp` 独立冻结本地候选 `0.1.0-beta.3`：打包 296 个文件，SHA-256 为 `d15088cd8b8769fa01aa63cd62774b9508a9c8064f218680ccc35b28c46082df`；解包完整性验证通过，MLP/Residual CNN/Transformer 静态 fixture 分析通过且未执行模型。
- 候选在临时 Codex、Claude Code、DeepSeek Harness 项目目录安装并 `verify` 通过；三个候选 launcher doctor 均报告 `releaseIntegrity=verified`、74/23。它们是项目级安装检查，不是三个真实客户端 E2E。
- 当前加载的 `/home/fzg/.codex/skills/archcanvas` 已替换为候选的完整、可搬迁 runtime 绑定副本；全局副本 `verify` 和 doctor 通过，旧 instruction-only 副本保存在 `/tmp/archcanvas-global-before-20261010`。回滚脚本为 [scripts/rollback_readiness_20261010.sh](../scripts/rollback_readiness_20261010.sh)。详细机器结果见 [candidate-beta3.json](evidence/skill-readiness-audit-20261010/candidate-beta3.json)。
- 浏览器打开了精确的 `?documentId=canvas-architecture-model.MLP-3654a3534b85-ab8e9edc`；切换编辑模式后画布继续显示 `features`、`network`、`Linear`、`GELU`、`Dropout`、`Output` 等英文模块名，并显示“源码组合模块已递归展开；可以编辑内部基础模块”。

这些结果修复了审计中的工程缺口，但没有把未测量的真实宿主任务、性能、研究者任务、出版尺寸人工审看或复杂 Transformer/PatchTST source lowering 宣称为已完成。

补充：研究导出、Stage2 HTTP 和 Beta.2 历史 manifest 诊断的针对性回归为 27/27 通过。全量旧测试集合（386 项）仍包含依赖冻结 Beta.2 dist 文件的打包/宿主 setup，以及一个 30 秒 visual-gold 超时；这些测试不应被旧收据改写为当前 beta.3 的发布证据。当前候选包已经在独立 staged tree 中完成对应的 pack/verify/install 检查。
