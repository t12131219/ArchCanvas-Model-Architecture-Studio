# Agent 补全后续验收（2026-10-29）

后续连线审查：当前源码已升级 native-semantic/19，修复嵌套检查依赖断链；此修复晚于本文 Beta.6 冻结。范围和未通过项目见 [连线修复记录](inspection-connections-20261029.md)。

本次补上了真实 CPU 成功、模型异常和环境不可用三种结果后的 Agent 接管路径，并修复原生源码导入的同步旧视图构建阻塞和扇出优化产生的端口冲突。仍不能将本地回归等同于双宿主客户端、真人视觉或大图发布认证。

## 真实 CPU 与失败后补视图

使用正式 `.venv-runtime`、锁文件和强制 Bubblewrap/seccomp 隔离，运行 TFB 的原始 `ChebyKANLayer.py` 字节副本；不导入 benchmark 顶层包、不下载权重、不改 TFB。构造参数为 input_dim=8、output_dim=4、degree=3，eval / seed=7。

| 场景 | 实际模型执行 | 探针结果 | 后续视图补全 |
| --- | --- | --- | --- |
| float32 x=[2,8] | 是 | passed / runtimeVerified=true | 成功 |
| float32 x=[2,7] | 是 | failed；真实 einsum 维度异常 | 成功 |
| 指定不存在的解释器 | 否 | unavailable | 成功 |

三条路径均增加 6 张源码检查卡片，保留 3 个计算未知边界，原计算节点与边逐项相等。TFB 280 个 Python 文件前后 SHA256 一致。完整报告及每次 receipt、handoff、preview、规则保存在 [CPU 证据](evidence/agent-unknown-views-20261029/probe-completion-final/report.json)。这验证指定样例的执行与失败后恢复，未证明任意输入、全部动态分支或黑盒计算等价。

新增 `adapter handoff --probe-spec ... --runtime-interpreter ... --dependency-lock ... --probe-output ...`，默认仍静态。失败或不可用仍返回成功的 handoff，必须检查 `probe.status`；退出 0 不代表模型执行成功。探针回执严格绑定源码、入口、配置，仅提供诊断依据；失败观察不会混入原生计算 IR。实际 CLI 已触发同一 einsum 错误并返回含 3 个请求的 handoff。

外层工具沙箱会阻止隔离器创建网络命名空间，真实测试经外层授权运行，但内层模型隔离始终启用。没有降级为无隔离执行。

## 浏览器卡顿修复与视觉验证

根因是原生导入在进入 Worker 前仍调用 `A.sources(bundle)`，同步生成并布线整套旧深度图。独立复现中 SHA 校验约 35 ms，旧 sources 构造超过 30 s 未完成。

原生路径现在完成来源校验后直接让 Worker 构建，并按原生契约验收；保留旧递归文档的兼容分支。新增回归确保原生注册不会调用旧 sources，同时使用真实 Python bundle 验证摘要和图接受性。41 项前端组合回归、生产构建和 authority audit 通过。

继续用真实失败探针的原始 preview、显式构造参数和默认优化器进行浏览器导入，发现扇出优化会让不同分支按旧状态分别校验通过，再同时占用同一目标操作数端口。现对整组候选统一校验后才接受，冲突方案回退；没有放宽端口或来源校验。新增 MIT 来源的精确 ChebyKAN fixture 和默认优化器回归。

隔离服务 8798 已由真实浏览器导入并恢复 CPU 失败场景的精确 ChebyKANLinear preview，展开 `acos → torch.acos → torch`，保存并刷新；导出对话框显示编辑 JSON 已下载，并实际生成 SVG 及服务器 receipt。下载事件接口未返回文件路径，不能将其当作本地文件重新导入证明；完整文件恢复另由前端与宿主生命周期测试覆盖。浏览器截图和 DOM 保存在 [followup](evidence/agent-unknown-views-20261029/followup)。用户原有 8796 服务未重启。

