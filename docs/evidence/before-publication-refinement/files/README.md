# ArchCanvas Studio · 视觉与受限双向审核 Alpha

从模型 Python 源码生成可编辑的架构画布。正式工程从头实现，使用新的 stdlib AST 静态分析前端、`CanvasDocument`、视觉操作历史与单一 SVG scene；不运行或回退到失败原型。

这是本地 Alpha。静态分析覆盖明确的源码子集，未知结构保留诊断；它不执行模型、不证明实际 tensor shape。M2 增加当前 scene 的 PDF/PNG 派生导出和受限参数事务。M3 新增显式 CPU 隔离观察、具名多输入 RebindInput、默认 ReLU/GELU 替换，以及唯一顶层浮点概率配置的来源修改。M4 增加六个静态 holdout 入口、300 层源码压力样例、容器详情页和最终字号预检，以及真实浏览器性能/匿名研究任务记录。浏览器测量尚未达到体验目标，真实研究者验收仍待执行；各项泛化与出版边界明确保留。结构事务需要独立静态 oracle 与实际运行门；样本运行不证明任意程序、全输入数值等价或外部 checkpoint 兼容。逐能力边界见 [docs/capability-matrix.md](docs/capability-matrix.md)，阶段出口、验收证据和未验证项见 [docs/m3-completion.md](docs/m3-completion.md)、[docs/m4-completion.md](docs/m4-completion.md) 与 [docs/acceptance.md](docs/acceptance.md)。

## 启动

需要 Python 3.11+。前端使用支持 `--experimental-strip-types` 的 Node.js，建议 Node 24+。在本目录执行；静态分析不需要安装 PyTorch，也不导入用户模型。`capabilities` 仅探测可信基础设施，不执行用户模型：

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

## 可选的显式 CPU 运行

静态画布无需此环境。实际执行目前只验收 Linux x86-64，要求 `/usr/bin/bwrap`、`/usr/bin/readelf`、可用的 user/mount/pid/net namespaces 和 seccomp。隔离探针失败时 `runtimeProfiles.available` 为 false，结构运行 profile 禁用；不回退为普通 subprocess，也不将 G6 跳过登记为 passed。Codex 的受限执行沙箱可能禁止创建隔离 namespace；在实际允许运行的本地服务宿主上重新检查能力。

在正式项目内建立独立环境。先从官方 PyTorch CPU index 安装准确的 CPU wheel，再从锁文件安装其余依赖；不要修改用户模型环境：

```bash
python3.11 -m venv .venv-runtime
.venv-runtime/bin/python -m pip install --require-virtualenv --index-url https://download.pytorch.org/whl/cpu --no-deps 'torch==2.5.1+cpu'
.venv-runtime/bin/python -m pip install --require-virtualenv -r requirements-runtime.lock
PYTHONPATH=src .venv/bin/python -m archcanvas_cli capabilities
PYTHONPATH=src .venv/bin/python -m archcanvas_cli runtime \
  --root fixtures/multi_input --entry model:MultiInputAttention \
  --input-spec fixtures/multi_input/input-spec.json \
  --interpreter "$PWD/.venv-runtime/bin/python" \
  --dependency-lock "$PWD/requirements-runtime.lock" \
  --output /tmp/archcanvas-runtime-receipt.json
```

InputSpec v1 显式声明所有具名输入的 shape/dtype/fill、seed、eval/train modes 和空 constructor；当前只使用源码默认构造。支持 float32/float64/int64/bool，normal/zeros/ones 有界生成，不下载权重、不加载 pickle/checkpoint。默认每进程地址空间 4 GiB、CPU 20 秒、单次 worker 墙钟 20 秒、文件 8 MB、64 个打开文件；kernel seccomp 禁止子进程和 socket，PyTorch 单线程，RLIMIT_NPROC 限制任务预算。没有 cgroup 聚合 RSS 或 tmpfs 总配额，具体 scope 写在回执中。

