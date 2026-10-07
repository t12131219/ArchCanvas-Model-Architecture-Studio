# M5：90 秒主演示与导出预检

M5 的这一项交付是可重复的导出预检和录制脚本。预检通过表示正式源码生成的当前 CanvasDocument 能形成与收据一致的 SVG/PDF/PNG；90 秒浏览器演示、三宿主兼容性、跨机器字体、出版美学分别记录，不能从本脚本的运行时间推定它们通过。M4 历史证据原样保留。

## 一次机器预检

在正式工程根目录运行；每次使用新的证据目录。静态分析不执行 fixture 模型，也不提交源码修改。

```bash
.venv/bin/python scripts/m5_beta_preflight.py \
  --python .venv/bin/python \
  --fixture mlp \
  --output-dir docs/evidence/m5-beta-preflight-mlp-v1
```

换成 `--fixture transformer` 或 `--fixture residual_cnn` 可准备其他来源。默认导出 85/180 mm、SVG/PDF/PNG；`--formats svg` 用于没有 CairoSVG 的环境。完整运行发现 PDF/PNG 不可用时，会把格式记录在 `skipped`、整体标为 `partial`，而不是跳过后称所有格式通过。已含 `receipt.json` 的目录拒绝覆盖。

收据包括原始 fixture、Architecture/Canvas 文件、源码与 IR digest、当前核心/导出脚本/dist 的字节摘要、实际工件及收据摘要、独立读取的物理尺寸结果、最小字号/线宽和导出器的 Cairo glyph coverage。SVG 保留字体引用，标记 `not-checked-text-svg`；PDF/PNG 的 `passed` 只表示 Cairo 该次字符覆盖。字体身份、shaping、嵌入和真实尺寸可读性仍有独立边界。小于 7 pt 的文字会列为建议项；7 pt 是可调起点，预检不会将其宣称为期刊通过线。

## 90 秒浏览器录制脚本

录制前用本次正式 build 启动独立服务，选择源码 Transformer 样例，使用屏幕上实际存在的模块名称和能力。把 URL、build asset SHA256、viewport/DPR、浏览器版本、操作系统、字体请求/可观察来源、开始/结束时间写入独立录制收据。下面的时间分配是目标；保存实际耗时，不剪去失败或等待后伪称连续 90 秒。

| 时间 | 操作 | 画面应证明什么 |
|---|---|---|
| 0–12 s | Harness 按正式 Skill 从源码生成模型图并打开 Studio 总览 | 来源真实，未知项可见，没有用手工图代替模型 |
| 12–27 s | 展开 Encoder 和一个 Attention | 相同对象的层级与端口连续性，视图仍可读 |
| 27–42 s | 选中一个模块，拖动，再对齐 | 连线跟随对象，其他手排对象没有无故跳动 |
| 42–57 s | 改显示名、蓝色和图例 | 显示编辑只改画布，来源事实继续保留 |
| 57–65 s | 撤销一次，再保存 | 撤销恢复正确对象；保存完成状态实际出现 |
| 65–74 s | 导出白底 SVG/PDF | 打开实际文件，并记录页宽、字号与字体限制 |
| 74–90 s | 改显式 dropout 概率，查看影响/minimal diff，由录制操作者批准后提交工作副本，再重分析 | 审核绑定具体 diff，排版保持，原始导入目录未被 HTTP 提交冒充写回 |

首段如果超时，保留实际时长并调节讲解/操作；机器预检 `preflightElapsedSeconds` 不充当视频时长。Harness 没有安装或未实测时，应把第一步单列为待验证，不能把本地 CLI 调用称为三宿主成功。浏览器不具备 PDF/PNG 能力时，演示 SVG 并显示原因；语义 gate 阻断时显示拒绝原因，不能在录制脚本里绕过。

可靠性演示另录一段：错误连接、过期源码、故障恢复、沙盒不可用；与视觉主片分别写收据。公开发布前为 Codex、Claude Code、DeepSeek Harness 各记录真实安装/启动/生成/审核/导出结果。本地预检不代表三宿主矩阵通过。

## 此次证据

本阶段初始实际运行见 [MLP 收据](evidence/m5-beta-preflight-mlp-v1/receipt.json) 和 [Transformer 收据](evidence/m5-beta-preflight-transformer-v1/receipt.json)。它们认证所绑定输入的机器输出边界；没有新真人参与、出版签署或 90 秒录屏。
