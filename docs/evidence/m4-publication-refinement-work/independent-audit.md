# Publication refinement independent audit

本审计绑定 `index-Qpo15b7_.js`（SHA-256 `185be462879d854c0a23520f1c7989afb706c78f1abbf7657f75ef0797fc1f9e`），即导出缓存新鲜度修复前的构建。其文件已经保存在 `before-publication-cache/`；审计期间 live dist 已变为后续构建，本文不将 Qpo 浏览器记录重标为后续构建证明。原始 journal、截图、收据和导出文件均未改写。

## 独立核验结果

- `browser-journal.json` 共 12 条：前 3 条属于 `Dzpr7_KM` 中间构建，并与 `initial-browser-journal.json` 精确相同；按 scripts 字段筛出后 9 条 Qpo 记录。
- 9/9 实际主 Canvas XML 与从输入文档重建的当前交互 SVG 精确相等；7/7 有效预览与同范围、同页宽的公共 SVG 精确相等。5 份详情下拉框的 nodeId、序号、路径、字号和页高逐项精确相等。XML 仅统一属性顺序及已解码 metadata 表示，不使用几何容差。
- 3 份真实服务导出分别为 feedforward 86 mm SVG、同范围 PDF、CNN 180 mm SVG。浏览器公开链接 id 对应收据路径；实际服务文件及收据与复制证据字节相等；输入文档与准备基线精确相等。所有输出 bytes/digest、sceneSvgDigest/inputSvgDigest、范围、视框和预检字段相符。
- 2 份 SVG 精确等于用同文档公共 SVG 输入正式发布转换器所得的字节。feedforward 86 mm 最小文字 `7.02534661553473 pt`，场景页高 `263.700288184438 mm`。
- PDF 与同 86 mm SVG 的 scene digest 一致；实际仅 1 页，MediaBox `243.779528 × 747.496885 pt`，与独立毫米转点公式的误差小于 `0.05 pt`，并与收据页面几何精确相等。未用 PDF 阅读器审查字形或版式。
- CNN 说明的场景宽度 `380`、高度 `50`；实际 SVG 两个 tspan 分别为 `Each residual block combines transformed features with its skip` 与 `path.`，没有 `ath.` 错误分行。
- 2 个模型重新用正式 AST 分析，architecture 与输入完整精确相等；4 个源码文件字节、嵌入内容和 digest 相符。导出场景构造未修改输入文档；主 Canvas XML 保持基线可见 frontier、geometry、source/IR 元数据。
- 归档清单 77 份复制文件及 6 份不可变链接的 bytes/SHA 全部匹配。旧 39 项矩阵只绑定归档构建，不继承为本轮覆盖。
- 既有日志记录 Studio 77/77、Python 10/10，`tsc --noEmit && vite build` 成功。独立副本报告 9 项检查通过，5 个包来源在副本；4434 份 source manifest 项和 5 份分析结果摘要经只读子审匹配，副本构建 3 文件与 Qpo 归档字节相等。审计未重跑完整测试或构建；Studio 独立性使用拷贝已有依赖，不证明 clean install。

## 已发现的证据缺陷

已逐张实际查看 9 张 Qpo 记录对应截图及 2 张打开 SVG 截图。以下 3 张滞后于同名公开 DOM 字段，不能证明目标截图状态：

| 截图 | 实际可见内容 | 同名 DOM 记录 |
|---|---|---|
| `whole-85-preflight.jpg` | 对话框打开前的 Canvas | 已打开 85 mm 导出面板 |
| `whole-236-preflight.jpg` | 85 mm、2.53 pt、建议 236 mm | 已采用 236 mm、7.03 pt |
| `invalid-width-24.jpg` | 输入框仍为 86，正常预检/预览 | 输入 24，验证提示，无预览/链接 |

其他截图支持其可见字段或结构；CNN overview 的说明文字很小，精确分行结论来自实际 SVG 字段。该缺陷没有推翻公共 DOM、实际导出字节与几何匹配结果，也不能被这些字段替代为截图成功声明。中间构建截图未审看。

## 适用边界

本轮没有发现 scene、document 或转换几何缺陷。Qpo 仍存在旧 export artifact 缓存只按文档身份而未按渲染内容校验的新鲜度风险；后续修复需要独立的新构建/浏览器证据，3 份本次新生成文件已与当前场景精确绑定。

本审计覆盖两个预备输入、9 条 Qpo DOM 记录、3 个实际导出。compact AX 记录主要是焦点/无树变化摘要，不是每步完整 AX 树；无效宽度记录没有独立保存生成按钮 disabled 字段。SVG 物理 height 的 8 位有效数字序列化使用 `0.00005 mm` 容差，场景 XML 无容差。确定性字体估算、码点断行及转换器字体覆盖不构成人工美学、字形/字体嵌入、原生交互性能、研究参与者或投稿出版质量验收。

完整文件绑定、各条结果和限制见同目录 `independent-audit.json`。
