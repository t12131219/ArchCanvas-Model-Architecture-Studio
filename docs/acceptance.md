# Alpha 验收记录与限制

验收依据是技术计划 §16、§18 和 §21，以及正式目录的 `AGENTS.md`。本记录只适用于新工程。

## 必须分开记录的证据

| 层面 | 证据 | 不能据此推出 |
|---|---|---|
| 源码静态事实 | 手工源码关系 oracle、端口/绑定反例、分析 diagnostics | 运行 shape、训练行为、任意 Python 支持 |
| 视觉文档 | 视觉操作不改变 source/IR digest、历史与保存重开 | 语义修改或批准写回 |
| 渲染与导出 | 当前文档的单一 scene/SVG renderer、真实尺寸审看 | PNG/PDF 已实现、出版质量已通过 |
| 独立发行 | `/tmp` 副本中的模块来源、CLI 分析与 Studio build | 三宿主安装与完整 E2E 认证 |
| 浏览器交互 | 用户任务、截图、空间连续性与性能测量 | DOM 更新等于顺滑、测试数等于支持范围 |

## 第一批手工用户任务

1. 导入一个实际 fixture，并核对源/目标输入、cross-attention memory 与残差两输入。
2. 展开层级；记录操作对象屏幕锚点、无关 pinned 节点位置，以及再次展开后局部排版。
3. 改显示别名、节点与边样式、独立图例和注释；撤销/重做。
4. 保存后重开，核对全部视觉字段和版本。两个页面同时编辑时，旧存储版本的保存应拒绝覆盖。
5. 导出当前 SVG，检查文字、连线、图例、黑白和真实尺寸；确认源文件字节与导入前一致。

自然语言客户端尚未接入时，不把手势编辑通过登记为语言编辑通过。未实现的语义事务保持未支持；不能把“提案”或“静态检查通过”描述为可批准写回。

## 证据登记

本轮运行结果在完成验证后写入本表。命令说明不等于命令已通过。

| 验证项 | 当前状态 | 证据/限制 |
|---|---|---|
| 正式目录独立性 | 通过 | 2026-10-04：`python scripts/check_independence.py --build`；最终 root 报告 `docs/evidence/independence-report.json（原运行目录 /tmp/archcanvas-independent-8755mub4）`。隔离包来源、三 fixture 静态分析、源字节不变、复制本地依赖后的独立 Studio build 均通过 |
| Python 静态语义检查 | 通过 | Transformer self/cross attention 端口角色、残差、多输出、共享实例、opaque、source 不执行与身份稳定等静态关系测试通过；HTTP 结果另行登记 |
| Studio 构建 | 通过 | M3 最终 `cd studio && npm test`：12/12，日志 `evidence/m3-studio-tests.txt`；`npm run build`：TypeScript 与 Vite 构建通过。唯一 identity reconcile、改变 tensor 绑定的边不继承旧样式、合束边样式保留均有反例 |
| Python runtime tests | 通过 | M3 最终允许 loopback 的正式 `.venv` 完整 103/103（11.370 s），无 skip，日志 `evidence/m3-tests.txt`；涵盖静态语义、publication、CLI、参数/连接事务和 HTTP。M2 的 68/68 日志保留。受限环境的 socket skip 不作为通过证据 |
| 浏览器用户任务 | Alpha 冒烟通过 | 2026-10-04：root 在真实页面选中 Encoder，改名为 Encoder Stack、改色、undo/redo、保存并刷新重开，alias 完整保留。图例文字改为“模型输入”、增加“实验说明”条目、修改说明文字为“源码支持的 Post-LN Transformer”，保存并刷新后完整恢复；展开 Encoder → EncoderLayer 1 → self attention，显示真实 Attention 契约节点。最终总览 696 × 806，主流两列。导出按钮触发后内置浏览器未提供下载事件，因此浏览器下载未认证；同一 renderer 的本地导出已验证，完整性能与出版尺寸审看仍待补齐 |
| 85/180 mm 和黑白审看 | 彩色 MLP 本机检查通过，其余待验收 | 同一当前 scene 的 SVG/PDF/PNG 在两种宽度均通过字节、digest 与物理几何检查；实际 PNG 中英混排和说明位置已审看。黑白、完整模型黄金图和研究者出版任务仍未认证 |
| 三宿主端到端 | 未认证 | 指令包校验不替代宿主实测 |
| 源码参数事务 | M2 本地通过 | 独立手写 `/tmp` oracle 的 14/14 黑盒反例通过；精确字节、共享调用、同 literal 多目标、derived 拒绝、full corpus/staged/review/approval tamper、重复批准、replace 失败、写后 rollback 与后续外部修改保留。真实浏览器隔离 MLP 完成参数选择、审核、批准、提交、重分析、保存重开；详情见 M2 证据。HTTP 仅改受管理工作副本 |
| 局部连接事务 | M3 首片段本地通过 | `docs/stage3-oracle.md` 的独立手写 source 与 11 项黑盒全部通过；候选名称/符号合同独立核对，只换一个 Name 与一个输入绑定，direct Input 也可作为 producer；不同 base、后置 producer、非法 port、12 类 unsupported scope、导入时框架 monkeypatch 拒绝。真实浏览器隔离 fixture 的 candidate/review/approve/commit/save/reopen 和三格式导出通过。仅此受限静态片段 |

