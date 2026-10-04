# ArchCanvas Studio · 视觉与受限双向审核 Alpha

从模型 Python 源码生成可编辑的架构画布。正式工程从头实现，使用新的 stdlib AST 静态分析前端、`CanvasDocument`、视觉操作历史与单一 SVG scene；不运行或回退到失败原型。

这是本地 Alpha。静态分析覆盖明确的源码子集，未知结构保留诊断；它不执行模型、不证明实际 tensor shape。M2 增加当前 scene 的 PDF/PNG 派生导出，以及显式浮点 literal Dropout `p` / MultiheadAttention `dropout` 的独立准备、审核与受限提交。M3 首片段加入直接根 `forward` 的局部 RebindInput：同一输入来源的纯 unary 链、单一赋值、已支配目标的 producer 和准确 `Name` 实参；兼容证据是有条件的符号 shape/dtype 保持。逐能力边界见 [docs/capability-matrix.md](docs/capability-matrix.md)，实际验收证据和未验证项见 [docs/acceptance.md](docs/acceptance.md)。

## 启动

需要 Python 3.11+。前端使用支持 `--experimental-strip-types` 的 Node.js，建议 Node 24+。在本目录执行；Python runtime 不需要安装 PyTorch，也不导入用户模型：

```bash
PYTHONPATH=src python -m archcanvas_cli capabilities
PYTHONPATH=src python -m archcanvas_cli analyze --root fixtures/transformer --entry model:Transformer --output /tmp/archcanvas-transformer.json
```

安装项目内前端依赖并构建：

```bash
cd studio
npm ci
npm run build
cd ..
PYTHONPATH=src python -m archcanvas_cli serve --host 127.0.0.1 --port 8765
```

打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)。服务和文档存储均由正式目录 runtime 提供。开发前端时，在另一个终端进入 `studio` 并执行 `npm run dev`；Vite 将 `/api` 转发到端口 8765 的同一个服务。

PDF/PNG 需要正式项目内的 Python 环境和系统 Cairo。用已锁定依赖安装 publication extra，再用该解释器启动服务：

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
PYTHONPATH=src .venv/bin/python -m archcanvas_cli capabilities
PYTHONPATH=src .venv/bin/python -m archcanvas_cli serve --host 127.0.0.1 --port 8765
```

capabilities 报告实际 Python、CairoSVG 与 native Cairo 来源；缺少转换依赖时 SVG 仍可用，PDF/PNG 明确显示不可用。共享 Scene font 首选 `Noto Sans CJK SC`，PDF/PNG 转换前检查宿主 Cairo 缺字并记录 glyph coverage；字体仍由宿主解析，当前不保证跨机器排字或全面字体嵌入。一个数据目录只运行一个文档服务进程。

多文件用户工程可用 `analyze --root PATH --entry module:Class --output FILE.json` 分析，再在 Studio 导入对话框读取架构 JSON。单文件可直接粘贴或读取 `.py`，未知结构保留为 opaque。

另外两个源码样例：

```bash
PYTHONPATH=src python -m archcanvas_cli analyze --root fixtures/mlp --entry model:MLP
PYTHONPATH=src python -m archcanvas_cli analyze --root fixtures/residual_cnn --entry model:ResidualCNN
```

## 首批范围

| 能力 | Alpha 范围/边界 |
|---|---|
| 静态分析 | 明确模块构造与 forward 数据流子集；多输入、残差、具名端口和源码位置保留证据。未支持结构据实诊断 |
| 层级视图 | 由同一事实图投影到画布；展开与折叠保留 canonical 连接身份 |
| 对象编辑 | 显示别名、节点/边样式、独立图例、注释、位置、pin 与页规格属于视觉文档 |
| 操作历史 | 视觉操作与 undo/redo 使用同一文档；不改模型源文件 |
| 局部语言指令 | 对选中节点解析颜色、`命名为…`、展开/收起/固定等确定性指令，复用同一视觉操作与历史；没有通用 LLM 语言解析 |
| 保存 | 本地服务保存文档；独立存储版本用于拒绝过期覆盖 |
| 导出 | 从当前 scene 导出 SVG，再用正式 publication runtime 派生 PDF/PNG；receipt 绑定文档、版本、scene hash、物理尺寸和实际依赖来源 |
| 运行观察 / shape 证明 | 尚未实现；静态分析不会执行用户模型 |
| 参数审核 | 仅显式浮点 literal Dropout `p` / MHA `dropout`；独立 expected/observed delta、具体 review、approval、完整 corpus freshness、单文件 journal 与 guarded recovery |
| 局部连接审核 | M3 首片段：HTTP / Python API 支持直接根 `forward` 的 Identity/Dropout/ReLU/GELU 纯直线单赋值链，换一个 positional `Name` 输入；同一 base input 的条件式符号签名，G6 仍为 not_run |
| 浏览器源码提交 | 只修改从所选源码建立的受管理工作副本；导入的原用户目录保持原样。成功后返回当前源码/架构供重分析 |
| 动态连接 / 配置表达式 / 通用源码写回 | 尚未实现；in-place/未知副作用、分支/循环、keyword input、alias/reassignment、不同输入来源或未证明 shape/dtype 路径均不进入 RebindInput；参数来源的派生值、变量引用、整数 literal 仍拒绝 |
| MCP | 尚未实现 |
| Codex / Claude Code / DeepSeek Harness | `skills/archcanvas` 为可移植指令包；三宿主端到端尚未认证 |

不以节点名称、颜色或画布上的示意细节推断完整模型语义。静态范围与人工关系基准见 [docs/source-oracle.md](docs/source-oracle.md)。本地浏览器视觉、受管理参数和首个局部连接任务已有实测；最终 Python 103/103、Studio 12/12 与构建通过。完整出版质量、真实性能和任意模型空间连续性仍待验收。

## 验证与独立发行

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
cd studio
npm test
cd ..
python scripts/check_independence.py --build
python scripts/check_stage2.py --build --python .venv/bin/python
python scripts/check_stage3.py --build --python .venv/bin/python
```

