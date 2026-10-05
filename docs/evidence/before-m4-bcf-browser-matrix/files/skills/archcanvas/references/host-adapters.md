# Codex、Claude Code 与 DeepSeek Harness 接入合同

核验日期：2026-10-04。DeepSeek 指用户指定的官方 [DeepSeek Harness](https://www.deepseek.com/en/harness/)，仓库为 [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)，不是仅使用 DeepSeek API 的任意第三方代理。

## 统一运行方式

三个宿主使用同一个 `SKILL.md`、同一套确定性运行工具、同一份 Studio 画布应用。Skill 负责理解意图、调度工具、报告证据与展示结果；画布状态、布局、图例编辑、审核和源码事务由 ArchCanvas 运行时负责。宿主原生插件只增强展示和工具发现，不建立第二套画布或另一套修改协议。

1. 读取实际加载的 Skill 路径，把所有相对资源路径解析到该 Skill 目录；不得假设它仍在开发仓库中。
2. 检查当前宿主暴露的文件、shell、浏览器和 MCP 能力。发现已配置 runtime 入口，用其 `--help` 确认实际可执行命令；本指令包没有随包可执行入口，不得从参考文档推断未实现的子命令。runtime 缺失时据实说明，继续可完成的静态源码分析/图草稿或安装方案，不声称打开了交互 Studio。
3. CLI 是三宿主的接入基线。优先在选定项目 workspace 内生成工件；检查命令退出状态与输出收据，再展示文件或已启动的 Studio URL。
4. 优先用宿主当前实际可用的浏览器/预览工具展示同一个 Studio。没有展示工具时交付工件路径和可打开的 URL，由用户打开；不得声称已经看到或验证画面。
5. MCP 是可选增强。只有服务器已配置、已连接且工具已发现后才调用；Skill 文件本身不启动 MCP，也不授予读写权限。
6. 视觉编辑保存到画布文档。模型参数或连接变更先生成带源码位置、图变化和源码 diff 的语义提案，再走 ArchCanvas 的审核与提交流程。宿主 shell 许可不替代这次模型修改的审核。

## 发现、安装与调用

下表是官方资料所支持的发现合同；不是本轮已经完成的三宿主运行认证。安装本指令包时复制完整 `skills/archcanvas`，保留 references 与 metadata，不能只复制 `SKILL.md`。本包不含 runtime；未来 bundled-runtime 发行另须携带其完整运行资源并验证版本。

| 宿主 | 项目发现位置 | 用户发现位置 | 用户调用 | 本项目接入原则 |
|---|---|---|---|---|
| Codex | `.agents/skills/archcanvas/SKILL.md`；从 CWD 向上扫描至仓库根 | `~/.agents/skills/archcanvas/SKILL.md` | CLI/IDE 的 `$archcanvas` 或 `/skills` 选择；其他界面使用该界面提供的选择器 | 共享 `.agents` 安装；`agents/openai.yaml` 为可选 UI 元数据 |
| Claude Code | `.claude/skills/archcanvas/SKILL.md`；父目录与嵌套目录规则见官方文档 | `~/.claude/skills/archcanvas/SKILL.md` | `/archcanvas`；也支持按描述匹配 | 同一包复制/链接到 `.claude`，用通用 CLI 与 Studio |
| 官方 DeepSeek Harness | 优先 `.dsh/skills/archcanvas/SKILL.md`，其次项目根 `.agents/skills/archcanvas/SKILL.md` | `$DSH_HOME/skills`，未设时 `~/.dsh/skills`；其次 `$DSH_AGENTS_HOME/skills`，未设时 `~/.agents/skills` | `/archcanvas`；模型通过 `skill` 工具加载 | 优先复用 `.agents`；仅需要 DSH 覆盖时使用 `.dsh` |

Codex 官方文档支持 symlink 技能目录；Claude Code 官方文档也说明项目/个人技能目录可链接。DeepSeek 源码和包文档记录发现路径与资源基址保留 symlink、预览使用已解析文件路径。发行包优先完整复制，开发调试可链接。不要无意在 `.dsh` 与 `.agents` 各安装一份同名 Skill：DeepSeek 会选择较高优先级版本，修改另一份不会生效。

不要把本环境的 `~/.codex/skills` 当作当前官方文档唯一推荐的用户发现位置。不同版本与发行环境可能仍使用该位置，安装器应依据目标版本与实际环境检测。

## 共同 frontmatter 与资源

共同入口使用最低共享字段，名称保持 kebab-case：

```yaml
---
name: archcanvas
description: Describe the exact model visualization and editing tasks that trigger this skill.
---
```

正文使用宿主中立的步骤和相对引用；较长的宿主规则、可视化合同和编辑合同放在 `references/`，确定性工具放在 `scripts/`，图例和主题资产放在 `assets/`。

- Codex 可选 `agents/openai.yaml` 的 `interface` 提供名称、图标、品牌色等；`policy.allow_implicit_invocation` 配置自动匹配；`dependencies.tools` 声明工具依赖。这些字段不能视为跨宿主权限规则。
- Claude Code 官方文档声明采用 Agent Skills 标准，并扩展 invocation control、subagent execution、dynamic context injection。Claude 专用能力应放进宿主适配说明；共享步骤不依赖动态命令注入或 Claude 特定子代理机制。
- DeepSeek 文件系统 provider 要求 `name` 与 `description`，另解析 `whenToUse`、`metadata`、`disable-model-invocation` 和 `user-invocable`。不要将 Claude 的其他 frontmatter 字段推定为 DSH 的执行合同。
- 如需限制副作用，必须在运行时工具和源码事务中落实；描述文字和 frontmatter 不能承担唯一保护。

## DeepSeek Harness 的确切合同

以下基于官方提交 `5badb15009ae1756c3afe0ae0cef1faafc290ccc` 的源码与 README。该提交的 root 和 CLI package 版本为 `0.2.1-alpha.1`；它是仓库版本证据，不是对 npm 当前发布版本的认证。官方说明为 developer preview，明确提示会有兼容性变化，集成发布需记录实际安装版本。

### 发现与加载

文件系统 provider 的默认根与优先级为：项目 `.dsh/skills` 100、项目 `.agents/skills` 200、`customSkillDirs` 300、用户 DSH `skills` 400、用户 agents `skills` 500。项目根为最近含 `.git` 的祖先；找不到时使用 cwd。因此在非 Git workspace 中，应安装在选定 cwd 下，或配置实际加载的自定义根。

只识别扫描根的直接 `<name>/SKILL.md` 与 `<name>.md`；不递归发现任意 `**/SKILL.md`。`includeDefaultRoots: false` 会取消默认项目/用户根；自定义 profile 必须检查文件系统 provider 是否加载、默认根是否启用。

需组合 `@deepseek-ai/dsh-skill`、`@deepseek-ai/dsh-skill-filesystem` 和 `@deepseek-ai/dsh-tool-skill` 才能形成“注册表 → 文件发现 → 模型目录/加载工具”的完整路径。官方模型加载接口是：

```text
skill({"name": "archcanvas"})
```

这是宿主工具调用形状，不能粘贴为 shell 命令。直接用户输入 `/archcanvas` 会注入相同完整指令，已经注入时不重复加载。`disable-model-invocation: true` 隐藏模型目录与模型加载；`user-invocable: false` 隐藏用户调用；未设置时默认允许两种入口。

provider 会监视目录变化，加载时重新读取正文；正文变化不改写已保留的历史指令。发现失败或非法 frontmatter 可能导致 Skill 不出现，应检查 harness 日志和实际安装路径，不能推断目录存在即安装成功。

### 工具与 MCP

DSH MCP client 是 `@deepseek-ai/dsh-mcp-client`：每个 server 一条配置，`serverName` 和 `transport` 必需；支持 `stdio` 与 `streamable-http`，分别使用 executable/argv 或 URL。发现后的工具名为 `mcp__<serverName>__<rawName>`，不会默认启用任何服务器。将来的 ArchCanvas MCP 可以复用同一运行时，但不得在服务器未实现时给用户一个假配置或声称工具可用。

MCP 的图片结果只有模型接受图像且 harness attachment 功能启用时才进入会话；音频和 embedded resources 等有不同处理限制。稳定交付应包含本地可打开工件/Studio URL，并保留结构化结果；不要把内嵌 HTML widget 渲染视为通用 MCP 必备能力。

浏览器操作由实际加载的 browser-use provider 提供。Skill 目录发现和 browser-use registry 本身不会产生浏览器控制工具。所有调用应从本次会话真实工具清单选择。

### 同一 Studio 的展示

DSH `ui-sidebar-browser` 可展示 HTTP(S)，包含 loopback。Web profile 默认禁用该 Browser，Desktop 默认启用；Web 使用 iframe，Desktop 使用 Electron webview。用户可从右 Sidebar 的 Browser 输入 URL。已实现的 DSH client 插件可以使用：

```text
ctx.sidebarRight.openTab('browser', { params: { url } })
```

这是 client 插件 API，**不是 agent 工具**。该 Browser UI 本身不注册模型工具、prompt 或 Session event。没有实现 client adapter 时，交付 URL 并使用可用的用户展示入口。

Sidebar Browser 拒绝 `file:` 地址；本地文件使用 Document Preview。Web iframe 的下载、顶层导航、mixed-content/CSP 等限制会影响体验；如导出在该容器不可用，用外部浏览器打开同一 Studio。先验证实际导出，不能把“页面打开”当作“导出通过”。同一画布应用应负责自己的可访问性、键盘操作、编辑历史和导出，不依赖宿主容器补齐这些能力。

### 权限与审核

DSH sandbox 与 approval 为分离的机制。`dsh-user-approval` 的 `ask` 将请求交给已组合的 human/machine answerer；无 answerer 时失败关闭。`never` 会拒绝需要审批的请求，不能解释为自动批准。其许可为单次工具请求，不能推定为持久授权。

在 DSH Web UI 中选定 workspace 后才可开始会话。保持当前用户指定的权限模式；不因启动 Studio 或执行导出擅自切换 Full access。文件写入、服务启动和 MCP 子进程分别遵守宿主实际限制；模型源码的审核收据仍由 ArchCanvas 自己维护。

## 支持声明与验证记录

官方资料证明三个宿主都能发现/使用相应 Skill 形态；这不自动证明本项目已在三个真实客户端完成端到端运行。

| 层级 | 可以声明 | 必须补充的证据 |
|---|---|---|
| 文档兼容 | 发现路径、frontmatter、DSH 工具/插件合同已核验 | 引用下列官方来源与对应版本 |
| 包兼容 | 同一包可安装到相应目录、资源相对路径可解析 | 安装回执、包清单/哈希、独立副本的启动检查 |
| CLI 接通 | 本机确定性命令返回有效工件和收据 | 实际命令、环境、退出码、输出路径 |
| 客户端认证 | 在真实 Codex/Claude Code/DSH 中完成任务 | 版本、Skill 发现/加载记录、Studio 打开与交互、持久化/导出记录 |
| 可选原生集成 | 对某宿主完成 MCP/client 插件接入 | 真实工具发现、插件加载、错误恢复与权限记录 |

每次声称新增宿主支持，至少记录：宿主版本与启动 profile、安装位置、实际 Skill 加载、共同 CLI 是否可执行、Studio 的展开/图例编辑/撤销/保存/导出、提案和源码审核是否保留。当前资料核验不应标成上述真实客户端认证。

## 官方证据

资料均在 2026-10-04 实际取回。DSH 链接固定源码提交，后续版本应重新核验。

1. [OpenAI 官方 Build skills](https://learn.chatgpt.com/docs/build-skills)；原 `https://developers.openai.com/codex/skills/` 当前重定向到该页面。正文取回地址为 [build-skills.md](https://learn.chatgpt.com/docs/build-skills.md)。
2. [Claude Code 官方 Skills](https://code.claude.com/docs/en/skills)；已成功取回 [skills.md](https://code.claude.com/docs/en/skills.md)，后续重复请求曾返回 403，不能因此将成功取回内容视为当前本机可稳定联网能力。
3. [DeepSeek Harness 官方入口](https://www.deepseek.com/en/harness/) 与 [官方 README](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/README.md)。
4. [DSH 官方 Web UI quickstart](https://deepseek-harness.github.io/deepseek-harness/en/guide/quickstart)。
5. [DSH skill-filesystem 合同](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/skill/skill-filesystem/README.md) 和 [实现](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/skill/skill-filesystem/src/index.ts)。
6. [DSH tool-skill 合同](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/skill/tool-skill/README.md) 和 [确切工具 schema](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/skill/tool-skill/src/index.ts)。
7. [DSH MCP client 合同](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/mcp/mcp-client/README.md)。
8. [DSH Sidebar Browser 合同](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/client/ui-sidebar-browser/README.md) 与 [browser-use registry 边界](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/browser-use/browser-use/README.md)。
9. [DSH approval 合同](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/interaction/user-approval/README.md) 与 [permission presets 合同](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/interaction/permission-presets/README.md)。
10. [DSH CLI package 版本证据](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/apps/cli/package.json)。