## 本地实际工件

- `evidence/studio-alpha.jpg`：真实浏览器截图。
- `evidence/transformer-overview.svg` 与 `.receipt.json`：已改 Encoder 别名/颜色和图例的当前总览，180 mm，revision 2。
- `evidence/transformer-edited.svg` 与 `.receipt.json`：包含层级展开、手动图例和说明文字的保存文档，revision 7。XML 有效，编辑控制不进入出版场景。
- `evidence/studio-m2-review.png`：具体参数 diff、前后影响区域和 gate 的真实审核页面。
- `evidence/studio-m2-committed.png`：提交后的 MLP 当前画布，p=0.2，别名、颜色和固定位置保留，revision 5。
- `evidence/studio-m2-export.png`：同一 revision 5 的导出面板，PNG 300 DPI 生成后的查看/下载/receipt 入口。
- `evidence/stage2-report.json`、`evidence/independence-m2-report.json`：M2 独立副本检查与实际模块来源。
- `evidence/mlp-m2-reviewed.svg`、`.pdf`、`.png` 及各自 `.receipt.json`：180 mm 的独立当前场景产物，保留中英 alias、图例和图外说明。
- `evidence/m2-tests.txt`：最终 68 项 Python 检查的完整运行日志。
- `evidence/stage3-report.json`、`evidence/independence-m3-report.json`：M3 首片段独立副本报告。
- `evidence/rebind-original-model.py.txt`、`evidence/rebind-committed-model.py.txt`、`evidence/rebind-evidence.json`、`evidence/rebind-review.json` 和 `evidence/rebind-commit.json`：独立手写源码、确切候选位置与具体事务证据。
- `evidence/rebind-before.svg`、`evidence/rebind-after.svg`、`evidence/rebind-after.png` 及收据：同一正式 renderer 的连接前后场景和保留视觉编辑的当前导出。
- `evidence/m3-browser-report.json`、`evidence/studio-m3-review.png`、`evidence/studio-m3-committed.png`、`evidence/studio-m3-export.png`：真实浏览器 fixture 工作副本的完整连接审核与保存重开证据。
- `evidence/rebind-m3-canvas.json`、`evidence/rebind-m3-managed-model.py`、`evidence/rebind-m3-reviewed.svg`、`.pdf`、`.png` 和收据：浏览器保存的 revision 4 文档、提交后的受管理源码与当前 scene 导出。
- `evidence/m3-tests.txt`、`evidence/m3-studio-tests.txt`：最终 103/103 Python、12/12 Studio 的实跑日志。
- `scripts/export_canvas.mjs`：Node 24+ 直接复用正式 TypeScript Scene/SVG renderer，从保存文档导出，不重新生成模型事实。

