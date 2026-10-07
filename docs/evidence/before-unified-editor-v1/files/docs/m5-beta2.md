# M5 Beta.2：目录发现与安装生命周期

2026-10-07，按用户要求继续 M5，不等待 M4 真人席位或出版审看。Beta.2 是本地候选，M4 保持 `partial`、M5 保持 `in_progress`；真人/出版门和真实宿主端到端分别登记。

## 当前交付

- 模块库按实际 11 个分类筛选，支持 FC、Swish、BN/LN、中文说明和参数名搜索。网络起点可按组成模块查找，并显示真实组成。支持数保持 17 个基础模块、3 个透明起点；Tanh、AvgPool2d 等精确名称不会误匹配其他算子。见 [源级专项收据](evidence/m5-catalog-discovery-v1/receipt.json)。
- [可恢复卸载](../scripts/m5_host_uninstall.py)先预览安装摘要，再把完整 Skill 移出宿主发现路径并归档；恢复重新核对字节且拒绝覆盖同名内容。用户数据目录保持独立。Linux 的原子 no-replace rename 有反例测试；Windows 分支未实测，其他平台失败关闭。见 [生命周期说明](m5-host-install.md)。
- [安装后可靠性检查](../scripts/m5_reliability_smoke.py)通过独立 loopback 服务实际验证错误端口、形状矛盾、草稿/画布 CAS 冲突、错误导出格式、过期源码绑定和未经批准的提交都被拒绝，且拒绝前后持久化文件不变。重启后验证 session 更新，以及保存草稿、画布、managed project 和待审提案精确恢复；不审批、不执行模型、不提交源码。
- 发布包携带安装/冒烟/卸载/可靠性脚本与对应测试。Beta.2 起校验器强制这些文件存在；旧 Beta.1 按原库存继续可安装、校验和回滚。包内自测从当前分发目录生成临时候选，不依赖未交付的旧 archive。真实 Beta.1 基线测试只在原工程有旧包时运行，分发副本把该一项记为 skip。

## 安装与验证

新候选：[archcanvas-0.1.0-beta.2.tar.gz](../.archcanvas/releases/archcanvas-0.1.0-beta.2.tar.gz)。独立解包后运行包内工具；以下所有目标均须为显式选择的本地目录。

```bash
python scripts/m5_beta_bundle.py verify \
  --bundle .archcanvas/releases/archcanvas-0.1.0-beta.2.tar.gz \
  --extract-to /tmp/archcanvas-beta2-release
python /tmp/archcanvas-beta2-release/scripts/m5_host_install.py install \
  --release-dir /tmp/archcanvas-beta2-release \
  --host codex --workspace /path/to/project
python /tmp/archcanvas-beta2-release/scripts/m5_host_smoke.py \
  --skill-directory /path/to/project/.agents/skills/archcanvas \
  --output /tmp/archcanvas-beta2-smoke
python /tmp/archcanvas-beta2-release/scripts/m5_reliability_smoke.py \
  --skill-directory /path/to/project/.agents/skills/archcanvas \
  --output /tmp/archcanvas-beta2-reliability
```

`claude-code` 和 `deepseek-harness` 使用同一命令、对应发现目录。上面两种 smoke 证明包的 CLI/HTTP 行为，不替代宿主客户端加载与浏览器任务认证。运行服务需要本机允许 loopback socket；缺失时保存失败/跳过结果。

```bash
cd /tmp/archcanvas-beta2-release
PYTHONPATH=src python -m unittest discover -s tests -p 'test_m5_*.py' -v
```

M5 工作树专项 63 项，正式 Studio 491/491、strict/build exit 0、正式 publication 11/11。完整测试/安装/升级回滚范围与候选摘要由包外 [最终收据](evidence/m5-beta2-release-v1/receipt.json)登记；历史 Beta.1 SHA256 保持 `2c44459c195540fd3ac99a0fa7f52583090d85eae47b26fea4a64d1da85ff9ff`。

## 导出与开放项

本次 build 的 MLP、Transformer 各自重新完成 85/180 mm SVG/PDF/PNG 机器预检：共 12 工件、0 skip，见 [MLP](evidence/m5-beta2-preflight-mlp-v1/receipt.json) 和 [Transformer](evidence/m5-beta2-preflight-transformer-v1/receipt.json)。字号、字体依赖与 physical size 信息按收据读取；机器输出不认证出版美学或物理可读性。

三宿主项目级包兼容已有本地验证；Codex 唯一 Skill metadata 发现有历史证据，真实客户端加载后的完整工作流尚未认证，Claude Code/DeepSeek 客户端本机未安装。90 秒录屏、presented FPS、全局路线美学和真人研究任务保持开放。Beta.2 不对这些项目作通过声明。