失败场景的 caseId 为 `source-bc04388a7d6a788f`，原生 IR 摘要为 `c188dee64e0a636c2d3e15df71cead0c6e3f46110ee612a49b7f3bfa65c1c8ec`。实际 SVG receipt 与记录的失败 preview 摘要相等，截图为 `followup/cpu-failed-browser-restored.png`。该相等性由独立核对取得；导出服务器的 `sourceBindingVerified=false`，不能把浏览器声明的绑定说成服务器来源认证。

180 mm 整图最小字约 6.01 pt，预检建议至少 210 mm；最终版面仍需按实际出版尺寸人工检查。导出成功不代表可读性验收通过。

## 性能验收的实际范围

Transformer 的 `self.encode` 原生引擎基准，非浏览器输入到显示延迟：

| 层级 | 节点/边 | 构建 | 8 单位移动 | 严格布局检查 |
| --- | --- | --- | --- | --- |
| F0 | 61 / 63 | 1656 ms | 24 ms | 通过 |
| F1 | 82 / 80 | 2744 ms | 32 ms | 通过 |
| 源码深度 1 | 59 / 58 | 1179 ms | 18 ms | 通过 |
| 源码深度 3 | 87 / 88 | 1524 ms | 26 ms | 通过 |
| self.encode 完全展开 | 1215 / 1306 | 9781 ms | 888 ms | 未通过；pending=30 / failed=0 |

完全展开移动能完成，但仍有布线质量和交互性能缺口。此基准不是根模型全展开，也不代表 FPS 或浏览器大图验收。最终结果另存 followup/final-depth-performance.json；旧 depth-performance.json 仅为修复前记录。

## Skill 和冻结发行状态

已按 Codex 与 Claude Code 官方 Skill 路径检查；共享指令与绑定运行时继续使用。打包工具现包含本次验证脚本、关键回归和 CPU 摘要，不覆盖历史 Beta.2。

Codex 实际客户端通过 `skills/list` 找到项目内 Skill，scope=repo、enabled=true。首次真实 `$archcanvas` 调用已由 Agent 读取安装指令并运行 doctor，但 30 s 限时在完成保存/导出前结束。因此它仅证明发现与初步调用，未证明完整 E2E。CLI `login status` 的未登录信号不能代表桌面环境的实际可调用性。

延长真实 Codex 验收的重试被自动审批拒绝：理由是可能向外部服务传输私有冻结工作区、Skill 及测试源码上下文，需要针对内容与目的地的明确授权。只读核对发现 Codex CLI 配置为 custom provider，端点主机 `api.solov.cc`，不能称为 OpenAI 官方目的地。未通过其他路径绕开拒绝；后续仅继续本地确定性验证。请求范围见 followup/host-acceptance-plan.md。

官方 Claude Code 2.1.312 安装在独立 `/tmp/archcanvas-claude-host-client`；实际 `/archcanvas` 调用返回 `Not logged in · Please run /login`，零模型 token / 零工具调用。未恢复备份或修改认证配置。该客户端完整 E2E 需要用户登录及相应传输授权。

真实 Codex 试运行还暴露两处 Agent 交互问题，现已修复：完整 doctor 输出可超过 1 MB，新增 `doctor --summary` 保留完整校验、版本、计数和资产总摘要，省略逐文件清单，Skill 默认使用它；安装 launcher 的 `serve --help` 原来被状态目录检查挡住，现在帮助可以直接读取，实际服务启动仍强制独立状态目录。篡改资产在 summary 模式仍失败，安装后的帮助与摘要回归通过。

本次最终冻结候选为 0.1.0-beta.6（Beta.3 / Beta.4 / Beta.5 为此前中间快照；Beta.6 包含最终扇出端口修复及精确失败样例视觉证据）。候选、独立解包、双宿主项目内安装、生命周期 smoke 和出版预检的最终收据单独写入 followup/release-verification.json；它们不改变 doctor 的 `hostE2E=not-tested` 和 `publicationReview=not-certified`。发行候选仍属于本地未签名 beta-preview，真人研究任务、双客户端登录后 E2E、千节点布线质量及真实浏览器性能为开放门槛。