浏览器撤销历史当前属于会话，刷新恢复当前视觉结果及版本。构建隔离通过不等于 wheel 已捆绑 Studio 与 fixtures；当前发行方式以完整正式目录为准。

## M2 独立证据

`python scripts/check_stage2.py --build` 在 `/tmp/archcanvas-independent-rhjedk05` 的纯正式源码副本运行，稳定报告为 `evidence/stage2-report.json` 和 `evidence/independence-m2-report.json`。静态 CLI 使用 `-I -S`，解析正式四包；publication 使用明确的正式 `.venv/bin/python`，receipt 保留 CairoSVG/Cairo 的实际来源。构建仅复制正式项目的本地 npm 依赖。

14 个独立事务反例全部通过，成功提交仅在 `/tmp` 手写模型副本。实际 source bytes 与手工只替换指定 literal 的预期相等；original fixture 文件未改。独立检查从副本的真实 MLP 源码建立 CanvasDocument，再通过正式 VisualOperation 修改颜色、图例与说明，输出 85/180 mm 的 SVG/PDF/PNG。三种输出绑定同一 input/scene SVG digest，PDF MediaBox 和 PNG dimensions/pHYs 与独立计算一致，publication output digest 与实际产物字节相等。

同一脚本还执行一次真实参数 commit，然后用 committedArchitecture 调用正式 `reconcileDocument`：别名、节点/边样式、独立图例、说明、pin、expanded frontier、layout、页规格完整保留，source binding/document identity 更新，revision 加一，新语义绑定从空视觉历史开始。实际 CAS 保存后用新 DocumentStore 实例重开，文档逐字段一致；被固定对象的 scene 坐标保持原位。

最终 `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` 在允许 loopback 的正式环境实跑 68/68（7.924 s），无 skip；其中 HTTP 包括受管理副本审核提交、错误批准/replay/跨项目/session/path 拒绝、stale/tamper、原 imported source 不变、GET 重分析、真实 SVG/PDF/PNG 与 receipt。新增 glyph preflight 的 publication 专项 7/7、Node core 11/11 和 TypeScript/Vite build 通过。

2026-10-04 的真实浏览器任务使用隔离 MLP 工作副本：选中 Dropout 3，改别名为 `Feature regularization`、填色为 `#ece3f4`，固定于 x=110/y=516；prepare 将 p 从 0.1 改为 0.2。ReviewReady 展示前后影响 crop/SVG、精确 diff 和验证门，刷新后继续恢复待审核项。勾选具体批准后状态为 Approved，再 commit 为 Committed，G10/G11 通过。8 个节点全部保留，新的 revision 5 从空视觉 undo 开始；保存、刷新后 p=0.2 与 alias/fill/pin 保留。正式 fixtures 未改。此任务验证当前受管理副本流程，不代表对任意用户模型或原导入目录的写回批准。

同一保存后的 revision 5 在导出面板实际生成 180 mm、300 DPI 的 PNG，并通过正式服务生成文件 URL 在浏览器打开；图像为 2126 × 3366 像素。PDF 实际生成并提供文件和绑定 receipt。刷新重开面板恢复与该文档/版本绑定的 PNG 查看链接。浏览器文件查看已实测，宿主下载到用户目录的行为没有另行认证。

初次 PNG 审看发现宿主 Cairo 将 `Noto Sans` 解析为 Latin 字体，中文说明出现缺字方框。修复在共享正式 Scene token 中首选宿主已有的 `Noto Sans CJK SC`；转换器没有另换样式。重新独立 release/build 后，85/180 mm PNG 的“已审核丢弃层”和“当前画布”正常，说明位于图外且不遮盖节点；两种宽度的 PDF/PNG receipt 均报告 Cairo glyph coverage passed、missingCharacters 为空。独立验收再次对 180 mm PDF 执行 `pdftotext`/`pdffonts`，确认中文可恢复、NotoSansCJKsc Bold/Medium 均为嵌入子集且有 Unicode mapping。覆盖检查不等于 shaping、跨机器字体一致或全面嵌入承诺；hash 与几何也不能单独证明字形正确。本轮仍不认证完整出版审美、黑白或 p95 性能。

