# 未知模型源码适配层

本目录把新模型的 Python/PyTorch 源码接入 Summary_Merge 的同一张递归图。模型名称不需要出现在原有 catalog 中。第一版使用标准库 AST，读取源码文本，不 import、不实例化、不执行模型。

## 使用

在 Summary_Merge 中启动带解析接口的服务：

```bash
cd ~/PycharmProjects/ArchCanvas/prototype/Summary_Merge
python3 -B source_adapter/serve.py --port 8767
```

打开 <http://127.0.0.1:8767/yworks_edge_router_lab/index.html>，点击“导入模型源码”，选择 Python 文件或目录，填写入口，例如 `models.network:MyModel`。单个同名类不歧义时可直接填写 `MyModel`。目录入口按所选择目录内的相对文件路径确定；目录选择器保留顶层目录名。可选构造参数是 JSON 对象，仅保存静态字面量，不会执行构造函数。

导入后，点击模块的 +/− 或双击模块逐级展开。拖动、兼容/实时模式、共享分支、源码检查、撤销、SVG/JSON 导出和 IndexedDB 保存使用现有编辑器。下载的编辑 JSON 包含源码适配包，可通过同一对话框重新导入。浏览器数据按 origin 保存，换端口时可用 JSON 搬运。

“体验陌生模型示例”打开 `RiverNet`：本地 `LanternUnit`、Sequential 门控、源码加乘和共享 Linear 实例。`examples/conditional_model.py` 演示输入相关条件保留为待解析模块。

已有纯静态 HTTP 服务可以导入离线生成的适配包；直接上传源码解析需要本目录的服务：

```bash
python3 -B source_adapter/analyze.py /path/to/model.py \
  --entry MyModel --config '{"width": 32}' --out /tmp/my-model.json
```

## 分层接口

1. **源码输入**：相对路径 → Python 文本，入口和构造参数；最多 80 文件、2 MB。
2. **静态适配**：`analyze.py` 提取本地模块、组合、变量依赖和源码位置；`registry.json` 按操作类型登记已知契约。
3. **统一 IR**：`summary-source-ir/1` 保存包含关系、调用节点、实例复用、独立输入/输出槽位、依赖边和证据。最多 480 节点、3600 边，模块展开深度最多 10。
4. **渲染投影**：`yworks_edge_router_lab/source-adapter.js` 生成安全 SVG 图元和概览/完整源码树，将其交给已有 `recursive-graph.js`。这两个源投影用于创建单一递归文档，用户不需要切换离散视图模式。
5. **通用交互及验证**：已有路由器、source contracts、包含关系和布局验证器处理折叠边投影、端口、边框通道与移动。编辑前后的 source/IR SHA256 和 canonical binding 保持一致。

`POST /api/source-adapter/analyze` 接收 `{files: {"model.py": "..."}, entry: "model:MyModel", config: {}}`，返回 `summary-source-adapter/1` JSON 包。服务只监听 `127.0.0.1`，请求上限 4 MB；接口只分析上传文本，不读取请求指定的服务器文件路径。

适配包包含 `files`（源码文本及 SHA256）、`sourceSha256`、`ir`、`canonicalIR`、`irSha256`、`evidence`（文件、行、UTF-8 字节列和片段）、`diagnostics`、`config`。这些摘要用来检测内容变更，不构成作者身份或语义正确性的证明。浏览器校验摘要、证据片段、包含关系、连接身份和初始布局后才注册案例；不接受包提供的 SVG/HTML。包中的所有显示文本均转义。

## 首版支持范围

| 源码结构 | 处理 |
| --- | --- |
| 直接继承 `nn.Module` 的本地类，跨文件相对导入 | 递归解析已提供定义的 `forward` |
| 构造器直接赋值的模块、本地组合、Sequential、属性别名 | 保留调用与实例身份；别名调用共享 instance |
| 位置/关键字参数、keyword-only 输入、静态默认值 | 按函数签名绑定；不合法调用保留 opaque |
| 局部赋值、二元 `+` / `*` / `@` / `-` / `/` | 按源码表达式保存依赖，二输入加乘显示圆圈符号 |
| tuple/list/dict 返回及静态槽位索引 | 保留不同返回节点和消费槽位 |
| 已登记 `nn` 模块、torch/F 函数、部分张量方法 | 按模块类型或调用语法分类，不推断 shape/dtype |
| 未注册调用、helper、外部定义、ModuleList、工厂、复杂继承/装饰 | 保存整体调用或待解析区域及可见变量依赖 |
| 动态 if/for/while、原位操作、状态或切片赋值、副作用 | 剩余区域整体 opaque，不按语句顺序猜测运行路径 |

箭头表示**静态源码值依赖**，不证明张量类型、广播规则、运行分支、训练状态或真实执行轨迹。加乘符号表示源码运算；没有运行类型证据时不宣称一定是逐元素张量运算。传入 config 不会让第一版执行或求值动态分支。暂不支持任意 Python 源码完整恢复、自动纠正源码、参数写回或从图重新生成模型。

## 扩展规则

新的标准操作可在 `registry.json` 登记，必须同时核对其纯调用/原位参数契约，补充正负源码 fixture、独立输入槽位及源码证据测试。复杂本地结构应扩展分析器，而不是按模型名称或图元距离连线。无法确认的部分继续 opaque。

其他后端应输出相同的节点/包含/依赖/证据接口，并声明证据类型及限制；不能把静态依赖伪装成运行图。FX、torch.export 和 ONNX 后端尚未接入。需要执行的后端应作为用户明确选择的独立流程，并保留样例输入、模式和约束；当前导入不会自动运行这些工具。

研究比较和可参考实现见 [RESEARCH.md](RESEARCH.md)。实测与截图见 [验证记录](../verification/source-adapter/README.md)。本次只改 Summary_Merge 的入口和适配层，未改现有 snapshots、catalog、原模型 IR 或 `Summary_Merge（复件）`。

## 检查

```bash
python3 -B -m unittest discover -s source_adapter -p test_analyze.py -v
node --test --test-isolation=none --test-reporter=spec tests/source-adapter.test.cjs
```

Node 测试使用 `verification/source-adapter/` 中由 CLI 生成的真实包。修改分析器或 registry 后，需要先重新生成这些新适配示例包；无需重生成原有模型 catalog。
