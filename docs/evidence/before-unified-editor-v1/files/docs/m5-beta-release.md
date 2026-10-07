# M5 当前工作入口

当前本地候选为 [Beta.2](m5-beta2.md)：模块库发现增强、项目级安装/可恢复卸载/恢复、CLI/HTTP 拒绝与重启验证，以及更新的 85/180 mm 导出预检。M4 `partial`、M5 `in_progress`，不等待真人席位/出版审看继续开发。候选未公开发布，真实三宿主客户端 E2E仍开放。

## 冻结 Beta.1 历史范围

### M5 Beta 发布脚手架（Beta.1 历史）

2026-10-07，按用户要求开始 M5，当前状态为 `in_progress`。M4 保持 `partial`：AI 模拟操作、自动化检查与真人参与者、出版尺寸审看分别登记。真人席位和出版审看继续保留为开放项，不阻塞 M5 的实现工作。

本轮新增可机器核对的 [发布 manifest](evidence/m5-beta-release-manifest.json)、[schema](../schemas/m5-beta-release.schema.json) 和 [校验器](../scripts/check_m5_beta_release.py)，并实现 `0.1.0-beta.1` 本地候选包的打包、验证和版本目录安装。manifest 状态为 `in_progress`，本轮交付范围是本地 Beta preview。当前 Studio package 版本仍为 `0.1.0`，候选版本不修改运行协议版本；公开 Beta 发布仍需完成独立出口。

本轮冻结交付见 [本地候选包](../.archcanvas/releases/archcanvas-0.1.0-beta.1.tar.gz) 和 [包外最终收据](evidence/m5-beta-release-work/final-receipt.json)。包内文件清单与包外收据分别记录冻结字节、独立解包分析和本地安装结果，最终摘要与数量保存在包外收据，避免自引用摘要。

## 支持矩阵

三个宿主共享 `skills/archcanvas` 与同一正式 runtime/Studio。以下发现合同来自已维护的 [宿主适配说明](../skills/archcanvas/references/host-adapters.md)，其 2026-10-04 核验日期保留；M5 发布前需要根据实际目标宿主版本重测。当前浏览器工作不是一次完整的 Skill 安装与宿主端到端认证。

| 宿主 | 项目发现路径 | 交付方式 | M5 端到端状态 |
|---|---|---|---|
| Codex | `.agents/skills/archcanvas` | 共享 Skill、CLI、本地 Studio URL；可用时在宿主浏览器打开 | `not-tested` |
| Claude Code | `.claude/skills/archcanvas` | 同一 Skill、CLI、本地 Studio URL | `not-tested` |
| 官方 DeepSeek Harness | `.dsh/skills/archcanvas` 优先，其次 `.agents/skills/archcanvas` | 同一 Skill、CLI、本地 Studio URL；实际客户端插件另行认证 | `not-tested` |

本轮 [本机宿主可用性检查](evidence/m5-host-availability-v1.json) 记录 PATH 中存在 `codex-cli 0.160.0`，Claude Code、`dsh` 与 `deepseek-harness` 命令未发现。这是可执行入口检查，三行端到端状态继续为 `not-tested`；它没有安装宿主，也没有将本机缺少命令扩展为该产品不支持对应宿主。

每个宿主后续独立记录实际版本、已加载 Skill 路径、runtime 真实来源、服务 URL/生命周期，并对同一 fixture 完成发现 → 打开 → 视觉编辑 → 保存重开 → 当前画面导出 → 有界语义提案。只有该宿主对应证据通过，才提升其 `e2e` 状态；CLI 分析成功不能替代浏览器编辑与导出。

## 版本与构建绑定

候选 manifest 绑定当前正式 Studio 的 `index-CimCnLHA.js` / `index-BOWsNy5e.css` 和入口 HTML 的 SHA-256，并记录当前 Git commit 与 `dirty-uncommitted` 状态。未提交更改是候选的一部分，因此 commit 本身不能重建这份候选。包脚本冻结全部交付 runtime、Skill、schema、视觉资产和 Studio 字节，携带完整文件清单；本地安装/升级/回滚已经过自动化验证，每次候选冻结与独立解包另写绑定收据。

校验不运行用户模型，也不安装依赖；它检查路径、当前文件摘要、三个且唯一的宿主行、正式 runtime 来源及 M4/M5 状态。正式工程从头实现、旧版没有已认证可复用片段；manifest 禁止依赖失败原型的 runtime、artifact 或回退路径。

```bash
python scripts/check_m5_beta_release.py
python -m unittest discover -s tests -p 'test_m5_beta_release.py' -v
```

schema 是发布合同的可读定义，Python 校验器读取并验证该 schema 所用的有限字段合同，再核对实际文件摘要。未经实测的宿主 `passed` 或候选 `released` 声明会被拒绝。通过该校验只证明元数据及所列资产匹配，不证明供应链/干净安装、宿主 E2E、出版美学或研究者任务完成。

