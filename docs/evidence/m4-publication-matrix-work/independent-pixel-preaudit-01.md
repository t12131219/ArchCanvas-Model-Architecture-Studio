# Transformer L0–L2 独立截图预审 01

锁定输入：`captures-snapshot-preaudit-01.json`，8065 bytes，SHA256 `18122fae36000362ec1c03faf49ac02795844ddecee86497ce483cc720ed603a`。

本次逐张通过 `tools.view_image` 查看 12 张原始 screenshot.jpg，覆盖 Transformer L0、L1、L2 × 论文彩色／黑白 × 85／180 mm。只读原始工件；未操作浏览器、未重跑测试或构建、未 stamp。当前原始 captures.json 后续追加记录不继承结论。

| 快照序号 | 截图 | 页头／配色 | 可见层级 | footer rev | 观察 |
|---|---|---|---|---:|---|
| 1 | `transformer-level0-paper-180-publication-ui` | 180 mm · PAPER COLOR | L0 | 0 | 整页、底部图例、无 modal；未见所审属性不同步 |
| 2 | `transformer-level0-paper-85-publication-ui` | 85 mm · PAPER COLOR | L0 | 1 | 整页、底部图例、无 modal；未见所审属性不同步 |
| 3 | `transformer-level0-monochrome-85-publication-ui` | 85 mm · MONOCHROME | L0 | 2 | 整页、底部图例、无 modal；未见所审属性不同步 |
| 4 | `transformer-level0-monochrome-180-publication-ui` | 180 mm · MONOCHROME | L0 | 3 | 整页、底部图例、无 modal；未见所审属性不同步 |
| 5 | `transformer-level1-paper-85-publication-ui` | 85 mm · PAPER COLOR | L1 | 7 | 整页、底部图例、无 modal；未见所审属性不同步 |
| 6 | `transformer-level1-paper-180-publication-ui` | 180 mm · PAPER COLOR | L1 | 8 | 整页、底部图例、无 modal；未见所审属性不同步 |
| 7 | `transformer-level1-monochrome-85-publication-ui` | 85 mm · MONOCHROME | L1 | 10 | 整页、底部图例、无 modal；未见所审属性不同步 |
| 8 | `transformer-level1-monochrome-180-publication-ui` | 180 mm · MONOCHROME | L1 | 11 | 整页、底部图例、无 modal；未见所审属性不同步 |
| 9 | `transformer-level2-paper-85-publication-ui` | 85 mm · PAPER COLOR | L2 | 16 | 整页、底部图例、无 modal；未见所审属性不同步 |
| 10 | `transformer-level2-paper-180-publication-ui` | 180 mm · PAPER COLOR | L2 | 17 | 整页、底部图例、无 modal；未见所审属性不同步 |
| 11 | `transformer-level2-monochrome-85-publication-ui` | 85 mm · MONOCHROME | L2 | 19 | 整页、底部图例、无 modal；未见所审属性不同步 |
| 12 | `transformer-level2-monochrome-180-publication-ui` | 180 mm · MONOCHROME | L2 | 20 | 整页、底部图例、无 modal；未见所审属性不同步 |

L0 白页约 x434–809，L1 约 x523–720，L2 约 x540–703；三层均 y161–595，全部位于工作区内。L0 可见折叠 encoder／decoder；L1 展开 encoder repeat 与 decoder，保留两张折叠 EncoderLayer；L2 展开两层 EncoderLayer 与 decoder feedforward 的子流程。六个图例标记均在白页底部。

截图可见页头、页宽选项、配色和修订号与屏幕收据／public DOM／canvas 的记录一致。JSON 为每项绑定 screenshot、screen-receipt、public-dom、accessibility、canvas、browser-scene 共 72 个文件的 SHA256／bytes，并绑定锁定快照；字段交叉检查错误 0。

L1 的 26% 与 L2 的 18% fit 使精细文字和端点太小；此次不认证精确字形、字体替代、细线端点、路线交叉或出版可读性。85／180 mm 适合相同视口可显示同样的像素页面，页宽 UI 一致不等于物理打印验证。未见不同步仅限已观察属性，不度量截图延迟。

这是独立 AI 像素／公开字段预审，人工审阅人数 0，humanCertified=false。环境 UA／DPR 来自收据明确绑定的早先 IAB 观察，未在 8887 重测；字体与硬件未知。