## M3 首片段独立证据

`python scripts/check_stage3.py --build` 在 `/tmp/archcanvas-independent-28gjtsis` 的纯正式源码副本通过，稳定报告为 `evidence/stage3-report.json` 和 `evidence/independence-m3-report.json`。该命令先完整运行 M2 独立检查，再在 `-I -S` 环境执行 11 项独立 RebindInput 黑盒 holdout；包含新增类创建继承 hook 的拒绝反例，没有采用旧原型目录、入口或源码。源码预期与完整关系表独立手写，成功写回仅发生在检查自行建立的 `/tmp` 项目。

独立正例把 `sink(original)` 改为 `sink(candidate)`：精确源码字节只换这个 Name，完整图只有目标 input 的 source/tensor 变化，所有 call/port/output identity 和其他关系保留。direct base Input producer 也通过；BOM、CRLF 与注释字节保留。独立反例拒绝不同 base/后置 producer/非法 port、表达式和 keyword input、未知或 in-place 路径、reassignment/control/nested/mutation、constructor shadow、导入时 `nn.ReLU = ...` / `setattr` /未知调用，以及 `Hook.__init_subclass__` 改写框架符号后由 `class Trigger(Hook)` 触发的类创建副作用；也拒绝另一条 staged 连接篡改和参数 approval 借用。外部 freshness 与写后故障恢复保留原/后续人工字节。

首次深审发现三类导入时框架修改仍能产生 ReviewReady，独立反例先实际失败。正式 sidecar 随后加入完整冻结 corpus 顶层副作用与类替换/装饰审查；重跑这三类反例全部拒绝。最终复核又补上本地继承触发 class creation hook 的副作用检查，并用独立手写 `Hook`/`Trigger` 拒绝预期回归。该证据说明 guard 对列出的错误有效，不推广为任意 Python effects 或 PyTorch 执行证明。

脚本额外留存原/新源码、源位置 sidecar、具体 review/commit 和正式 Scene renderer 的前后 SVG。真实 commit 后以正式 `reconcileDocument` 核对 alias、node style、未受影响 edge style、legend、annotation、pin、frontier、layout 与 page 保留；固定目标坐标不动，revision 加一，新 source binding 开始空视觉历史。最后实跑 Python 103/103（11.370 s），无 skip；Studio 12/12 与 TypeScript/Vite build 通过。HTTP 回归在允许 loopback 的实际环境运行。

2026-10-04 的真实浏览器连接任务使用正式 `Input Rebinding Lab` fixture 的受管理副本：将 regularizer 的输入从 activation/`activated` 改为 branch/`alternative`。候选 inspection、确切 one-Name 源码预览、前后连接 review、具体 review approval、commit、源码重分析与 save/reopen 全部通过。alias “正则化输出”、紫色 `#ece3f4` 与 pin 保留；文档存储坐标 x=148/y=362，对应展示坐标 x=198/y=454。原 fixture 的 SHA-256 保持不变，记录见 `evidence/m3-browser-report.json`，不是对原用户目录的写回。

同一浏览器保存文档 revision 4 生成 SVG/PDF/PNG 与绑定收据；180 mm/300 DPI 的 PNG 为 2126 × 2534，实际审看中文、branch→regularizer 连线和完整画面无裁切。文件、画布文档和截图均已留存。此证据只覆盖该 authored fixture 和当前宿主，不能扩展为任意拖线、数值等价或完整出版任务认证。

M3 当前仅首个受限静态片段。Compatibility 表示相同 base input 的 unary chains 在输入满足已注册操作合同的条件下保留符号 shape/dtype；G6 为 not_run，不 import/执行用户模型，不证明实际尺寸、dtype、数值或训练行为等价。不存在通用 RebindInput、完整 runtime profile、配置追踪或多文件原子事务承诺。