独立性脚本在 `/tmp/archcanvas-independent-*` 下留下可复核的正式源码副本、发行文件 SHA-256 清单与 JSON 报告。Python 使用 `-I -S` 禁止原环境和 site 包注入，检查包实际来源，再分析三个 fixture；不依赖相邻目录。`--build` 仅复制本项目已安装的 `studio/node_modules` 作为构建依赖，不安装全局包；这不等于干净网络安装认证。M2 检查另用明确指定的正式 publication 环境生成 85/180 mm 的 SVG/PDF/PNG；M3 检查保留手写原/新源码、具体连接审核与提交收据、重分析后的当前 scene。成功提交和故障反例只操作检查自行创建的 `/tmp` 模型副本。

文档保存的 CAS 版本与 `CanvasDocument.revision` 分离，前者保护存储覆盖，后者属于视觉操作历史。事实 digest 随视觉编辑保持不变。实现基线与复用登记见 [ADR 0001](docs/adr/0001-independent-alpha.md)；目前没有采用任何失败原型代码片段。

CLI `patch` 与服务共用事务守卫。每个动作都必须提供明确 `--root`、`--entry` 和该项目私有 `--store`。先查看实际参数帮助：

```bash
PYTHONPATH=src python -m archcanvas_cli patch prepare --help
PYTHONPATH=src python -m archcanvas_cli patch review --help
PYTHONPATH=src python -m archcanvas_cli patch approve --help
PYTHONPATH=src python -m archcanvas_cli patch commit --help
```

`prepare` 用分析返回的准确 `--node`、`--parameter p|dropout`、`--value` 和 `--base-source-digest` 创建隔离 diff；`review` 展示 `--transaction` 的影响、gate 和 reviewDigest。对真实模型展示并取得该具体 review 的批准后，`approve --review-digest` 记录批准，`commit --approval-id` 才可修改显式 `--root` 中的原文件。浏览器修改受管理副本，CLI 修改显式根目录；不要把二者的写回路径混淆。测试脚本中的模拟批准只适用于它自己在 `/tmp` 创建的模型。

浏览器导出面板可生成并查看当前 SVG/PDF/PNG 和绑定收据，也提供下载链接；下载行为取决于宿主。已保存的画布还可用同一 renderer 导出本地文件：

```bash
node scripts/export_canvas.mjs --document .archcanvas/documents/DOCUMENT_ID.json --output .archcanvas/exports/figure.svg
node scripts/export_canvas.mjs --document .archcanvas/documents/DOCUMENT_ID.json --output .archcanvas/exports/figure.pdf --format pdf --python .venv/bin/python
node scripts/export_canvas.mjs --document .archcanvas/documents/DOCUMENT_ID.json --output .archcanvas/exports/figure.png --format png --dpi 300 --python .venv/bin/python
```

文档保存的是当前视觉结果；撤销/重做历史目前属于当前浏览器会话。语义提交后重分析会建立新的事实绑定，普通视觉 undo 不回滚源文件。完整出版质量、性能、更多连接/配置来源和三宿主认证仍属于后续阶段。具体 scope、独立字节/关系预期与反例见 [M2 oracle](docs/stage2-oracle.md) 和 [M3 首片段 oracle](docs/stage3-oracle.md)。