worker 读取冻结的只读源码 generation，仅映射正式 venv、私有只读 Python 可执行文件/标准库/ELF 动态依赖副本和私有 scratch。环境回执绑定全部 venv 字节、标准库/依赖库、解释器、锁文件及可信 adapter；执行后重新核验 venv freshness。实际 kernel 探针确认隔离 namespaces、宿主文件不可见、源码不可写、socket/进程创建被拒。模式观察记录调用/端口/实际 producer、shape/dtype、forward/backward、同种子重建 replay、parameters/buffers/tied identities 和状态变化。replay 的精确 CPU 相等仅属于该样本；有意连接或激活变更不要求旧/新输出相等。外部 optimizer/scheduler/training progress 未提供，不能称为已迁移。

## 首批范围

| 能力 | Alpha 范围/边界 |
|---|---|
| 静态分析 | 明确模块构造与 forward 数据流子集；多输入、残差、具名端口和源码位置保留证据。未支持结构据实诊断 |
| 层级视图 | 由同一事实图投影到画布；展开与折叠保留 canonical 连接身份 |
| 对象编辑 | 显示别名、节点/边样式、独立图例、注释、位置、pin 与页规格属于视觉文档 |
| 对象来源事实 | 只读展示共享instance的不同call、repeat独立/共享实例、完整返回槽位、opaque边界与源码位置；SVG metadata保留canonical事实和绘制对象/端口映射，视觉别名不改变事实 |
| 拖动预览 | gesture开始冻结snapshot，每帧仍用同一Scene/SVG，松开通过guarded history；source/revision变化使旧gesture失效。独立CPU优化不等同浏览器帧率通过 |
| 操作历史 | 视觉操作与 undo/redo 使用同一文档；不改模型源文件 |
| 局部语言指令 | 对选中节点解析颜色、`命名为…`、展开/收起/固定等确定性指令，复用同一视觉操作与历史；没有通用 LLM 语言解析 |
| 保存 | 本地服务保存文档；独立存储版本用于拒绝过期覆盖 |
| 导出 | 从当前 scene 导出 SVG，再用正式 publication runtime 派生 PDF/PNG；receipt 绑定文档、版本、scene hash、物理尺寸和实际依赖来源 |
| 运行观察 / 实际 shape | 显式 Linux x86-64 CPU profile；默认静态。真实隔离、冻结输入/环境、多输入 eval/train、forward/backward、binding replay 和 state receipt；仅声明样本 |
| 参数审核 | 显式浮点 literal Dropout `p` / MHA `dropout`，或唯一顶层 float 配置且全部读者都是已注册概率参数；独立 expected/observed delta、具体 review/approval、完整 corpus freshness、单文件 journal/recovery |
| 局部连接审核 | 保留条件式同-base unary 静态 API；新增必须执行的 structural-verified，支持 entry-root 直线 unary/MHA 的 positional/keyword `Name` 输入、显式具体 shape/dtype 和实际 producer；CLI/HTTP/Python 共用守卫 |
| 激活替换 | 直接无参 ReLU↔GELU constructor，完整声明影响；Studio/CLI 使用显式 structural-verified forward/backward/replay，未知/in-place/functional 路径拒绝 |
| 浏览器源码提交 | 只修改从所选源码建立的受管理工作副本；导入的原用户目录保持原样。成功后返回当前源码/架构供重分析 |
| 动态连接 / 派生配置 / 通用源码写回 | in-place/未知副作用、分支/循环、alias/reassignment、未证明端口/type/shape 路径拒绝；派生/歧义配置和整数概率 literal 拒绝；不承诺多文件原子事务 |
| MCP | 尚未实现 |
| Codex / Claude Code / DeepSeek Harness | `skills/archcanvas` 为可移植指令包；三宿主端到端尚未认证 |

不以节点名称、颜色或画布上的示意细节推断完整模型语义。静态范围与人工关系基准见 [docs/source-oracle.md](docs/source-oracle.md)。本地浏览器视觉、受管理参数、局部连接、真实运行和一个独立 vision holdout 已有实测；最新测试和阶段门以验收记录为准。完整出版质量、真实性能、研究者任务和任意模型空间连续性仍待验收。

