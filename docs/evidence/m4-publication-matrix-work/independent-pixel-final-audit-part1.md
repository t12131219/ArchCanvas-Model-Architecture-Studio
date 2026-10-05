# 最终矩阵独立像素核验 — 第1部分

范围为锁定39条原始 captures.json 的 indices0–19：Transformer L0–L3共16图，MLP L0共4图。其余indices20–38未由此报告查看，不继承结论。

captures.json：25740 bytes，SHA256 `1929c84f5d4a7ba0a9e7acc2ce691ef721e3f29c2949fb623057709885152b6e`。
raw-final-bindings.json：83700 bytes，SHA256 `9986a4951effbda8109f06c917d98bc8bf3b969d24c54697668eb61d93af6f50`。

本轮20张原始截图全部重新调用 `tools.view_image`（detail=original）实际查看；前12张早先预审并未代替本次查看。每case完整9个原始工件绑定SHA256和bytes，共180项。

| index | case | 可见页头 | 层级 | footer rev | 像素观察 |
|---:|---|---|---|---:|---|
| 0 | `transformer-level0-paper-180-publication-ui` | 180 mm / PAPER COLOR | L0 | 0 | 整纸／图例／无modal，未见所审属性不同步 |
| 1 | `transformer-level0-paper-85-publication-ui` | 85 mm / PAPER COLOR | L0 | 1 | 整纸／图例／无modal，未见所审属性不同步 |
| 2 | `transformer-level0-monochrome-85-publication-ui` | 85 mm / MONOCHROME | L0 | 2 | 整纸／图例／无modal，未见所审属性不同步 |
| 3 | `transformer-level0-monochrome-180-publication-ui` | 180 mm / MONOCHROME | L0 | 3 | 整纸／图例／无modal，未见所审属性不同步 |
| 4 | `transformer-level1-paper-85-publication-ui` | 85 mm / PAPER COLOR | L1 | 7 | 整纸／图例／无modal，未见所审属性不同步 |
| 5 | `transformer-level1-paper-180-publication-ui` | 180 mm / PAPER COLOR | L1 | 8 | 整纸／图例／无modal，未见所审属性不同步 |
| 6 | `transformer-level1-monochrome-85-publication-ui` | 85 mm / MONOCHROME | L1 | 10 | 整纸／图例／无modal，未见所审属性不同步 |
| 7 | `transformer-level1-monochrome-180-publication-ui` | 180 mm / MONOCHROME | L1 | 11 | 整纸／图例／无modal，未见所审属性不同步 |
| 8 | `transformer-level2-paper-85-publication-ui` | 85 mm / PAPER COLOR | L2 | 16 | 整纸／图例／无modal，未见所审属性不同步 |
| 9 | `transformer-level2-paper-180-publication-ui` | 180 mm / PAPER COLOR | L2 | 17 | 整纸／图例／无modal，未见所审属性不同步 |
| 10 | `transformer-level2-monochrome-85-publication-ui` | 85 mm / MONOCHROME | L2 | 19 | 整纸／图例／无modal，未见所审属性不同步 |
| 11 | `transformer-level2-monochrome-180-publication-ui` | 180 mm / MONOCHROME | L2 | 20 | 整纸／图例／无modal，未见所审属性不同步 |
| 12 | `transformer-level3-paper-85-publication-ui` | 85 mm / PAPER COLOR | L3 | 24 | 整纸／图例／无modal，未见所审属性不同步 |
| 13 | `transformer-level3-paper-180-publication-ui` | 180 mm / PAPER COLOR | L3 | 25 | 整纸／图例／无modal，未见所审属性不同步 |
| 14 | `transformer-level3-monochrome-85-publication-ui` | 85 mm / MONOCHROME | L3 | 27 | 整纸／图例／无modal，未见所审属性不同步 |
| 15 | `transformer-level3-monochrome-180-publication-ui` | 180 mm / MONOCHROME | L3 | 28 | 整纸／图例／无modal，未见所审属性不同步 |
| 16 | `mlp-level0-paper-85-publication-ui` | 85 mm / PAPER COLOR | L0 | 1 | 整纸／图例／无modal，未见所审属性不同步 |
| 17 | `mlp-level0-paper-180-publication-ui` | 180 mm / PAPER COLOR | L0 | 2 | 整纸／图例／无modal，未见所审属性不同步 |
| 18 | `mlp-level0-monochrome-85-publication-ui` | 85 mm / MONOCHROME | L0 | 4 | 整纸／图例／无modal，未见所审属性不同步 |
| 19 | `mlp-level0-monochrome-180-publication-ui` | 180 mm / MONOCHROME | L0 | 5 | 整纸／图例／无modal，未见所审属性不同步 |

Transformer L0至L3白页约宽375／197／163／131px，y161–595均完整位于中央工作区；缩放约54%／26%／18%／14%。L0encoder/decoder折叠，L1展开repeat/decoder，L2展开两层EncoderLayer及decoder feedforward，L3再展开encoder feedforward。Transformer六个图例标记均在纸页底部。

MLP L0白页约x387–856、y161–595，79%；features→4×network→output的三张卡片保持network折叠，五个图例标记完整可见。标题与可读卡片副标题留在卡片内，未见文字溢出。彩色版为淡色分类填充，黑白版白填充／灰线，UI树图标自身仍可有颜色。

记录页头85／180mm、PAPER COLOR／MONOCHROME、页宽选项（首图对象面板无页宽控件）、层级轮廓、footer修订号、整页边界及无modal与实际截图一致。公开字段交叉检查、180项锁定文件bytes／SHA及20项完整导出文档对应检查无错误。

细字边界未认证：Transformer L1–L3共12图在fit下文字过小，精确字形、字体替代、文字端点、细线端点及密集布线碰撞不能可靠评判。粗略未见图页裁切不等于精密字体验证。85／180mm的同尺寸屏幕fit不构成实际物理尺寸或出版可读性证明。

这是独立AI像素／公开文件核验；humanCertified=false、人工参与者0，无审美或出版人审结论。本次不操作浏览器，不stamp，不修改raw，不运行测试／构建或产品代码。
