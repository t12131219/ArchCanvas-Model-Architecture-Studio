# Agent 未知模块视图补全与 Skill 就绪度（2026-10-29）

> 后续验收已补充真实 CPU、失败后接管及浏览器导入修复，见 [本轮跟进报告](agent-completion-followup-20261029.md)。下文保留第一阶段静态验证范围；不再代表本轮最终状态。

本轮已实现可由当前 Codex / Claude Code Agent 主动采用的未知模块视图工作入口，接通默认 Summary 原生画布，并以 TFB 的三个独立样例进行只读验证。结论是：源码树可本地使用；不能据此宣称任意黑盒计算已解析，或两种真实客户端已完成发行验收。

## 原有缺口与本轮实现

原来已有 `archcanvas-source-rule/1` AST 规则、适配器生成/验证/注册流程，但缺少明确的 Agent 接管工作请求。更关键的是，适配器卡片只进入 portable 投影，默认原生画布读取 `ir.semantic_ir`，因此看不到这些补充元素。

本轮增加：

- `adapter handoff`：返回 `archcanvas-agent-view-handoff/1`，包含真实未知边界、原因、源码位置/片段、候选符号、文件摘要、构造配置、预算及两种起始规则。
- `POST /api/adapters/handoff`：保留现有会话和输入校验；`agentViewCompletion` 能力声明可由宿主发现。
- Skill 的 [未知模块工作规范](../skills/archcanvas/references/unknown-module-views.md)：要求当前 Agent 检查证据、编写有限 AST 规则、独立校验、注册并打开新预览。
- 原生视图投影：将验证过的补充卡片加入 Summary IR，并重新校验封存、portable 摘要及浏览器投影。
- 编辑边界：检查卡片可以保存在文档中，但没有 tensor 端口，不能被连接成可执行计算。

工作链为：发现未知边界 → `handoff` → Agent 阅读实际源码 → 选择/编写规则 → `rule-validate` → `scaffold` → `validate` → `register` → `preview --semantic-mode summary` → 打开新文档检查。

没有新增模型 API、后台 Agent 或任意 Python 插件。Agent 的主动行为来自 Skill 指令；程序提供确定性的请求、模板、校验和原生展示入口。

## 证据和权限边界

补充元素为 `kind: opaque`、`semantic_type: source-inspection`、`inspection_only: true`、`generationContract: null`。新增连线为 `source-inspection` / `syntaxOnly`，表示 AST 语法依赖。回执 `source_inspection_views` 记录基础 IR 摘要及所有新增 ID。

原计算节点/连线逐项保持不变，原未知边界继续计为未知；已有计算契约不为补充卡片授权。显式指定的装饰器方法允许检查其源码体，默认 callable 解析仍不把该方法当成已验证实现。只在真实未知区域应用原生规则，避免已知调用被重复扩图。

有源码时，Agent 可补充调用、接收对象、表达式、循环等可证实的内部结构。没有实现源码时，只能保留有来源的 opaque 调用卡片和解释。CPU 探针的个别运行观察不能证明未观察输入或分支；此路径不要求探针成功。

## TFB 只读验证

源目录：`/home/fzg/PycharmProjects/ArchCanvas/Source_Code_Project/TFB`。不导入 TFB/torch，不实例化模型，不执行探针，不写入该目录。分析前后核对 280 个 Python 文件的 SHA256，全部一致。

大型 benchmark 采用各模型子项目的独立源码语料，保留完整相对包路径；外部依赖保留未知。三例复用同一 attribute-call 规则。PhaseFormer 另按实际装饰器 helper 编写 Return→Call 规则，并显式检查 `_to_phase_series`。

| 样例入口 | 原节点 → 新节点 | 新增检查卡片 | 保留计算未知数 | 规则应用数 |
| --- | ---: | ---: | ---: | ---: |
| MixLinear Model | 73 → 83 | 10 | 5 | 5 |
| ChebyKANLinear | 70 → 76 | 6 | 3 | 3 |
| PhaseFormer Model | 99 → 117 | 18 | 13 | 8 |

