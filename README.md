# ArchCanvas Studio · 视觉 Alpha

从模型 Python 源码生成可编辑的架构画布。正式工程从头实现，使用新的 stdlib AST 静态分析前端、`CanvasDocument`、视觉操作历史与单一 SVG scene；不运行或回退到失败原型。

这是第一批视觉 Alpha。静态分析覆盖明确的源码子集，未知结构保留诊断；它不执行模型，不证明 tensor shape，也不提供源码写回。逐能力边界见 [docs/capability-matrix.md](docs/capability-matrix.md)，实际验收证据和未验证项见 [docs/acceptance.md](docs/acceptance.md)。

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
| 导出 | 从当前 scene 导出 SVG；PNG/PDF 尚未实现 |
| 运行观察 / shape 证明 | 尚未实现；静态分析不会执行用户模型 |
| 参数 / 连接写回 | 尚未实现；没有批准提交源码的接口 |
| MCP | 尚未实现 |
| Codex / Claude Code / DeepSeek Harness | `skills/archcanvas` 为可移植指令包；三宿主端到端尚未认证 |

不以节点名称、颜色或画布上的示意细节推断完整模型语义。静态范围与人工关系基准见 [docs/source-oracle.md](docs/source-oracle.md)。出版质量、真实性能和空间连续性仍需独立浏览器验收。

## 验证与独立发行

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
cd studio
npm test
cd ..
python scripts/check_independence.py --build
```

独立性脚本在 `/tmp/archcanvas-independent-*` 下留下可复核的正式源码副本、发行文件 SHA-256 清单与 JSON 报告。Python 使用 `-I -S` 禁止原环境和 site 包注入，检查包实际来源，再分析三个 fixture；不依赖相邻目录。`--build` 仅复制本项目已安装的 `studio/node_modules` 作为构建依赖，不安装全局包；这不等于干净网络安装认证。

文档保存的 CAS 版本与 `CanvasDocument.revision` 分离，前者保护存储覆盖，后者属于视觉操作历史。事实 digest 随视觉编辑保持不变。实现基线与复用登记见 [ADR 0001](docs/adr/0001-independent-alpha.md)；目前没有采用任何失败原型代码片段。

浏览器内导出使用下载。若宿主内置浏览器不提供下载，可从已保存的画布使用同一 renderer 输出本地 SVG 和摘要收据：

```bash
node scripts/export_canvas.mjs --document .archcanvas/documents/DOCUMENT_ID.json --output .archcanvas/exports/figure.svg
```

文档保存的是当前视觉结果；撤销/重做历史目前属于当前浏览器会话。完整出版质量、性能、PNG/PDF 与源码写回仍属于后续阶段。