## 验证与独立发行

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
cd studio
npm test
cd ..
python scripts/check_independence.py --build
python scripts/check_stage2.py --build --python .venv/bin/python
python scripts/check_stage3.py --build --python .venv/bin/python
python scripts/check_m3_complete.py --build --publication-python .venv/bin/python --runtime-python .venv-runtime/bin/python
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

`prepare` 用分析返回的准确 `--node`、`--parameter p|dropout`、`--value` 和 `--base-source-digest` 创建 literal diff；`configuration` 追踪唯一顶层配置来源；`rebind` 和 `activation` 额外要求准确目标/producer、`--input-spec`、`--runtime-interpreter` 和 `--dependency-lock`。先检查各 action 的 `--help`。`review` 展示 `--transaction` 的影响、gate 和 reviewDigest。对真实模型展示并取得该具体 review 的批准后，`approve --review-digest` 记录批准，`commit --approval-id` 才可修改显式 `--root` 中的原文件。运行输入、profile、环境、receipt 或源码版本改变均使批准失效。浏览器修改受管理副本，CLI 修改显式根目录；不要把二者的写回路径混淆。测试脚本中的模拟批准只适用于它自己在 `/tmp` 创建的模型。

浏览器导出面板可生成并查看当前 SVG/PDF/PNG 和绑定收据，也提供下载链接；下载行为取决于宿主。已保存的画布还可用同一 renderer 导出本地文件：

```bash
node scripts/export_canvas.mjs --document .archcanvas/documents/DOCUMENT_ID.json --output .archcanvas/exports/figure.svg
node scripts/export_canvas.mjs --document .archcanvas/documents/DOCUMENT_ID.json --output .archcanvas/exports/figure.pdf --format pdf --python .venv/bin/python
node scripts/export_canvas.mjs --document .archcanvas/documents/DOCUMENT_ID.json --output .archcanvas/exports/figure.png --format png --dpi 300 --python .venv/bin/python
```

文档保存的是当前视觉结果；撤销/重做历史目前属于当前浏览器会话。语义提交后重分析会建立新的事实绑定，普通视觉 undo 不回滚源文件。完整出版质量、固定性能 p95、研究者任务、更多连接/配置来源和三宿主认证仍属于后续阶段。具体 scope、独立字节/关系预期与反例见 [M2 oracle](docs/stage2-oracle.md)、[M3 首片段 oracle](docs/stage3-oracle.md)、[完整 M3 出口](docs/m3-completion.md) 和 [M4 验收](docs/m4-completion.md)。

M4 详情导出使用同一当前 Scene：选中并展开容器后，在导出面板选择详情范围及 85/180 mm；跨边界来源/消费者与隐藏/省略清单写入收据。CLI 等价参数是 `--scope-node CANONICAL_ID --width-mm 85`。本次真实浏览器已验证别名/颜色保存刷新及 Encoder 详情生成；新测量入口为 `?benchmark=1`，研究任务入口为 `?study=1`。过程与限制见 [性能记录](docs/m4-performance.md)、[压力样例](docs/m4-stress-scenario.md) 和 [研究任务协议](docs/m4-research-protocol.md)。

当前交互构建为 `index-DWpF-img.js` / `index-DK5lov-h.css`。工具栏提供“选择对象”和“平移画布”，手工具支持普通左键拖动；手势记录 pointer identity，松开时同步处理最后一次相机坐标，失去捕获、取消与模态输入有明确守卫。说明默认放在图下方，已有说明可显式“移到图下方”，并提示与叶节点正文、图例和其它说明的矩形冲突。保存的既有位置不会自动迁移。完整 Studio 68/68、strict TypeScript、生产build及[纯正式副本独立发行核对](docs/evidence/m4-pan-annotation-work/independence.txt)通过；Python219项仍为此前未改 runtime 的全套快照，专项数字不累加。