## 本地候选包与版本目录

[包脚本](../scripts/m5_beta_bundle.py) 新增 `pack`、`verify`、`install`、`activate` 与 `rollback`。`pack` 在所有入口文档结束编辑后冻结正式 `src`、Studio `dist/src`、fixtures、Skill、schema、视觉资产、锁文件、顶层文档、发布自测和第三方许可证说明；它生成仅本地的 `tar.gz` 预览包与完整 `BUNDLE-MANIFEST.json`。两份 [M5 导出预检与 90 秒任务卡](m5-demo-export.md) 的机器输出随包携带；M4 历史 evidence、venv、npm 依赖、用户文档和秘密不随包，顶层历史文档的 evidence 链接按原仓库路径阅读，不计本包认证。来源文件正在变动时拒绝混合快照，版本不得通过覆盖参数重新标记。

`verify` 拒绝越界路径、archive 链接、重复文件、文件/目录前缀冲突和库存/摘要不匹配，同时核对内层发布 schema、版本和当前资产；随后解包到独立目录，在该目录通过显式 `PYTHONPATH=.../src` 与 Python `-S -B` 完成 MLP、Residual CNN 和 Transformer 静态分析，并核对模块实际来源。该分析不导入或执行用户模型。包摘要用于本地收据；这个预览包没有签名或公开发行认证。

以下示例都要求显式路径，默认不修改全局环境或任何宿主 Skill 目录：

```bash
python scripts/m5_beta_bundle.py pack --output /tmp/archcanvas-0.1.0-beta.1.tar.gz
python scripts/m5_beta_bundle.py verify --bundle /tmp/archcanvas-0.1.0-beta.1.tar.gz
python scripts/m5_beta_bundle.py install --bundle /tmp/archcanvas-0.1.0-beta.1.tar.gz --prefix /tmp/archcanvas-local-beta --activate
PYTHONPATH=/tmp/archcanvas-local-beta/current/src python -m archcanvas_cli analyze --root /tmp/archcanvas-local-beta/current/fixtures/mlp --entry model:MLP
```

版本保存在 `<prefix>/releases/<version>`；安装先在本次独占临时目录完整验证后原子加入版本目录，失败只清理本次临时目录，安装同版本不同字节会拒绝覆盖。安装较新版本并 `--activate` 完成本地升级；`rollback --prefix PREFIX --version PREVIOUS_VERSION` 重新校验已安装字节后切回该版本。它只改变 `<prefix>/current` 指针，保留每个版本文件；已有普通用户目录、未登记的 symlink、陌生 activation 收据及临时 symlink 都拒绝替换。已安装源文件改变也会阻止激活。此流程不安装依赖、不迁移用户文档，也不停止正在运行的服务；旧服务须先停止，再从明确版本入口重新启动。

```bash
python scripts/m5_beta_bundle.py install --bundle NEW_VERSION.tar.gz --prefix /tmp/archcanvas-local-beta --activate
python scripts/m5_beta_bundle.py rollback --prefix /tmp/archcanvas-local-beta --version 0.1.0-beta.1
python -m unittest discover -s tests -p 'test_m5_beta_*.py' -v
```

## 已知限制与下一批 M5 工作

- 三宿主发现资料已核验；三宿主端到端和各宿主 Skill 安装尚未实测，MCP 仍未实现。独立本地版本目录安装、合成新版本升级和回滚已过自动化验证，这不扩展为三宿主安装认证。
- 当前 Skill 是指令包，不随包附带 Python 环境、依赖或构建的 Studio。本地候选包同时包含正式 runtime 源码与已构建 Studio，但需要显式本地安装、环境预检与服务启动；最终候选冻结和公开发布尚未完成。
- 字体依宿主解析；没有跨机器固定排字或全面字体嵌入认证。导出预检不等同出版尺寸审看。
- 大图输入到实际呈现、固定硬件/字体性能、全局最小交叉/最少折角仍未认证；窄缝箭头、密集图路线和页面可读性保持公开边界。
- 从零建模当前为 17 种基础模块和 3 个透明网络起点；Attention/LSTM/GRU 等超出该受限搭建合同，模型生成是静态验证，不等于实际执行。
- 自动化和 AI 审查不计为真人参与者；M4 真人任务与 85/180 mm 彩色/黑白人工审看保持开放。

本轮已实现可离线复制的候选打包/验证、本地版本安装/回滚及发布反例自测：[29 项检查](evidence/m5-beta-bundle-work/suite-final-after-schema.txt) 覆盖发布合同、打包/安装边界、合成版本升级回滚、三 fixture 独立静态分析和预检反例。合成 `beta.2` 仅在 `/tmp` 测试源码副本生成，真实候选保持 `beta.1`。环境/字体/导出机器预检见 [90 秒演示与导出记录](m5-demo-export.md)。后续按各宿主实际能力执行同一 90 秒浏览器演示与端到端矩阵，各行只在取得该宿主证据后提升。
