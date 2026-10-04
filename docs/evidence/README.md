# Alpha、M2 与首个 M3 片段的实际证据

`studio-alpha.jpg` 来自正式 Studio 的真实浏览器截图。`transformer-overview.svg` 与 `transformer-edited.svg` 从浏览器保存的 CanvasDocument 用同一正式 Scene/SVG renderer 导出，分别包含显示别名/颜色/图例，以及展开层级/手动图例/说明文字。对应 receipt 记录 source/IR/SVG digest、视觉 revision 和物理尺寸。

`independence-report.json` 来自正式源码的独立 /tmp 副本，检查 Python -I -S 的实际包来源、三个源码样例、源码字节不变，以及复制正式项目本地 Node 依赖后的独立构建。不是旧项目运行记录，也不是干净网络安装或三宿主认证。

`studio-m2-review.png` 是隔离 MLP 工作副本的具体参数审核：p 从 0.1 改到 0.2，展示前后影响区域、源码 diff 和 gate。`studio-m2-committed.png` 是提交、重分析和保存后保留 alias、填色与 pin 的当前画布，revision 5；刷新也已核对。`studio-m2-export.png` 是同一文档生成 PNG 300 DPI 后的查看、下载与 receipt 入口。

`stage2-report.json` 和 `independence-m2-report.json` 来自 `/tmp/archcanvas-independent-rhjedk05` 的新发行副本。85/180 mm 的 SVG/PDF/PNG 都绑定当前编辑 scene，几何与 digest 独立校验；180 mm 产物稳定保存为 `mlp-m2-reviewed.{svg,pdf,png}` 与各自 receipt。实际 PNG 中英混排无缺字，shared Scene token 首选 Noto Sans CJK SC，receipt 保留本机 Cairo glyph coverage；本机 PDF 的中文 text recovery 和嵌入字体子集也已独立检查。字体仍依赖宿主，不代表跨机器字体/排字认证。

`m2-tests.txt` 记录最终允许 loopback 的正式 `.venv` 68/68 tests（7.924 s），无 skip。Studio 的 11 项 core tests 与 TypeScript/Vite build 同时通过。

M1 浏览器 SVG 下载事件在当时内置浏览器不可取；M2 的正式生成文件 URL 已在浏览器打开 PNG，180 mm/300 DPI，2126 × 3366；PDF 文件和 receipt 也实际生成。刷新重开恢复与当前 revision 绑定的 PNG 查看链接。下载到用户目录未另行认证。全套模型/黑白黄金图、人类出版审查与性能测量不在这批证据中。详见 `../acceptance.md` 的逐项边界。

`stage3-report.json` 与 `independence-m3-report.json` 来自 `/tmp/archcanvas-independent-28gjtsis` 的独立正式副本，含 M2 回归和 M3 的 11 项手写 source holdout，包括本地继承触发 `__init_subclass__` 修改框架符号的拒绝反例。`rebind-original-model.py.txt` / `rebind-committed-model.py.txt` 保留 exact one-Name 改动；`rebind-evidence.json`、`rebind-review.json`、`rebind-commit.json` 是真实 sidecar 和具体事务证据。成功/故障只在检查自行创建的 `/tmp` 模型副本操作。

`rebind-before.svg` / `rebind-after.svg` 来自正式 shared Scene renderer；连接由 first→sink 改为 branch→sink，alias、样式、未受影响边的样式、图例、图外说明和 pin 保留。`rebind-after.png` 与 receipt 是同一当前文档的 180 mm/300 DPI 输出，2126 × 2163；中英文字与连接已实际审看。符号兼容仍是有条件同输入签名，没有运行模型或执行等价证明。

`m3-browser-report.json` 和 `studio-m3-{review,committed,export}.png` 记录真实浏览器完整任务：候选检查、regularizer 输入由 activation/activated→branch/alternative 的具体审核、批准提交、源码重分析、保存重开；alias “正则化输出”、紫色填色和 pin 保留。原正式 fixture 不变，成功写回仅作用于受管理副本。`rebind-m3-canvas.json` / `rebind-m3-managed-model.py` 保留当前文档与副本源码；`rebind-m3-reviewed.{svg,pdf,png}` 与 receipt 是同一 revision 4 的导出，PNG 为 2126 × 2534（180 mm/300 DPI），实际审看无裁切。

`m3-tests.txt` 是最终允许 loopback 的 Python 103/103（11.370 s），无 skip；`m3-studio-tests.txt` 是 Studio 12/12，TypeScript/Vite build 也通过。这是首个 bounded 静态 RebindInput 片段，不是完整 M3 runtime profile、跨宿主认证或任意模型支持。