[实际 UI 与独立字段核对](docs/evidence/m4-pan-annotation-work/ui-field-audit.md)记录 Transformer 相机 +64/+40，公开 SVG、rev18、frontier/pin 与按钮状态不变；十份 viewport 均相同。旧说明从 (0,1445) 移到 (50,1885)，正文矩形冲突由1变0，undo/redo 恢复对应位置，重复执行不新增 revision；新说明位于 (50,1944)。最终保存/重开 rev23 与实际 SVG 重建逐字节一致，PDF 已生成，仅核文件/收据，没有本轮实际打开审看。重开相机改变、会话历史重置，不能宣称跨刷新保留视图或历史。正文矩形检查不涵盖连线、marker、页头或字体塑形。

[输入观测 v2](docs/m4-input-observation.md)在两份独立原始 session 中核对四次手工具平移：+80/+48、+32/+20、从展开控件起手 +24/+16、从输入端口起手 +20/+12，最终相机均精确匹配，公开 SVG/frontier/pins 不变。选择模式端口仍进入 proposal；模态守卫由实际按键检查。取消进行中手势目前只有pure tests与代码证据；观测器/独立validator32/32[详细反例日志](docs/evidence/m4-pan-annotation-work/observer-tests-expanded.txt)与产品suite分开。离散匹配子集 p95 为2008/2024 ms，连续 pointermove 仅 DOM proxy；固定硬件/解析字体、持续呈现帧率与计划性能目标仍未认证。

当前[完整浏览器矩阵](docs/evidence/browser-visual-matrix-pan-annotation-full/manifest.json)已封存同一 `index-DWpF-img.js` 构建的36/36基础组合＋三模型各一编辑后，共39case/234工件，artifactCoverage=complete、visualAcceptance=pending-human-review、humanAcceptanceCertified=false。三份编辑后说明均有实际文本undo/redo、保存/重开记录；Transformer/CNN回总览后显式移动说明，MLP保留L1。重开保持当时SVG/revision，但相机改变、会话history重置；随后又切配色/页宽、保存导出，最终rev54/22/39并非立即重开值。工件覆盖不证明每个基础组合都完成编辑任务、真人或出版评分。

新的 `.archcanvas/m4-research-trial-pan-annotation` 已prepare/verify，S01–S05五个独立pristine席位（8881–8885）仍0 assignment/collected/researcher。[准备收据](docs/evidence/research-trial/pan-annotation-build/preparation-verification.json)只核基线/工具/build，实际接手见[交接说明](docs/m4-human-review-handoff.md)。本轮Transformer L3/85mm minText≈2.531pt、nodeLabel≈3.290pt；先前rev23代表图≈2.896pt属于另一范围，真实出版可读性均未认证。M4保持partial，人工39case/234准则、固定性能与3–5研究者任务继续待完成。

[修正账本](docs/evidence/m4-pan-annotation-matrix-corrected/export-copy-correction.json)保留采集helper复制旧导出URL造成的37项错误；按完整Canvas及SVG格式唯一匹配实际服务导出后再collect。截图/时间/DOM/Canvas不变，这不是浏览器重新读取链接或复采。原错误raw、1项先导、旧zoom39及旧严格70fail均保留各自范围；旧12份current文档另存[完整矩阵前归档](docs/evidence/before-pan-annotation-full-matrix/manifest.json)。[独立字段核对](docs/evidence/browser-visual-pixel-observation-pan-annotation-full/field-audit.json)重建全部39份Canvas/DOM/publication SVG并精确核234工件；[AI像素观察](docs/evidence/browser-visual-pixel-observation-pan-annotation-full/pixel-review.md)记录39图页头/全纸/图例可见，但密集fit小字无法可靠逐项阅读。CNN说明英文被逐字符换行为“skip p / ath.”，这是待修可读性问题；字段/AI检查不替代人审或真实尺寸印样。

静态证据仍分别保留：[MLP/CNN完整源码 oracle与holdout](docs/m4-holdout.md)、[sourceFacts独立5/5与保存/重开/SVG链](docs/m4-source-facts.md)、[scene/拖动CPU对比](docs/m4-drag-preview.md)、[展开空白修复](docs/m4-expansion-intrusion.md)与[历史缩放修复](docs/m4-zoom-controls.md)。CPU结果、历史浏览器工件和 automation 五步自报各自属于其绑定版本与范围，不代表真人、持续 paint 或出版通过。
