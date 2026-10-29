# 源码构件导入与全展开移动修复

## 结果

1. 构件卡片、模块标题和插入根节点保留源码标识，如 `PositionwiseFeedForward`、`MultiHeadAttention`。去掉生成工具中的中文翻译映射，重新生成全部 262 个内置版本。相同结构归并后仍保留代表版本的实际源码名称，不用分类标题覆盖模块名。
2. “原始源码构件库 → 从模型项目导入构件”支持目录或多个 Python 文件，发现模型入口，指定构造参数，解析并保存模块和算子。内置库和导入项目库独立；新增库不依赖当前画布或预设案例。
3. 全展开 Transformer 的移动操作与原生展开采用相同的显式待布线验收规则。无关的待布线路径不会阻止合法移动；源码、精确槽位、有限坐标、节点碰撞、分支连接和已完成路径仍受校验。

## 构件导入实现

- 公共抽取核心：`src/archcanvas_preview/component_library.py`。内置库构建脚本与外部项目导入共用候选筛选、资源闭包、边界接口及保守结构指纹。指纹计算不再隐式修改输入。
- 项目库：`src/archcanvas_preview/component_store.py`。原始提交的 Python 文件、入口、参数与抽取模块保存在服务数据目录的 `source-components/library.json`；默认路径为正式项目 `.archcanvas/source-components/library.json`，指定 `--data-dir` 时随该数据目录存放。单文件快照加锁、临时文件写入、fsync 后原子替换，失败保留原库。
- 相同精确事实指纹复用版本，来源归并；构造参数不同保留不同版本。仍采用保守有序图匹配，不声称任意 Python 实现等价。内置库和导入库各自保留来源范围。
- `GET /api/preview/source-components` 读取项目索引；`GET /api/preview/source-components/src-…` 读取构件；`POST /api/preview/source-components/import` 执行导入，需当前会话令牌和允许的本地来源。HTTP 只接受源码文本及逻辑相对路径，不接受服务器磁盘路径。
- 前端以 `componentScope:'project'` 选择项目来源，校验索引身份、字节数、SHA-256 和语义结构后插入。项目索引和资产不使用旧缓存；插入后的编辑稿自包含，可独立保存恢复。
- 外部源码仅经静态 AST 分析，不 import/执行用户模型。解析在独立受限进程进行：20 秒墙钟、15 秒 CPU、768 MiB 地址空间、32 MB 结果预算；每次提交最多 80 个文件 / 2 MB，当前语义入口最多 480 节点 / 3600 依赖。大型项目可按子模块入口分批导入；动态和外部依赖仍保留解析器的未知事实。

## 移动报错原因与修复

完全展开的 3371 节点 Transformer 可显式保留 `pendingRouting` / `failed` 路径。原来的 Worker 移动、主线程回退和实时移动要求整个图所有路径立即通过严格校验，因此移动任意模块都会受到无关待布线路径的影响，出现大量 `unrelated tensor lane overlap` 错误。

现在移动沿用原生视图验收条件，并保留移动前已有的未完成标志；待布线路径随内部子树平移或更新准确端点。局部修复只处理需要完成约束的路径，不把移动操作当作全图重布线。不会通过给新失败路径添加待处理标志来绕过校验。无法满足合法位置或布线的移动继续完整回滚。

## 验证

- Python 10 项通过：原始名称、指纹纯函数、内置库逐字节再生成、跨文件解析、精确版本去重、参数变体、磁盘重开、失败不改库、源码不执行、HTTP 会话/来源/字段限制及下载摘要。
- 38 项相关前端 / 原生编辑检查通过，包括原有 34 项、新增项目库解析检查、3371 节点全展开移动检查，以及两组严格图交互检查。全展开检查覆盖整体、叶节点和内部容器移动，验证源码与槽位不变、历史快照独立，并拒绝伪造绑定和节点重叠。最近的面板、authoring 与手势检查在最终 UI 调整后再次通过。
- `npm run build`、预览依赖审计、集成资源摘要核对和 `git diff --check` 通过。构建仍有现有主包体积提示。
- 浏览器实测：完全展开编辑模式中，`w_o · Linear` 从 x=162.456 移到 x=170.455（屏幕坐标，8 px 拖动）；显示“节点、所属文字与连接已同步更新”，撤销恢复 x=162.456。
- 浏览器目录导入 `tests/fixtures/source_component_project` 的两个 Python 文件，选择 `model:ProjectEncoder`、`width=24`，新增 6 个版本；重复导入新增 0、复用 6。将项目库 `ExternalFeedForward` 插入另一空白模型，同时插入内置 `PositionwiseFeedForward`，两者保留英文源码名。服务重启、浏览器刷新后，编辑稿中的名称和项目库条目均恢复成功。

## 截图

- [全展开移动成功](evidence/component-import-and-expanded-move-20261029/transformer-moved.png)
- [内置与项目构件插入](evidence/component-import-and-expanded-move-20261029/source-names-and-project-insertion.png)

浏览器验证服务沿用已有数据目录 `/tmp/archcanvas-ui-tavotto-20261029`；生产使用时应将 `--data-dir` 指向需要长期保存的目录。已插入的历史中文名称不会被静默重命名；新插入的构件采用修正后的源码名。
