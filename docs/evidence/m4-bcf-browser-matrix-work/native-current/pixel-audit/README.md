# MLP 四向操作的独立像素与 DOM 复核

本目录只保存新复核；未修改既有 39 张视觉矩阵、旧 seals、真人验收表或原始失败记录。

复核者：Codex 子 Agent `/root/proxy_novice`。操作者：root 的 CUA 同源 iframe 操作。AI Agent 不算真人研究者、小白参与者或出版审看者。

`mlp-four-directions-pixel-observations.json` 是逐张实际打开 8 张原始 JPEG 后保存的像素观察。其 `pending-root-journal-save` 是当时的真实状态，原文件保留。后续 `mlp-four-directions-journal-cross-check.json` 改用公开 DOM observer 的 `raw-full.json` 做独立数值核对。这个后续文件名字沿用任务约定，内容明确不是补造丢失的 root capture journal。

| 操作 | 画布/相机位移 | 实际像素与几何结果 |
| --- | --- | --- |
| 节点右移 | Linear1 x 110→162 | 父 network 和 MLP 宽度各增 52；network 输入端口也向右 26，三个 route 更新。卡片无兄弟重叠。 |
| 节点左移 | Linear1 x 110→58 | network 左边界仍为 80，卡片越出父容器 22；截图无警告，不能作为 containment 合格。 |
| 节点上移 | Linear1 y 316→264 | 进入 network 顶部 42 单位标题区，重叠高度 32；截图有标题区/缺少通路警告。 |
| 节点下移 | Linear1 y 316→368 | 与 GELU2 重叠 14；edge3 有 4 个非零弯折，穿入两个重叠卡片内部，截图有重叠/缺少通路警告。 |
| 画布右移 | camera e +40 CSS px | SVG 和 selection 原字节不变，图纸整体右移。 |
| 画布左移 | camera e −40 CSS px | SVG 和 selection 原字节不变，图纸整体左移。 |
| 画布上移 | camera f −32 CSS px | SVG 和 selection 原字节不变，图纸整体上移。 |
| 画布下移 | camera f +32 CSS px | SVG 和 selection 原字节不变，图纸整体下移。 |

8 个状态 × 6 条可见连线的公开 SVG 端点全部匹配对应 port circle，所有记录段均正交。这只确认端点与方向几何，不能证明通路畅通、每个弯折必要或箭头美观。严格内部垂直/水平交叉的计算不包括共同源路径、共线重叠、T 接触、端点和箭头轮廓。向下状态已有明确卡片穿线，不能因该交叉数为 0 宣称合格。

四次 undo 均恢复移动前的公开 SVG，比较时仅移除 SVG 与 metadata 的 revision。第一次右移前未选中、undo 后保留选中，所以 selection 不等；其余三次 selection 一致。right redo 恢复右移公开 SVG。以上不认证隐藏 CanvasDocument 或 undo history 相等。

70 个 textarea chunks 的 SHA256、UTF-16 offset 与重组全文独立核对通过。原 `raw.json` 单次读取被工具截断、JSON 无效，保持原样。完整记录使用 `raw-full.json`。

重要限制：截图与 trial 通过操作顺序、文件名、截图坐标字段和粗略平移关联。root 的 capture journal 在 CUA timeout/reset 后丢失，无 surviving 原子 screenshot/trial 时间戳绑定，未补造。每张 JPEG 为 1425×1089；声明 outer viewport 为 1440×1100、iframe 为 1280×720，三者单独记录，未重采样或推导物理出版尺寸。帧与 frame callback buffers 各丢弃 4102 条，iframe observer 含测量开销；本报告不是 native performance pass、字体环境锁定或真人验收。M4 仍为 partial。

`palette-novice-readonly-review.json` / `.md` 是独立源码复核，不是浏览器小白交互实验。现有左侧预制目录提供 17 个基础模块、11 类分组、中文/英文搜索和点击/拖入。缺口是更多受后端正确性契约支持的常用模块、组合模板、连续可见的 shape/dtype 信息和逐步新手引导；未声称 DL-Playground 功能对等或这些建议已经实现。

`derive_mlp_four_directions_cross_check.py` 是标准库只读推导脚本，可复核报告数值与输入绑定。它拒绝覆盖既有报告。`evidence-manifest.json` 绑定此目录输出、8 张截图、4 个原始 raw/重组文件及 70 个 chunks；既有输入保持原字节。