三例共 34 个新增卡片，21 个计算未知边界仍如实保留，无规则预算截断，原计算节点和连线逐项相等。MixLinear / PhaseFormer 的构造配置为 `{}`，因此不是完整配置模型的运行认证；ChebyKANLinear 使用 `input_dim=8, output_dim=4, degree=3`。

复现：

```bash
python -B scripts/validate_tfb_agent_views.py \
  --source-root /home/fzg/PycharmProjects/ArchCanvas/Source_Code_Project/TFB \
  --output /absolute/independent-evidence/tfb
```

[机器报告及全部文件摘要](evidence/agent-unknown-views-20261029/tfb/report.json)、每例 handoff/before/preview/registry、两种规则及保留的 TFB MIT 许可证均在 evidence 目录。未知实现未被“绘图补全”伪装成已解析计算。

## 验证记录

- 新增 Agent 补全 Python 测试：6 项通过；含不执行源码、不写 registry、原计算不变、幂等、改名复用、过期/伪造证明拒绝、缺失实现和装饰器边界。
- 规则回归：58 项通过；适配器 registry 最终回归：20 项通过。
- HTTP 回归：15 项通过、零跳过，含新 handoff 路由及静态执行边界。
- 前端组合回归：18 项通过；新增的 2 项实际加载 Python 生成的 bundle，经浏览器使用的 SHA/投影验证、原生图构建/展开、authoring 校验和文档保存恢复，并拒绝 tensor 连接。
- TypeScript / Vite 生产构建、preview authority audit、Skill quick validation 通过。
- 当前候选安装器测试：12 项通过，覆盖项目内发现路径、嵌入运行时、迁移/篡改检查；该打包快照先于最后的装饰器小修，不是最终字节冻结发布认证。

这些是程序回归证据。额外浏览器验收使用隔离服务 `8797`，未重启用户的 `8796` 服务。文件选择上传、随后备用的源码粘贴均遇浏览器自动化超时，未完成最终图面视觉验收，未取得可宣称成功的截图。保存恢复的程序测试不能替代这一人工/真实客户端检查。

相应日志保留在 [checks](evidence/agent-unknown-views-20261029/checks)。

## Codex / Claude Code 的就绪度

已对照 [Codex Skill 文档](https://learn.chatgpt.com/docs/build-skills) 与 [Claude Code Skill 文档](https://code.claude.com/docs/en/skills)。共享 `SKILL.md`、相对资源、绑定 CLI 的方案适用；安装器分别使用 Codex `.agents/skills`、Claude Code `.claude/skills` 的项目内发现路径。

| 项目 | 本轮结论 |
| --- | --- |
| Skill 指令、入口、相对资源、运行时绑定 | 已实现；本地 launcher 和打包兼容性检查通过 |
| 默认原生画布读取新增检查卡片 | 已接通；摘要、展开、编辑及保存恢复程序测试通过 |
| Codex 真实安装后自动发现→调用→保存/导出 | 尚未验证；本机存在 Codex CLI，但未把本轮打包结果安装后做客户端验收 |
| Claude Code 同一完整流程 | 尚未验证；本机未安装 Claude CLI |
| 任意未知模型、探针失败、所有分支/动态实现恢复 | 不具备普遍保证；本轮只做三例静态只读补视图 |
| 冻结安装包含本轮能力 | 尚未重新制作本轮正式冻结发行物；已有安装包不会自动更新 |
| 发布/真人视觉/大图性能出口 | 仍开放，不能宣称正式发布完善 |

最终源码树 doctor：`status=ready-local`，`distribution=development-checkout`，`releaseIntegrity=development-bytes`，`releaseVersion=null`，`hostE2E=not-tested`，`publicationReview=not-certified`。见 [doctor 摘要](evidence/agent-unknown-views-20261029/checks/doctor-summary.json)。

因此目前可作为开发版本地 Skill 使用。要称为面向 Codex 和 Claude Code 的完整发行品，仍需在冻结当前字节后完成两宿主真实发现/调用/保存导出验收、未知模块图面审看以及既有发布和性能出口。
