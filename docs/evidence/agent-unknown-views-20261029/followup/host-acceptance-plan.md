# 待授权的真实宿主模型调用验收

当前已有可审查结果：CPU 三条路径、原生浏览器源码卡片与保存恢复、真实 SVG、12 个出版导出及冻结安装 smoke。真实 Codex 已发现并初步调用 Skill；延长 E2E 调用被自动审批拒绝，完整保存/导出未认证。Claude Code 实际调用因未登录失败。

## 需要明确的内容与目的地

允许真实 Codex 客户端将本地 ArchCanvas Skill 指令、被读取的配套运行时/接口上下文、随包 MLP 测试源码、CLI 诊断及测试会话结果发送至当前 Codex CLI 的自定义模型服务 `api.solov.cc`（只读检查 config.toml 的 model_provider 与 base_url 主机名所得；并非 OpenAI 官方端点），用于发现→调用→保存→导出验收。若同时验收 Claude Code，对应内容会发送至 Anthropic/Claude Code 模型服务，且需用户先完成登录。测试不需要 TFB 源码、用户原有模型、权重、数据集或认证文件。

## 具体测试任务

从最终冻结包的项目内宿主安装启动。使用绑定 launcher 的 `doctor --summary` 确认真实版本与资产摘要。在安装目录之外启动独立 loopback state root，仅打开随包 `fixtures/mlp/model.py`、入口 `model:MLP`。读取真实 session identity/revisions，保存，再导出该会话 SVG，并独立核对收据、源码摘要与文件存在性。停止测试自己的服务。输出 acceptance.json；无浏览器能力时只认证 CLI 客户端部分。

约束：不修改模型源码、安装 Skill 字节、认证或全局配置；不加载 TFB，不下载权重，不把视觉连接当作可执行源码。Skill 明确要求读取实际接口，禁止自行猜测。

## 本轮暂不认证的门槛

双宿主完整 Agent E2E、真人视觉与交互研究、千节点完全展开的严格布线质量及真实浏览器性能仍开放。该授权只允许测试上下文传输，不会自动把上述门槛标为通过。
